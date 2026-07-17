# STS2_Things（尖塔：琐事）

同时支持以下 Slay the Spire 2 分支的原生 Mod 工程：

- 正式版：`v0.107.1`
- 测试版：`v0.109.0`

当前 Mod 版本：`1.6.1`。项目包含版本专用 DLL、版本专用 manifest 和共用 PCK。

## 内容

- Boss：始源雾菇、腐化之遗、缩放巨甲虫、盛碗虫族母
- 精英与遭遇：灵魂鱼子团、抢劫队等
- 事件：Backrooms、假商人抢劫、美杜莎
- 卡牌、遗物、能力与附魔扩展
- 自定义贴图、背景、场景、音效及中英文本地化

## 怪物视觉

- 九个怪物场景均使用单一完整 PNG 的 `Sprite2D`。
- 发布贴图逐字节镜像 `source_assets/monsters/` 原画，不做调色、描边、颗粒或亮度处理。
- Spine、分件与骨骼素材保留为编辑源，但构建脚本不会生成或装载骨骼场景。
- 运行时场景不引用 `SpineSprite`、`Skeleton2D`、`Bone2D` 或 `Polygon2D`。

## 环境

- Godot：`4.5.1 Mono`
- .NET：`9.0`
- C#：`13`
- V109 基线：`v0.109.0` / commit `c12f634d`

工程仅使用游戏原生 API、Godot、Harmony 与官方工具链，不依赖 RitsuLib 或 BaseLib。

## 构建

默认构建当前测试版：

```powershell
.\scripts\build.ps1 -TargetVersion v109
```

构建正式版时必须指向 `v0.107.1` 的真实程序集目录：

```powershell
.\scripts\build.ps1 `
  -TargetVersion v107.1 `
  -DataDir "D:\path\to\v0.107.1\data_sts2_windows_x86_64" `
  -SourceRoot "D:\path\to\STS2-V107.1"
```

一次构建两个版本：

```powershell
.\scripts\build-all.ps1 `
  -DataDirV1071 "D:\path\to\v0.107.1\data_sts2_windows_x86_64" `
  -DataDirV109 "D:\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64"
```

只验证 DLL 时可追加 `-SkipPck`。构建并安装单一目标版本：

```powershell
.\scripts\build.ps1 -TargetVersion v109 -Install
```

发布工件分别位于：

- `build/v107.1/STS2_Things.json|dll|pck`
- `build/v109/STS2_Things.json|dll|pck`

两个版本使用相同 Mod ID。每个游戏安装目录只能放入与该游戏分支对应的一套工件；多人游戏中的所有玩家还必须使用相同游戏分支和相同 Mod 构建。

## 项目结构

- `STS2_Things/`：C# 模型、Hook、兼容层与初始化代码
- `manifests/`：正式版和测试版的目标 manifest
- `images/`、`scenes/`、`sfx/`、`audios/`：共用 PCK 资源
- `STS2_Things/localization/`：`eng` 与 `zhs` 本地化表
- `scripts/build.ps1`：单目标构建、验证和安装
- `scripts/build-all.ps1`：双版本构建入口
- `scripts/verify_project.py`：版本、确定性、Nullable、本地化与资源回归检查
- `docs/DUAL_VERSION_SUPPORT.md`：双版本 API 差异与发布合同
- `docs/MIGRATION_V109.md`：V109 API 漂移、验证证据与发布工件哈希

## License

See [LICENSE](LICENSE).
