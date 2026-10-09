# 玩家上报系统与后台审查

后续状态：本次审查列出的主要缺陷已修复，交付与验证见 [修复记录](</D:/Things/Things-Workspace/STS2_Things/docs/bug-report-fix-20261009.md>)。下文保留为修复前的审查基线。

审查日期：2026-10-09。范围为当前 `BugRunRecorder.cs`、Worker、D1 schema、管理页面及测试脚本。本轮没有修改这些实现，没有上传、删除生产报告或读取管理员密钥。

结论：后台基本管理流程已经具备，显式选择 F2 分类上传、管理员鉴权、参数化 SQL 和以 textContent 显示报告的方向合理；但当前客户端还有一个阻止交付的生命周期错误，而且缺少诊断本项目手牌卡死问题所需的数据。不能仅根据后台测试通过和两版本编译通过，认定整套系统已经完善。

## P0：同一客户端开始第二局会递归初始化

触发：已经记录过一局，随后在同一游戏进程开始另一局，RunManager 已切换到新 RunState。

[OnStarted](</D:/Things/Things-Workspace/STS2_Things/STS2_Things/Diagnostics/BugRunRecorder.cs:70>) 在 `_run` 仍指向旧局时先调用 `Persist()`，而 [Persist](</D:/Things/Things-Workspace/STS2_Things/STS2_Things/Diagnostics/BugRunRecorder.cs:237>) 调用 `BuildJournal()`。后者看到 RunManager 中的新局与 `_run` 不同，又调用 [OnStarted(current)](</D:/Things/Things-Workspace/STS2_Things/STS2_Things/Diagnostics/BugRunRecorder.cs:211>)。

调用链为 `OnStarted(new) → Persist → BuildJournal → OnStarted(new)`，旧引用没有来得及更新，因此没有终止条件。最终可能触发 StackOverflowException、结束游戏进程；外层 `catch (Exception)` 不能使无限递归安全。

验证：从当前源文件原样提取三个方法，在 .NET 9 隔离桩运行时中执行第二局初始化；加入上限保护后，一次初始化仍发生 9 次状态读取，证实递归重入。此证据属于源码方法运行验证，尚未在真实客户端故意制造栈溢出。

建议：保存旧局使用已经冻结的旧 journal，序列化方法保持纯读取；先清楚完成旧 executor 的解除订阅，再绑定新局。记录器需要持有实际订阅的 executor，而非切局后从 RunManager 获取新 executor 来解除旧订阅。至少覆盖同进程连续两局、退出到菜单再继续、切换存档三种流程。

## P1：上报缺少定位手牌卡死的关键证据

[CaptureSnapshot](</D:/Things/Things-Workspace/STS2_Things/STS2_Things/Diagnostics/BugRunRecorder.cs:130>) 保存了卡组、HP、金币、遗物、药水和路线，但没有：实际手牌/费用、抽弃消耗牌堆、能量、玩家 Phase、选择流程、UI 卡位对应关系、Buff 层数、敌人下一步状态和意图。

而 [AfterAction](</D:/Things/Things-Workspace/STS2_Things/STS2_Things/Diagnostics/BugRunRecorder.cs:94>) 只记录成功完成的动作。如果杂技卡在弃牌选择中，或寄生卡牌停在结算中，这个最重要的动作还不会出现在列表。原版 ActionExecutor 已提供 `BeforeActionExecuted` 和 `CurrentlyRunningAction`，可用于记录已开始但尚未完成的动作。

建议：冻结上报时的手牌模型与可见卡位差异，记录 Power 的 ID/Amount、当前执行动作与选择上下文；同步记录动作开始/完成/异常。保留当前原生路线投影，不把原始完整游戏对象直接序列化。截图或脱敏异常片段可作为玩家明确选择的附加资料。

验收重点：用一次正在等待弃牌的实际遭遇报告，能看到两张同名寄生的独立身份、实际费用、候选/已选牌、玩家阶段和等待中的动作。能够区分合法等待选牌与真正停滞。

## P1：读档和提交失败会损失资料

