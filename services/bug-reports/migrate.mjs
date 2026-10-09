import fs from "node:fs";
import path from "node:path";
import {spawnSync} from "node:child_process";
import {fileURLToPath} from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
export function missingColumns(existing) {
  const columns = new Set(existing);
  return [
    ["status", "ALTER TABLE reports ADD COLUMN status TEXT NOT NULL DEFAULT 'new'"],
    ["developer_note", "ALTER TABLE reports ADD COLUMN developer_note TEXT NOT NULL DEFAULT ''"],
    ["updated_at", "ALTER TABLE reports ADD COLUMN updated_at TEXT"]
  ].filter(([name]) => !columns.has(name)).map(([,statement]) => statement);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const remote = process.argv.includes("--remote");
  if (!remote && !process.argv.includes("--local")) throw new Error("Specify --local or --remote explicitly");
  const script = process.env.WRANGLER_JS || (process.env.APPDATA
    ? path.join(process.env.APPDATA,"npm/node_modules/wrangler/bin/wrangler.js") : null);
  if (!script || !fs.existsSync(script)) throw new Error("Set WRANGLER_JS to the installed Wrangler entrypoint");
  function query(sql) {
    const result = spawnSync(process.execPath,[script,"d1","execute","sts2-things-bug-reports",
      remote?"--remote":"--local","--json","--command",sql],{cwd:root,encoding:"utf8",timeout:60000});
    if (result.status !== 0) throw new Error("D1 migration command failed: " + result.stderr);
    return JSON.parse(result.stdout);
  }
  // CREATE IF NOT EXISTS creates fresh tables; existing tables are inspected before ALTER.
  const schema = fs.readFileSync(path.join(root,"schema.sql"),"utf8");
  const createTable = schema.slice(0,schema.indexOf("CREATE INDEX"));
  query(createTable);
  const info = query("PRAGMA table_info(reports)");
  const columns = info.flatMap(r=>r.results||[]).map(r=>r.name);
  for (const sql of missingColumns(columns)) query(sql);
  query(schema);
  console.log(JSON.stringify({ok:true,target:remote?"remote":"local",columns:"complete",reentrant:true}));
}
