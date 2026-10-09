import DASHBOARD from "./dashboard.html";
import {canonical, validateReport} from "./validation.js";

const encoder = new TextEncoder();
const HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store, private",
  "x-content-type-options": "nosniff",
  "referrer-policy": "no-referrer",
};
const respond = (data, status = 200, extra = {}) =>
  new Response(JSON.stringify(data), {status, headers:{...HEADERS,...extra}});
const str = (v,n) => typeof v === "string" ? v.slice(0,n) : "";
const time = () => new Date().toISOString();
const statuses = new Set(["new","investigating","resolved"]);
const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
class RequestFailure extends Error {
  constructor(status, code) { super(code); this.status = status; }
}
async function readJson(req, maximum) {
  if (!(req.headers.get("content-type") || "").toLowerCase().startsWith("application/json")) throw new RequestFailure(415, "invalid_content_type");
  if (Number(req.headers.get("content-length") || 0) > maximum) throw new RequestFailure(413, "too_large");
  if (!req.body) throw new RequestFailure(400, "invalid_json");
  const reader = req.body.getReader(), chunks = [];
  let length = 0;
  try {
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > maximum) { await reader.cancel(); throw new RequestFailure(413, "too_large"); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(length); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  const raw = new TextDecoder().decode(bytes);
  try { return {raw, data: JSON.parse(raw)}; }
  catch { throw new RequestFailure(400, "invalid_json"); }
}
function cookie(name, value, age) {
  return name + "=" + value + "; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=" + age;
}
function fail(status = 401, error = "unauthorized") {return respond({error},status)}
async function digest(text) {return new Uint8Array(await crypto.subtle.digest("SHA-256",encoder.encode(text)))}
function hex(bytes) {return Array.from(bytes,b=>b.toString(16).padStart(2,"0")).join("")}
function compare(a,b) {if(a.length!==b.length)return false;let x=0;for(let i=0;i<a.length;i++)x|=a[i]^b[i];return x===0}
function encBase(s) {return btoa(s).replaceAll("+","-").replaceAll("/","_").replace(/=+$/,"")}
function decBase(s) {return atob(s.replaceAll("-","+").replaceAll("_","/"))}
async function key(env) {return crypto.subtle.importKey("raw",encoder.encode(env.SESSION_SECRET),{name:"HMAC",hash:"SHA-256"},false,["sign","verify"])}
async function createSession(env) {
  const plain = Date.now()+"|"+crypto.randomUUID();
  const unsigned = encBase(plain);
  const signature = new Uint8Array(await crypto.subtle.sign("HMAC",await key(env),encoder.encode(unsigned)));
  return unsigned+"."+hex(signature);
}
async function authorized(req, env) {
  if(!env.SESSION_SECRET)return false;
  const raw=req.headers.get("cookie")||"";
  const m=raw.match(/(?:^|;\s*)spire_admin_session=([^;]+)/);
  if(!m)return false;
  const [unsigned,sign]=m[1].split(".");
  if(!unsigned||!sign||!/^[0-9a-f]{64}$/i.test(sign))return false;
  try {
    const s=decBase(unsigned);
    const [t,n]=s.split("|");
    const issued=Number(t);
    if(!n||!Number.isFinite(issued)||issued>Date.now()+60_000||issued<Date.now()-12*3600000)return false;
    const bytes=new Uint8Array(sign.match(/../g).map(s=>parseInt(s,16)));
    return crypto.subtle.verify("HMAC",await key(env),bytes,encoder.encode(unsigned));
  }catch{return false}
}
function sameOrigin(req) {return req.headers.get("origin")===new URL(req.url).origin}
function htmlPage() {
  return new Response(DASHBOARD,{headers:{
    "content-type":"text/html; charset=utf-8",
    "cache-control":"no-store, private",
    "x-content-type-options":"nosniff",
    "referrer-policy":"no-referrer",
    "x-frame-options":"DENY",
    "content-security-policy":"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
  }});
}
async function rateBucket(req,tag) {
  const ip=req.headers.get("cf-connecting-ip")||"unknown";
  return tag + "-" + hex((await digest(ip+":"+new Date().toISOString().slice(0,13)+":"+tag)).slice(0,12));
}
async function claimRate(env,bucket,limit) {
  const result = await env.DB.prepare("INSERT INTO intake_rate(bucket,count,updated_at) VALUES (?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1,updated_at=excluded.updated_at WHERE intake_rate.count<? RETURNING count")
    .bind(bucket,time(),limit).all();
  return result.results.length > 0;
}
async function login(req,env) {
  if(!env.ADMIN_PASSWORD||!env.SESSION_SECRET)return respond({error:"admin_not_configured"},503);
  if(!sameOrigin(req))return fail(403,"origin_mismatch");
  const bucket=await rateBucket(req,"admin_login");
  if(!(await claimRate(env,bucket,10)))return fail(429,"rate_limited");
  const {data:body}=await readJson(req,1024);
  const input=typeof body?.password==="string"?body.password:"";
  const passwordOk=input.length>0&&input.length<=200&&compare(await digest(input),await digest(env.ADMIN_PASSWORD));
  if(!passwordOk)return fail();
  const token=await createSession(env);
  return respond({ok:true},200,{"set-cookie":cookie("spire_admin_session",token,43200)});
}
async function receive(req,env) {
  const {raw,data:p}=await readJson(req,300000);
  if(!validateReport(p))return respond({error:"invalid_report"},422);
  const bucket=await rateBucket(req,"intake");
  const id=crypto.randomUUID(),created=time();
  try {
    const results = await env.DB.batch([
      // One transaction reserves a slot only for a new ID, then inserts iff this reservation changed a row.
      env.DB.prepare("INSERT INTO intake_rate(bucket,count,updated_at) SELECT ?,1,? WHERE NOT EXISTS(SELECT 1 FROM reports WHERE client_report_id=?) ON CONFLICT(bucket) DO UPDATE SET count=count+1,updated_at=excluded.updated_at WHERE intake_rate.count<12 AND NOT EXISTS(SELECT 1 FROM reports WHERE client_report_id=?) RETURNING count")
        .bind(bucket,created,p.client_report_id,p.client_report_id),
      env.DB.prepare("INSERT INTO reports(id,client_report_id,created_at,source,description,game_version,mod_version,seed,ascension,act_index,payload_json) SELECT ?,?,?,?,?,?,?,?,?,?,? WHERE changes()=1 ON CONFLICT(client_report_id) DO NOTHING")
        .bind(id,p.client_report_id,created,p.source,p.description,str(p.run.game_version,80),str(p.run.mod_version,80),str(p.run.state?.seed,100),
          Number.isInteger(p.run.state?.ascension)?p.run.state.ascension:null,
          Number.isInteger(p.run.state?.current_act_index)?p.run.state.current_act_index:null,raw),
      env.DB.prepare("SELECT id,payload_json FROM reports WHERE client_report_id=?").bind(p.client_report_id),
      env.DB.prepare("DELETE FROM intake_rate WHERE updated_at<?").bind(new Date(Date.now()-48*3600000).toISOString())
    ]);
    const receipt=results[2].results[0];
    if(!receipt)return respond({error:"rate_limited"},429,{"retry-after":"3600"});
    if(canonical(JSON.parse(receipt.payload_json))!==canonical(p))return respond({error:"report_id_conflict"},409);
    return respond({ok:true,report_id:receipt.id,duplicate:results[1].meta.changes===0},201);
  } catch(err) {console.error("intake error",err?.message);return respond({error:"storage_unavailable"},503)}
}
async function stats(env) {
  const [c,t] = await Promise.all([
    env.DB.prepare("SELECT COUNT(*) AS total, SUM(CASE WHEN status='new' THEN 1 ELSE 0 END) AS new_count, SUM(CASE WHEN status='resolved' THEN 1 ELSE 0 END) AS resolved, SUM(CASE WHEN created_at>=? THEN 1 ELSE 0 END) AS week FROM reports").bind(new Date(Date.now()-7*86400000).toISOString()).first(),
    env.DB.prepare("SELECT substr(created_at,1,10) AS day, COUNT(*) AS count FROM reports WHERE created_at>=? GROUP BY substr(created_at,1,10) ORDER BY day").bind(new Date(Date.now()-7*86400000).toISOString()).all()
  ]);
  const byDay=new Map(t.results.map(x=>[x.day,x.count]));
  const trend=Array.from({length:7},(_,i)=>{
    const date=new Date(Date.now()-(6-i)*86400000).toISOString().slice(0,10);
    return {day:date,count:byDay.get(date)||0};
  });
  return respond({total:c.total||0,new:c.new_count||0,resolved:c.resolved||0,week:c.week||0,trend});
}
async function list(req,env) {
  const url=new URL(req.url),search=str(url.searchParams.get("q"),90).trim();
  const status=statuses.has(url.searchParams.get("status"))?url.searchParams.get("status"):null;
  const sort=url.searchParams.get("sort")==="oldest"?"ASC":"DESC";
  const limit=Math.floor(Math.min(50,Math.max(1,Number(url.searchParams.get("limit"))||20)));
  const page=Math.floor(Math.min(10000,Math.max(0,Number(url.searchParams.get("page"))||0)));
  const where=["1=1"];const binds=[];
  if(status){where.push("status=?");binds.push(status)}
  if(search){where.push("(description LIKE ? OR seed LIKE ? OR game_version LIKE ? OR mod_version LIKE ? OR id LIKE ?)");
    const term="%"+search+"%";binds.push(term,term,term,term,term)}
  const clause=where.join(" AND ");
  const [rows,count]=await Promise.all([
    env.DB.prepare("SELECT id,created_at,source,description,game_version,mod_version,seed,ascension,act_index,status,updated_at FROM reports WHERE "+clause+" ORDER BY created_at "+sort+" LIMIT ? OFFSET ?").bind(...binds,limit,page*limit).all(),
    env.DB.prepare("SELECT COUNT(*) AS n FROM reports WHERE "+clause).bind(...binds).first()
  ]);
  return respond({items:rows.results,total:count.n,page,limit});
}
async function reportRoute(req,env,id) {
  if(!ID.test(id))return fail(404,"not_found");
  if(req.method==="GET"){
    const report=await env.DB.prepare("SELECT * FROM reports WHERE id=?").bind(id).first();
    if(!report)return fail(404,"not_found");
    const {payload_json,...info}=report;
    let payload;try{payload=JSON.parse(payload_json)}catch{payload=null}
    return respond({report:{...info,payload}});
  }
  if(req.method==="PATCH"){
    if(!sameOrigin(req))return fail(403,"origin_mismatch");
    const {data:body}=await readJson(req,16000);
    if(!body||typeof body!=="object"||Array.isArray(body))return fail(422,"invalid_update");
    const keys=Object.keys(body);if(keys.length===0||keys.some(x=>x!=="status"&&x!=="developer_note"))return fail(422,"invalid_update");
    if(keys.includes("status")&&!statuses.has(body.status))return fail(422,"invalid_status");
    if(keys.includes("developer_note")&&(typeof body.developer_note!=="string"||body.developer_note.length>3000))return fail(422,"invalid_note");
    const sets=[],args=[];
    if(keys.includes("status")){sets.push("status=?");args.push(body.status)}
    if(keys.includes("developer_note")){sets.push("developer_note=?");args.push(body.developer_note)}
    sets.push("updated_at=?");args.push(time(),id);
    const result=await env.DB.prepare("UPDATE reports SET "+sets.join(",")+" WHERE id=?").bind(...args).run();
    if(!result.meta.changes)return fail(404,"not_found");
    return respond({ok:true});
  }
  if(req.method==="DELETE"){
    if(!sameOrigin(req))return fail(403,"origin_mismatch");
    const result=await env.DB.prepare("DELETE FROM reports WHERE id=?").bind(id).run();
    return result.meta.changes?respond({ok:true}):fail(404,"not_found");
  }
  return fail(405,"method_not_allowed");
}
export default {
  async fetch(request,env) {
    const url=new URL(request.url),path=url.pathname,method=request.method;
    try {
      if(path==="/health"&&method==="GET"){
        try {
          await env.DB.prepare("SELECT id,status,developer_note,updated_at FROM reports LIMIT 0").all();
          await env.DB.prepare("SELECT bucket,count,updated_at FROM intake_rate LIMIT 0").all();
          return respond({ok:true,service:"sts2-things-reports",version:"1.1.0",database:"ready",dashboard:true});
        }catch{return respond({ok:false,service:"sts2-things-reports",version:"1.1.0",database:"unavailable"},503)}
      }
      if(path==="/api/reports"&&method==="POST")return await receive(request,env);
      if(path==="/"&&method==="GET")return Response.redirect(url.origin+"/admin",302);
      if(path==="/admin"&&method==="GET")return htmlPage();
      if(path==="/api/admin/login"&&method==="POST")return await login(request,env);
      if(path.startsWith("/api/admin/")){
        if(!(await authorized(request,env)))return fail();
        if(path==="/api/admin/me"&&method==="GET")return respond({ok:true});
        if(path==="/api/admin/logout"&&method==="POST"){
          if(!sameOrigin(request))return fail(403,"origin_mismatch");
          return respond({ok:true},200,{"set-cookie":cookie("spire_admin_session","",0)});
        }
        if(path==="/api/admin/stats"&&method==="GET")return stats(env);
        if(path==="/api/admin/reports"&&method==="GET")return list(request,env);
        const m=path.match(/^\/api\/admin\/reports\/([a-f0-9-]+)$/i);
        if(m)return await reportRoute(request,env,m[1]);
      }
      return fail(404,"not_found");
    }catch(err){if(err instanceof RequestFailure)return respond({error:err.message},err.status);
      console.error("worker error",err?.message);return respond({error:"server_error"},500)}
  }
};
