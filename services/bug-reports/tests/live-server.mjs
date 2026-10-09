// Local-only proxy for real game F2 tests. Nothing here is deployed to Cloudflare.
import fs from "node:fs/promises";
import path from "node:path";
import http from "node:http";
import {createRequire} from "node:module";
import {fileURLToPath} from "node:url";
const require=createRequire(import.meta.url);
let Miniflare;try{({Miniflare}=require("miniflare"));}catch{({Miniflare}=require(path.join(process.env.APPDATA,"npm/node_modules/wrangler/node_modules/miniflare")));}
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const mf=new Miniflare({scriptPath:path.join(root,"worker.js"),modules:true,
 modulesRules:[{type:"ESModule",include:["**/*.js"]},{type:"Text",include:["**/*.html"]}],compatibilityDate:"2026-08-01",
 d1Databases:{DB:"report-live-test"},bindings:{ADMIN_PASSWORD:"local-fixture-password-only",SESSION_SECRET:"local-fixture-session-secret-only"}});
const db=await mf.getD1Database("DB");await db.exec((await fs.readFile(path.join(root,"schema.sql"),"utf8")).replaceAll("\n"," "));
let mode="success";
const server=http.createServer(async(req,res)=>{
 try{
  const chunks=[];for await(const part of req)chunks.push(part);const body=Buffer.concat(chunks);
  if(req.url==="/__test/mode"&&req.method==="POST"){mode=JSON.parse(body.toString()).mode;res.end('{"ok":true}');return;}
  if(req.url==="/__test/reports"){const rows=await db.prepare("SELECT payload_json FROM reports").all();res.setHeader("content-type","application/json");res.end(JSON.stringify(rows.results.map(r=>JSON.parse(r.payload_json))));return;}
  if(req.url==="/api/reports"&&mode==="fail"){res.writeHead(503,{"content-type":"application/json"});res.end('{"error":"fixture_offline"}');return;}
  const headers={...req.headers,"cf-connecting-ip":"127.0.0.1"};delete headers.host;delete headers['content-length'];
  const result=await mf.dispatchFetch("http://127.0.0.1:21173"+req.url,{method:req.method,headers,...(req.method!=="GET"&&req.method!=="HEAD"?{body}: {})});
  res.writeHead(result.status,Object.fromEntries(result.headers));res.end(Buffer.from(await result.arrayBuffer()));
 }catch(error){res.writeHead(500);res.end(JSON.stringify({error:error.constructor.name}));}
});
server.listen(21173,"127.0.0.1",()=>console.log("Local report fixture ready on 127.0.0.1:21173"));
for(const signal of ["SIGINT","SIGTERM"])process.on(signal,async()=>{server.close();await mf.dispose();process.exit(0);});
