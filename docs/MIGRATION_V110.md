# STS2_Things V110 迁移记录

## 基线

- 游戏版本：`v0.110.1`
- commit：`db5d3552`
- 发布时间：`2026-07-31T01:18:29-07:00`
- main assembly hash：`-959015736`
- `SlayTheSpire2.pck` SHA-256：`F526EF85CD5B7CF653DEFB545A8BA22196C72E6A0E95AD66F78F2F3A168B28C9`
- shipped `sts2.dll` SHA-256：`7C446EFABF80614C429B5088E87101423AA5BB4C04FC3E73393261F6E6D404FD`
- shipped `0Harmony.dll` SHA-256：`EF1898322C9F5C86DC1B0758B272A9C440823B4A41CA9A0B82A3AA6B3D206387`
- 反编译索引：`D:\Things\Things-Workspace\STS2-V110`

GDRE 2.5.0-beta.5 共提取 15,796 个文件、反编译 3,580 个脚本、转换 4,015 个资源；29 个脚本路径映射失败，
1,253 个资源为有损转换，已知场景解析错误仍是 `scenes/debug/back_confirm_example.tscn:21`。反编译解决方案以
0 警告、0 错误编译，691 份本地化 JSON 均可解析。

## API 审计

V109.1 到 V110.0 的 C# 索引差异为新增 41、删除 3、修改 243 个文件；V110.0 到 V110.1 仅修改 3 个 C# 文件，
分别是 AutoSlay 商店覆盖层排空逻辑和 LoadRunLobby 就绪查询。Mod 使用到的公开 API 仍可直接编译，
迁移需要处理的运行时和测试合同包括：

- `CombatManager` 把 `_state`、战斗取消令牌和回合标志收拢到内部 `CombatTurnState`，并新增 `CombatId`。
- `sts2.dll` 模块初始化新增 `Sentry.Godot.dll` 依赖。
- `The Scythe.Increase` 从 4 调整为 5，升级增量从 1 调整为 2。
- V110 继续使用 `ModManager.AssociateAssemblyWithMod`、统一 `ModelIdSerializationCache` 和六参数伤害 Hook。
- 删除的 `LobbyPlayer`、`Scare`、`OutbreakPower` 未被本 Mod 引用。

## 工程迁移

- 活动目标由 `v107.1 + v109` 调整为 `v107.1 + v110`，编译常量为 `STS2_V107_1` 与 `STS2_V110`。
- Mod 版本升至 `1.9.4`；统一 manifest 最低版本保持 `v0.107.1`，V110 诊断 manifest 为 `v0.110.0`。
- 统一引导内嵌 `STS2_Things.Implementations.v107.1.dll` 与
  `STS2_Things.Implementations.v110.dll`；五参数签名选择旧版，六参数签名加 `CombatId` 类型指纹选择 V110。
- V107.1 继续使用类型追加和 assembly 提升桥；V110 走原生程序集归属路径。
- 商人议价只在 `STS2_V110` 编译，规则保持差值不超过 20、第五次尝试触发。
- 所有 Godot 行为探针增加 `Sentry.Godot.dll`，切换目标时强制重建；假战斗夹具同时支持旧 `_state` 与新 `_turnState`。

## 验证

- 两套实现均以 `TreatWarningsAsErrors=true` 编译：0 警告、0 错误。
- 两版 Harmony target、SavedProperty、怪癖草蜢、分裂、对撞、抢劫者与灵潮巨蛞蝓探针通过。
- V110 商人议价探针通过：20 金币边界、第五次触发、胜负/异常状态、18 张手势资源和购买补丁目标均成立。
- V110 PCK 导出、挂载和资源合同通过；V107.1 复用同一 PCK 字节序列。
- 统一包探针在两版各加载 58 个具体 `AbstractModel`，模型集合完全一致，嵌入 DLL 哈希与独立构件一致。
- 严格 manifest/artifact 校验为 0 error、0 warning。

## 当前工件

| 工件 | SHA-256 |
|---|---|
| `build/v107.1/STS2_Things.dll` | `CC225DDF5274CBF3B96B8F5554E36119CD47453EBEAECD33D879B232201522ED` |
| `build/v110/STS2_Things.dll` | `B7A05CBEC190866E1130164A57003229622D51172CF00A9DF5A003D594EA183E` |
| 两版及统一包 `STS2_Things.pck` | `2FF1D2438B49E40B5AEF282B15B608D3801806E5E224F4A1A4F5D90D1FA4E4C2` |
| `build/unified/STS2_Things.dll` | `0F8D867FAAB6D1ECE0BA203B73FFE47BE0D55AB90E346F5DC28A571734185073` |
| `build/unified/STS2_Things.json` | `CF901E2FB11A32CED00C8F64F3A42F57E54A58392E70020995BD90A9D22ABFED` |

Steam Workshop 条目 `3747607944` 已于 2026-07-31 更新为 `v1.9.4` 统一包；Steam 日志确认
ManifestID `5065994009519036547` 上传成功，远端简介、公开可见性和 V107.1/V110.x 兼容说明均已复核。
