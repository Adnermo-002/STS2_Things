# STS2_Things 双版本支持

## 目标

同一份业务源码仍分别链接两套真实游戏程序集，但最终发布为一个统一订阅包：

| 实现目标 | 游戏分支 | 编译常量 | 内部程序集 |
|---|---|---|---|
| `v107.1` | 正式版 | `STS2_V107_1` | 内嵌资源 `v107.1.dll` |
| `v109` | 测试版 | `STS2_V109` | 内嵌资源 `v109.dll` |

对外文件 `STS2_Things.dll` 的内部程序集名是 `STS2_Things.Bootstrap`。两套实现内部名均为
`STS2_Things`，但每个进程只加载一套，因此不会发生程序集身份冲突。引导层以
`AbstractModel.ModifyDamageMultiplicative` 的五/六参数签名识别游戏版本，只加载对应的
内嵌实现。`STS2_Things.pck` 只包含 Godot 4.5.1 资源，两版共用同一字节序列。

## 已隔离的 API 差异

1. `AbstractModel.ModifyDamageMultiplicative`
   - 107.1：五个参数。
   - 109：增加 `CardPlay?` 参数。
2. 事件战斗布局
   - 107.1：`_combatStateForCombatLayout`。
   - 109：`_combatSynchronizer.CombatStateForLayout`。
3. 怪物节点可见性
   - 107.1：通过 `Creature.GetCreatureNode()?.Visible`。
   - 109：使用 `Creature.SetNodeVisible`。
4. 保存属性缓存
   - 107.1 由兼容层显式登记 `CurseRemover`。
   - 109 在 `ModelIdSerializationCache.Init()` 中自动扫描全部模型和属性，并纳入多人 hash。
5. Mod 内容排序
   - 107.1 使用稳定的 `ModelId -> assembly -> full type name` 回退排序。
   - 109 使用官方 `ContentSorter<ModelId>` 与 `AssemblyInfo.ModForType`。
6. 玩家选择上下文
   - 109 新增 `OwnerId`、`BranchingPlayerChoiceContext`，并修改内部选择开始信号。
   - 本 Mod 只透传原生上下文。

## 引导注册

- V109：在 `AssemblyInfo.Init()` 前调用官方
  `ModManager.AssociateAssemblyWithMod("STS2_Things", implementationAssembly)`。
- V107.1：旧版一个 Mod 只记录一个 `assembly`。引导层在 `ModelDb.Init()` 使用的
  `ReflectionHelper.ModTypes` 结果中追加实现类型，并在
  `ModelIdSerializationCache.Init()` 前把目标 Mod 的 assembly 提升为选中的实现。
- 两版都由引导层显式调用实现的 `STS2_ThingsInit.Initialize()`；未选中的程序集不会加载、
  扫描或安装 Harmony Patch。

## 发布合同

- 正式发布目录只使用 `build/unified/STS2_Things.json|dll|pck`。
- 统一 manifest 为 `1.7.0`，`min_game_version` 为 `v0.107.1`。
- `build/v107.1` 与 `build/v109` 是可独立加载的诊断/回退构件，不直接上传到同一 Workshop 条目。
- Workshop 中仍只有标准三件套；两个实现 DLL 是引导 DLL 的嵌入资源，不作为 loose DLL 发布。
- 联机双方必须使用相同游戏版本；同版本玩家会选择相同实现，并使用完全相同的统一包哈希。
- 游戏程序集只作为本地编译引用，不提交到 Git。

## 构建与验证

```powershell
.\scripts\build-all.ps1 `
  -DataDirV1071 D:\path\to\v107.1\data_sts2_windows_x86_64 `
  -DataDirV109 D:\path\to\v109\data_sts2_windows_x86_64 `
  -Install
```

该入口执行：源码审计、双实现严格编译、双 Harmony 目标探针、PCK 挂载检查、统一引导编译、
两版资源选择、嵌入字节哈希、45 个自定义模型类型加载、V107.1 Mod 归属桥和最终三件套严格校验。
