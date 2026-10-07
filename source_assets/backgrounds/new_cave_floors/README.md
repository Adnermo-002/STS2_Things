# 全新洞穴地面 · 已完成

> 最新版本新增四套不同洞穴，并将本页四套场景提亮。请使用相邻目录 `../cave_diversity/` 的八套明亮版资源包；本目录交付保留作提亮前的历史版本。

本修订对应最新要求：四套洞穴方案的地板全部使用独立生成的新绘景。生成输入只提供洞壁布局与岩体笔触参考，没有提供原版地板。此前的资产包保留作历史版本，新的交付以本目录的 ZIP 和 PCK 为准。

四幅新地面已生成、接入场景并完成 Godot 实渲自审。每个运行时 `_00.png` 与对应的新地面源图逐像素一致，没有叠加旧地表纹理、拼缝或旧地板。洞壁、石柱、洞顶与前景仍使用上轮独立图层。

| 方案 | 新地面设计 |
|---|---|
| 幽蓝溶洞 | 连续水蚀板岩，斜向侵蚀沟、少量淤积与圆砾；没有人工石板铺装 |
| 苔光岩窟 | 平滑石灰岩与暗土自然过渡，稀疏苔岛；没有复用蔓生遗迹的石板或植物形状 |
| 余烬石窟 | 冷却岩流的长条褶皱、碎薄壳与少量炭屑；没有蜂巢六边格或规则多边形铺装 |
| 紫雾深窟 | 自然片岩薄层、细矿脉、边缘碎片；没有辉煌场景的砌石拼缝 |

## 成品与预览

工作区中的成品是 `delivery/cave_region_new_floors.zip` 和 `delivery/cave_region_new_floors.pck`。ZIP 根目录内含 PCK；`runtime/` 可对齐现有模组项目根目录合并；`preview_project/` 为独立预览工程。

- `review/final/new_floor_scenes.jpg`：四套完整场景的实际渲染对照。
- `review/final/new_floor_paintings.jpg`：四张新地面绘景的单独对照。
- `review/final/`：三种画幅的完整截图与验证数据。
- `generated/`：四张 2048 × 960 RGBA 新地面源图。
- `STYLE_AUDIT.md`：画风、结构与原版地板移除检查。

ZIP 内的预览图位于 `review/final/`，源地面、原始生成结果、提示词、参考和生成记录位于 `source/new_cave_floors/`。

打开 `preview_project/project.godot` 后运行：`1` 苔光、`2` 余烬、`3` 紫雾、`4` 幽蓝；左右方向键循环选择，`F` 切换环境效果，`Esc` 退出。独立预览使用 GDScript，不需要游戏 C# 服务。

## 画风与接入规格

- 四幅分别生成独立构图，不能用一幅图换色充当四种新地面。
- 原版参考只用于手绘描线、色面层次、笔触密度、低明度和地面透视。
- 新绘景整体为 2048 × 960 的不透明 PNG，包含地表及上方自然消隐的暗色空气。
- 不画岩壁、石柱、钟乳石或前景岩脊；这些已有独立图层。
- 战斗区域保持平整低干扰，把大部分地质细节放在边缘与近处。
- 新图片直接成为各场景 `_00.png`，没有再叠加旧地板、旧拼缝或旧地表纹理。
- 两个绘景构建配方已经改成只读取新地面输入；缺失时会报错，不会回退到原版地板。
- 仍使用原版 2764.8 × 1296 的绘景显示尺寸、BPTC 压缩与五层场景结构。游戏入口保持 `NCombatBackground.cs`，背景动态雾和微光由原生材质/粒子渲染。

合并 PCK 包含四套场景的 84 项资源，依赖原版游戏的背景脚本和公共雾、光斑、微粒贴图。新地面已接入项目资源，但没有修改遭遇选择逻辑，也没有启动真实战斗。

## 文件

`generation_brief.json` 包含四个绘制任务、参考图路径、新图路径和运行时目标。

`prompts/` 是可直接用于图像生成的四份提示词。

`references/` 只含去掉当前第 00 层后的洞壁布局，以及原版岩体笔触样本，不含原版地板。

`check_floor_inputs.py` 检查四幅是否齐备、尺寸、透明度和是否为原版文件的精确复制。`finalize_new_floors.py` 另外验证运行时地面与新源图像素一致，以及绘景配方没有原版地板依赖。它们与视觉审查配合使用，不把哈希检查当成原创性的单独证明。

## 生成方式与复现

通过用户指定的 OpenAI 兼容 API，以 imagegen 技能附带的 CLI 执行参考图条件生成：请求模型 `gpt-image-2`、`quality=high`、不透明 PNG。四张分别请求生成，不是同一张的调色版本。完整提示词保存在 `prompts/`，参数和文件哈希记录在 `generation_provenance.json`。

服务返回的画幅接近目标比例；为匹配原生贴图画布，使用 Lanczos 统一到 2048 × 960 并转为不透明 RGBA，没有混入旧地面。服务原始输出也保留在交付包中，原始尺寸见生成记录。

复用已生成的源图重建时，把 ZIP 的 `source/` 三个子目录放回 `STS2_Things/source_assets/backgrounds/`。先运行 `hollow_grotto/build_art.py`、`hollow_grotto/build_scene.py` 和 `hollow_grotto_variants/build_variants.py`；然后导入变种预览工程，使用正常 GPU 渲染进程和 `--fixed-fps 60 -- --capture=本目录/review/native_r01` 截图，再运行 `finalize_new_floors.py review`。

审核命令生成 `pack_manifest.json`。用 Godot 4.5.1 运行 `pack.gd` 将清单打包到 `delivery/cave_region_new_floors.pck`，保存通过日志后运行 `finalize_new_floors.py package`。游戏资源导出请保持对应的 Godot 版本。

API 凭据没有写入工程、提示词、生成记录或交付文件。
