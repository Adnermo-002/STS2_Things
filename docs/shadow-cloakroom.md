# 深处事件：影子寄存处 · 1.20.0

支付 25 金币，选择一张能升级、能移除的攻击、技能或能力牌，暂时从牌组移出。进入本章 Boss 房间之前，自动归还并升级一次。也可以免费离开。

## 选择与数值

原版升级类事件通常能直接提供强化；本事件额外提供临时精简牌组，因此收取较低的 25 金币费用，并要求先承受失去选定卡牌的风险。寄存基础牌可以暂时提高循环效率；寄存高费核心牌，则要考虑剩余精英和普通战能否应付。数值尚未进行实战调校。

- 使用原版选牌界面，确认有效选择后才结算；取消不会扣款。
- 仅能寄存可升级、可移除的攻击、技能、能力牌；至少留一张牌在牌组中。
- 收据在该局内只领取一次；金币不足、没有合格牌或已持收据时显示对应锁定选项。
- 「寄存收据」是原生 Event 类遗物，不进入普通遗物奖励池。悬浮可查看所寄存的牌及其说明。
- 归还后收据使用原生 `IsUsedUp` 与禁用显示，保存已领取状态，防止重复归还。

## 原生实现与存档

`ShadowCloakroom` 只加入深处的普通事件池，默认启用。开关接入本模组设置、BaseLib 和 RitsuLib；向既有配置列表末尾追加，保留原有索引。

沿用原版 `PaelsTooth` 保存和归还卡牌的流程：`CardModel.ToSerializable` / `FromSerializable` 保存升级层级、附魔、卡牌 SavedProperties 及原加入层数；原生 `CardPileCmd` 负责出入牌组和相关钩子。归还采用原生加入牌组规则，因此正常遗物和模组对加入牌组的修正仍然有效。

收据保存 `StoredCard`、`DepositActIndex`、`Returned`，没有外部存档文件或静态寄存列表。v107.1 的兼容层显式注册新遗物 SavedProperty，并重算网络属性编号位宽；v111 使用原生模型扫描。

归还发生在 `BeforeRoomEntered`，早于 `CombatRoom.Enter` / `SetUpCombat` 复制和洗入战斗牌组，所以可参与 Boss 首轮抽牌。该时机参考了原版进入房间、建立战斗的调用顺序。仅使用 `BeforeCombatStart` 会晚于战斗牌组创建，故未采用。

- 跨章兜底：如果通过其他机制跳过本章 Boss，进入下一章时归还并升级。
- 非正常移除收据：释放寄存牌，但不提前获得升级奖励。原版遗物交易不接收 Event 类遗物。
- 加入牌组失败：保持收据未领取，不消耗寄存数据。
- 多人每名玩家拥有独立事件和收据，选牌沿用原生同步；保存的卡牌只还给对应玩家。收据的偿还不受后续关闭事件开关影响。

## 叙事

> 石壁间嵌着一间寄存处。你还没走近，自己的影子已经靠在柜台上，不耐烦地敲着桌面。
>
> 柜员从一排空衣钩间抬起头，把一张收据推给你。
>
> 「一张牌，25 枚金币。到这层的大门前，送还给你。我们会替你……收拾一下。」

寄存后，牌被抖成一件黑衣，挂到身后的衣钩上。离开分支中，影子不情愿地贴回脚底，柜员只要求「下次请一起到」。遗物风味文字是「凭影领取」。

完整文本：`source_assets/events/shadow_cloakroom/localization.json`。

## 美术

使用用户指定的 `gpt-image-2.5-sunburst`，通过 imagegen skill 官方 CLI 和既有授权 API 制作。原版 `waterlogged_scriptorium.png` 作为绘画风格参考输入；新场景是一间洞穴寄存处，有疲倦的柜员、主动排队的影子与挂在衣钩上的黑衣。

主体使用原版式大块明暗与带卡通感的比例。画面覆盖完整场景，从主体向外围持续渐暗；外围仍有岩壁、柜架与衣钩，不使用剪影开窗遮罩。按原生视口超幅裁切留足空间，右侧文字区保留低对比景物。

收据图标保留生成结果的真实透明通道，清理少量边缘杂点并制作原生图集资源与白色轮廓。已人工查看 256、64、48 像素表现，图形可辨认。

- 原始图：`output/imagegen/shadow_cloakroom/event_portrait_v1.png`、`claim_ticket_v1.png`。
- 完整提示词：`source_assets/events/shadow_cloakroom/prompts/event_portrait.txt`、`claim_ticket.txt`。
- 正式插画：`images/events/shadow_cloakroom.png`；尺寸 3440 × 1616。
- 正式遗物：`images/relics/shadow_claim_ticket.png`；尺寸 256 × 256。
- 原画、渐暗遮罩、透明图标母版均保存在 `source_assets/events/shadow_cloakroom/`。
- 生成接入脚本：`scripts/prepare_shadow_cloakroom.py`；共用预览工具：`scripts/native_event_preview.py`。
- 中英文离线预览：`build/shadow_cloakroom/event-layout-review.jpg`、`event-layout-review-eng.jpg`。
- 遗物缩放预览：`build/shadow_cloakroom/relic-review.jpg`。

人工画风审查：柜员表情与影子轮廓清楚，岩壁、木柜和衣物以大色块组织，暖色收据形成焦点；外围景物连贯渐暗。中英文正文与两个选项完整可读。以上图片是 Pillow 合成的制作预览，不能当作游戏截图。

## 验证与交付

发行包与逐文件哈希、编译日志和安装记录位于 `build/shadow_cloakroom/delivery.json`，发行路径为 `dist/v1.20.0/STS2_Things-v1.20.0.zip`。

v107.1、v111、统一启动程序集及 BaseLib 配置桥均编译成功，0 警告、0 错误；Godot 图像导入与 PCK 导出完成。中英文静态审查通过：事件 120 条、遗物 20 条、设置 68 条，键与占位符一致。

1.20.0 已安装到本机游戏，清单、统一程序集、PCK 和配置桥四个文件均与发行包 SHA256 一致。旧版备份位于 `STS2-MCP/.state/install-backups/STS2_Things-20261005T142306-7b1084`。

遵守用户此前「不用测试」的要求：仅源码审查、本地化静态审查、制作预览、编译和资源导出；不启动游戏或运行原生、战斗、存读档及多人测试。存档和多人兼容性结论限于实现审查与目标版本编译。
