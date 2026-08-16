# STS2_Things（尖塔：琐事）

同时支持以下 Slay the Spire 2 分支的原生 Mod 工程：

- 兼容正式版：`v0.107.1`
- 当前正式版：`v0.111.0`

当前 Mod 版本：`1.10.0`。Steam/GitHub 正式产物是同一套统一订阅包，运行时会按游戏 API 自动选择内嵌的 V107.1 或 V111 实现。

## 内容

- Boss：始源雾菇、腐化之遗、缩放巨甲虫、盛碗虫族母
- 精英与遭遇：灵魂鱼子团、抢劫队、怪癖草蜢等
- 事件：Backrooms、假商人抢劫、美杜莎、命悬一线
- 卡牌、遗物、能力与附魔扩展（含战士卡“对撞”与附魔“分裂”）
- 自定义贴图、背景、场景、音效及中英文本地化

## 配置

遭遇战（含 Boss 启用/强制）、事件、商人猜拳与涅奥起始遗物都可独立开关（详见
[docs/CONFIGURATION.md](docs/CONFIGURATION.md)）：

- 已安装 **BaseLib** 或 **RitsuLib** 时，游戏内出现本模组的配置页（两者都不是前置依赖，
  可选的运行时集成；配置写入同一份 `user://mod_configs/STS2_Things.cfg`）。
- 未安装两者时直接编辑该 JSON 文件即可。
- 同一幕的 Boss 槽位最多一个“强制遭遇”项，冲突自动裁决。

## 怪物视觉

- 九个自制怪物场景均使用单一完整 PNG 的 `Sprite2D`。
- 发布贴图逐字节镜像 `source_assets/monsters/` 原画，不做调色、描边、颗粒或亮度处理。
- Spine、分件与骨骼素材保留为编辑源，但构建脚本不会生成或装载骨骼场景。
- 运行时场景不引用 `SpineSprite`、`Skeleton2D`、`Bone2D` 或 `Polygon2D`。
- 怪癖草蜢沿用偷窃草蜢的完整 Spine 动作合同，并使用独立贴图把四段躯体交替绘成高对比钴蓝/亮橙色；原版线稿、明暗、翅膀和肢体色阶保持不变。
- 怪癖草蜢优先偷取诅咒、基础打击/防御，并同步偷走一瓶药水；击杀会把原卡留在牌库并把原药水还至原槽位，逃跑才会永久带走战利品。
- 粉色蝴蝶结是绑定 `head` 的独立后置骨骼挂件，会跟随待机、偷窃、攻击、受击、起飞、悬停、逃跑与死亡动作。

## 环境

- Godot：`4.5.1 Mono`
- .NET：`9.0`
- C#：`13`
- V111 基线：`v0.111.0` / commit `41cef1ea`

工程仅使用游戏原生 API、Godot、Harmony 与官方工具链，不依赖 RitsuLib 或 BaseLib。

## 构建

构建统一发布包：

```powershell
.\scripts\build-all.ps1 `
  -DataDirV1071 "D:\path\to\v0.107.1\data_sts2_windows_x86_64" `
  -DataDirV111 "D:\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64"
```

它会依次编译两套实现、导出一次共用 PCK、构建引导 DLL，并对两套真实游戏程序集执行选择、类型加载、Harmony 与保存缓存探针。追加 `-Install` 可安装统一包。

只构建某个版本的实现用于诊断：

```powershell
.\scripts\build.ps1 `
  -TargetVersion v107.1 `
  -DataDir "D:\path\to\v0.107.1\data_sts2_windows_x86_64" `
  -SourceRoot "D:\path\to\STS2-V107.1"
```

V111 单目标诊断构建：

```powershell
.\scripts\build.ps1 -TargetVersion v111
```

发布工件位于：

- `build/unified/STS2_Things.json|dll|pck`

版本专用诊断/回退构件位于：

- `build/v107.1/STS2_Things.json|dll|pck`
- `build/v111/STS2_Things.json|dll|pck`

统一 manifest 的最低版本为 `v0.107.1`。所有订阅玩家下载完全相同的三件套；引导 DLL 只加载当前游戏对应的实现。多人游戏中的所有玩家仍必须使用相同游戏版本和相同 Mod 构建。

## 项目结构

- `STS2_Things/`：C# 模型、Hook、兼容层与初始化代码
- `bootstrap/`：统一入口、版本指纹检测和内嵌实现注册
- `manifests/`：版本专用诊断 manifest
- `images/`、`scenes/`、`sfx/`、`audios/`：共用 PCK 资源
- `STS2_Things/localization/`：`eng` 与 `zhs` 本地化表
- `scripts/build.ps1`：单目标构建、验证和安装
- `scripts/build-all.ps1`：双实现与统一包构建入口
- `scripts/build-unified.ps1`：引导 DLL、嵌入、探针、安装与打包
- `scripts/verify_project.py`：版本、确定性、Nullable、本地化与资源回归检查
- `docs/DUAL_VERSION_SUPPORT.md`：双版本 API 差异与发布合同
- `docs/UNIFIED_PACKAGE.md`：统一订阅包架构、V107.1 桥接与验证门禁
- `docs/MIGRATION_V110.md`：V110 API 漂移、验证证据与发布工件哈希
- `docs/MIGRATION_V111.md`：V110.1→V111.0 差异、迁移决策与验证证据
- `docs/CONFIGURATION.md`：配置键表、冲突规则与三套配置入口

## License

See [LICENSE](LICENSE).
