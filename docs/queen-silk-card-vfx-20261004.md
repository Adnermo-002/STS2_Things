# 1.13.1 · Queen 同类卡牌特效

牵丝效果改用 Queen「魂缚锁链」的原版卡牌附着渲染结构。两张牌保留 1／2 的顺序信息，规则仍是先获得 buff，在下回合抽牌结束后选牌；先打出 1 才能使用 2，解开不减费。

## 原版参考

原版调用路径为 `Queen.PuppetStringsMove` → `ChainsOfBindingPower.AfterCardDrawn` → `CardCmd.AfflictAndPreview<Bound>(..., CardPreviewStyle.None)` → `Bound` 的 overlay 场景。`NCard` 在 Affliction 变化时创建或销毁该场景。

原版 `vfx_ui_card_affliction_bound.tscn` 使用完整的 300×422 卡牌遮罩、极坐标噪声边缘材质、暗角、辉光、GPU 微粒和主图纹理。主图把强度、流光噪声和覆盖分别打包进 R、G、A 通道。新版沿用这套结构和布局，在独立资源路径中引用副本，避免更改 Queen 本身。

## 新版表现

- 独立制作四角丝束覆盖和柔光，替换原版锁链图形；保留 Queen 的流光通道约定。
- 浅绿卡框光、象牙色丝束和微粒共同附着于卡面；不再使用旧版大椭圆与跨牌弧线。
- 0.55 秒施加动画与 0.48 秒解除动画；解除时丝束材质溶解并轻微向外松开。
- 两张牌各自使用独立材质实例，进度互不影响。
- 使用原版卡牌减益意图 `CardDebuffIntent`，以及原版 `AfflictAndPreview` 入口；无额外选牌弹窗。

重建入口：`scripts/build_silk_card_overlays.py`。原版路径、源场景哈希、通道说明与资源映射保存在 `source_assets/ui/silk_queen/reference.json`。丝束是特效通道图，使用确定性的纹理生成脚本制作；本轮没有重新生成怪物立绘。

原生并排预览的左侧为未修改的 Queen 原版束缚，右侧两张为牵丝。视频位于 `build/silk_queen/review/queen-silk-card-vfx.mp4`；它是 Godot 原生渲染对照，不是实机战斗录像。

## 验证与实机

- v111：292 项原生机制与画面检查通过，包括卡牌形状遮罩、粒子、材质实例隔离和解除进度；采集 121 帧，20fps／6.05 秒。
- v107.1：140 项机制检查通过；双版本统一包各 96 个模型，内嵌实现与对应目标程序集一致。
- 源码及最终 PCK 静态检查通过。独立探针错误日志为空。
- v0.111.0 单人实机确认普通手牌与悬停卡牌都显示丝束和卡框光；被锁定的 2 费痛击不可使用。打出 1 费先手防御后，牵丝及卡牌附着解除，痛击恢复可用，仍为 2 费，能量由 3 降至 2。

实机状态与截图位于 `build/silk_queen/live/`。本轮没有人工联机对战；多人对象隔离由原生机制探针覆盖。
