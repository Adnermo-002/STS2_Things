# STS2_Things v1.3.2 — V108 怪物全链路原生化

日期：2026-07-14
目标：Slay the Spire 2 `v0.108.0` / commit `58694f64`

## 结论

旧实现把模型登记、Act 遭遇池、怪物视觉、Boss 背景、控制台补全和房间退出音频清理集中在 `MonsterRegistrar`，并全局 Patch `MonsterModel.CreateVisuals`、反射写入 `NCreatureVisuals._body`、替换 `NCombatRoom` 背景容器。这不符合 V108 的原生职责边界，也绕过资源预加载合同。

v1.3.2 删除该注册中心，并在原生链路上补齐首回合阶段切换、槽位占用和多人缩放合同：

```text
ModManager 加载 DLL/PCK
  → ModelDb 自动发现 MonsterModel / EncounterModel
  → Act.GenerateAllEncounters 窄 Postfix 追加 canonical EncounterModel
  → EncounterModel.GenerateMonsters 产生 mutable MonsterModel + slot
  → EncounterModel.GetAssetPaths 预加载背景、遭遇场景、怪物视觉和动态随从
  → MonsterModel.CreateVisuals 按 VisualsPath 实例化 NCreatureVisuals 场景
  → NCombatRoom 按 EncounterModel.Slots/Marker2D 定位怪物
```

## 已正常化的环节

### 1. 模型发现与 Act 候选池

- 所有具体 `MonsterModel`、`EncounterModel` 仅依赖 V108 `ModelDb.Init()` 自动发现，不再手工登记。
- 新增 `Hooks/MonsterContentPatches.cs`，只 Patch 原版没有公共注册 API 的：
  - `Overgrowth/Underdocks/Hive.GenerateAllEncounters()`
  - 三个 Act 的 `BossDiscoveryOrder` getter
- Postfix 追加 canonical `ModelDb.Encounter<T>()`，保留原版前缀，并用官方 `ContentSorter<ModelId>` 排序 Mod 后缀。
- 删除多余的 `FightConsoleCmd` 补丁；V108 原版已从 `ModelDb.AllEncounters` 生成完整补全列表。

### 2. Godot 怪物视觉

- 删除全局 `MonsterModel.CreateVisuals` 视觉替换、隐藏 fallback 节点和 `_body` 私有字段反射。
- 为所有使用自有 PNG 的怪物建立原生 `res://scenes/creature_visuals/<model_id>.tscn`。
- 每个场景完整提供 `%Visuals`、`%Bounds`、`%CenterPos`、`%IntentPos`。
- `NThingsCreatureVisuals` 仅作为 `NCreatureVisuals` 的 Godot C# ScriptPath，不接管游戏生命周期。
- `OriginEyeWithTeeth` 复用原版 EyeWithTeeth Spine 场景，并通过 `MonsterModel.SetupSkins` 的原生虚方法完成紫色调制，不再依赖全局 Postfix。
- `SoulRoe` 三种视觉变体由同步的起始阶段选择，全部进入 `AssetPaths`。

### 3. 原生 Boss 背景

四个 Boss Encounter 均改为 `HasCustomBackground => true`，使用 V108 `BackgroundAssets` 目录合同：

```text
scenes/backgrounds/<encounter_id>/<encounter_id>_background.tscn
scenes/backgrounds/<encounter_id>/layers/<encounter_id>_bg_00_a.tscn
scenes/backgrounds/<encounter_id>/layers/<encounter_id>_fg_a.tscn
```

背景选择、资源预加载、层挂载和清理由 `EncounterModel.CreateBackground()` / `NCombatBackground` 完成，不再清空 `NCombatRoom.BgContainer` 或维护全局前景引用。

#### 打包后的背景合同

仅验证源目录中的 TSCN 不足以覆盖实际运行。Godot 文本资源二进制转换曾在
PCK 内生成 `.tscn.remap`；V108 `BackgroundAssets` 枚举背景目录后会把这些
映射项带入加载流程，导致背景场景加载失败并抛出 `AssetLoadException`。

当前处理为：

- `project.godot` 与 `export_presets.cfg` 固定
  `export/convert_text_resources_to_binary=false`；
