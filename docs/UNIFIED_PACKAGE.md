# STS2_Things 统一订阅包

## 目的

Steam Workshop 的单个条目只能保存一套 `content/`。从 `1.8.0` 开始，所有玩家下载同一套：

```text
STS2_Things.json   min_game_version=v0.107.1
STS2_Things.dll    统一引导与两个内嵌实现
STS2_Things.pck    两版共用资源
```

Steam 不负责按分支选文件。选择发生在游戏加载引导 DLL 时。

## 启动顺序

1. 原生 ModManager 加载 `STS2_Things.dll` 与 PCK。
2. `UnifiedBootstrap` 检查当前 `AbstractModel.ModifyDamageMultiplicative` 签名与 V110 的 `CombatId` 类型。
3. 五参数选择内嵌 `v107.1.dll`；六参数且存在 `CombatId` 时选择内嵌 `v110.dll`。
4. 引导层在 `ModelDb` 和多人缓存初始化前注册选中的程序集。
5. 引导层调用原有 `STS2_ThingsInit.Initialize()`；业务注册与 Harmony 仍由版本专用实现负责。
6. 未选中的实现始终停留在嵌入资源中。

未知签名会直接终止 Mod 初始化并报告支持范围，不会猜测最近版本。

## V107.1 特殊桥

V107.1 的 `Mod` 只有单个 `assembly` 字段，且加载器在 initializer 返回后才把引导程序集写入该字段。
因此引导层安装两个窄补丁：

- `ReflectionHelper.ModTypes` Postfix：在 `ModelDb.Init()` 发现模型时追加选中实现的类型。
- `ModelIdSerializationCache.Init` Prefix：把已加载 `STS2_Things` Mod 的 assembly 切换为实现程序集，
  使旧版模型 ID、网络 hash、控制台和后续类型扫描都使用真实业务程序集。

这两个补丁不改变玩法状态、RNG 或模型顺序，只恢复旧加载器没有提供的多程序集归属能力。

## V110 原生路径

V110 直接调用官方 `ModManager.AssociateAssemblyWithMod`。随后
`AssemblyInfo.Init()`、`ModelDb.Init()`、`ContentSorter` 与统一保存属性缓存会把实现类型归属到
`STS2_Things` manifest。

## 门禁

- 两套实现分别以 `TreatWarningsAsErrors=true` 编译。
- 两套实现分别执行 Harmony target 和 SavedProperty 合同探针。
- 引导 DLL 必须且只能包含两个固定名称的实现资源。
- 嵌入资源 SHA256 必须与版本专用构件逐字节一致。
- 两套 `sts2.dll` 都必须能加载选中的实现全部类型；当前两版各发现 58 个具体 `AbstractModel`。
- V107.1 合成 Mod 必须通过类型追加和 assembly 提升验证。
- 最终 `build/unified` 只包含 manifest、引导 DLL 与共用 PCK。
- V110 还必须完成实际 Steam 启动烟雾测试。

跨游戏版本联机不在支持范围；同一局内所有玩家仍必须使用同一游戏版本。
