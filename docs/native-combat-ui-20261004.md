# 1.12.1 · 原版意图与能力接入

本轮统一海绵、水蛭和灯笼鱼的意图、能力显示及相关提示，保留已确认的战斗机制。

## 对照原版实现

| 功能 | 原版入口 | 本轮结果 |
| --- | --- | --- |
| 攻击、强化、格挡、减益、塞牌意图 | `MonsterMoveStateMachine`、`MoveState`、原版 Intent 类型 | 全部使用原版类型；喷淋为 `SingleAttackIntent` + `BuffIntent`，与原版瀑布巨人的攻击／强化组合一致 |
| 意图数值、动画与提示 | `NIntent`、`IntentAnimData` | 原版计算攻击数值并播放 30 帧强化动画；删除自定义单帧意图、注册类和私有字典写入 |
| 能力层数、增减和移除 | `PowerModel`、`PowerCmd` | 使用原版 Counter／None、叠层、扣层、零层移除与回调；保留上限 3 积水、2 冲净、6 致盲 |
| 能力触发提示 | `PowerModel.Flash`、`NPower` | 吸水体质、冲净与致盲通过原版事件播放能力闪烁 |
| 能力和状态牌说明 | `smartDescription`、`ExtraHoverTips`、`HoverTipFactory` | 积水和冲净动态显示当前层数；寄生使用原版再生、力量、固有和消耗说明 |
| 图标 | `PowerModel.PackedIconPath`／`ResolvedBigIconPath` | 四个新能力提供 64px 小图与 256px 大图；按各版本原版加载路径解析 |

资源加载有版本差异：v107.1 原生读取 `.sprites/*.tres` 中的 64px AtlasTexture；v111 原版 `AtlasResourceLoader` 对新增模组能力会使用 `images/powers/*.png` 回退，随后由原版 NPower 缩放显示。此处使用官方回退，不修改原版图集、加载器或私有缓存。

参考源码位于 `STS2-V111/src/Core/`：`Models/Monsters/WaterfallGiant.cs`、`MonsterMoves/Intents/`、`Nodes/Combat/NIntent.cs`、`Nodes/Combat/NPower.cs`、`Models/PowerModel.cs`、`Commands/PowerCmd.cs`、`HoverTips/HoverTipFactory.cs`、`Assets/AtlasResourceLoader.cs`。同时比较了 v108／v111 相关 API，并编译实际 v107.1／v111 DLL。

## 保留的机制

海绵肚腹四档水位、身体膨胀、喷后退水均保留。寄生被打出或其他效果消耗后，存活血蛭准备补牌；普通弃牌不触发。冲净仍自动消耗寄生并触发该响应。致盲仍按原版抽牌与本回合费用接口执行费用变化，牌面干扰继续使用此前确认的专属视觉效果。

## 检查

- v111 海绵原生机制及画面：244 项通过。包含原版意图类型、30 帧动画实际切换、NPower 层数文字、SmartFormat、四档水位、触发闪烁与移除事件。
- v107.1 机制：146 项通过。
- 灯笼鱼／致盲回归：66 项通过，包含神器阻挡、抽牌限制、星能与 X 费、多人归属、费用恢复和原版动作结算。
- 中英能力表：91 项，键与占位符检查通过。
- 源码与 PCK 检查通过，确认新图标尺寸及旧自定义意图资源已移除。
- 统一包检查通过，两目标均识别 89 个模组模型，内嵌 DLL 与对应被测实现哈希一致。

本轮检查文件位于 `build/native_combat_ui/`；此前 1.12.0 的安装包与验证记录仍保留。新版安装前通过游戏菜单保存退出，并备份了当前存档与旧安装包。

## v0.111.0 实机确认

已安装 1.12.1 并重启游戏。三次正常打击让积水依次达到 1／2／3，快照确认满水意图类型为原版 `SingleAttackIntent, BuffIntent`。画面显示原版攻击数值与强化箭头，积水悬浮说明显示 3/3 并关联冲净说明。

喷淋实际结算后，海绵积水移除、肚腹退水，玩家获得 1 层冲净。悬浮框正确显示剩余 1 次，展开寄生卡预览及原版再生、力量、固有和消耗提示。截图与状态 JSON 位于 `build/native_combat_ui/live/`。

启动日志中另有联机重制模组初始化时的 `process_frame` 断连报错；它发生在进入测试战斗之前，本次意图与能力的实机流程正常完成。多人机制仅有原生模拟回归，未进行网络联机测试。