- `scripts/verify_pck.gd` 挂载最终导出的 PCK，而不是读取源工程；
- 对四套 Boss 背景逐目录确认只暴露可加载的 `.tscn`；
- 最终 PCK 中禁止出现 `.tscn.remap`。

### 4. 槽位与动态召唤

- Encounter 的 `Slots` 与 TSCN `Marker2D` 现在严格一一对应。
- 删除 Origin Fogmog 场景中两个未声明的幻象槽位。
- Origin Fogmog 的开场招式是 `ILLUSION_MOVE`。若第一回合在该招式执行前被打到半血，
  `CreatureCmd.Stun` 会替换尚未执行的开场招式；v1.3.2 会先读取同步的
  `NextMove.StateId`，让强制 `STUNNED` 回调一次补足 2 只
  `OriginEyeWithTeeth`，同时保留“开场 1 只 + 二阶段 1 只”的设计结果。
- 正常路径仍是开场召唤 1 只 Eye，之后半血转阶段再召唤第 2 只，不会额外增殖。
- Origin Eye 即使已经 0 HP，只要 `IllusionPower` 仍在排队处理复活，就继续占用原槽位；
  只有该实体完全不在 `CombatState.Enemies` 中时槽位才释放，防止复活 Eye 与新 Eye
  在同一 Marker2D 重叠。Soul Roes 的死亡补位波则按其独立合同只让存活鱼子占槽。
- Soul Roes 正式声明 8 个小鱼籽槽位，与生成逻辑及场景一致；越界索引会失败而不是进入缺失节点。
- 动态生成上限按可用槽位钳制。
- 召唤者按原版 Queen 模式通过 `AssetPaths` 预加载全部潜在随从：
  - Origin Fogmog → Origin Eye With Teeth
  - Soul Roes → Soul Roe 三种视觉
  - Bowlbug Progenitor → 四种 Bowlbug
- Origin Eye 的 `IllusionPower` 会原生追加 `MinionPower`；两者的图标都由
  Origin Fogmog 的战斗资源集显式预加载，避免动态召唤时出现 cache miss。

### 5. 图鉴、地图与历史

- 修正全部怪物招式本地化键：V108 图鉴会先移除状态 ID 的 `_MOVE` 后缀再查询。
- 补齐 Origin Fogmog 的 `TRIPLE`、`HEAL` 与 Origin Eye 的复苏眩晕名称。
- 删除 Legacy 旧的 `ECHO1/ECHO2/BLOOD1/BLOOD2` 键并匹配当前状态机。
- Boss 地图图标继续通过 `BossNodePath` 原生加载；四个 Boss 的 run-history 正/描边图均进入 `ExtraAssetPaths`。
- Act `AllMonsters` 由已注入 Encounter 的 `AllPossibleMonsters` 自动覆盖自定义 Boss、精英、普通怪和动态随从。

### 6. 生命周期与多人

- 房间退出音频清理拆到独立 `CombatRoomAudioCleanupPatch`，不再属于注册层。
- 候选池只含 canonical 模型，最终顺序稳定；不使用 unordered collection、进程随机哈希或 Godot 全局 RNG 决定玩法。
- 动态召唤继续使用 Encounter RNG / Monster AI RNG、原生 `CreatureCmd.Add` 和同步槽位。
- Origin Fogmog、Bowlbug Progenitor 与 Scale Beetle 的敌方招式格挡
  只传基础值并保留 `ValueProp.Move`，由 V108 `MultiplayerScalingModel` 缩放一次；
  不再手工预乘玩家数。Bowlbug 的基础格挡为 `20`/`16`，Scale Beetle 的 Molt
  基础格挡为 `14`。
- The Legacy 修改硬化外壳时先以整数除法计算目标层数，再把整数差值交给
  `PowerCmd.ModifyAmount`；因此 HP/4 等阶段严格取下整，不会因 decimal 偏移截断而多 1 层。

## 自动回归

`scripts/verify_project.py` 现在额外检查：

- 禁止 `MonsterRegistrar` 和 fallback 视觉；
- 8 个自有怪物视觉场景及四个必需 unique node；
- 5 个 Encounter 的 Slots 与 Marker2D 精确一致；
- 4 个 Boss 的原生背景目录与层；
- 所有 `MoveState` 的 eng/zhs 图鉴键及陈旧键；
- Act Encounter catalog 完整性；
- 所有动态召唤候选的 `AssetPaths` 预加载合同。
- Origin 首回合 `ILLUSION_MOVE` 被半血眩晕覆盖时的双 Eye 回调，以及复活 Eye
  保留槽位的合同；
