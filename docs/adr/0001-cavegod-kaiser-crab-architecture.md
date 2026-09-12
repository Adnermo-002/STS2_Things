# ADR-0001: 采用帝王蟹（Kaiser Crab）全屏背景 Spine 模式构建山神（CaveGod）Boss 遭遇

## 状态
已通过（Accepted）- 由用户在 2026-09-13 裁决（Q1: B, Q2: B, Q3: A）

## 背景与上下文
此前模组中的探索性实现“活体巨岩”（`LivingRock`）尝试将山神巨型骨骼直接作为单体怪兽节点的内置 Visuals，导致：
1. 超大尺寸骨骼在标准战斗场景中产生裁切与缩放失衡；
2. 怪物碰撞体、血条与骨骼原点脱节；
3. 左右转身动画逻辑混乱，缺乏宏大 Boss 战场视差与全景镜头表现。

经过对 STS2 原版 Act 2 巨怪 Boss 帝王蟹（`KaiserCrab`）的逆向与架构分析发现：
- 官方对于万吨级巨型 Boss 的标准工业级解法是：**多轨背景 Spine 宿主（`NKaiserCrabBossBackground`）+ 全景镜头缩放（`CameraScaling: 0.75f`、`CameraOffset: Vector2.Down * 35f`、`FullyCenterPlayers: true`）**；
- 战斗场景由专门的 `EncounterModel` 定义槽位与背景联动；
- 怪兽实体（`MonsterModel`）负责意图、AI 状态机、数值、伤害判定，并在行动与受击时通知背景骨骼宿主播放对应动画。

## 决策内容
1. **完全剔除活体巨岩（Purge LivingRock）**：
   - 清理所有旧版 `LivingRock` 的代码、场景、材质、配置项与测试探针；
   - 释放命名空间与配置项位置。
2. **构建独立山神遭遇战（CaveGodBossEncounter）**：
   - 新建 `CaveGodBossEncounter`，继承 `ModBossEncounter`；
   - 对齐帝王蟹的镜头参数：`CameraScaling = 0.75f`，`CameraOffset = Vector2.Down * 35f`，`FullyCenterPlayers = true`；
   - 配置专用背景场景 `res://scenes/backgrounds/cave_god_boss_encounter/cave_god_boss_encounter_background.tscn`。
3. **中央单体主宰怪兽实体（Single Central Titan Entity）**：
   - 设立单一中央实体 `ThingsCaveGod`（位于正前方中右侧核心攻击范围）；
   - 保留未来在左右两侧扩展部件实体（如浮游岩核、破土巨拳）的扩展性；
   - AI 状态机驱动 5 组核心正面动作：
     - `central_slam`（中央万钧重砸，高额单体）
     - `front_sweep`（四指拳锋贴地横扫，全队 AOE 横推）
     - `alternating_jabs`（左右交替刺拳，多段连击）
     - `double_fist_crush`（双拳对撞，易伤/重创）
     - `grab_player`（单臂抓取压制）
   - 受击时触发 `hit_recoil`，血量进入狂暴阈值或阶段转换时触发 `main_angry` 熔岩变体。
4. **导入并搭载 CentralCombat_v4 终极骨骼资产**：
   - 将 `CaveGod_3.8.75_CentralCombat_v4` 中已完成 Catmull-Rom 流畅动力学重构、35张原版PNG贴图100%保持不变的 Spine 4.2 / 3.8 资源正式导入模组工程。

## 影响评估
- 旧版 `LivingRock` 相关测试与脚本需重定向或重写；
- 模组架构与官方二幕大体型 Boss 实现标准完全统一，消除了此前一切内嵌 Spine 引起的漂移与缩放异常。
