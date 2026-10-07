# 深处实用事件：遗物修补摊、药水试饮会、窄门

版本：1.23.1。三个事件加入深处普通事件池，默认启用。各玩家独立选择、支付和领奖；不改变其他章节的事件池。

## 规则与数值

| 事件 | 主要选择 | 保守选择 |
| --- | --- | --- |
| 遗物修补摊 | 交出一件可交易遗物并支付 30 金币，换取提前展示的、尚未持有的普通遗物；或出售一件可交易遗物，获得 200 金币 | 扶稳桌脚，获得 15 金币 |
| 药水试饮会 | 免费获得一瓶随机原版药水；或支付 30 金币获得两瓶；或交出一瓶自有药水获得两瓶 | 免费药水就是无损选择；无法获得任何药水时，改为喝热水回复 4 点生命 |
| 窄门 | 前三项分别显示一张牌，点击即移除；第四项“换个姿势”，支付 25 金币更换候选一次 | 免费移除就是无损选择；完全没有可移除牌时，第一项改为歇脚、回复 4 点生命 |

遗物交易遵守原版 `RelicModel.IsTradable`：初始、事件、先古、已用尽、有获得时效果等被原版排除的遗物不进入支付列表。普通遗物使用原版 grab bag 抽取并预留，菜单往返不重抽。如果普通遗物池耗尽，不把原版兜底头环伪装成普通遗物。每次访问仅结算一个分支。

药水按原版战外工厂的角色池、解锁与稀有度权重抽取，排除其他模组的药水。结果只生成一次，领取前隐藏，往返支付菜单不重抽；赠送一瓶或两瓶，不再让玩家挑选奖励种类。换药时仍明确选择自己交出的瓶子。`Hook.ShouldProcurePotion` 检查添水等获得限制，无法兑现的奖励不收费；药水栏已满不算禁止获得，由原版奖励界面处理弃置旧药水、领奖和拒绝领取。奖励前恢复本事件临时冻结的药水操作权限；退出事件也恢复原值。V107.1 使用 `CanRemovePotions`，V111 使用 `CanUseOrRemovePotions`。

窄门把三张实际卡牌直接展开为三个原版事件按钮，标题使用原版牌名（含升级标记），悬停显示对应卡面。点击后直接移除该实例，不打开第二层选牌界面。不足三张时，空位显示锁定，第四项的位置不变。禁止移除最后一张牌；完全没有合法选择时，以第一项的歇脚收益保证事件可结束。重选优先使用此前未展示的牌，不足三张才从旧候选补齐；没有其他候选、金币不足或已重选时锁定第四项。重选完成后仍然直接显示三张牌。

遗物和支付药水列表每页三个选项，加“更多”和“返回”，避免大背包溢出原版事件区域。菜单中的返回只负责退回上一层；结局的原版继续按钮不会重复奖励。

## 原版实现与多人

- 参考 `RelicTrader`、`TheFutureOfPotions`、`PotionCourier`、`TeaMaster`、`RanwidTheElder`。
- 使用原版 `EventModel`、`EventOption`、悬停提示、`RelicCmd`、`PotionCmd`、`RewardsCmd`、`CardPileCmd.RemoveFromDeck` 和金币命令。
- 全部为个人事件；事件 RNG 和原版事件选项同步决定结果，没有本地 UI 私自改库存的逻辑。
- 返回和翻页只生成原版事件选项，不消耗 RNG；资源只在最终确认时扣除，结算标记防止重复领取。
- 新配置项追加在原配置表末尾，接入 RitsuLib 和 BaseLib；不改变既有配置索引。多人玩家须使用同一版本的模组。
- 本次没有新增跨房间债务、临时牌或自定义存档协议。
- 对照原版 `RelicTrader`、`TeaMaster`、`RanwidTheElder`、`Wellspring` 重写开场、结局与效果句：具体动作、简短对白，效果明确写“失去”“获得”“移除”。旧药水选择页与窄门旧通用删牌键仅保留给 1.23.0 历史记录使用；当前菜单不引用它们。

代码入口：

- [RelicWorkshop.cs](../STS2_Things/Events/RelicWorkshop.cs)
- [PotionTasting.cs](../STS2_Things/Events/PotionTasting.cs)
- [NarrowGate.cs](../STS2_Things/Events/NarrowGate.cs)
- [事件池注册](../STS2_Things/STS2_ThingsInit.cs)

## 插画与自审

使用 imagegen 官方 CLI 的 API 模式，模型为用户指定的 `gpt-image-2.5-sunburst`。原版 `tea_master.png` 作为画法参考，对照 `ranwid_the_elder.png`、`relic_trader.png` 及原生 `default_event_layout.tscn`。

三张原画分别是甲虫修补摊、蝾螈试饮摊和带困倦表情的窄石门。人物保持轻度卡通比例，使用简化轮廓、宽阔明暗面和节制细节。保留完整石壁、货架、通道和地面，再叠加覆盖全画幅的连续明暗场；没有椭圆开窗、剪影黑边或硬相框。主体、桌面和门口接触关系自然，右侧暗部不干扰文字。

插画沿用 1.23.0 的原图与渐暗处理。本次重新审查中英文初始页面、遗物出售页、药水支付页、窄门四按钮页面及重选/无牌页面：关键主体完整，按钮文字未超出预览区域。所有预览都是 Pillow 离线排版合成，使用原版字体、按钮与 2662×1251 的肖像显示变换，**不是游戏截图**。

| 事件 | 游戏资产（3440×1616） | 最终提示词 | API 原图 |
| --- | --- | --- | --- |
| 遗物修补摊 | [relic_workshop.png](../images/events/relic_workshop.png) | [portrait.txt](../source_assets/events/relic_workshop/prompts/portrait.txt) | [portrait_v1.png](../output/imagegen/relic_workshop/portrait_v1.png) |
| 药水试饮会 | [potion_tasting.png](../images/events/potion_tasting.png) | [portrait.txt](../source_assets/events/potion_tasting/prompts/portrait.txt) | [portrait_v1.png](../output/imagegen/potion_tasting/portrait_v1.png) |
| 窄门 | [narrow_gate.png](../images/events/narrow_gate.png) | [portrait.txt](../source_assets/events/narrow_gate/prompts/portrait.txt) | [portrait_v1.png](../output/imagegen/narrow_gate/portrait_v1.png) |

每个 `source_assets/events/<事件>/` 保留 `portrait_unframed.png`、`peripheral_fade_mask.png`、`portrait_master.png` 和中英文权威文本 `localization.json`。插图和排版可通过 `scripts/prepare_practical_events.py` 重建；文本通过 `scripts/integrate_practical_events.py` 合入。

## 验证与交付

按用户“无需测试”的要求，不启动游戏，不运行原生、战斗、存读档或多人探针。执行双版本编译、Godot 资源导入和 PCK 导出、静态本地化审查、源码分支审查及离线画风/排版审查。编译和静态审查不等同于实机验证。

- [离线预览总览](../build/practical_events_polish/events-overview.jpg)
- [排版记录](../build/practical_events_polish/art-layout-review.json)
- [交付记录及哈希](../build/practical_events_polish/delivery.json)
- [1.23.1 安装包](../dist/v1.23.1/STS2_Things-v1.23.1.zip)

事件池一般在章节/房间队列生成时确定；已经生成的旧存档不会自动补入新事件，新一局可自然遇到。三个开关分别为 `EventRelicWorkshopEnabled`、`EventPotionTastingEnabled`、`EventNarrowGateEnabled`。