- 四类敌方招式格挡只走一次原生多人缩放，以及 The Legacy 外壳整数除法合同。

此外，`scripts/verify_pck.gd` 挂载最终 PCK，单独检查四套 Boss 背景目录、
场景可加载性与 `.remap` 禁止项。

## 单人实机回归

`fight` 只在已经进入 Run 后具有完整战斗上下文。测试统一从主界面选择
“单人游戏”，选择角色并开始游戏，至少推进到涅奥遗物选择阶段，再打开开发
控制台执行 `fight <ENCOUNTER_ID>`。最新安装日志确认
`Version=1.3.2.0`、`Loaded 1 mods (1 total)`。

| 遭遇 | 已验证结果 | 状态 |
|---|---|---|
| Origin Fogmog | `235` HP；开场 `ILLUSION_MOVE` 执行前使用 `damage 118 1`，在 `117` HP 精确触发二阶段并进入 `STUNNED`，同一眩晕回合一次生成两只 `9/9` `OriginEyeWithTeeth`，`kill all` 明确列出两只 Eye；正常路径则先生成 1 只、半血后再生成第 2 只；Eye 死亡进入 `REVIVE_MOVE` 后恢复为 `9/9`，复活等待期间保留原槽位；再次击杀令玩家能量由 `3/3` 变为 `4/3` | 通过 |
| Scale Beetle | 自定义背景正常显示，Boss 为 `200/200`；击杀后进入标准胜利流程 | 通过 |
| Soul Roes | 父体死亡补 6 只、存活至第 4 回合后的精确 8 只，以及范围伤害同批死亡后的 6 只补位波均通过 | 通过 |
| The Legacy | 自定义背景正常显示，Boss 为 `285` HP；初始死亡律动 `2`、硬化外壳 `95`；状态按 `EXHAUST → ECHO → BLOOD → STRENGTHEN` 推进；首次强化获得 Artifact `1` | 通过 |
| Bowlbug Progenitor | Boss 为 `260` HP，伤害计数阈值 `52`；首回合生成 `14` HP 的 `BOWLBUG_EGG`；清除子体后按 `DISRUPT → RALLY` 推进；Rally 复用死亡槽位生成下一种 `25/25` Bowlbug，Boss 与子体均获得力量 `3` | 通过 |

### Soul Roes 边界证据

两局均观察到招式顺序
`BECKON_STR → MULTI6 → MULTI4_INT → SPAWN`：

1. 父体存活至第 4 回合并先生成 2 只 Soul Roe；执行 `kill 0` 后补充 6 只，
   `kill all` 明确列出 8 个 `SOUL_ROE`。
2. 另一局在第 4 回合生成 2 只后执行 `damage 999`，父体与两只子体在同批
   伤害中死亡。战斗没有提前结束，随后补充 6 只处于眩晕状态的 Soul Roe；
   `kill all` 明确列出 6 个 `SOUL_ROE`，并正常进入胜利流程。

四套 Boss 背景均已在实际游戏中显示。上述运行日志未出现
`AssetLoadException`、`.tscn.remap`、音乐缺失、脚本/资源缺失或无效转换。
日志中出现过一次 Godot `ERROR: Unable to open clipboard.`，来自剪贴板访问，
与本 Mod 的怪物、召唤或战斗链路无关。

## 双人 fastmp 回归

- 主机和客户端均只加载 `STS2_Things 1.3.2`，ModelId cache 均为
  `1693` entries / hash `296163847`，Custom lobby 握手成功。
- 最终安装产物通过网络化控制台进入 Origin Fogmog，`damage 300` 后双端 Boss
  均为 `217/517` 并同步进入 `STUNNED`。
- 双方结束回合后，主机和客户端都在两个不同槽位显示两只 `19/19`
  `OriginEyeWithTeeth`；checksum 上下文 id `0–7` 的顺序一致，未记录
  mismatch/desync。
- 本轮最终产物日志未再出现 `images/powers/minion_power.png` cache miss。
