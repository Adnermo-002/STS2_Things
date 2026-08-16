# STS2_Things 双版本支持

## 目标

同一份业务源码仍分别链接两套真实游戏程序集，但最终发布为一个统一订阅包：

| 实现目标 | 游戏分支 | 编译常量 | 内部程序集 |
|---|---|---|---|
| `v107.1` | 兼容正式版 | `STS2_V107_1` | 内嵌资源 `v107.1.dll` |
| `v110` | 当前正式版 | `STS2_V110` | 内嵌资源 `v110.dll` |

对外文件 `STS2_Things.dll` 的内部程序集名是 `STS2_Things.Bootstrap`。两套实现内部名均为
`STS2_Things`，但每个进程只加载一套，因此不会发生程序集身份冲突。引导层以
`AbstractModel.ModifyDamageMultiplicative` 的五/六参数签名及 V110 的 `CombatId` 类型识别游戏版本，只加载对应的
内嵌实现。`STS2_Things.pck` 只包含 Godot 4.5.1 资源，两版共用同一字节序列。

## 已隔离的 API 差异

1. `AbstractModel.ModifyDamageMultiplicative`
   - 107.1：五个参数。
   - 110：六个参数，包含 `CardPlay?`。
2. 事件战斗布局
   - 107.1：`_combatStateForCombatLayout`。
   - 110：`_combatSynchronizer.CombatStateForLayout`。
3. 怪物节点可见性
   - 107.1：通过 `Creature.GetCreatureNode()?.Visible`。
   - 110：使用 `Creature.SetNodeVisible`。
4. 保存属性缓存
   - 107.1 由兼容层显式登记 `CurseRemover`。
   - 110 在 `ModelIdSerializationCache.Init()` 中自动扫描全部模型和属性，并纳入多人 hash。
5. Mod 内容排序
   - 107.1 使用稳定的 `ModelId -> assembly -> full type name` 回退排序。
   - 110 使用官方 `ContentSorter<ModelId>` 与 `AssemblyInfo.ModForType`。
6. 玩家选择上下文
   - 110 使用 `OwnerId`、`BranchingPlayerChoiceContext` 与新版内部选择开始信号。
   - 本 Mod 只透传原生上下文。
7. 卡牌攻击来源上下文
   - 107.1：`AttackCommand.FromCard(CardModel)`。
   - 110：`AttackCommand.FromCard(CardModel, CardPlay?)`，伤害 Hook 可读取本次出牌上下文。
   - “对撞”在条件编译分支中分别调用精确重载，之后统一走 `DamageCmd` 与 `PowerCmd`，不使用
     `LocalContext` 限制共享玩法。
8. 战斗生命周期
   - 107.1：`CombatManager` 直接保存 `_state` 与 `IsInProgress`。
   - 110：战斗级状态收拢到内部 `_turnState`/`CombatTurnState`，并用 `CombatId` 标识当前战斗。
   - 业务代码只调用公开 API；独立行为探针通过窄反射夹具分别构建两版假战斗。
9. 独立 Godot 探针运行时
   - 110 的 `sts2.dll` 模块初始化新增 `Sentry.Godot.dll` 依赖，所有探针显式复制该文件。
10. 原版数值漂移
   - `The Scythe` 的 `Increase` 从旧版 4 调整为 V110 的 5；“分裂”探针从当前原版变量推导期望值，
     分别验证 107.1 的 9 与 110 的 10。

## 引导注册

- V110：在 `AssemblyInfo.Init()` 前调用官方
  `ModManager.AssociateAssemblyWithMod("STS2_Things", implementationAssembly)`。
- V107.1：旧版一个 Mod 只记录一个 `assembly`。引导层在 `ModelDb.Init()` 使用的
  `ReflectionHelper.ModTypes` 结果中追加实现类型，并在
  `ModelIdSerializationCache.Init()` 前把目标 Mod 的 assembly 提升为选中的实现。
- 两版都由引导层显式调用实现的 `STS2_ThingsInit.Initialize()`；未选中的程序集不会加载、
  扫描或安装 Harmony Patch。

## 发布合同

- 正式发布目录只使用 `build/unified/STS2_Things.json|dll|pck`。
- 统一 manifest 为 `1.9.5`，`min_game_version` 为 `v0.107.1`。
- `build/v107.1` 与 `build/v110` 是可独立加载的诊断/回退构件，不直接上传到同一 Workshop 条目。
- Workshop 中仍只有标准三件套；两个实现 DLL 是引导 DLL 的嵌入资源，不作为 loose DLL 发布。
- 联机双方必须使用相同游戏版本；同版本玩家会选择相同实现，并使用完全相同的统一包哈希。
- 游戏程序集只作为本地编译引用，不提交到 Git。

## 构建与验证

```powershell
.\scripts\build-all.ps1 `
  -DataDirV1071 D:\path\to\v107.1\data_sts2_windows_x86_64 `
  -DataDirV110 D:\path\to\v110\data_sts2_windows_x86_64 `
  -Install
```

该入口执行：源码审计、双实现严格编译、双 Harmony 目标探针、每版怪癖草蜢、分裂附魔、对撞卡牌、
抢劫者与灵潮巨蛞蝓行为探针、V110 商人议价探针、PCK 挂载检查、统一引导编译、两版资源选择、
嵌入字节哈希、关键模型存在性与两版完整模型集合一致性、V107.1 Mod 归属桥和最终三件套严格校验。
