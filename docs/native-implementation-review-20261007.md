# 全模组原版实现复用审查

审查基线：2026-10-07 工作区 **1.25.8**。不改玩法、版本或运行文件；本轮交付为审查与准则更新。

## 范围与依据

全量建立了 228 个生产 C# 文件、25,640 行的调用与扩展入口索引，涵盖游戏逻辑、Godot 视觉、统一引导和可选配置桥；工具和解包源码不计入生产代码。索引保存文件哈希、命令调用、覆写、反射和手工 UI 标记，位于 `build/native-implementation-review-20261007/source-inventory.json`。

核查全部 67 个 Harmony 声明的职责类别及运行时手动补丁；对核心命令、存档、事件、UI 和高风险自定义流程作调用链复查。不是逐帧美术验收，也不是全模组运行正确性证明。本轮没有运行游戏、战斗探针或联机。

原版依据来自当前 Steam v0.111.0 DLL、真实 v0.107.1 缓存 DLL，以及对应源码；对商人价格、古神奖励、开局造牌和抽牌流程重新反编译了实际程序集。目录名和旧审查结论不代替当前 API 证据。

## 建议优先处理

### 1. 商人议价价格：可迁到原生价格 Hook

- 位置：[价格补丁](../STS2_Things/Features/MerchantBargain/MerchantBargainPatches.cs)、[议价管理器](../STS2_Things/Features/MerchantBargain/MerchantBargainManager.cs)。目前 Prefix 直接返回议价后的 `Cost`，跳过 getter。
- 原版证据：v111 `MerchantEntry.Cost` 在商人房间调用 `Hook.ModifyMerchantPrice`；`AbstractModel.ModifyMerchantPrice(Player, MerchantEntry, decimal)` 在两目标中均存在。`ModHelper.SubscribeForRunStateHooks` 可提供一个只读取当前条目议价状态的策略模型。
- 建议：保留协商和购买前拦截，把临时价格职责交给 Hook。未议价条目返回传入价格，议价条目返回约定价格；策略不作为自定义开局规则写入 `RunState.Modifiers`。
- 迁移前验证：卡牌／遗物／药水、失败和取消后的价格恢复、会员卡及快递员、反复读取 `Cost`、功能关闭。原版 Hook 顺序中原生遗物先于模组 run subscribers，但其他模组仍可提供后续价格修改，必须说明组合行为。
- 限制：现有议价仅在 v111 编译启用；107 有价格 Hook 不代表已支持同一议价功能。**价格 Hook 不能提前拦截失败购买并启动猜拳**，因此不能顺手删掉购买 wrapper 补丁。

### 2. 水蛭开局寄生牌：可由原生造牌维护手牌 UI

- 位置：[水蛭](../STS2_Things/Monsters/SanguineLeech.cs)。当前 `BeforeCombatStart` 静默加牌，随后 `BeforeHandDraw` 搜索缺失 holder，手动 `NCard.Create`、`handUi.Add` 和刷新索引。
- 原版证据：两目标的 `Toolbox.BeforeHandDraw` 在第一回合调用 `CardPileCmd.AddGeneratedCardToCombat`；v111 `VexingPuzzlebox` 在首次抽牌后的 Hook 中使用同一命令。原版负责造牌通知和手牌显示。
- 建议：在适合当前规则的开局 Hook 中创建并通过原生命令加入寄生牌，取消手工补 holder。不要简单地把原来的静默加牌改为播放动画：原来的战斗初始化时序已发生过 UI 问题。
- 迁移前验证：寄生牌仍在第一回合开头可见，每只水蛭、每名玩家的数量一致；普通抽牌张数、手牌上限、工具箱／固有牌组合不变；多人只有本地 UI 显示本地手牌；重入 Hook 不重复生成。开局生成与“抽到牌”是不同事件，不能无意触发致盲或冲净的抽牌效果。

### 3. 涅奥模组遗物：复用古神选项工厂

- 位置：[初始化中的 NeowCurseOptionsPatch](../STS2_Things/STS2_ThingsInit.cs)。目前手工拼 `EventOption`、`RelicCmd.Obtain`，再反射 `Done`。
- 原版证据：两目标的 `AncientEventModel.RelicOption(RelicModel, string, string?)` 已创建领取回调、设置结束页并调用 `Done`；`Done` 负责古神选择历史和事件结束。
- 建议：在原有候选池扩展中包装这个工厂，继续让原版涅奥生成和抽取选项。它是 **protected**，并非可以直接调用的 public API；在原版 Neow 实例上仍需明确、缓存且按签名验证的兼容适配。不要为了避免反射另造一个涅奥模型或重写随机抽选。
- 迁移前验证：三个模组遗物开关、相同种子、选择历史中的 `WasChosen`、结束页、领取一次、旧局异常恢复和真实自定义开局。当前代码未发现“每次领取都失败”的证据，迁移收益是减少重复职责与脆弱的 `Done?.Invoke`。

### 4. 回流抽牌：值得缩小自定义范围，不能直接删补丁

