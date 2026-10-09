# 尖塔：琐事 1.25.13

2026-10-10，统一包支持游戏 v0.107.1 与 v0.111.0。此版本汇总 1.25.10 之后完成的内容与修复。

## 更新内容

- 深处强怪池新增「血蛭之母」。巨硕母蛭默认熟睡；前三回合未唤醒则离开，战斗直接结束且不发放奖励。受到攻击后苏醒，首次行动召唤两只血蛭，并向每名玩家手牌加入两张寄生；随后轮换吸血、压击与休养。采用独立原画、睡眠及苏醒等十二套骨骼动作。
- 深处强怪池新增「织茧蛾群」：一只织茧巨蛾和两只垂丝蛾错峰缠绕。大蛾的两层牵丝在连续两个玩家回合各缠绕一对牌，提前解开只消耗当前一层。包含独立原画及精修的九套骨骼动作。
- 修正开场寄生的手牌加入时机，沿用原生造牌与手牌流程，避免手工补 UI 卡位引起费用隐藏、弃牌及回合卡住。保留消耗寄生后下回合插入再寄生行动的规则。
- 调整多组怪物站位，更新放缩巨甲虫的洞穴背景、地面及透明前景；重绘并按原生图标合同导出五件事件遗物图标与描边。
- 原版 F2 增加「琐事 Bug（上传本局）」及重试待发送分类。玩家主动提交时附带本局路线、动作历史、当前战斗、手牌费用与 UI 状态；失败报告保存在本机，同一报告重试沿用原 ID 与正文，成功显示回执。其他反馈分类沿用原版。
- 修复反馈记录器切局递归、同局恢复、旧动作订阅清理与失败队列；上报后台加入战斗现场视图、严格字段校验、原子限流及可重复迁移。后端源码随本版本同步到 GitHub，生产服务沿用已部署的 Worker 1.1.0。
- 更新 `.gitignore` 与资源导出排除规则，避免构建缓存、Cloudflare 状态、本地数据库和私密配置进入源码提交或游戏资源包。

## 验证与使用

本次重新构建两个目标实现、统一引导、BaseLib 可选桥及完整 PCK。双版本最终包均通过原生 ModManager 启动、血蛭之母 98 项、蛾类 284 项、深处 8289 项与反馈诊断 17 项检查。另通过本地反馈存储 21 项、Worker/D1 九组集成场景，以及放缩巨甲虫背景单人／四人原生组件渲染 11 项检查；检查最终 PCK 的 1280 个资源，406 项可直接比对的资源与源码一致。

此前独立 v111、17 模组客户端已验证寄生出牌／弃牌、母蛭苏醒及退场，以及 F2 失败后重试和回执。本次发布检查采用独立探针，没有操作用户正在游玩的游戏窗口。原生多人模型及四人组件渲染不等于真实多机联机；完整 v107.1 F2 交互尚未实测。

手动安装时将 ZIP 内 `STS2_Things` 文件夹放入游戏 `mods`，在退出游戏后替换旧文件。四件运行文件为 `STS2_Things.json`、`STS2_Things.dll`、`STS2_Things.pck` 和 `STS2_Things.BaseLibBridge.dll`；无强制前置，BaseLib／RitsuLib 仍是可选设置集成。新遭遇不会重排旧存档中已经生成的章节与队列。

反馈仅在主动选择琐事 F2 分类后上传。不发送 Steam 身份、本机绝对路径、原始存档或官方日志 ZIP。上传失败可再次打开 F2 选择重试；待发送资料保留在 `user://mod_data/STS2_Things/bug_reports/pending/`。

多召唤物死亡闪退、晶片抽牌及进阶解锁反馈尚未确定存在模组根因，本版本不将这些调查宣称为已修复。

## English

- Added the Leech Mother to the Depths' strong encounter pool. Leave her asleep for three turns to end the encounter without rewards, or wake her to face two summoned leeches and two Parasites added to each player's hand. Includes distinct artwork and twelve skeletal animations.
- Added a Great Silk Moth with two Silk Moths. Their silk actions alternate; the great moth's two layers bind a pair of cards on each of two consecutive player turns. Includes refined artwork and nine animations.
- Corrected opening Parasite creation through the native hand flow, preserving delayed reinfestation. Updated encounter positions, the Scale Beetle's layered cave background, and five event relic icons and outlines.
- Added optional Things bug submission and retry categories to the original F2 feedback UI, with local report storage, combat diagnostics and receipt IDs. Fixed recorder lifecycle, restored-run tracking and retry identity; updated the reporting backend and admin combat view.
- Updated Git and runtime-export exclusions for local state and credentials. No required dependencies; the unified package supports v0.107.1 and v0.111.0.

Both final targets passed native startup and behavior checks. Reporting was previously exercised in an isolated v111 client with 17 mods; this release's verification did not control the user's active game. Native multiplayer models are not a substitute for real multiplayer testing.
