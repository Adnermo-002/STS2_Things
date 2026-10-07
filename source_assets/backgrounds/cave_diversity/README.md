# 多样洞穴 · 八套明亮版

新增四个结构明显不同的洞穴场景，并将之前四套已采用全新地面的场景提亮。新增洞体、地面及画面内的岩石、晶簇和菌根都通过用户指定 API 独立生成，原版绘景只作画法参考。

| 预览键 | 场景 | 特征 / 资源 ID |
|---|---|---|
| 1 | 天隙岩厅 | 破顶天光、石灰岩拱、开阔岩台；`cave_skylight` |
| 2 | 回水石湾 | 地下河湾、低岩檐、干燥战斗平台；`cave_riverbend` |
| 3 | 白晶裂窟 | 乳白晶簇、断层岩壁、细砂地表；`cave_quartz` |
| 4 | 根垂菌洞 | 垂落根须、巨型菌伞、土岩地面；`cave_rootfungus` |
| 5 | 幽蓝溶洞 · 提亮版 | 保留已生成的水蚀岩床；`hollow_grotto` |
| 6 | 苔光岩窟 · 提亮版 | 保留已生成的石灰岩与苔土；`hollow_grotto_moss` |
| 7 | 余烬石窟 · 提亮版 | 保留已生成的冷却岩流；`hollow_grotto_ember` |
| 8 | 紫雾深窟 · 提亮版 | 保留已生成的层状片岩；`hollow_grotto_violet` |

## 交付

工作区成品位于 `delivery/cave_region_diverse_readable.zip` 和 `delivery/cave_region_diverse_readable.pck`。

ZIP 中 `runtime/` 对齐模组 Godot 项目根目录；`preview_project/` 是独立预览工程；根目录 PCK 是八套场景的合并素材包。场景没有自动绑定到实战遭遇，接入方式继续沿用项目的背景资源加载流程。

- `review/final/new_caves.jpg`：新增四套的实际渲染对照。
- `review/final/existing_caves_brighter.jpg`：现有四套的提亮版本。
- `review/final/brightness_before_after.jpg`：原先亮度与本次亮度并排比较。
- `review/final/`：各场景 1920 × 1080、2560 × 1080、1440 × 1080 的实渲结果。

ZIP 内上述预览文件位于 `review/`。源图、提示词与生成记录位于 `source/cave_diversity/`。

## 提亮方式

提亮是真正的场景材质调整，已进入运行时资源包，不只是修改预览截图。材质仅挂在背景绘景的 `TextureRect`，不会套到角色或战斗 UI。

原有四套使用 `cave_readable_existing.tres`：中间调 gamma 为 0.82，曝光系数 1.03。保留真黑和贴图 alpha，主要提升岩壁、地面和远景的可读性。实际画面灰度中位数提高到原先的约 1.47–1.53 倍；这是截图像素值诊断，不是显示器物理亮度测量。

新增场景在绘制时已使用更清楚的环境光，再以 `cave_readable_new.tres` 的 gamma 0.96 做轻微调整。天光、河湾、矿洞和菌洞保留各自的自然明暗关系。

调整强度可编辑 `materials/backgrounds/` 下的两份材质；shader 位于 `shaders/backgrounds/cave_readability.gdshader`。

## 图层结构

原有四套保留五个绘景层和原生效果。本次新增四套使用三层：

1. `Layer_00`：完整原创新绘景，包含洞体和全新地面。
2. `Layer_01`：原生薄雾、微光与空气微粒。
3. `Foreground`：从同一幅新绘景提取的静态前景遮雾层，让环境效果位于近景边缘之后。

前景层是用于静态合成的遮挡层，并没有补画移开前景后被遮住的内容。它不应当作可任意移动的独立道具或视差层。河水和瀑布属于绘景，动态部分是雾与微粒。

各入口仍使用原版 `NCombatBackground.cs`、相同的图层扫描命名方式、2764.8 × 1296 绘景显示尺寸及 23 像素背景容器偏移。原版加载器支持可变的背景图层数量。PCK 依赖游戏的背景脚本和公共雾、光斑、微粒纹理。

## 预览与重建

用标准版 Godot 打开 `preview_project/project.godot`，导入后运行。`1`—`8` 直接切换场景，左右方向键循环，`F` 切换环境效果，`Esc` 退出。

本次素材与实渲使用 Godot 4.5.1 / D3D12 / Forward Mobile 验证。向游戏导出资源包时应使用游戏对应版本。

在本项目中执行 `python build_scenes.py` 会重新标准化新绘景、制作静态前景遮挡、生成场景、为旧场景重新挂接提亮材质，并组装八套预览工程。原始绘景不会被反复烘焙提亮。

导入预览工程后，以正常 GPU 渲染进程运行，并传入 `--fixed-fps 60 -- --capture=本目录/review/native_r01`。随后运行 `python finalize.py review`；用 `pack.gd` 将生成的 `pack_manifest.json` 打包到 `delivery/cave_region_diverse_readable.pck`，保存通过日志后运行 `python finalize.py package`。

若先运行了之前版本的场景生成脚本，最后请再执行本版 `build_scenes.py` 或 `brighten_existing.py`，以保留提亮材质。旧资源包与之前审核报告保留作历史版本。

## 生成与审核

使用 imagegen 技能附带 CLI，通过用户指定的 OpenAI 兼容 API 请求 `gpt-image-2`，高质量、不透明输出。原始生成结果保留；尺寸统一到 2048 × 960，来源与哈希见 `generation_provenance.json`。

完整提示词集在 `prompts/`：四份初稿请求，以及天隙、白晶、菌洞的构图修订请求。天隙开口和两组主要晶簇 / 菌伞经过重新构图，确保游戏居中裁切后仍可见。

自审与运行时验证结果见 `STYLE_AUDIT.md` 和 `review/final/validation.json`。本次未启动真实战斗，也未修改遭遇选择逻辑。
