# STS2_Things v1.3.2 — V108 审计与优化记录

日期：2026-07-14
目标游戏：Slay the Spire 2 `v0.108.0` / commit `58694f64`
工程：Godot `4.5.1 Mono`、`.NET 9`、C# 13
依赖边界：仅原生 STS2 API、Godot 与 Harmony；不使用 RitsuLib/BaseLib。

## 结论

本轮完成了代码、资源、构建链和多人确定性审计。已修复已确认的共享玩法异步顺序问题、跨 Mod 加载顺序问题及多个 checksum 状态盲区，并把工程提升为 Nullable/警告全严格构建。

## 已修复的多人确定性问题

1. **SavedProperty net ID 提前注入**
   - 删除初始化器中的六次 `SavedPropertiesTypeCache.InjectTypeIntoCache`。
   - V108 会在 `AssemblyInfo.Init → ModelDb.Init → SavedPropertiesTypeCache.Init` 中使用官方 `ContentSorter` 扫描并排序所有 Mod 模型。提前注入会绕过该排序，并可能在联机双方 Mod 加载顺序不同的情况下映射出不同的属性 net ID。

2. **死亡回能 Task 未等待**
   - `OriginGainEnergyPower.AfterDeath` 改为逐玩家、稳定顺序 `await PlayerCmd.GainEnergy`。
   - 避免异步能量 Hook 尚未完成，死亡 Hook 已返回并进入后续 action/checksum。

3. **候选列表依赖加载/容器顺序**
   - Encounter 注册从 `HashSet<Type>` 改为显式去重的 `List<Type>`，注入前按 `ModelId` 和完整类型名排序。
   - 对原版 Card/Relic/Potion 池的 Mod 贡献使用 V108 官方 `ContentSorter<ModelId>` 排序；原版内容顺序保持不变。
   - Act Event、Encounter、BossDiscoveryOrder 的 Mod 后缀同样在最低 Harmony 优先级统一排序。
   - 贴图变体由 `ModelId + SlotName` 的确定性哈希选择，不再使用进程随机数。

4. **Recall 抽牌合同与 RNG 流**
   - 弃牌堆随机选择改用 `CombatCardSelection`，不再污染 `CombatCardGeneration`。
   - 补齐 `Hook.ShouldDraw`、阻止抽牌回调、`Math.Ceiling`、战斗结束/手牌上限、抽牌 History、`Hook.AfterCardDrawn`、`InvokeDrawn` 与标准抽牌音效。

5. **跨动作状态未进入 checksum**
   - `OriginPower.Amount` 直接保存同步的“半血阶段阈值”，阶段触发改为比较当前 HP；不再累计未格挡伤害，因此治疗不会造成提前转阶段。
   - 新增隐藏 `BowlbugSequencePower`，以 Amount 保存下一只盛碗虫索引。
   - 新增隐藏 `LegacyProgressPower`，以 Amount 保存腐化之遗下一次强化阶段。
   - `BowlbugProgenitorPower` 的重置阈值由同步的 `Owner.MaxHp` 重建，不再依赖实例字段。

6. **敌方招式格挡被重复按玩家数缩放**
   - V108 `MultiplayerScalingModel` 会自动缩放带 `ValueProp.Move` 的敌方招式格挡；
     Origin Fogmog、Bowlbug Progenitor 与 Scale Beetle 不再先手工预乘玩家数。
   - Bowlbug Progenitor 的基础格挡固定为 `20`/`16`，Scale Beetle Molt 固定为 `14`，
     然后只走一次原生多人缩放；`verify_project.py` 同时禁止再次引入“玩家数 × 基础值”。

## 玩法与 API 合同修复

