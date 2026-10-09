import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import {createRequire} from "node:module";
import {test, before, after} from "node:test";
import {fileURLToPath} from "node:url";
import {missingColumns} from "../migrate.mjs";

// Prefer project dependencies; use the already installed Wrangler runtime on the author's machine.
const require = createRequire(import.meta.url);
let Miniflare;
try { ({Miniflare} = require("miniflare")); }
catch { ({Miniflare} = require(path.join(process.env.APPDATA, "npm/node_modules/wrangler/node_modules/miniflare"))); }
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const fixturePassword = "local-fixture-password-only";
let mf, db;
before(async () => {
  mf = new Miniflare({scriptPath:path.join(root,"worker.js"), modules:true,
    modulesRules:[{type:"ESModule",include:["**/*.js"]},{type:"Text", include:["**/*.html"]}],
    // Installed workerd supports up to 2026-08-08; production keeps its existing compatibility date.
    compatibilityDate:"2026-08-01",
    d1Databases:{DB:"report-fix-test"}, bindings:{ADMIN_PASSWORD:fixturePassword,SESSION_SECRET:"local-fixture-session-secret-only"}});
  db = await mf.getD1Database("DB");
  await db.exec((await fs.readFile(path.join(root,"schema.sql"),"utf8")).replaceAll("\n"," "));
});
after(async () => { await mf?.dispose(); });

function payload(schema=2) { return {schema,source:"sts2_things",client_report_id:crypto.randomUUID().replaceAll("-",""),
  description:"isolated regression report",reported_at:new Date().toISOString(),run:{schema,game_version:"v0.111.0",mod_version:"test",
    client_run_id:crypto.randomUUID().replaceAll("-",""),active_mods:[{id:"STS2_Things",version:"test"}],events:[],
    state:{seed:"test",ascension:10,current_act_index:1,players:[],route:[]}}}; }
function intake(value, ip=crypto.randomUUID()) { return mf.dispatchFetch("https://test.invalid/api/reports", {
  method:"POST",headers:{"content-type":"application/json","cf-connecting-ip":ip},body:JSON.stringify(value)}); }
async function auth() {
  const r=await mf.dispatchFetch("https://test.invalid/api/admin/login",{method:"POST",
    headers:{"content-type":"application/json",origin:"https://test.invalid","cf-connecting-ip":crypto.randomUUID()},
    body:JSON.stringify({password:fixturePassword})});
  assert.equal(r.status,200);return r.headers.get("set-cookie").split(";")[0];
}

test("fresh schema and its second execution support admin queries and database health",async()=>{
  await db.exec((await fs.readFile(path.join(root,"schema.sql"),"utf8")).replaceAll("\n"," "));
  const r=await mf.dispatchFetch("https://test.invalid/health");assert.equal(r.status,200);
  assert.equal((await r.json()).database,"ready");
  assert.equal((await mf.dispatchFetch("https://test.invalid/api/admin/stats")).status,401);
  const cookie=await auth();
  assert.equal((await mf.dispatchFetch("https://test.invalid/api/admin/stats",{headers:{cookie}})).status,200);
});
test("legacy schema 1 and diagnostic schema 2 are accepted",async()=>{
  for(const schema of [1,2])assert.equal((await intake(payload(schema))).status,201);
});
test("malformed nested arrays cannot poison admin rendering",async()=>{
  for(const mutate of [p=>p.run.active_mods=42,p=>p.run.state.players="wrong",p=>p.run.state.route={},
    p=>p.run.events=[{kind:42}],p=>p.run.state.players=[{powers:[{id:"POWER.STRENGTH",amount:"wrong"}]}]]){
    const p=payload(1);mutate(p);assert.equal((await intake(p)).status,422);
  }
});
test("same immutable client ID is acknowledged once and uses one quota slot",async()=>{
  const p=payload(),ip=crypto.randomUUID();
  const before=await db.prepare("SELECT COALESCE(SUM(count),0) AS n FROM intake_rate WHERE bucket LIKE 'intake-%'").first();
  const a=await intake(p,ip),b=await intake(p,ip);
  assert.equal(a.status,201);assert.equal(b.status,201);
  assert.equal((await a.json()).report_id,(await b.json()).report_id);
  const row=await db.prepare("SELECT count(*) AS n FROM reports WHERE client_report_id=?").bind(p.client_report_id).first();
  assert.equal(row.n,1);
  const after=await db.prepare("SELECT COALESCE(SUM(count),0) AS n FROM intake_rate WHERE bucket LIKE 'intake-%'").first();
  assert.equal(after.n,before.n+1);
  p.description="different immutable body";assert.equal((await intake(p,ip)).status,409);
});
test("parallel uploads are limited atomically and duplicate retransmission stays available at quota",async()=>{
  const ip=crypto.randomUUID();
  const initial=payload();assert.equal((await intake(initial,ip)).status,201);
  const responses=await Promise.all(Array.from({length:20},()=>intake(payload(),ip)));
  assert.equal(responses.filter(r=>r.status===201).length,11);
  assert.equal(responses.filter(r=>r.status===429).length,9);
  const retry=await intake(initial,ip);assert.equal(retry.status,201);assert.equal((await retry.json()).duplicate,true);
});
test("actual stream bytes are bounded without content-length",async()=>{
  const body=new ReadableStream({start(controller){controller.enqueue(new TextEncoder().encode("x".repeat(301000)));controller.close();}});
  const r=await mf.dispatchFetch("https://test.invalid/api/reports",{method:"POST",headers:{"content-type":"application/json"},body,duplex:"half"});
  assert.equal(r.status,413);
  const largeLogin=await mf.dispatchFetch("https://test.invalid/api/admin/login",{method:"POST",
    headers:{"content-type":"application/json",origin:"https://test.invalid","cf-connecting-ip":crypto.randomUUID()},
    body:JSON.stringify({password:"x".repeat(2000)})});assert.equal(largeLogin.status,413);
});
test("authenticated updates require origin and preserve exact report identity",async()=>{
  const r=await intake(payload()),id=(await r.json()).report_id,cookie=await auth();
  const url="https://test.invalid/api/admin/reports/"+id;
  assert.equal((await mf.dispatchFetch(url,{method:"PATCH",headers:{cookie,"content-type":"application/json",origin:"https://wrong.invalid"},body:'{"status":"resolved"}'})).status,403);
  assert.equal((await mf.dispatchFetch(url,{method:"PATCH",headers:{cookie,"content-type":"application/json",origin:"https://test.invalid"},body:'{"status":"investigating","developer_note":"checked"}'})).status,200);
  const detail=await (await mf.dispatchFetch(url,{headers:{cookie}})).json();assert.equal(detail.report.developer_note,"checked");
});
test("expired rate rows are cleaned up without removing reports",async()=>{
  await db.prepare("INSERT INTO intake_rate(bucket,count,updated_at) VALUES('expired-test',5,'2000-01-01')").run();
  assert.equal((await intake(payload())).status,201);
  assert.equal(await db.prepare("SELECT bucket FROM intake_rate WHERE bucket='expired-test'").first(),null);
});
test("legacy database columns migrate once and the complete schema is reentrant",()=>{
  assert.equal(missingColumns(["id","payload_json"]).length,3);
  assert.deepEqual(missingColumns(["id","status","developer_note","updated_at"]),[]);
});