新进程继续游戏时，代码直接 [清空事件并重建 journal](</D:/Things/Things-Workspace/STS2_Things/STS2_Things/Diagnostics/BugRunRecorder.cs:85>)，没有恢复磁盘里的同局记录。首次写入会覆盖 `current-run.json`，崩溃前已经保存的历程也会失去。当前初始快照同样被后续快照覆盖，无法兑现“本局开始时及上报时都有快照”的文档目标。

[提交路径](</D:/Things/Things-Workspace/STS2_Things/STS2_Things/Diagnostics/BugRunRecorder.cs:263>) 每次生成新 client_report_id，失败正文只保存在同一个 `pending-report.json`，没有读取并重试旧 pending 的流程。第二份报告会覆盖第一份；响应丢失后再次点击可能产生重复报告。超过 300KB 时在写 pending 前返回，因此该次玩家描述没有被保存为待发送报告。

建议：同局恢复稳定 client_run_id，保存开始/关键阶段/最终快照；采用原子文件替换，保留损坏恢复路径。失败报告按独立 ID 排队，同一份重试沿用原正文和 ID；保留描述与本地完整资料，再压缩或截断可选诊断字段以符合上传大小，并标明截断情况。成功必须验证回执结构，向玩家提供 report_id 和可理解的失败原因。

## P1：后端输入校验和并发限流有缺口

[receive](</D:/Things/Things-Workspace/STS2_Things/services/bug-reports/worker.js:91>) 只严格检查顶层字段和 events 数量，未验证 `state.players`、`active_mods`、route 和事件元素的类型。本地运行当前 Worker 时，`state.players="not-an-array"`、`active_mods=42` 仍得到 201。管理页面对这些字段调用 `.entries()` / `.map()`，会使该报告的详情显示报错。

[限流](</D:/Things/Things-Workspace/STS2_Things/services/bug-reports/worker.js:87>) 先读计数，再在另一个事务内增加计数。以剩一个名额、四个读取先于写入的合法并发交错运行当前 Worker，本地 D1 double 接收了四份，计数由 11 变为 15。重传同一 client_report_id 虽能返回同一 receipt、只存一行，但仍重复消耗限流配额。

建议：共享 schema 校验字段类型、长度和嵌套数量；读取真实 body 字节上限而非仅信任 Content-Length。使用原子配额占用，并明确无效请求、重复提交与成功报告各自的计费规则；定期清理过期 intake_rate。上线前用数据库并发验证确认配额不会越界。

上述并发证据来自本地可控 D1 double，不是对生产服务的压力测试。

## P2：新安装和健康检查需补完整

[schema.sql](</D:/Things/Things-Workspace/STS2_Things/services/bug-reports/schema.sql>) 不包含管理 API 必需的 status、developer_note、updated_at。按 README 所述“首次使用 schema.sql/rate.sql、schema-admin.sql 用于现存数据库升级”准备新 SQLite 数据库，管理统计 SQL 返回 `no such column: status`。当前远端可能已经完成升级；此项不等于远端数据库已损坏。

建议统一可重复执行的初始化/版本迁移流程；`/health` 分别给出应用存活与数据库就绪状态。目前健康接口不查 D1，不能证明存储或迁移正常。

## 本轮验证与未覆盖项

- 真实端点只读检查：`/health` 返回 200；未登录的 `/api/admin/stats` 返回 401。
- 当前 Worker 的本地执行：异常嵌套字段仍被接受；并发配额交错可越界；相同 client_report_id 去重有效，但配额重复增加。
- 新数据库 schema 查询：重现缺失 status 列。
- 原样提取客户端生命周期方法：重现第二局递归重入。
- 没有执行游戏 F2 完整提交、实际断网重试、崩溃后重启恢复或真实联机。已有后台 smoke/浏览器测试不能覆盖这些客户端路径。

证据与可重复脚本保存在 [审查目录](</D:/Things/Things-Workspace/STS2_Things/build/bug-report-review-20261009>)。修复顺序建议为：第二局递归 → 卡死现场信息 → 同局恢复/失败队列 → 后端 schema 和原子配额 → F2 双版本实机验收。