- 删除始源雾菇动态召唤后对 `IllusionPower` 的重复施加。
- `REVIVE_MOVE` Harmony Prefix 只作用于 `OriginEyeWithTeeth`，不再改变所有原版/其他 Mod 怪物。
- 劫掠者召唤删除反射和永远从 0 开始的实例计数器，改用同步 `MonsterAi` RNG 和原生 `CreatureCmd.Add`。
- `ScaleDownPower` 的伤害倍率下限钳制为 0，避免层数超过 100 后出现负伤害。
- `SoulfyshDisease` 与 `ReusePower` 生成卡牌改走 `AddGeneratedCardToCombat`，进入标准生成卡历史。
- `SoulfyshDisease` 使用 `BeckonCount.IntValue`，移除重复的升级数值分支。
- `Reuse` 将真实 `PlayerChoiceContext` 继续传给 Power 应用；`ScaleBeetlePower` 同样传递 Hook 收到的 context。
- `PackUp` 的普通抽牌不再错误标记为回合初始手牌抽取。
- `Surrender` 强制切换目标意图，避免不可转换状态令卡牌静默失效。
- 假商人战斗的 HP 修改改走 `CreatureCmd.SetMaxAndCurrentHp`。
- 初始化失败记录完整异常后重新抛出；增加重复初始化保护并移除未启用的全局强制 Boss Patch。
- `SoulRoesPower` 扫描完整 8 槽，以独立计数生成 6 只鱼子；0 HP 待处理怪物不再占用槽位，避免 AOE 死亡链漏召唤。
- Origin 半血阶段和 Eye 复活的必要状态转换使用仅限本 Mod 模型/状态的强制转换，已有眩晕不再吞掉一次性阶段。
- 若 Origin Fogmog 在第一回合开场 `ILLUSION_MOVE` 执行前到达半血，
  `CreatureCmd.Stun` 会替换待执行招式；现在先检查同步的 `NextMove.StateId`，
  在强制 `STUNNED` 回调中一次生成 2 只 Eye，保留被打断的开场召唤与二阶段召唤。
- Origin Eye 的槽位合同与死亡补位怪不同：0 HP 但等待 `IllusionPower` 复活的 Eye
  仍占用原槽，避免新 Eye 与复活 Eye 重叠；Soul Roes 与 Bowlbug 的补位逻辑则只让
  存活实体占槽，AOE 中 0 HP 待处理实体不会阻塞补位。
- 补齐 Origin Eye 经 `IllusionPower` 间接获得的 `MinionPower` 图标预加载，清除动态
  召唤阶段的 `images/powers/minion_power.png` cache miss。
- The Legacy 修改硬化外壳时先执行整数 `MaxHp / divisor`，再将整数目标差值传给
  `PowerCmd.ModifyAmount`；HP/4 等阶段严格取下整，不再因 decimal 偏移截断而多 1 层。
- Bowlbug 休息招式移除错误的 Buff 意图。
- SoulRoe 高进阶生命区间修正为高于普通进阶。

## 音频、资源与本地化

- 统一死亡音效路径：正常 Spine 死亡由 `SfxCmd.PlayDeath` 替换，无 Spine 时才由 `StartDeathAnim` 兜底，避免重复播放。
- 删除按 Model Entry 的跨实例死亡音效去重状态，避免同类多怪或复活后死亡被误抑制。
- 音频路径尊重 `NonInteractiveMode`/战斗结束状态；线性音量正确转换为 dB。
- 无 Spine 的 Sprite2D 怪物在原生死亡生命周期中补调 `SfxCmd.PlayDeath`；最后一只敌人令战斗进入 ending 后仍可播放死亡音效。
- 修复 Origin Boss 的 FMOD 参数为 `the_kin_progress`，并将自定义怪物复用音效约束为 V108 已存在事件。
- 本地音频变体使用独立 Godot RNG，不触碰玩法 RNG。
- 修正资源名：`scale_beetle_boss_icon*.png`、`almond_water.tres`。
- 修正 `LEGACY_BEAT_OF_DEATH_POWER.*` 本地化键。
- eng/zhs 新增隐藏同步 Power 的完整本地化，键集合保持一致。
- 删除旧嵌套 `STS2_Things/.godot` 缓存并用 Godot 4.5.1 重新导入改名资源。

## 工程质量

- `<Nullable>enable</Nullable>`。
- `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`。
- 清零全工程 Nullable/编译警告。
- 具体模型设为 `sealed`；移除无用反射、死字段和无 `await` 的 async 方法。
- 新增 `scripts/verify_project.py`，检查版本一致性、严格编译设置、禁用 RNG/API、SavedProperty 提前注入、本地化键一致性、关键资源和旧缓存。
- Mod 版本提升到 `1.3.2`；共享玩法合同变化不再与旧 DLL 复用同一联机版本号。

## 构建与 PCK 运行时合同

- `scripts/build.ps1` 的 Godot 导出增加 `--editor`，消除 Godot 4.5.1 在
  PCK 已成功导出后产生的 `_EDITOR_GET` 假错误。
- Boss 背景加载故障定位为导出阶段生成的 `.tscn.remap`：源工程场景可加载，
  但 V108 `BackgroundAssets` 枚举最终 PCK 目录后会遇到映射项并加载失败。
- `project.godot` 与 `export_presets.cfg` 均禁用文本资源二进制转换；最终 PCK
  不含 `.tscn.remap`。
