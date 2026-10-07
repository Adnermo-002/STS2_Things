# 幽蓝溶洞 · Hollow Grotto

> 地面已按最新要求改为 API 全新绘景。当前交付与重建说明见相邻目录 `../new_cave_floors/README.md`；本文及旧 `delivery/` 包记录的是此前的原版素材重组版本。

洞穴主题的《杀戮尖塔 2》战斗背景资产，参考本项目 `STS2-V111` 的实际背景资源与加载代码制作。终版为 r04，完成日期为 2026-10-03。

这是**原版绘景素材的拆分、调色与重新构图**：洞壁、石笋、钟乳石、岩脊和地面沿用原版画师的笔触。没有使用 AI 生图。素材来源及 SHA-256 记录在 `asset_manifest.json`，所有变换可由 `build_art.py` 重建。

## 直接查看

- `review/final/hollow_grotto_native.png`：1920 × 1080、含动态效果的 Godot 原生渲染帧。
- `review/final/style_comparison.jpg`：新场景与三套原版场景的同渲染器对照。
- `review/final/layer_breakdown.jpg`：五层绘景拆解。
- `STYLE_AUDIT.md`：退回重做的原因、终版视觉自审与验证结果。
- `delivery/hollow_grotto_scene_assets.zip`：完整交付包。
- `delivery/hollow_grotto.pck`：约 10.5 MiB 的游戏素材包。

以上是本工作区目录。解压交付 ZIP 后，PCK、说明和重建脚本在压缩包根目录；可合并到模组项目的文件在 `runtime/`，独立预览在 `preview_project/`。

## 项目内的运行时资源

以 `STS2_Things` 为 Godot 项目根目录：

| 资源 | 路径 / 用途 |
|---|---|
| 背景入口 | `scenes/backgrounds/hollow_grotto/hollow_grotto_background.tscn` |
| 原版加载脚本 | `res://src/Core/Nodes/Rooms/NCombatBackground.cs`，由游戏提供 |
| 图层目录 | `scenes/backgrounds/hollow_grotto/layers/`，四层背景加一层前景 |
| 绘景贴图 | `images/rooms/hollow_grotto/`，五张 2048 × 960 PNG |
| 动态效果 | `Layer_01` 中的微光、两组低速雾、16 个微粒 |

图层职责依次为：远处空气和地面；远景岩群与效果；中景洞壁；洞顶、钟乳石与碎石；近处岩脊。第 00 层完全不透明，另外四张保留真正的 alpha。贴图均按原版使用 BPTC 高质量压缩，不生成 mipmap，不预乘 alpha，不修补 alpha 边缘。

PCK 只新增 `hollow_grotto` 命名空间，保留对游戏原版 `NCombatBackground.cs` 和 `images/vfx/{fog_sheet_1,light,dot}.png` 的依赖。它是场景素材包，不是会自动更换战斗背景的独立模组。

## 沿用的原版渲染流程

1. `BackgroundAssets.cs` 扫描 `layers/`，按 `_bg_00_`、`_bg_01_` 等前缀分组并排序，另外选择 `_fg_` 图层。
2. `NCombatBackground.Create()` 实例化根场景，依次把图层加到 `Layer_00` 至 `Layer_03` 和 `Foreground` 槽位。
3. 2048 × 960 的透明绘景在 `TextureRect` 中显示为 2764.8 × 1296，即原版常用的 1.35 倍尺寸；以中心为原点，偏移范围为 `(-1382.4, -648)` 至 `(1382.4, 648)`。
4. 原版 `combat_room.tscn` 把 `BgContainer` 居中，并向右偏移 23。预览同样保留这个偏移。背景画幅超出标准 1920 × 1080 视口，覆盖扩展画幅。
5. 普通绘景使用 alpha 混合；雾、微光和微粒使用原版 `CanvasItemMaterial` 的加色混合。雾保持原版 1 × 3 帧图集设置，由 `CPUParticles2D` 缓慢漂移。
6. 整个 `BgContainer` 位于角色容器之前；`Foreground` 是背景内部最后一层。它没有被提到角色、意图图标或战斗 UI 之上。

