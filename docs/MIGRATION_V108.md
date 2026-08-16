# STS2_Things v0.108.0 迁移记录

## 来源

- C# 旧项目：`C:\Users\adner\Documents\STS2_Things`
  - Git commit：`2483ec2`
  - 保留了迁移开始时尚未提交的源码改动。
- 资源旧项目：`C:\Users\adner\Documents\things-images`
  - Git commit：`6ab5c7a`
  - 保留了迁移开始时尚未提交的本地化与贴图改动。
- 目标游戏：STS2 `v0.108.0`，commit `58694f64`。
- 目标 API 索引：`D:\Things\Things-Workspace\STS2-V108`。

原目录保持不变。旧项目中两份反编译游戏、Godot 缓存、IDE 缓存和复制来的编辑器插件没有迁入。

## 工程调整

- 将 C#、Godot/PCK、贴图、场景、音频和本地化合并为一个工程。
- 目标为 Godot `4.5.1 Mono`、`.NET 9`、C# 13。
- C# 引用改为当前 Steam 游戏的 `sts2.dll` 与 `0Harmony.dll`。
- 新增可覆盖的 `Sts2GameDir` / `STS2_GAME_DIR` 构建合同。
- 新增 `STS2_Things.json`，当前版本 `1.3.2`，最低游戏版本 `v0.108.0`。
- PCK 导出排除源码、工程文件、manifest 和构建目录，只发布资源与本地化。
- 清除了重复 UID 的旧 `images/ui/map` 资源副本。
- 增加 `scripts/build.ps1`，统一执行 DLL 构建、资源导入、PCK 导出、验证和可选安装；Godot 4.5.1 的导出调用使用 `--headless --editor --export-pack`，避免成功导出后出现 `_EDITOR_GET` 假错误。

## v0.108.0 API 修复

- 三个 `ModifyDamageMultiplicative` override 增加 `CardPlay? cardPlay` 参数。
- 事件战斗布局由旧 `_combatStateForCombatLayout` 迁移到
  `_combatSynchronizer.CombatStateForLayout`。
- 显式调用 `ScriptManagerBridge.LookupScriptsInAssembly`。
- 使用唯一 Harmony owner `Adnermo.STS2_Things` 并显式 Patch 当前程序集。
- 删除手工 `SavedPropertiesTypeCache.InjectTypeIntoCache`；V108 在
  `ModelDb.Init()` 之后由 `SavedPropertiesTypeCache.Init()` 按官方
  `ContentSorter` 顺序扫描模型，包含继承状态与 `CurseRemover.TimesUsed`。
- 修正 Release solution configuration，并清除 nullable 构建警告。

没有引入 RitsuLib 或 BaseLib 依赖、API、模板或教程实现。

## v1.3.2 怪物链路修复

- Origin Fogmog 若在第一回合开场 `ILLUSION_MOVE` 执行前被打到半血，原生
  `CreatureCmd.Stun` 会替换当前待执行招式。现在依据同步的 `NextMove.StateId`
  选择回调：该竞态路径在眩晕回合一次补足 2 只 `OriginEyeWithTeeth`，正常路径
  仍按“开场 1 只、半血阶段 1 只”执行。
- 等待 `IllusionPower` 复活的 Origin Eye 继续占用原槽位，避免复活实体与新召唤
  叠在同一 Marker2D；Soul Roes 的父体死亡补位波仍只让存活鱼子占槽。
- Origin Eye 通过 `IllusionPower` 间接获得的原生 `MinionPower` 图标已加入
  Origin Fogmog 的 `AssetPaths`，动态生成时不再触发 power icon cache miss。
- Origin Fogmog、Bowlbug Progenitor 与 Scale Beetle 的敌方招式格挡
  移除手工玩家数预乘，统一把基础值与 `ValueProp.Move` 交给 V108 原生多人缩放。
  Bowlbug 的 `20`/`16` 与 Scale Beetle Molt 的 `14` 均只缩放一次。
- The Legacy 的硬化外壳先用整数除法得到 HP/divisor 目标层数，再调用
  `PowerCmd.ModifyAmount`，修复 HP/4 等阶段因 decimal 差值截断而多 1 层的问题。
- Mod 版本提升到 `1.3.2`，使包含上述共享玩法修复的新 DLL 不会与上一版 DLL
  以相同 Mod 版本通过联机版本检查。

## PCK 与背景资源加固

- 四个 Boss 背景改用 V108 `BackgroundAssets` 的原生目录与分层场景合同。
- 根因确认：Godot 的文本资源二进制转换会在最终 PCK 中生成
  `.tscn.remap`；`BackgroundAssets` 枚举背景目录后无法把这些映射项作为
  正常背景场景加载，最终触发 `AssetLoadException`。
- `project.godot` 与 `export_presets.cfg` 均固定
  `export/convert_text_resources_to_binary=false`，最终 PCK 不再包含
  `.tscn.remap`。
- `scripts/verify_pck.gd` 会挂载实际导出的 PCK，逐一验证四套 Boss 背景目录
  只暴露可加载的 `.tscn`，从而覆盖“源目录正常、打包后失效”的回归路径。

## 验证

- `scripts/verify_project.py`：`STS2_Things source audit: PASS`。
- FMOD 静态审计：`STS2_Things FMOD audit: PASS`。
- Release 构建：0 warnings / 0 errors。
- 最终 PCK 挂载验证：`STS2_Things PCK runtime background contract: PASS`。
- `validate_mod.py`：0 errors / 0 warnings。
- Steam 安装目录中的 manifest、DLL、PCK 成功加载；日志确认
  `Version=1.3.2.0`、`Loaded 1 mods (1 total)`，未出现本 Mod 的 Harmony、资源、
  脚本或本地化异常。
- 五个自定义遭遇已经从单人游戏的涅奥遗物选择阶段通过原版 `fight` 命令
  进入并覆盖核心链路实测；Soul Roes 的精确 8 只与同批范围伤害死亡补位
  边界也已通过；Origin Fogmog 首回合半血竞态的双 Eye 结果也已通过，逐项证据见
  `docs/MONSTER_PIPELINE_V108.md`。

- 双进程 fastmp 中，主机与客户端均只加载 `STS2_Things 1.3.2`，双方
  `ModelIdSerializationCache` 都是 `1693` entries / hash `296163847` 并成功加入
  Custom lobby。固定 seed `STS2THINGS108MP` 回归已同步执行网络化 `fight` 与
  半血伤害动作；最终安装三件套又在双端实际推进到 `STUNNED` 敌方回合，双方
  都显示两只 `19/19` Origin Eye。checksum 上下文从 id `0` 到 `7` 对齐，日志无
  mismatch/desync。

测试日志位于忽略提交的 `build/` 目录。
