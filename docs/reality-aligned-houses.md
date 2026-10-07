# 深处事件：对齐之屋 · 1.19.4

深处第二章的专属普通事件。画面是一望无际的草原、道路两侧不断重复的住宅、直达地平线的大路，以及异常明净的蓝天白云。配色和光感借鉴 Frutiger Aero 的乐观、清澈与旧日数字景观；绘制仍采用尖塔插画的大块明暗和简化轮廓。完整场景从左侧主体附近向周边连续渐暗，天空、房屋与草地延伸到暗部，经过较长距离才融入黑色。文字和选项沿用右侧原生布局。后续事件遵循 [事件美术规范](event-art-guidelines.md)。

## 四个选择

| 选项 | 效果 | 限制与代价 |
| --- | --- | --- |
| 合并两扇门 | 把两张同名牌合为一张升级版 | 两张均须未升级、未附魔、可升级、可移除；通过原版选牌界面分别选定保留与移除的牌 |
| 给自己留一间 | 升级一张牌，赋予原版「完美契合」 | 失去 5 点最大生命；需要可升级且能获得该附魔的牌 |
| 走到天黑为止 | 绕回同一只邮筒，付出生命领取金币 | 每圈后可退出，最多三圈；代价与金币逐圈翻倍 |
| 从蓝屋的后门走 | 安全离开 | 无隐藏代价 |

「完美契合」沿用原版实现：战斗中再次洗牌时，把这张牌放到抽牌堆顶；开场洗牌仍遵从原版规则。本事件没有自行改写牌堆，也没有新增一套同名 buff。

绕路的每次结算：

| 圈数 | 本圈生命代价 | 本圈基础金币 | 累计生命代价 | 累计基础金币 |
| --- | --- | --- | --- | --- |
| 第一圈 | 4 | 35 | 4 | 35 |
| 第二圈 | 8 | 70 | 12 | 105 |
| 第三圈 | 16 | 140 | 28 | 245 |

每个继续选项显示下一圈的确切数值，并沿用原版致死提示；受伤致死时不发放该圈金币。获得金币仍经过原版金币修正与遗物钩子。第三圈结束自动收尾，不能无限刷取。其成本档位参考巢穴「巨型花朵」的付血取金，递增选择流程参考原版「深渊浴场」。数值没有经过实战胜率调校。

## 叙事

> 石阶忽然尽了。眼前是一望无际的绿草与过分干净的蓝天。白房子沿着大路两侧，整齐地排到视线之外。
>
> 你走了一会儿，又看见同一只蓝色邮筒。天上的云连边缘都没有变。
>
> 里面有封信，纸上是你的笔迹：
> 「欢迎回来。房子已经替你留好了。」

合并路线把两座房屋像纸页一样合拢；留房路线让一部分自己成为屋里的住客，使一张牌记住回家的路；绕路路线逐次遇到自己写来的信，第三圈看到另一个拎着自己背包的身影。各路线、途中退出、无有效选牌和死亡都有独立文本。

完整中英文源文本在 `source_assets/events/reality_aligned_houses/aero_text.json`。旧版 HOME／ALIGN 文本键保留给历史记录；当前游戏信息目录只公布新选项。

## 原生接入与多人

- `RealityAlignedHouses` 继续通过 `Depths.AllEvents` 加入深处池；保留默认启用开关及 BaseLib、RitsuLib 设置页。
- 使用普通非共享 `EventModel`：多人各自拥有实例，分别选择、选牌和结算，绕路计数不会互相累加。
- 两步选牌均用原版 `CardSelectCmd` 同步。合并只移除玩家明确选定的另一张牌，并原地升级保留牌；不会随意吃掉强化或附魔版本。
- 留房先完成有效选牌，再结算最大生命代价。使用 `PerfectFit` 和原生升级预览展示最终成牌。
- 循环次数与 DynamicVars 保存在事件实例中，使用与原版递增事件一致的流程；不使用本机随机数或画面状态决定奖励。
- 使用原版默认布局和文字样式；文字区背景逐步压暗，保留微弱景物延伸。

