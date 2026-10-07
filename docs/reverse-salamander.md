# 1.15.0 · 逆流蝾螈

在「深处」精英池加入单只逆流蝾螈，遭遇 ID：`REVERSE_SALAMANDER_ELITE`。采用已有原创河湾洞穴与地板，玩家队伍沿用向下 60 像素的站位。

## 机制与数值

生命 168／188（坚韧敌人），参考原版巢穴 Entomancer 的 145／165 与 InfestedPrism 的 161／171；因为每轮回流会给予玩家额外牌与减费，生命略高。

开场逆潮 12／14；随后循环：尾浪 16／18 → 倒卷 5×3／6×3 → 蓄流 10／12 并获得 12／15 格挡。斜线为对应高进阶。

每名玩家抽牌结束后，查询原版战斗记录，取上一回合最后一张可返还的攻击或技能牌。排除消耗词条、X 能量、不可打出、其他附着、已消耗或已移出战斗的牌。若该牌仍在抽牌堆或弃牌堆，则移回手牌；若已正常抽到，则直接附着回流并减费。满手牌时不从牌堆追加。

回流牌耗能减少 1，按原版“本回合”规则在打出或回合结束时恢复。打出回流牌后，存活的蝾螈获得 2 力量（致命敌人下 3），并清除该玩家当前的回流标记，避免现有复制牌重复触发同次回流。玩家可不使用这张牌。普通弃牌保留当回合标记；消耗、回合结束、能力移除或蝾螈死亡清除。

实现参考原版 `HistoryCourse` 的 `CardPlaysFinished`／`HappenedLastPlayerTurn` 查询，使用实际卡牌对象、`CardPileCmd`、`AfflictAndPreview`、`AddThisTurnOrUntilPlayed` 和 `StrengthPower`。不复制回流牌、不修改永久牌组、不维护另一套出牌记录。回流卡牌使用原版 Affliction 场景与蒙版，加上淡色动态水纹；说明、意图、费用显示和能力图标走原版接口。

## 美术和骨骼

角色与能力图标使用用户指定的 **gpt-image-2.5-sunburst**，通过 imagegen 官方 CLI 制作。角色采用 `edit` 入口，以原版 Spiny Toad、Toadpole 图谱作为画风参考；图标采用 `generate`。

- [角色提示词](../source_assets/monsters/reverse_salamander/character_prompt.txt)
- [能力图标提示词](../source_assets/monsters/reverse_salamander/power_prompt.txt)
- 原始与清理后的图片位于 `source_assets/monsters/reverse_salamander/`，密钥未写入文件。

造型为灰蓝、米色的圆润蝾螈，带困倦双眼、暖色鳃叶和向上卷起的瀑布尾。制作时清除了多余外发光，并补绘腿部、眼睛与尾根遮挡区域。画风自审查看了原版参考、透明原画、能力图标及骨骼制作画面；修正了前冲时远侧眼睛与头部贴合不足的问题。

原生 Spine 4.2 资源在 1.15.1 中细化为 **50 根骨骼、11 个绘画层、12 组动作**：待机、尾浪、逆潮、三段倒卷、蓄流、回牌、施法、强化、受击、死亡、复起、出现。四足使用烘焙的两段 IK 控制；尾巴七段递进运动，鳃叶、尾鳍、眼睛、下颌与腹部独立绑定。胸背、后胯与尾鳍末端增加局部控制，腿根平滑贴合身体。攻击有蓄力、接触停留与回弹；三段攻击在 0.46／0.74／1.02 秒结算，蓄流的伤害与格挡分别对齐 0.56／1.20 秒。[1.15.1 动作与能力文案说明](salamander-animation-and-power-copy.md)。

水流材质只作用于尾部图集区域，光带朝尾尖上行；随力量提高加快流动。制作预览仅展示骨骼，不含游戏内水流材质和卡牌 UI。

## 交付范围

按用户“不用测试”的要求，本轮 **没有运行自动化测试、行为或原生渲染探针、Spine 运行时验证，也没有进行战斗试玩**。完成的是素材制作中的画面自审、v107.1／v111 编译与 Godot 资源导出。两套实现及统一入口编译成功；这不等同于运行时与联机验证。

1.15.1 编译日志位于 `build/reverse_salamander_polish/`。构建入口 `scripts/build-reverse-salamander-release.ps1` 只编译、导入和导出，不调用项目测试脚本。

- [原画预览](../source_assets/monsters/reverse_salamander/character_review.jpg)
- [骨骼制作预览](../build/reverse_salamander_polish/authoring/motion.gif)
- 安装包：`dist/v1.15.1/STS2_Things-1.15.1.zip`

素材重建入口：`scripts/prepare_reverse_salamander.py`；骨骼在 `tools/ReverseSalamanderRig/` 依次运行 `python -m rigkit build`、`python -m rigkit export`、`python package.py`；场景及文本入口为 `scripts/integrate_reverse_salamander.py`。

手动进入遭遇可使用 `fight REVERSE_SALAMANDER_ELITE`。本轮没有执行此命令。
