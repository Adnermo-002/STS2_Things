# STS2_Things v0.109.0 迁移记录

## 基线

- 游戏版本：`v0.109.0`
- commit：`c12f634d`
- 发布时间：`2026-07-17T02:31:41+00:00`
- main assembly hash：`1833084275`
- API/资源索引：`D:\Things\Things-Workspace\STS2-V109`
- 工具：GDRE Tools `v2.5.0-beta.5`

V109 索引从当前 Steam `SlayTheSpire2.pck` 重新恢复，没有覆盖 V108 历史基线。
GDRE 成功反编译 3545 个脚本，23 个脚本失败；4002 个导入资源中成功转换
4001 个，1252 个为 lossy，唯一场景解析失败仍是
`scenes/debug/back_confirm_example.tscn`。FMOD 插件下载失败后，发布库从当前
Steam 安装补齐，编辑器/调试库从哈希一致的 6.1.0 V108 缓存补齐。

## 108 到 109 的相关 API 变化

- `ModManifest`、`ModManager` 与 `ModHelper` 文件哈希未变化，外置 manifest、
  DLL/PCK basename、加载顺序与池注册合同保持不变。
- 独立 `SavedPropertiesTypeCache` 被移除；保存属性扫描合并进
  `ModelIdSerializationCache.Init()`。它按 `ContentSorter<ModelId>` 排序
  `ModelDb.All`，缓存 `[SavedProperty]`，计算属性位宽，并把 gameplay Mod 的
  ModelId/属性名纳入同一多人 hash。
- `ModelDb.Init` 新增可选 `Type[] injectedModelTypes` 测试入口；正常无参启动仍扫描
  全部原版与已加载 Mod 的具体 `AbstractModel`。
- `ContentSorter` 改由 `AssemblyInfo.ModForType` 解析类型归属，排序规则不变。
- `PlayerChoiceContext` 新增 `OwnerId`，`SignalPlayerChoiceBegun` 增加选择者参数，
  并新增实验性的 `BranchingPlayerChoiceContext`。本 Mod 没有直接调用受影响成员。
- `ModifyDamageMultiplicative`、事件战斗同步器、`Creature.SetNodeVisible`、Act 遭遇与
  Boss 列表入口仍与 V108 兼容。

## 项目调整

- 活动测试版目标由 `v108` 替换为 `v109`，正式版目标继续为 `v107.1`。
- Mod 版本提升到 `1.6.1`，避免 V108/V109 DLL 在多人检查中复用同一版本号。
- 新增 `STS2_V109` 编译常量和 `manifests/v109/STS2_Things.json`。
- 构建、双版本编排、源码审计、Harmony 探针、README 与发布合同同步到 V109。
- Harmony 探针能区分 V107.1 旧缓存、V108 独立自动缓存和 V109 统一缓存。

## 验证

- 当前业务源码直接链接 shipped V109 `sts2.dll`：0 warning / 0 error。
- V109 FMOD 事件与三个 Act 的动态音乐 bank 合同：PASS。
- `scripts/verify_project.py`：PASS。
- V107.1 与 V109 严格 Mod 校验：均为 0 error / 0 warning。
- V107.1 `SavedPropertiesTypeCache` 兼容桥与 V109 统一
  `ModelIdSerializationCache` 合同探针：PASS。
- 两套 Harmony 目标、PCK 挂载背景合同：PASS；双版本 PCK 字节一致，SHA256 为
  `722911EB687F3650C7B92F01CC70916AC6199EAFD50592CDB40BC0F2A3459134`。
- V109 构建已安装到 Steam。实机日志确认游戏为
  `v0.109.0 / c12f634d`，本地 `STS2_Things 1.6.1`、eng/zhs 本地化和模型缓存均加载成功。
- 模型缓存为 20 categories / 1699 entries / 57 epochs / 47 properties，hash
  `4143645734`；没有本 Mod 的 Harmony、保存、资源或本地化错误。
- 自动化强制退出会记录资源泄漏诊断，旧存档还包含未知原版 ID 警告；二者均与本 Mod
  的 V109 加载路径无关。

## 发布工件

| 目标 | 文件 | SHA256 |
|---|---|---|
| V107.1 | `STS2_Things.json` | `21E31738EA75C2004CE2A2114EC3EE7CF52CE5AC9582155AAD9E99DC2D13D429` |
| V107.1 | `STS2_Things.dll` | `38CD1AD597B393CF29B82C16B6DEF41F35F327376B730CE832A4D67AD3130C9F` |
| V109 | `STS2_Things.json` | `1EF5DA320A7B0B901DD8BCC48BE153C43142908EBE095EAF589CC6E20A323D2E` |
| V109 | `STS2_Things.dll` | `2882A63D048915AEB593F71D7AE85C256D91905499CD1C3C7A637B58DE614F06` |
| 共用 | `STS2_Things.pck` | `722911EB687F3650C7B92F01CC70916AC6199EAFD50592CDB40BC0F2A3459134` |