## 美术与制作预览

草原原画使用用户指定的 `gpt-image-2.5-sunburst`，经 imagegen skill 官方 CLI 生成。正式画幅为原版事件的 3440 × 1616。1.19.4 保留原画并恢复完整场景铺底，使用连续的明暗分布从中心向外围衰减；外围景物仍完整存在，随距离逐渐退入暗部。蓝色小屋位于可见画区内，道路消失点与两侧重复住宅保持完整。

用户最终明确周边也要有画面，只是视觉权重更低、慢慢变黑。1.19.3 的羽化剪影仍像开窗，因此删除轮廓曲线和基于轮廓距离的遮罩，改用跨越数百像素的连续亮度衰减。主体约占中部 2/3 是视觉重心要求；不沿这个比例裁切画面，也不压缩原生文字和选项。

- 原始输出：`output/imagegen/reality_aligned_houses/event_portrait_v3_grassland.png`。
- 提示词：`source_assets/events/reality_aligned_houses/prompts/event_portrait_v3_grassland.txt`。
- 母图：`source_assets/events/reality_aligned_houses/portrait_master.png`。
- 游戏资产：`images/events/reality_aligned_houses.png`。
- 明暗遮罩：`source_assets/events/reality_aligned_houses/peripheral_fade_mask.png`。
- 中文、英文排版预览：`build/reality_aligned_houses_radial_fade/event-layout-review.jpg`、`event-layout-review-eng.jpg`。
- 无 UI 插画预览：`build/reality_aligned_houses_radial_fade/event-art.jpg`。
- 插画区域放大预览：`build/reality_aligned_houses_radial_fade/illustration-detail.jpg`。
- 原版参照对照图：`build/reality_aligned_houses_radial_fade/style-review.jpg`。
- 合成源代码：`scripts/aligned_houses_composite.py`，由 `prepare_reality_aligned_houses.py` 调用。
- 1.19.3 剪影版备份：`build/reality_aligned_houses_radial_fade/before/`。
- 1.19.2 构图与原画备份：`build/reality_aligned_houses_soft_edges/before/`。
- 1.19.1 窄边版本备份：`build/reality_aligned_houses_black_surround/before/`。
- 1.19.0 旧版源码及插画：`build/reality_aligned_houses_aero/before/`。

已人工查看最终插画和中英离线排版：蓝色小屋、两排住宅、大路消失点与亮色天空保持清晰，四周保留逐渐变暗的连贯景物，没有剪影开窗轮廓；四个选项保持可读。明亮的 Frutiger Aero 配色沿用用户指定方向。预览使用原版场景尺寸、字体与按钮纹理，但由 Pillow 合成，不能当作真实游戏截图。

## 来源与许可

灵感来源为 [Level 995 — Reality Aligned Houses](https://backrooms-wiki.wikidot.com/level-995)，作者 RiemannHypothesis（页面亦署名 RiemannHypothesis/FoodPieIntegration），Backrooms Wiki，CC BY-SA 3.0。引用的是无尽住宅、熟悉却错位的归处与蓝屋出口等意象，未复用原报告文字或照片。

完整署名与改编说明位于 `STS2_Things/credits/reality_aligned_houses.txt` 并随 PCK 导出。新增改编叙事和新插画按 CC BY-SA 3.0 提供，其他代码与资源保留各自许可。

## 交付记录

发行包：`dist/v1.19.4/STS2_Things-v1.19.4.zip`。编译、导出、文件哈希、安装与备份记录在 `build/reality_aligned_houses_radial_fade/delivery.json`。

v107.1、v111、统一启动程序集和 BaseLib 配置桥均编译通过，0 警告、0 错误。Godot 图像导入和 PCK 导出通过。

1.19.4 已安装到本机游戏，清单、统一程序集、PCK、BaseLib 配置桥四个文件均与发行包哈希一致。上一版本备份保存在 `STS2-MCP/.state/install-backups/STS2_Things-20261005T134155-298d72`。

遵守此前“不用测试”的要求：不启动游戏，不运行原生探针、战斗或联机测试；实际运行表现仍未实测。
