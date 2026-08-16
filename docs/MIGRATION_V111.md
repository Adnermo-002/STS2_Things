# STS2_Things V111 迁移记录

## 基线

- 游戏版本：`v0.111.0`
- commit：`41cef1ea`
- 发布时间：`2026-08-13T17:39:18-07:00`
- main assembly hash：`222455745`
- `SlayTheSpire2.pck` SHA-256：`C60F672EE7804E6AEFA1E19A582FA1C80B126A7B0EEF4D084D3ABF110DF2EAB7`
- shipped `sts2.dll` SHA-256：`0861BFA1DF347538D932F22D580E75420F08082792EB914E53B4882764ACDBE9`
- shipped `0Harmony.dll` SHA-256：`EF1898322C9F5C86DC1B0758B272A9C440823B4A41CA9A0B82A3AA6B3D206387`（与 V110 相同）
- 反编译索引：`D:\Things\Things-Workspace\STS2-V111`

GDRE 2.5.0-beta.5 共提取 15,890 个文件、反编译 3,591 个脚本、转换 4,029 个资源；30 个脚本路径映射失败，
1,253 个资源为有损转换，已知场景解析错误仍是 `scenes/debug/back_confirm_example.tscn:21`。反编译解决方案以
0 警告、0 错误编译。C# 反编译树与安装目录 shipped 程序集逐字节一致（`.baseline/`）。

## API 审计

V110.1 到 V111.0 的 C# 索引差异（同构 GDRE 树对比）为**新增 11、删除 1、修改 186** 个文件：

- 删除 `Core/Multiplayer/Messages/Lobby/ClientConnectionFailedMessage.cs`。
- 新增 `Core/Multiplayer/Connection/HandshakeManager.cs`、`HandshakeResult.cs`、`HandshakeStatus.cs`、
  `IHandshakeHandler.cs` —— v0.111.0 重做了连接握手层，客户端连接失败由握手结果取代旧消息。
- 新增 `Core/Combat/StuckCombatException.cs`、`Core/Nodes/SentryBootstrap.cs`、
  `Core/Saves/Migrations/SettingsSaves/SettingsSaveV7ToV8.cs`、`Core/TestSupport/AbstractTestNetHost.cs`。
- 修改集中在 `Core/Nodes`（69）、`Core/Models`（44，含 `CardModel`/`CharacterModel`/`PotionModel` 与
  多张卡/角色/怪物/遗物数值）、`Core/Multiplayer`（22）、`Core/Entities`（8）、`Core/Platform`（7）、
  `Core/Commands`（3：`CardCmd`/`CardPileCmd`/`CreatureCmd`）、`Core/Combat`（3：
  `CombatManager`/`CombatTurnState`/`PendingLossState`）、`Core/Modding`（3：`ModManager` 与文件 IO 抽象）。

Mod 用到的公开 API 直接编译通过（0 警告、0 错误），无需反射绕过。迁移需要处理的运行时合同包括：

- `AbstractModel.ModifyDamageMultiplicative` 仍为六参数，`CombatId` 仍在 —— 引导层需用
  v0.111.0 新增的 `HandshakeManager` 类型指纹区分 v110 与 v111，避免把 v111 误判为 v110。
- 旧版 `ClientConnectionFailedMessage` 删除；本 Mod 未引用，无影响。
- `Sentry.Godot.dll` 运行时依赖延续（`SentryBootstrap` 节点新增，属原版内部引导）。
- Mod 引用的原版资源（`corpse_slug` 图集、`ravenous_power` 图标等）在 v110.1 与 v111.0 之间逐字节一致。
- `The Scythe` 等被“分裂”探针引用的原版数值未见再漂移，探针继续从当前 canonical 变量推导期望值。

## 工程迁移

- 活动目标由 `v107.1 + v110` 调整为 `v107.1 + v111`，编译常量为 `STS2_V107_1` 与 `STS2_V111`。
- Mod 版本升至 `1.10.0`；统一 manifest 最低版本保持 `v0.107.1`，V111 诊断 manifest 为 `v0.111.0`。
- 统一引导内嵌 `STS2_Things.Implementations.v107.1.dll` 与
  `STS2_Things.Implementations.v111.dll`；五参数签名选择旧版，六参数签名加 `CombatId` 类型指纹后，
  再用 `HandshakeManager` 类型区分 v111；检测到 v0.110.x 时抛出明确的“请升级游戏”错误。
- V107.1 继续使用类型追加和 assembly 提升桥；V111 走原生 `ModManager.AssociateAssemblyWithMod` 路径。
- 商人议价改在 `STS2_V111` 条件编译，规则保持差值不超过 20、第五次尝试触发。
- 构建脚本、统一包探针、Harmony 目标探针与全部行为探针的版本参数切换为 `v111`；`manifests/v110` 移除，
  新增 `manifests/v111`；引用原版资产的审计脚本改指 `STS2-V111` 树。

## 验证

- 两套实现均以 `TreatWarningsAsErrors=true` 编译：0 警告、0 错误。
- 两版 Harmony target、SavedProperty、怪癖草蜢、分裂、对撞、抢劫者与灵潮巨蛞蝓探针通过。
- V111 商人议价探针通过：20 金币边界、第五次触发、胜负/异常状态、18 张手势资源和购买补丁目标均成立。
- V111 PCK 导出、挂载和资源合同通过；V107.1 复用同一 PCK 字节序列。
- 统一包探针在两版各加载相同数量的具体 `AbstractModel`，模型集合完全一致，嵌入 DLL 哈希与独立构件一致。
- 引导构建确定性验证通过（连续两次构建字节一致）。
- 严格 manifest/artifact 校验为 0 error、0 warning。
- 统一包已安装到当前游戏 `mods/STS2_Things`，可直接在 v0.111.0 上启动验证。

## 当前工件

| 工件 | SHA-256 |
|---|---|
| `build/v107.1/STS2_Things.dll` | `A672AE1B33E7ECCDA4C569BF21A867F74A00EBADAA987C242319ABD865E10F24` |
| `build/v111/STS2_Things.dll` | `119098B60177E0E206ED9C4EB479444182870C59578A2E5D306562100344F790` |
| 两版及统一包 `STS2_Things.pck` | `E7CCA65DC00E437E6D8966A6D8CFAC57E6A918BF0BED0EE61BF5375536DB4020` |
| `build/unified/STS2_Things.dll` | `9E77D1A5F2E6D3F7460551534C80026BE744A69F945179D96A10B953F25DE39B` |
| `build/unified/STS2_Things.json` | `DA66CDB27B8BC3AF3BB4C0E50FC343EC04B9AD8F601E9B5517750008C109C062` |
