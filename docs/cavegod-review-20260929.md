# 山神（CaveGod）全面审查 · 对照《杀戮尖塔2》原版 Boss

2026-09-29 · 只读审查，未修改任何源码 / Spine / 场景。
依据：`STS2_Things` 当前磁盘源码、`cave_god.spjson`（Spine 4.2.43）、`STS2-V111` 反编译原版（Crusher/Rocket、KnowledgeDemon、WaterfallGiant、CeremonialBeast、Queen、TestSubject、Aeonglass、TheInsatiable、LagavulinMatriarch、Vantom、SoulFysh）、`verify_project.py` 实跑结果。

---

## 0. 一句话结论

架构（帝王蟹式全屏背景 Spine + 双臂实体 + 核心单一状态机）已经很扎实，**缺的是"原版味"的三样东西：可读的意图文本、每个招式独有的动作、以及一个只属于山神的核心资源机制**。另外有 3 个会直接影响手感/构建的 P0 问题。

---

## 1. P0：必须先修（影响构建或玩家可读性）

| # | 问题 | 证据 | 影响 |
|---|---|---|---|
| P0-1 | **意图标题本地化缺失，且校验被静默绕过** | 手臂 MoveState ID 是 `Rest/Down/Sweep/Grab/Slam/WeakStun/WeakAttack/Recover/EscapeStun`，本地化里却是 `FRONT_SWEEP / GRAB_PLAYER / AIR_SLAM / WEAK_STUN_1 / *_FALLBACK`；躯干缺 `P1_REST_SWEEP / P2_REST_GRAB / P2_REST_SLAM`。`verify_project.py` 只匹配 `new MoveState(`，而代码用的是 `new(Jabs, …)` 目标类型写法；手臂又是 `abstract` 基类 → 检查一个都没扫到 | 悬停意图 / 图鉴可能显示原始键名或空标题（需进游戏确认）。旧实体 `THINGS_CAVE_GOD.*`（名字仍是"活体巨岩"）属于残留键 |
| P0-2 | **动画打击帧与伤害结算不同步** | `front_sweep` 的 `central_hit` 事件在 **1.35s**，代码 `Cmd.Wait(0.90f)` → 伤害**早 0.45s** 结算（拳还没到）；`central_slam` 事件 1.88s，代码 1.98s（晚 0.10s）；`double_fist_crush` 意图是 2 段，动画只有 1 个撞击事件 | 原版最看重的"拳到数字到"打击感丢失 |
| P0-3 | **构建被山神背景场景阻断** | `verify_project.py` 实跑唯一失败：`cave_god_boss_encounter_background.tscn overrides native background z-order`（场景里有 `z_index=`） | `build.ps1` 直接中止，连带 the_legacy 也没法安装测试 |

另外两项小问题：
- `MOUNTAIN_GUARD`（攻击 + 格挡 + 成长）复用了 `double_fist_crush` 动画，和 P2 的"巨拳夹击"长得一模一样，玩家分不清。
- 手臂阶段转换时力量会被清空，躯干的力量却保留；ADR-0002 写的是"力量跨阶段保留"，封印能力的描述又写"清空双臂力量"。三处说法不一致，需要确定以哪个为准。

---

## 2. 与原版 Boss 设计的差距

原版 Boss 的共同"配方"（从 v0.111 源码归纳）：

1. **一个专属核心资源 / 能力**：Waterfall Giant 的「蒸汽喷发」层数 → 爆炸 DeathBlow；Ceremonial Beast 的「犁」→ 被打断眩晕；Aeonglass 的逐步加码；Lagavulin 的「沉睡 + 金属化」；Kaiser Crab 的 `CrabRage`（一只钳死了另一只 +6 力量 +99 格挡）。
2. **至少一个往牌组塞状态牌的招式**：Aeonglass「凋零」、TestSubject「灼伤」、Vantom「伤口」、Insatiable、SoulFysh。
3. **每个意图都有独有的动作**：Kaiser Crab 的每只手都有 `idle_loop / charge_up / charged_loop / attack_heavy / rest_loop / hurt / hurt_charged / hurt_resting / die / wake_up`，外加独立的 `reactions/*` 轨道。
4. **能看懂的"危险倒计时"**：Rocket「充能 → 激光 → 休整(Sleep)」、Waterfall Giant「即将爆炸(Stun) → 爆炸」。

山神的现状：

