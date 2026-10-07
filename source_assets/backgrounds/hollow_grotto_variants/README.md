# 洞穴场景变种 · r02

> 三套变种的地面现已改为全新生成绘景。请使用相邻目录 `../new_cave_floors/` 的最新资源包与说明；本目录旧交付包和下文记录保留作历史版本。

在「幽蓝溶洞」基础上制作的三个完整场景变种。继续使用 `STS2-V111` 原版绘景的拆分、调色与重新构图，保留原版分层加载、BPTC 贴图和原生雾效流程。

| 变种 | 特征 | 场景 ID |
|---|---|---|
| 苔光岩窟 | 较低的岩拱，开阔的内部空间，苔色地面、少量植物与萤光 | `hollow_grotto_moss` |
| 余烬石窟 | 暖褐龟裂地面，重排的大岩柱和破碎岩棚，缓慢上升的余烬 | `hollow_grotto_ember` |
| 紫雾深窟 | 不对称高柱、较窄的通道、碎石地面和紫色薄雾 | `hollow_grotto_violet` |

三个版本都调整了岩体位置、洞顶轮廓、地表和环境效果。上一版幽蓝溶洞在独立预览工程中保留为对照。

## 交付内容

- `delivery/hollow_grotto_variants.zip`：工作区中的完整交付包。
- `delivery/hollow_grotto_variants.pck`：三套变种的合并素材包。
- `review/final/variants_comparison.jpg`：三款变种与上一版的对照图。
- `review/final/hollow_grotto_*.png`：1920 × 1080、2560 × 1080 和 1440 × 1080 的实际渲染结果。
- `STYLE_AUDIT.md`：退回修改与终版自审记录。
- `preview_project/project.godot`：可独立打开的 Godot 预览工程。

每个变种有五张 2048 × 960 RGBA 绘景、五个图层场景和一个背景入口，共 15 张绘景、18 个场景文件。第 00 层是完全不透明底图，其余四层保留 alpha。

ZIP 解压后的 `runtime/` 对齐模组 Godot 项目根目录，合并后可按原有流程导入和导出。ZIP 中的 PCK 位于根目录；重建源码在 `source/`。

## 预览切换

用标准版 Godot 打开 `preview_project/project.godot`，完成导入后运行。

- `1` / `2` / `3`：苔光 / 余烬 / 紫雾。
- `4`：上一版幽蓝溶洞。
- 左右方向键：依次切换方案。
- `F`：切换环境光、雾与微粒。
- `Esc`：退出。

独立预览只使用 GDScript，不依赖游戏的 C# 服务。实际素材、截图和 PCK 使用 Godot 4.5.1 / D3D12 / Forward Mobile 验证。建议向游戏导出时使用对应的 4.5.1。使用本机 Mono 编辑器导入时可能出现之前记录的 .NET SDK 环境提示；纯 GDScript 预览可用标准版 Godot 打开。

## 游戏资源入口

以 `STS2_Things` 为项目根目录，三套入口分别是：

```text
res://scenes/backgrounds/hollow_grotto_moss/hollow_grotto_moss_background.tscn
res://scenes/backgrounds/hollow_grotto_ember/hollow_grotto_ember_background.tscn
res://scenes/backgrounds/hollow_grotto_violet/hollow_grotto_violet_background.tscn
```

入口保留游戏的 `NCombatBackground.cs`，四个背景槽位为 `Layer_00` 至 `Layer_03`，另有 `Foreground`。坐标、2764.8 × 1296 的绘景尺寸、23 像素背景容器偏移和绘制顺序都与已审核方案一致。

使用独立场景 ID **整套切换**。不要把不同色系直接改成同一背景的 A/B/C 图层：原版会逐层随机选择，可能把不同配色的岩壁和地面混搭。

PCK 仅加入三个新的资源命名空间，依赖游戏提供的 `NCombatBackground.cs` 以及 `images/vfx/fog_sheet_1.png`、`light.png`、`dot.png`。它是素材包，尚未绑定到某个实战遭遇；现有模组的场景选择逻辑没有被修改。

## 重建与来源

`variants_manifest.json` 记录配色、原版素材 SHA-256 和场景 ID。重建源码保留 `hollow_grotto_variants` 与 `hollow_grotto` 两个相邻目录；放回本项目的 `source_assets/backgrounds/` 后运行：

```powershell
python build_variants.py
```

接着导入预览工程，使用正常 GPU 渲染进程运行，并传入 `--fixed-fps 60 -- --capture=完整路径/review/native_r02`。完成后：

```powershell
python finalize_variants.py review
```

该命令生成对照图、校验结果和 `pack_manifest.json`。用 4.5.1 的 `pack.gd` 生成 `delivery/hollow_grotto_variants.pck` 后，运行 `python finalize_variants.py package` 生成 ZIP 并逐项校验 SHA-256。

制作方法是原版绘景素材重组，没有使用 AI 生图；原版图像来源于本项目解包文件。新资产的五层源文件与重建代码均保留，便于后续调整。