- `scripts/verify_pck.gd` 直接挂载发布 PCK，验证四套 Boss 背景目录只包含
  可加载的 `.tscn`。这项检查现在是构建门禁，而不是仅检查源文件存在。

## 验证范围

自动验证包括：

- 源码静态回归检查；
- Release clean build，0 warning / 0 error；
- Godot 4.5.1 资源导入与 PCK 导出；
- `validate_mod.py --require-artifacts`；
- JSON/TRES/TSCN 引用与 eng/zhs 键集合检查；
- 最终 PCK 挂载、四套 Boss 背景运行时合同与 `.tscn.remap` 禁止项；
- PCK 内容清单和安装三件套哈希比对；
- 实际游戏加载日志、三个 Act 遭遇注入及 Harmony/资源/本地化错误检查。

最新严格构建结果：

- `STS2_Things source audit: PASS`；
- `STS2_Things FMOD audit: PASS`；
- Release：0 warnings / 0 errors；
- `STS2_Things PCK runtime background contract: PASS`；
- `validate_mod.py`：0 errors / 0 warnings。

最新安装三件套 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `STS2_Things.dll` | `1C494F2148090BFDF07573A42A6E56C062B10F5557AD7640284023083F20C058` |
| `STS2_Things.json` | `7DE0D29CB104E5578AA96238600E881D19390363CAF81711A88532A385343208` |
| `STS2_Things.pck` | `21833FDA4BE1B04E9038C77F93D77B494B74182AFAF2803D6240536B1EB6EB93` |

## 实际游戏验证

最新启动日志确认 `Version=1.3.2.0`、`Loaded 1 mods (1 total)`。测试按正式
界面流程进入：主界面选择单人游戏、选择角色、开始游戏并至少到达涅奥遗物
选择阶段，然后才使用原版 `fight` 命令。

- Origin Fogmog：开场招式执行前以 `damage 118 1` 压到 `117/235` 后直接进入
  `STUNNED`，同一眩晕回合生成两只 `9/9` Eye；`kill all` 明确列出两只
  `ORIGIN_EYE_WITH_TEETH`。正常路径仍是开场 1 只、之后半血再生成第 2 只；
  Eye 复活与死亡回能也通过。
- Scale Beetle：自定义背景、`200/200` HP 与标准胜利流程通过。
- Soul Roes：招式按 `BECKON_STR → MULTI6 → MULTI4_INT → SPAWN` 推进；
  第 4 回合先生成 2 只后杀死父体，补位波令 `kill all` 精确列出 8 只；另一局
  以 `damage 999` 同批杀死父体与两只子体后，战斗未提前结束，补充 6 只眩晕
  Soul Roe，随后 `kill all` 列出 6 只并正常胜利。
- The Legacy：背景、初始 Power、四段状态机与首次 Artifact 强化通过。
- Bowlbug Progenitor：蛋生成、死亡槽位复用、Rally 召唤及双方力量增益通过。

四套 Boss 背景均已实际显示；日志未出现 `AssetLoadException`、
`.tscn.remap`、音乐缺失、脚本/资源缺失或无效转换。逐步数值与状态证据见
`docs/MONSTER_PIPELINE_V108.md`。

日志另有一次 Godot `ERROR: Unable to open clipboard.`，属于剪贴板访问错误，
不在本 Mod 的怪物、召唤或战斗执行链内。

## V108 的已知边界

V108 正式界面仍拒绝加入进行中的 Run，测试界面的 rejoin 路径也尚未实现。因此，隐藏 Power 加固解决的是当前 replay/checksum 状态盲区并为未来重连准备，而不是宣称已经复现了正式版“运行中重连”问题。

### fastmp 最终证据

- 主机与客户端均只加载 `STS2_Things 1.3.2`；双方 ModelId cache 均为
  `1693` entries、hash `296163847`，Custom lobby 握手通过。
- 固定 seed `STS2THINGS108MP` 的 v1.3.2 回归已让网络化 `fight` 与半血伤害动作
  在双端执行，并生成相同的 checksum 上下文。
- 对最终安装 DLL `1C494F…C058` 再做精确产物双端回归：网络化
  `fight ORIGIN_FOGMOG_BOSS_ENCOUNTER` 后以 `damage 300` 把多人 Boss 压到
  `217/517`，双方都进入 `STUNNED`；敌方回合后主机和客户端均显示两只
  `19/19` Origin Eye。两端 checksum 上下文 id `0–7` 顺序一致，日志没有
  mismatch/desync，也没有 `minion_power.png` cache miss。