| 配方 | 山神现状 | 差距 |
|---|---|---|
| 专属资源 | 只有通用力量成长 +2/+3；「封印」「老化」只是被动说明 | **缺一个只属于山神、玩家能看懂也能对抗的计数器** |
| 状态牌 | 无（偷牌是拿走牌，不是塞牌） | 缺 |
| 独有动作 | 8 个意图对应约 6 套动作；格挡/成长、苏醒预兆、手臂眩晕、破爪、偷牌持握都没有专属动作 | 见第 4 节 |
| 危险倒计时 | 抓取 → 重摔有了（很好）；暴露期第 3 回合「苏醒预兆」只有意图，画面上没有 | 缺画面预告 |
| 开场 | `arrive`（8.6s，带 `left_destroy/right_destroy` 事件）已经做好，但**从没被调用** | 白白浪费了 |

数值方面：P1 核心 130/140、手臂 50/55，P2 200/215 / 80/90，四招一轮 +2/+3 力量，和帝王蟹/知识恶魔在同一档，**不建议大改**。真正的风险是战斗时长：暴露期 3 回合，外加每次苏醒都成长。

---

## 3. 创新机制提案（全部用原版的积木，不引入新类型系统）

按"性价比 / 原版味"排序。

### ★ 提案 A：「晶脉」——山神的专属资源（推荐首选）
- **来源**：美术本身就是背上 + 拳上的晶簇（蓝 → 红熔岩），天然就是计量表。
- **规则**：躯干持有 `晶脉 N`（Counter 能力，初始 0）。每次**普通招式结算后 +1**，**满 4 层时下一招替换为「晶簇崩发」**（全体攻击 + 给每位玩家塞 2 张「碎晶」状态牌），然后清零。**击倒一条手臂会移除 2 层**。
- **作用**：把"断臂"从单纯的输出窗口变成"打断危险技能的节奏"，和 Ceremonial Beast 打断「犁」、Waterfall Giant 压蒸汽是同一种玩法。同时取代现在「每 4 招固定 +力量」这种玩家看不见的时钟，意图栏会直接显示层数。
- **碎晶**（状态牌，原版风格）：不能打出；回合结束时如果还在手里，受到 2 点伤害；可以被消耗。玩法上类似原版的 Burn/Wound，但带岩石主题。
- **动画**：晶簇槽位的 rgba 脉冲（层数越高越亮）+ 新动作 `crystal_burst`。

### 提案 B：「崩落裂痕」——奖励暴露期爆发输出
- 核心暴露期显示计数器 `裂痕 X/阈值`（例如 25/30，按人数缩放）。3 回合内对核心打满阈值 → 苏醒时**不获得成长**，并掉落 1 张「岩石铠甲」。
- 这样就解决了平衡审查里写的"苏醒成长是否过快"：成长变成了**玩家可以争取避免**的东西，而不是固定惩罚。原版 Vantom / Knowledge Demon 也是"打够阈值换收益"的设计。

### 提案 C：「岩中淬炼」——偷牌的正向反转
- 现在是：横扫偷走 1 张牌，击倒手臂后还回来（沿用原版 Thieving Hopper 的做法）。
- 改为：击倒**握着这张牌的那条手臂**时，这张牌**升级后**返回手牌（战斗内有效）。这样偷牌就从纯粹的负面变成"去救回来还能变强"，而且会影响玩家先打哪条手臂。

### 提案 D：P2 熔岩化
- `P2_CENTRAL_SLAM` 追加：往弃牌堆塞 2 张灼伤（原版 `Burn`，参照 TestSubject 的「灼烧咆哮」）。意图改成攻击 + 状态。
- P2 的「磐石守势」改成「熔岩外壳」：双臂获得格挡；在格挡被打破之前，攻击手臂会受到 3 点反伤（原版 Thorns 语义）。

### 提案 E：开场 & 命名
- 开场播放现成的 `arrive`（1.5 倍速约 5.7s，`left_destroy/right_destroy` 事件接碎石特效），第一回合给一个「苏醒」Buff 意图（参照 Lagavulin）。
- 名称统一：遭遇名 / 躯干名 / 旧的「活体巨岩」统一改成**山神**（或「洞穴之神」）；「老化」（其实是给玩家发岩石铠甲）改名为「**风化剥落**」更贴切。

> 建议组合：**A + B + P0 修复** 作为下一版；C/D/E 视时间追加。

---

## 4. 骨骼动画审查

### 4.1 资产现状
- Spine 4.2.43，**27 根骨骼、34 个槽位、无网格变形**（刚体切片），双调色板靠槽位切 attachment（`*_red`）。2 个 IK（手臂）；**没有使用 4.2 的 physics 约束**。
- 共 52 个动画；代码实际用到约 36 个。
- **全部是逐帧烘焙的线性关键帧**：0 条贝塞尔曲线，单条时间线最多 568 个 key。`.spjson` 有 12.9 MB，几乎没法在 Spine 编辑器里手改。
- PCK 同时打包了 `.skel`、`.spskel`、`.spjson`（场景只用 `.spjson`），**多带了约 4.5 MB 冗余**。`.bak` 文件没有被打包（这点没问题）。

