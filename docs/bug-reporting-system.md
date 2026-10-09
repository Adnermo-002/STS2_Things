# STS2_Things 玩家 Bug 历程与上报系统

2026-10-10 更新：已修复第二局递归、加入独立失败队列和同局恢复，F2 增加“重试待发送”，后台新增战斗现场信息并更新原子限流。以下旧验证段落保留为初版记录；当前结构、安装状态和实际验证以 [修复记录](</D:/Things/Things-Workspace/STS2_Things/docs/bug-report-fix-20261009.md>) 为准。

## 复现信息最低标准

1. 游戏版本、模组版本、其他已启用模组版本、模式与进阶。
2. 文字种子及章节顺序（尤其替换章节，如第二层「深处」）。
3. 每层实际地图节点、事件/遭遇/怪物 ID、多房间事件链。
4. 关键事件选项、卡牌/遗物/药水奖励选择、休息点操作。
5. 本局开始时及上报时的角色血量、金币、卡组、遗物、药水、状态。
6. 战斗回合、出牌目标、药水槽位、结束回合及进入房间动作。
7. 玩家描述：复现步骤、实际结果、预期结果、发生概率。

仅有种子无法确定玩家决策，更无法还原动态 RNG 消耗与其他模组影响，因此本系统同时记录本局选择、关键操作和阶段快照。历史数据用于复现辅助，并不是完全确定性回放文件。

## 数据流

玩家开启原版 F2 -> 在分类中选择「琐事 Bug（上传本局）」 -> 填写问题描述 -> 按原版发送按钮 -> 向 https://reports.adnermo.online/api/reports 发送 JSON -> Cloudflare Worker 校验大小和字段 -> D1 存储单行完整 JSON 与检索字段 -> 返回带 report_id 的回执。

其他 F2 分类依旧调用原版官方上传接口；不会将玩家对官方的反馈拦截到模组服务。

v0.107.1 与 v0.111 两套目标均已编译包含原版 F2 分类补丁；两个版本均支持使用原版反馈分类选择「琐事 Bug（上传本局）」。无需额外创建窗口。目前未安装到本机游戏进行 F2 实际交互验收，UI 行为仅经源代码核实和双版本编译检查。

上报失败时，玩家的 JSON 保存在 Godot user://mod_data/STS2_Things/bug_reports/pending-report.json；成功则保留 last-receipt.json。局内概要也保存在同目录 current-run.json 和 last-run.json。局内记录不自动联网。

## 隐私与防滥用

只上报玩家显式选择的单局资料；不发送 Steam 账号、原版 FeedbackData.uniqueId、Sentry Session ID、原版日志 ZIP、IP/设备标识、操作系统账户名称或本机绝对路径。玩家自行填写的描述仍可能包含自愿提供的私人信息，提交前应检查。

最大请求体 300KB；描述最多 4000 字；事件窗口最多 700 条；服务器以按小时哈希化的来源网络地址桶限制每小时 12 次。D1 数据的在线读取、修改和删除仅通过经身份验证的管理员接口进行。管理登录使用独立 64 位十六进制随机密钥、HMAC 签名 12 小时 HttpOnly/Secure/SameSite Cookie，按小时限制失败登录尝试，并检查管理变更请求 Origin；公共 API 不开放读接口。上报内容不应公开展示。Cloudflare 基础设施可能按其正常服务运营处理网络请求元数据。

## 管理页面与认证

管理后台：https://reports.adnermo.online/admin 。包括报告数量、7 日趋势、搜索和排序、状态筛选、章节路线、关键操作时间线、角色卡组、JSON 导出、调查备注、状态修改和报告删除。入口需要管理员密码。

管理员密码仅保存在本机 `%LOCALAPPDATA%\\STS2_Things\\private\\reports-admin-password.txt`（当前 Windows 用户私有访问权限），在 Cloudflare 中以 `ADMIN_PASSWORD` 和 `SESSION_SECRET` secrets 持有；不包含于仓库。网页使用 12 小时 HMAC 签名的 HttpOnly、安全 Cookie，并拒绝其他站点发来的写请求。部署和测试说明见 `services/bug-reports/README.md`。

## 开发者读取上报

在服务目录运行：

```powershell
wrangler d1 execute sts2-things-bug-reports --remote --command "SELECT id, created_at, description, game_version, mod_version, seed, ascension, act_index FROM reports ORDER BY created_at DESC LIMIT 20"
wrangler d1 execute sts2-things-bug-reports --remote --command "SELECT payload_json FROM reports WHERE id='REPLACE_ID'"
```

数据库在 Cloudflare D1 上，即使本机 cloudflared 离线也可上报。沿用已托管于 Cloudflare 的 adnermo.online 域名，给 Worker 单独设置 reports 子域名，没有修改 update 子域名上的本机 tunnel。

## 已执行测试

- v0.111 和 v0.107.1 模组编译：通过（0 警告、0 错误）。
- Worker 部署及 reports.adnermo.online/health：通过。
- 远端 POST /api/reports：返回 201 与 report_id。
- D1 中查到测试上报，随后删除测试行：通过。
- 尚未把编译产物安装到游戏或检查 F2 运行时画面；这些仍需实际游戏验收。