参考实现包括 `STS2-V111/src/Core/Rooms/BackgroundAssets.cs`、`src/Core/Nodes/Rooms/NCombatBackground.cs`、`scenes/rooms/combat_room.tscn`、`scenes/backgrounds/underdocks/`、`overgrowth/` 和 `glory/`。这套干燥洞穴不需要水面反射；原版加色材质已经能表达雾和微光。

## 预览

用标准版 Godot 打开本目录的 `preview_project/project.godot`，等待首次贴图导入，按 F6/F5 运行 `preview.tscn`。游戏资源和截图使用 4.5.1 制作；独立预览同时验证了本机标准版 4.6.1。预览不需要 .NET SDK。

- `1`—`5`：切换五个绘景平面。
- `F`：切换雾、微粒与微光。
- `R`：恢复全部显示。
- `Esc`：退出。

预览工程内包含所需的绘景和原版公共效果资源，能够独立运行。仅在这个独立工程的根场景副本中移除了游戏 C# 生命周期脚本，改由 `preview.gd` 按相同槽位组装实际图层。游戏用入口保持原版脚本引用。向游戏导出资源包请仍使用游戏对应的 Godot 4.5.1。

复现批量截图：

```powershell
& $GodotExe --headless --editor --path $PreviewProject --import --quit
& $GodotExe --path $PreviewProject --rendering-method mobile --rendering-driver d3d12 --fixed-fps 60 -- --capture=C:/your-output-folder
```

截图应使用有 GPU 的正常渲染进程；`--headless` 仅用于导入和资源包校验。

## 接入

ZIP 中的 `runtime/` 与现有 Godot 项目根目录对齐，先导入再按模组原有流程导出资源包。也可以在原版游戏资源之后挂载随附 PCK。资源需要进入游戏的预加载缓存，随后可按原版方式构建：

```csharp
var assets = new BackgroundAssets("hollow_grotto", rng);
var background = NCombatBackground.Create(assets);
```

现有 `EncounterModel.HasCustomBackground` 的自动路径使用 `Id.Entry.ToLowerInvariant()`。若通过这个自动流程接入一个已有遭遇，请把场景目录、场景文件名前缀和入口名称配成该遭遇 ID，同时保留 `Layer_00`—`Layer_03` / `Foreground` 槽位。`layers/` 里只放图层场景，不放说明文件或子目录。

本次新增了资产，没有改动已有洞穴之神或其他遭遇的选择逻辑。运行时渲染、三种画幅和 PCK 加载已验证；尚未将新背景接入一场真实战斗。

## 重建

在本工作区保留 `STS2-V111` 和 `STS2_Things` 的相邻目录结构，Python 安装 Pillow、numpy 后运行：

```powershell
python build_art.py --revision r04
python build_scene.py
```

按上面的 Godot 命令导入并渲染到 `review/native_r04` 后，运行 `python review_assets.py`。它输出对照图、分层图、透明度校验、灰度诊断、效果运动验证，并将成功导入的贴图元数据同步到运行时目录。

`python package_assets.py --prepare-pack` 生成 `pack_manifest.json` 并把 `pack.gd` 放入预览工程，然后调用：

```powershell
& $GodotExe --headless --path $PreviewProject --script res://pack.gd -- $PackManifest $OutputPck
```

其中清单是本目录的 `pack_manifest.json`，输出为 `delivery/hollow_grotto.pck`。最后运行 `python package_assets.py` 整理 ZIP 和校验清单。

完整交付包包含可编辑源码；重建脚本从其在本项目中的位置解析路径。如果从 ZIP 取出源码重建，请放回 `STS2_Things/source_assets/backgrounds/hollow_grotto/`。