### 4.2 已有但未使用的动作（零成本收益）
| 动画 | 时长 | 建议用途 |
|---|---|---|
| `arrive` / `arrive_angry` | 8.6s | 开场入场（提案 E） |
| `earthquake` | 4.33s（3 个 `earthquake_02` 事件） | 提案 A 的「晶簇崩发」或新的地震招式 |
| `leftpunch` / `rightpunch` | 4.7s（`gift_begin/gift_end` 事件） | 映射表里有，但从没被调用 → 可以做暴露期另一只手的"重拳"变体，让手臂的弱攻击动作不止一套 |
| `main_01(_angry)`、`main_01_left_to_right` 等 | 5–10s | 长 idle 变体：idle 播 N 轮后随机插入一次，缓解重复感 |
| `main_happy` | 8s | 玩家全灭 / 胜利嘲讽（原版 Boss 的 victory 反应） |

### 4.3 建议新增的动作（按优先级）
| 优先级 | 动作名 | 用于 | 说明 |
|---|---|---|---|
| ★★★ | `mountain_guard` / `_angry` | 磐石守势（格挡 + 成长） | 双拳砸地撑起、晶簇亮起、胸口鼓起。解决和巨拳夹击撞动画的问题 |
| ★★★ | `reactions/hurt_body`（只驱动 body/head/beard） | 所有受击 | **仿照帝王蟹的 reactions 轨道**：只 key 躯干，叠在任何招式上面。这样抓取时也能有受击反馈，不用再关掉 hit_recoil |
| ★★★ | `weak_waking_left/right` | 暴露期第 3 回合「苏醒预兆」 | 晶簇逐渐复燃、断臂抽动，给出画面倒计时（参照 Rocket 的 charge、Lagavulin 醒来） |
| ★★ | `arm_stun_left/right`（loop） | 原生眩晕 / 破爪后的 EscapeStun | 手臂瘫软摇晃；现在这种情况直接回 idle |
| ★★ | `grab_break_left/right` | 石爪被击碎 | 手掌被震开、碎石飞溅、玩家掉落；现在只靠代码补间 |
| ★★ | `crystal_burst` / `_angry` | 提案 A | 晶簇蓄能 → 爆发，可以复用 `earthquake` 的下半段 |
| ★★ | `idle_hold_card_left/right`（叠加轨道） | 偷牌之后 | 握拳持牌，替代现在代码挂在 Marker 上的卡牌 |
| ★ | `crush_double`（两次撞击，2 个 `central_hit` 事件） | 巨拳夹击 | 和 2 段意图对齐 |
| ★ | `intro_roar` | P2 转阶段结尾 | `main_angry` 以 1.5 倍速播放时结尾偏平，可以补一个更短、更有力的收尾 |

### 4.4 技术优化
1. **打击帧对齐**：以 Spine 事件时间为唯一来源。建议在 `verify` 里加一条检查：从 `.spjson` 读取 `central_hit` 时间，和 C# 里的 `Cmd.Wait` 常量比较，误差超过 ±0.05s 就报失败。结算继续用 `Cmd.Wait`（保证联机 / headless 结果一致），只是常量要对齐。
2. **关键帧精简**：把烘焙的逐帧 key 拟合成贝塞尔曲线（误差 < 0.5px / 0.2°），预计 `.spjson` 能从 12.9 MB 降到 1–2 MB，也能回到编辑器里修改。精简前后要逐帧渲染比对。
3. **Spine 4.2 physics**：给胡须三段（beard1-3）和晶簇加 physics 约束，自动获得次级运动，不用再手 key。
4. **多轨道拆分**（参照帝王蟹：body / left / right / reactions 四条轨道）：可以同时"左手攻击 + 右手 idle"，"持牌握拳"也可以用叠加轨道实现。这是工作量最大、收益也最大的一项。
5. 导出过滤器去掉冗余的 `.skel` / `.spskel`（先确认代码里确实没有地方引用它们）。

---

## 5. 建议的下一步（等你确认后再做）

1. **P0 修复包**：本地化键对齐 + 修正校验正则；打击帧对齐；背景场景 z-order 修正（让构建恢复）；给磐石守势换动作。
2. **机制包**：提案 A「晶脉」+ 提案 B「崩落裂痕」（新增 2 个能力 + 1 张状态牌 + 本地化 + 行为探针）。
3. **动画包**：优先做 ★★★ 这三个（`mountain_guard`、`reactions/hurt_body`、`weak_waking`），接入已有的 `arrive` / `leftpunch`；每个动作都附联系表 / GIF 供你审阅。

所有改动之前都会先备份到 `build/cavegod-review-20260929/baseline/`，只修改活体巨岩（cave_god）相关文件。

---

## 实施记录（2026-09-29，第二阶段：修 bug + A + B + 统一名称）

