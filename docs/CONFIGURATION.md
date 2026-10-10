# STS2_Things 配置说明

本模组的背景音乐、遭遇战、事件、商人猜拳与涅奥起始遗物都可以独立开关，
并可调整六个 Boss 和灵魂鱼子团精英的出现权重、筛选本模组 Boss。配置保存在
`user://mod_configs/STS2_Things.cfg`（JSON；真实游戏环境下通常在
`%APPDATA%\SlayTheSpire2\mod_configs\STS2_Things.cfg`），
首次启动自动生成，损坏时自动备份并回退默认值。

## 三套配置入口（同一份文件）

| 入口 | 条件 | 说明 |
|---|---|---|
| **游戏内配置页（BaseLib）** | 已订阅并启用 BaseLib | BaseLib 的"模组设置"页出现「尖塔：琐事」，由可选桥 `STS2_Things.BaseLibBridge.dll` 提供（随包安装，无 BaseLib 时不被加载） |
| **游戏内配置页（RitsuLib）** | 已订阅并启用 RitsuLib（v0.5.12+） | RitsuLib 设置页出现「尖塔：琐事」页，经零依赖互操作契约注册 |
| **手动编辑文件** | 无需配置库 | 退出游戏后编辑 `STS2_Things.cfg`，下次启动加载 |

BaseLib 与 RitsuLib **都不是前置依赖**；两者都未安装时模组以默认配置独立运行。
模组本身从不引用两个库（无编译期依赖，源码审计强制校验）。

### 显示语言

两套配置页的显示语言跟随游戏语言自动切换：游戏为简体中文（`zhs`）或繁体中文（`zht`）时
显示中文，其余语言回退英文。BaseLib 标签经游戏 `settings_ui` 表解析（缺键自动回退
`eng` 表）；RitsuLib 文本映射使用游戏语言码 `zhs`/`zht`/`en`。

## 可配置项

### 背景音乐

| 键 | 默认 | 说明 |
|---|---|---|
| `FeatureCustomBgmEnabled` | true | 启用模组指定的 Boss 音乐；关闭后恢复原版地图音乐，保留战斗音效 |

六个 Boss 共用此开关，包含墓潮蛞蝓的 WAV 音乐和其余 Boss 的 FMOD 曲目。
战斗中切换也会生效：关闭时停止当前模组音乐并恢复原版曲目，重新开启时恢复当前 Boss 音乐与阶段参数。联机时由房主操作，队员自动跟随。

### 遭遇战·Boss（启用 + 强制 + 权重）

| 键 | 默认 | 说明 |
|---|---|---|
| `BossOriginFogmogEnabled` / `BossOriginFogmogForced` | true / false | 始源雾菇（Overgrowth） |
| `BossScaleBeetleEnabled` / `BossScaleBeetleForced` | true / false | 放缩巨甲虫（Overgrowth） |
| `BossGravetideSlugEnabled` / `BossGravetideSlugForced` | true / false | 墓潮蛞蝓（Underdocks） |
| `BossTheLegacyEnabled` / `BossTheLegacyForced` | true / false | 腐化之遗（Underdocks） |
| `BossBowlbugProgenitorEnabled` / `BossBowlbugProgenitorForced` | true / false | 盛碗虫族母（Hive） |
| `BossCaveGodEnabled` / `BossCaveGodForced` | true / false | 活体巨岩（Hive / Depths；强制项只参与 Hive 的互斥选择） |
| `BossOnlyModBosses` | false | 对应地图仅从本模组可用 Boss 中抽取 |


- `Enabled=false`：该 Boss 从对应 Act 的遭遇池与 Boss 候选移除（不会随机到）。
- `Forced=true`：对应地图幕末**必定遭遇**该 Boss，包括已发现该 Boss 的存档；优先于权重与仅模组模式，且隐含 `Enabled=true`。
- `BossOnlyModBosses=true`：Overgrowth、Underdocks、Hive 分别只抽取上表对应的两个模组 Boss，不把 Boss 移到其他地图。若两者都禁用或权重为 0，则回退原有可用 Boss 池，避免空池。
- 双 Boss 规则下，优先选择其他可用 Boss；若强制/仅模组筛选后只剩一个，就再次遭遇它，保留第二场战斗。
- **冲突规则**：同一 Act 的 Boss 槽位最多一个强制项。加载配置或写入时自动裁决——
  规范顺序（上表顺序）先到先得，其余强制项降级为普通启用，并记录警告；
  两套配置页中同槽位的后续强制开关也会被隐藏（BaseLib `[ConfigVisibleIf]` /
  RitsuLib `visibleWhenMethod`）。

### 出现权重

七个滑块范围均为 **0–1000**，默认 **100**。`0` 表示不出现，`100` 表示默认权重，`200` 表示两倍权重。
这是相对权重，不是固定出现概率：只有两个候选且权重为 200 与 100 时，前者被抽中的概率为 2/3。
原版及其他模组的候选保持原有权重。关闭 `Enabled` 也会移除该候选；强制 Boss 的权重即使为 0，仍按强制设置出现。

| 键 | 对应内容 |
|---|---|
| `BossOriginFogmogWeightPercent` | 始源雾菇 |
| `BossScaleBeetleWeightPercent` | 放缩巨甲虫 |
| `BossGravetideSlugWeightPercent` | 墓潮蛞蝓 |
| `BossTheLegacyWeightPercent` | 腐化之遗 |
| `BossBowlbugProgenitorWeightPercent` | 盛碗虫族母 |
| `BossCaveGodWeightPercent` | 活体巨岩 |
| `EncounterSoulRoesWeightPercent` | 灵魂鱼子团（精英） |

