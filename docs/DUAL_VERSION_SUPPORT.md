# STS2_Things 双版本支持

## 目标

同一份业务源码生成两套独立 DLL/manifest：

| 目标 | 游戏分支 | 编译常量 | 最低游戏版本 |
|---|---|---|---|
| `v107.1` | 正式版 | `STS2_V107_1` | `v0.107.1` |
| `v108` | 测试版 | `STS2_V108` | `v0.108.0` |

PCK 只包含 Godot 4.5.1 资源。双版本构建只导出一次并按字节复制给两个目标，保证 PCK 哈希相同。DLL 必须分别针对对应分支的 `sts2.dll` 和 `0Harmony.dll` 编译。

## 已隔离的 API 差异

1. `AbstractModel.ModifyDamageMultiplicative`
   - 107.1：五个参数。
   - 108：增加 `CardPlay?` 参数。
2. 事件战斗布局
   - 107.1：`_combatStateForCombatLayout`。
   - 108：`_combatSynchronizer.CombatStateForLayout`。
3. 怪物节点可见性
   - 107.1：通过 `Creature.GetCreatureNode()?.Visible`。
   - 108：使用 `Creature.SetNodeVisible`。
4. `SavedPropertiesTypeCache`
   - 107.1 只自动缓存原版模型，因此兼容层显式登记 `CurseRemover`。
   - `TimesUsed` 已是 107.1 原版属性名，登记不会改变网络属性 ID 位宽。
   - 108 会在 `ModelDb.Init` 后按官方 `ContentSorter` 自动缓存 Mod 模型，不执行手工登记。
5. Mod 内容排序
   - 107.1 使用稳定的 `ModelId -> assembly -> full type name` 回退排序。
   - 108 使用官方 `ContentSorter<ModelId>`。
6. 敌方招式格挡
   - 两个版本都接收未预乘人数的基础值与 `ValueProp.Move`。
   - 107.1/108 各自的 `MultiplayerScalingModel` 决定对应版本的官方缩放倍率，Mod 不做第二次缩放。

## 发布合同

- `manifests/v107.1/STS2_Things.json` 只能配套 107.1 DLL。
- `manifests/v108/STS2_Things.json` 只能配套 108 DLL。
- 两套工件不能同时安装到同一个 `mods/STS2_Things` 目录。
- 联机双方必须使用相同游戏分支、相同 manifest 版本和相同 DLL/PCK 哈希。
- 游戏程序集只作为本地编译引用，不提交到 Git。

## 验证

```powershell
python scripts/verify_project.py

dotnet build STS2_Things.csproj -c Release `
  /p:Sts2TargetVersion=v107.1 `
  /p:Sts2DataDir=D:\path\to\v107.1\data_sts2_windows_x86_64

dotnet build STS2_Things.csproj -c Release `
  /p:Sts2TargetVersion=v108 `
  /p:Sts2DataDir=D:\path\to\v108\data_sts2_windows_x86_64

.\scripts\verify-harmony-targets.ps1 `
  -DataDir D:\path\to\target\data_sts2_windows_x86_64 `
  -ModDll build\target\STS2_Things.dll
```