备份：`build/cavegod-review-20260929/baseline/`（19 个被修改文件的原件，保持相对路径）。

### 已完成
- **P0-1 本地化键**：手臂 MoveState id 改为与本地化键一致的 `REST / DOWN_STATE / FRONT_SWEEP / GRAB_PLAYER / AIR_SLAM / WEAK_STUN / WEAK_ATTACK / RECOVER / GRAB_STUNNED`（`ThingsCaveGodHand.MoveId(Action)`）；补齐核心缺失的 `P1_REST_SWEEP / P2_REST_GRAB / P2_REST_SLAM`；删除无引用的 `THINGS_CAVE_GOD.*` 与 `*_FALLBACK`、`WEAK_*_1/2/3` 陈旧键。
- **P0-2 打击帧**：新增 `Visuals/CaveGodAnimTiming.cs` 作为唯一时间来源。横扫 0.90→1.35s（总长仍 3.45s），重砸 1.98→1.88s；连拳/夹击改用命名常量。夹击双段与抓取 1.15s 未改（见"未做"）。
- **P0-3 z-order**：背景 tscn 删除 3 处 `z_index`，改由 `_Ready`/`ResetVisualState` 用常量设置，渲染层级不变。
- **提案 A 晶脉**：`ThingsCaveGodCrystalVeinPower`（真实层数在 `ThingsCaveGodBody.CrystalVein`，双臂镜像显示）。每完成一个循环招式 +1；满 4 层后插入 `CRYSTAL_BURST` 晶簇崩发（全体攻击 P1 12/14、P2 15/17，每名玩家弃牌堆 +2 张碎晶，然后 +2/+3 力量），再回到被插队的循环位置。击倒手臂 -2 并取消待发的崩发；转阶段清零。磐石守势、狂暴崩山不再附带成长（BuffIntent 已移除），但仍负责交换主攻手。
- **碎晶**：`ThingsCaveGodCrystalShard`，1 费、消耗；回合结束留在手中受 2 点伤害；卡图复用原版 Debris。
- **提案 B 崩落裂痕**：`ThingsCaveGodFissurePower`（挂核心，层数 = 剩余所需伤害，最大生命 25% 向上取整）。归零即裂痕贯通：当场把苏醒意图换成 `FISSURE_RECOVER`（仅回血、无强化），苏醒时不成长并清空晶脉。**与原报告不同**：不再给玩家岩石铠甲，奖励改为"取消成长 + 清空晶脉"，与 A 形成联动。
- **统一名称**：显示名改为「活体巨岩 / 巨岩左臂 / 巨岩右臂」（Living Megalith / Megalith Left Arm / Megalith Right Arm）；类名、ModelId、配置键、资源路径均未改。代码注释与 CONTEXT.md 同步。
- **顺手修复**：`ToMutable()` 是 MemberwiseClone，手臂的 `_stolenCards` 列表原本被所有实例（含 canonical）共享，未释放的被偷卡可能跨战斗/跨局残留；已用 `DeepCloneFields` 修复（Body 新增的查表同理）。
- **图标**：两个新能力的 256px/64px 图标 + 图集 tres（PIL 绘制，扁平粗描边风格）。
- **校验**：`verify_project.py` 新增 `verify_cave_god_contract`：移动键覆盖/陈旧键/遗留键、显示名、新能力与卡牌本地化、图标尺寸、卡池注册、打击帧常量对照 spjson 事件（±0.05s）、禁止硬编码打击等待。已用原始文件做反向测试，能报出全部原问题。
- **探针**：更新循环/成长相关断言；新增晶脉与崩发、断臂抽晶脉、崩落裂痕（两种时机）4 组测试。

### 验证（均在用户 PC 实际执行）
- `scripts/verify-cavegod.ps1 -OutputDirectory build/cavegod-review-20260929`：Release 构建 0 警告，探针构建通过，headless 行为探针 **PASS**（25 组）。
- `python scripts/verify_project.py`：**PASS**（此前唯一失败的 z-order 已消除）。
- Godot 4.5.1 headless import + export-pack 到 `build/cavegod-review-20260929/test.pck`：成功，新资源与本地化键均在包内；`verify_project.py --pck` **PASS**。

### 未做 / 需要你决定
- 未进游戏实测；未安装；未替换 `build/v111`；未提交 git；未改版本号（玩法变更，联机前建议升版本）。
- 晶簇崩发暂复用 `central_slam` 动作 + 晶光着色/碎石特效，专属动画留到动画包。
- 夹击 2 段伤害 vs 动画 1 个打击事件、抓取 1.15s vs 事件 1.10s（差 0.05s）未改。
- 数值未经实战：成长由每 4 回合变为约每 5 回合一次，外加一次全体伤害和碎晶。