自定义 Boss 权重或仅模组模式生效时，原版的“优先发现未见 Boss”不会覆盖抽取结果。
默认配置保留原版的发现顺序与随机数消费方式。
精英使用非默认正权重时，按权重重复抽取，并保留原版避免连续相同遭遇/标签的规则；因此较高权重也不保证连续出现。
默认权重、权重为 0 或地图中没有灵魂鱼子团时，沿用原版精英抽取方式。

### 遭遇战·其他

| 键 | 默认 | 说明 |
|---|---|---|
| `EncounterSoulRoesEnabled` | true | 灵魂鱼子团（Underdocks 精英） |
| `EncounterQuirkyHopperEnabled` | true | 怪癖草蜢（Hive 遭遇；同时控制其偷窃奖励策略） |

### 事件

| 键 | 默认 | 说明 |
|---|---|---|
| `EventRobberyFakeMerchantEnabled` | true | 假商人抢劫（Overgrowth/Underdocks） |
| `EventBackroomsEnabled` | true | Backrooms（Overgrowth/Underdocks） |
| `EventMedusaEnabled` | true | 美杜莎（Hive） |
| `EventCuttingItCloseEnabled` | true | 命悬一线（Overgrowth/Underdocks） |
| `EventRelicWorkshopEnabled` | true | 遗物修补摊（深处） |
| `EventPotionTastingEnabled` | true | 药水试饮会（深处） |
| `EventNarrowGateEnabled` | true | 窄门（深处） |

### 商人猜拳

| 键 | 默认 | 说明 |
|---|---|---|
| `FeatureMerchantBargainEnabled` | true | 商人处的猜拳讨价还价小游戏（v107.1／v111；多人由房主决定，各玩家独立交易） |

### 涅奥起始遗物

| 键 | 默认 | 说明 |
|---|---|---|
| `NeowRelicCurseRemoverEnabled` | true | 诅咒清除器（涅奥起始选项） |
| `NeowRelicWhiteFlagEnabled` | true | 白旗（涅奥起始选项） |
| `NeowRelicMagicGloveEnabled` | true | 魔法手套（涅奥起始选项） |

> 说明：卡牌、事件遗物（杏仁水、美杜莎之发）与附魔（分裂、虚无）**不是**可配置项——
> 它们是事件/遗物/附魔内容的一部分，随所属事件与遗物启用。

## 生效时机与限制

- 游戏内修改会更新共享内存配置。Boss 筛选和权重在**下一次幕的房间生成时**生效；已经生成的地图、遭遇队列和存档不重新抽取。原版可能提前生成后续幕，测试配置建议开始新局。
- 音乐开关在当前战斗中也可生效。手动编辑文件需重启游戏加载。
- 禁用内容**不改变 ModelId 与存档/联机 ABI**：模型仍被 ModelDb 发现（只不进池），旧存档与
  联机哈希保持稳定。
- 联机配置由房主同步，队员无需手动保持本地配置一致。具体规则见下一节。

## 多人配置权限

- 房主决定全部设置，包括音乐、Boss 筛选、出现权重、事件、商人猜拳和涅奥选项。
- 新局在准备界面接受房主修改，开局前通过游戏可靠通道发送最终配置，然后各端开始生成房间。玩法配置在本局内锁定，防止中途改变随机数或奖励规则。
- 读档时采用房主打开存档前的配置并锁定；已经保存的地图和遭遇队列不重抽。进行中的游戏发生断线重连时，队员重新取得该局已锁定的配置。
- 音乐由房主在局内实时调整并同步给队员，音效保留。
- 队员的个人设置文件始终保留；断开、取消加入、退出房间或返回单人模式时恢复自己的设置。BaseLib 的延迟保存也不会把房主临时配置写进队员的文件。
- BaseLib 将不可编辑的控件置灰；RitsuLib 隐藏不可编辑的控件，设置页保留权限说明。底层写入也会校验权限。
- 所有玩家须使用相同游戏版本及 **1.10.2 或后续相同构建**的模组。此次增加网络消息，版本号同步升级，让原版握手阻止与旧包混连。配置不兼容或缺少最终房主配置时停止进入游戏，不退回各自设置继续运行。

## 文件格式与升级

为与 BaseLib 的文件读取器兼容，保存时统一使用 JSON 字符串值，例如
`"FeatureCustomBgmEnabled": "False"`、`"BossScaleBeetleWeightPercent": "200"`。
旧版的布尔值、数字和字符串值都可读取，已有偏好会保留，新增键补入默认值。
权重会限制在 0–1000 之间，非法值使用默认值。两套配置页同步共享状态，延迟保存不会覆盖另一入口的修改。

## 校验

- `scripts/verify_project.py` 校验：键常量表（单一来源）与 BaseLib 桥属性名、
  RitsuLib schema 引用、`settings_ui` 本地化键（`STS2_THINGS-<SLUG>.title`，eng+zhs）三者一致；
  Config/ 集成层禁止编译期引用两个库。
- 探针：`tools/ThingsConfigProbe` 验证迁移、限值、实际房间生成、指定 Boss、空池回退、双 Boss、权重统计、种子复现和音乐开关；
  `tools/BaseLibBridgeProbe` 验证真实 BaseLib 的即时写入、反向同步和共享文件；
  `tools/RitsuLibInteropProbe` 验证真实 RitsuLib 注册后生成的七个滑块及新开关绑定。
- 多人配置探针额外验证权限、数据包往返、冲突配置下的房间/RNG 一致性、锁定、音乐、重连、退出恢复与文件隔离。
- `scripts/test-config-network.ps1` 启动三个隔离 Godot 进程，通过真实 ENet 通道检查房主与两个队员的一致性、消息时序、音乐同步和实际断线重连。
