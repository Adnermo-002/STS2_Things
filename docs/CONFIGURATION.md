# STS2_Things 配置说明

本模组的遭遇战、事件、商人猜拳与涅奥起始遗物都可以独立开关。配置保存在
`user://mod_configs/STS2_Things.cfg`（JSON；真实游戏环境下通常在
`%APPDATA%\SlayTheSpire2\mod_configs\STS2_Things.cfg`），
首次启动自动生成，损坏时自动备份并回退默认值。

## 三套配置入口（同一份文件）

| 入口 | 条件 | 说明 |
|---|---|---|
| **游戏内配置页（BaseLib）** | 已订阅并启用 BaseLib | BaseLib 的"模组设置"页出现「尖塔：琐事」，由可选桥 `STS2_Things.BaseLibBridge.dll` 提供（随包安装，无 BaseLib 时不被加载） |
| **游戏内配置页（RitsuLib）** | 已订阅并启用 RitsuLib（v0.5.12+） | RitsuLib 设置页出现「尖塔：琐事」页，经零依赖互操作契约注册 |
| **手动编辑文件** | 两者都未安装 | 直接编辑 `STS2_Things.cfg`，重启或下次池生成时生效 |

BaseLib 与 RitsuLib **都不是前置依赖**；两者都未安装时模组以默认配置独立运行。
模组本身从不引用两个库（无编译期依赖，源码审计强制校验）。

### 显示语言

两套配置页的显示语言跟随游戏语言自动切换：游戏为简体中文（`zhs`）或繁体中文（`zht`）时
显示中文，其余语言回退英文。BaseLib 标签经游戏 `settings_ui` 表解析（缺键自动回退
`eng` 表）；RitsuLib 文本映射使用游戏语言码 `zhs`/`zht`/`en`。

## 可配置项

### 遭遇战·Boss（启用 + 强制）

| 键 | 默认 | 说明 |
|---|---|---|
| `BossOriginFogmogEnabled` / `BossOriginFogmogForced` | true / false | 始源雾菇（Overgrowth） |
| `BossScaleBeetleEnabled` / `BossScaleBeetleForced` | true / false | 缩放巨甲虫（Overgrowth） |
| `BossGravetideSlugEnabled` / `BossGravetideSlugForced` | true / false | 盛碗虫族母（Underdocks） |
| `BossTheLegacyEnabled` / `BossTheLegacyForced` | true / false | 腐化之遗（Underdocks） |
| `BossBowlbugProgenitorEnabled` / `BossBowlbugProgenitorForced` | true / false | 盛碗虫族母·原版系（Hive） |
| `BossCaveGodEnabled` / `BossCaveGodForced` | true / false | 山神（Hive） |


- `Enabled=false`：该 Boss 从对应 Act 的遭遇池与 Boss 候选移除（不会随机到）。
- `Forced=true`：本幕结尾**必定遭遇**该 Boss（BossDiscoveryOrder 只保留它）。
- **冲突规则**：同一 Act 的 Boss 槽位最多一个强制项。加载配置或写入时自动裁决——
  规范顺序（上表顺序）先到先得，其余强制项降级为普通启用，并记录警告；
  两套配置页中同槽位的后续强制开关也会被隐藏（BaseLib `[ConfigVisibleIf]` /
  RitsuLib `visibleWhenMethod`）。

### 遭遇战·其他

| 键 | 默认 | 说明 |
|---|---|---|
| `EncounterSoulRoesEnabled` | true | 灵魂鱼子团（Underdocks 遭遇） |
| `EncounterQuirkyHopperEnabled` | true | 怪癖草蜢（Hive 遭遇；同时控制其偷窃奖励策略） |

### 事件

| 键 | 默认 | 说明 |
|---|---|---|
| `EventRobberyFakeMerchantEnabled` | true | 假商人抢劫（Overgrowth/Underdocks） |
| `EventBackroomsEnabled` | true | Backrooms（Overgrowth/Underdocks） |
| `EventMedusaEnabled` | true | 美杜莎（Hive） |
| `EventCuttingItCloseEnabled` | true | 命悬一线（Overgrowth/Underdocks） |

### 商人猜拳

| 键 | 默认 | 说明 |
|---|---|---|
| `FeatureMerchantBargainEnabled` | true | 商人处的猜拳讨价还价小游戏（仅当前正式版编译） |

### 涅奥起始遗物

| 键 | 默认 | 说明 |
|---|---|---|
| `NeowRelicCurseRemoverEnabled` | true | 诅咒清除器（涅奥起始选项） |
| `NeowRelicWhiteFlagEnabled` | true | 白旗（涅奥起始选项） |
| `NeowRelicMagicGloveEnabled` | true | 魔法手套（涅奥起始选项） |

> 说明：卡牌、事件遗物（杏仁水、美杜莎之发）与附魔（分裂、虚无）**不是**可配置项——
> 它们是事件/遗物/附魔内容的一部分，随所属事件与遗物启用。

## 生效时机与限制

- 配置在每次池生成时读取：修改后**下一次**遭遇池/事件列表求值生效（进入新 Act、新事件池时）。
- 禁用内容**不改变 ModelId 与存档/联机 ABI**：模型仍被 ModelDb 发现（只不进池），旧存档与
  联机哈希保持稳定。
- 联机：同局所有玩家应使用相同配置（内容池不同会导致可见差异；配置本身不参与同步）。
- 强制 Boss 与原版 Boss 的取舍：强制项生效时本幕 Boss 候选仅剩该强制 Boss（原版 Boss 不出现）。
- `Forced=true` 隐含 `Enabled=true`（自动裁决）。

## 校验

- `scripts/verify_project.py` 校验：键常量表（单一来源）与 BaseLib 桥属性名、
  RitsuLib schema 引用、`settings_ui` 本地化键（`STS2_THINGS-<SLUG>.title`，eng+zhs）三者一致；
  Config/ 集成层禁止编译期引用两个库。
- 探针：`tools/ThingsConfigProbe`（默认值/往返/冲突/门控）、`tools/BaseLibBridgeProbe`
  （真实 BaseLib 注册与共享文件）、`tools/RitsuLibInteropProbe`（真实 RitsuLib 互操作注册）。