- 位置：[DrawFromDiscardPatch](../STS2_Things/Cards/DrawFromDiscardPatch.cs)。目前接管整次 Draw，并复制抽牌阻止、移堆、历史、抽牌 Hook、通知和音效。
- 原版证据：107 的 `Draw` 和 111 的 `DrawInternal` 已负责这些工作，还包含满手提示与 `ShuffleIfNecessary` 等逻辑。当前版本没有直接指定“从弃牌堆随机抽取下一张”的公开 Draw 参数；两个版本的异步方法布局也不同。
- 建议：先原生对照测试，再评估仅替换“下一张来源”的窄适配，让原版继续结算。它仍可能需要 Harmony，并涉及异步状态机目标；不能把这种方案称为现成公开 Hook 或立即可删除的补丁。
- 迁移前验证：`ShouldDraw`／`AfterPreventingDraw` 恰好一次、满手提示、弃牌耗尽后回退、洗牌边界、抽牌后消耗又抽牌、战斗结束、抽牌计数和历史。避免递归调用 Draw 后重复检查，或先移牌进抽牌堆而改变 RNG、牌堆通知与洗牌语义。

### 可选简化：遗物工坊的选择界面

`RelicSelectCmd.FromChooseARelicScreen` 提供原生遗物选择界面，可以替代工坊的翻页选遗物。但现有翻页已经使用原生 `EventOption`，并显示交易对象与报价，**不是必须迁移的自绘选择系统**。只有保持预览、返回／取消、多人选择和事件历史体验时才值得改；本轮不建议为缩短代码牺牲这些体验。

## 已正确采用原版的部分

| 区域（生产文件数） | 本轮核查结论 |
| --- | --- |
| 怪物 35、遭遇 32、意图 1 | 主要使用原生状态机、攻击构建器和意图；双生子换血用 `CreatureCmd.SetCurrentHp`；人面柱坍落用原生眩晕。自定义协调器承担实际跨怪机制，有保留理由。 |
| 能力 44、卡牌 12 | 主要由 Power/Card Hook、`DamageCmd`、`PowerCmd`、`CardCmd`、`CardPileCmd` 结算。蜗牛壳用 `ShouldClearBlock`／`AfterBlockBroken`，冲净用原生消耗，致盲费用用 `SetThisTurn`；主要候选是上述开局 UI 与整段抽牌重写。 |
| 附着 3、附魔 2 | 缠丝已接入 `AfflictionModel` 和原生附着场景。分裂涉及永久成长、升级、费用和存档还原，单纯伤害 Hook 不能覆盖原有规则。 |
| 事件 14、遗物 9、休息选项 1、策略 3 | 选牌、删牌、交易、造牌、奖励、存卡与休息规则多数已使用原版 Cmd、Factory、SavedProperty 和 Hook。`ShadowClaimTicket` 的静默 Deck 加牌与手牌静默加牌不是同一上下文，不能因关键字相同就判成同一问题。 |
| 章节 1、目录 Hook 7、地图 6 | 原生章节覆写、地图 Hook、网络 GameAction 和 SavedProperty 已使用；剩余目录／横路补丁具有固定目录、同行历史或非虚方法的明确缺口。 |
| 商人功能 6 | 购买结算返回原生 wrapper；价格部分还有原生 Hook 可用。自定义猜拳呈现与购买前拦截分别评估。 |
| 音频 6、视觉 35 | Godot 节点、Spine 和模型 AssetPaths 正常承担自定义表现。WAV 播放路由、特殊卡牌花屏、根连接和水位没有现成同效原版模型，不用普通图标替换已接受的表现。 |
| 配置 6、兼容 1、引导 1、桥 2、初始化 1 | 配置传输使用原生网络协议入口；V111 内嵌程序集使用官方归属 API。107 的旧保存缓存与程序集归属兼容仍需保留。 |

## 保留补丁与边界

- **深处事件池**：`AllEvents` 覆写不能阻止非虚 `GenerateRooms` 追加共享事件，也不能自行清理旧保存池；已有补丁调用原版 `RemoveEventFromSet`，并不重写事件结算。`ModifyNextEvent` 只能替换结果，不能等价清理全部保存池。
- **横路**：原生 GameAction、扣金、地图连接与 Modifier 存档已复用；同行访问历史、免费旅行和内部 Modifier 引起的涅奥分支需要兼容。只把 ledger 换成无存档的订阅者会丢路线数据。
- **遭遇权重与强制 Boss**：目录覆写控制成员，不等于可配置权重、强制结果及旧局政策；没有找到等价通用选择 Hook。
- **音频**：FMOD 事件和本地 WAV 是不同播放路径，资源预载原生化不等于 WAV 路由可以删除；退出节点清理也不同于正常战斗结束 Hook。
- **特殊视觉与兼容**：致盲恢复／复制、Queen 式卡牌特效、空 Spine 轨道、专属站位和蜗牛计数分别属于显示或兼容职责，不替换成不同玩法。
- **活体对象静默移除**：兼容层按 Escape 清理顺序移除被吞随从，特意避免死亡／逃跑记录。未找到等价公开命令；`Kill`／`Escape` 会改变语义，暂不迁移。

## 下一轮建议与本轮交付

推荐顺序：商人价格 → 水蛭开局造牌 → 涅奥选项工厂 → 回流抽牌。前三项可各自独立改动和对照验证；第四项先建立专用抽牌回归。

已将“找同类原版完整调用链、核对实际双版本、优先 Cmd／模型覆写／Hook、记录缺口与验证边界”的流程加入制作准则，并同步维护源、个人安装副本和工作区副本。旧的“商人价格没有 Hook”记载已更正。当前没有据此删除生产补丁，没有改包或自动发布。
