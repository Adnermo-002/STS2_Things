## 管理后台

地址：**https://reports.adnermo.online/admin**。可查看总量与近 7 日上报趋势、搜索报告、按状态筛选、浏览完整本局快照、章节路径、战斗事件、模组版本、导出 JSON、保存开发者备注和删除报告。

### 管理员登录

初始口令在本机下述 Windows 用户私有目录，**不要把口令写进 git、Steam 更新日志或公开 Bug 工单**：

`%LOCALAPPDATA%\STS2_Things\private\reports-admin-password.txt`

该文件已限制为当前 Windows 用户访问。远端仅作为加密 Cloudflare Worker secrets 配置：
`ADMIN_PASSWORD` 和 `SESSION_SECRET`。如需换口令，在本地生成新随机值并执行 `wrangler secret put ADMIN_PASSWORD`；不要将密钥硬编码进 Worker。可通过 `wrangler secret list` 查看密钥名称，但无法读取已保存的密钥明文。12 小时会话到期或退出后需要重新登录。

### 源码结构和部署

- `worker.js`：公开上传与需要鉴权的后台 API。
- `dashboard.html`：管理 UI，静态打包为 Worker Text module，不引用外部 CDN。
- `schema.sql`：包含上报、管理字段、限流和索引的完整新库结构。
- `migrate.mjs`：检查已有列后补齐，支持重复执行；`schema-admin.sql` 仅保留为历史迁移。
- `wrangler.toml`：数据库绑定、自定义域名、必需的 Secret 名称。

发布：

```powershell
cd D:\Things\Things-Workspace\STS2_Things\services\bug-reports
node migrate.mjs --remote
wrangler deploy
```

数据库升级只在首次配置时执行；Cloudflare D1 可免费运行，但应关注单库 500 MB 限制、每日读写额度。

### 测试

```powershell
.\tests\smoke-admin.ps1
python -X utf8 .\tests\visual-check.py
```

第一套测试覆盖鉴权、安全 Origin、上传、筛选、状态、备注、删除和退出。第二套用 Chromium 真实浏览器验收登录页、桌面/移动布局、本局档案、三章路线和操作时间线；会临时插入示例报告，结束时自动删除。截图保留在本地忽略目录 `output/`。


## 修复版诊断与验证

兼容旧 schema 1 和诊断 schema 2。新版记录手牌实例与费用、牌堆、Power 层数、动作开始/等待选择/结束状态，并在后台“战斗现场”页显示。初始快照注明首次观测，读档保留同局 ID 和事件；缩减上传内容时保留完整本机资料并明确标记。

客户端 F2 增加“琐事 Bug（重试待发送）”。每份失败报告独立入队，同一报告重试使用原 ID 和原正文；只有验证 ok/report_id 回执后移出队列。玩家主动选择分类才会上传，普通 F2 分类仍交给原版。

本地验证：

```powershell
node --test tests/worker.test.mjs
# tests 复用本机 Wrangler 的 Miniflare，或项目已安装的 miniflare。
# 本地 workerd 日期为 2026-08-01，生产保留既有 2026-10-01。
```

限流采用 D1 原子事务：新报告每来源小时桶最多 12 次，重传既有 ID 不再占用配额，不同正文复用 ID 返回 409。管理员登录按所有尝试计数，避免并发绕过；过期桶自动清理。/health 现在实际检查数据库必需字段。

生产修复记录与模组验证详见 ../../docs/bug-report-fix-20261009.md。
