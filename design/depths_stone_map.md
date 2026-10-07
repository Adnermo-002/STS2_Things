# 深处大地图：石板

用户要求大地图使用专属石板，并自然连贯。曾按反馈制作简化化石版；**最新选择为恢复第一版**，运行资源和选用记录均已切回第一版。

当前使用第一版的浅蓝灰石面、风化边缘和细微矿物纹理，内部保留路线可读性。第二版的菊石／鱼骨方案仅作为备选源素材保留。

## 原生接入

保持 `Depths` 原有路径与地图颜色，替换 `images/packed/map/map_bgs/depths/` 下的上、中、下三张 PNG。
原版 `NMapBg` 使用无间距 VBoxContainer，三张 TextureRect 的最小高度均为 1080，`EXPAND_IGNORE_SIZE`、`KEEP_ASPECT_CENTERED`。

制作时先将一整块石板归一化为 2036×4320，再按相邻区域裁成三张 2036×1440。色彩、比例和透明边缘只在母图上统一处理；切开后不对各段分别缩放、调色或羽化。
重组图与母图逐像素相同。原生 Godot 渲染对照中，三段拼接与整张绘制最大差异为一个 8-bit 色阶，两条接缝没有额外色带。

## 文件与重建

- 选用记录：`source_assets/backgrounds/depths_stone_map/selection.json`。
- 提示词：`source_assets/backgrounds/depths_stone_map/prompt.txt`。
- 最终母图：`source_assets/backgrounds/depths_stone_map/stone_master_final.png`。
- 重建：`python scripts/build_depths_stone_map.py --deploy`。
- 渲染检查：`scripts/test-depths-stone-map.ps1`。
- 打包：`python scripts/package_depths_stone_map.py`。

`prepare_depths_assets.py` 已接入选定的石板重建步骤，避免后续准备整章时重新生成旧的淡化洞穴背景。
替换前的三张贴图保存在 `build/depths_stone_map/before`。初稿仍保留在源素材目录。

生成方式为用户指定接口上的 imagegen CLI `gpt-image-2/high`。原版巢穴地图仅用作画风和长图构图参考，没有复制到最终石板。
交付中的路线图为原版图标可读性示意；Godot 验证针对原版背景容器的实际尺寸、缩放和分段拼接，没有创建或修改玩家存档。

## 完整模组集成（2026-10-04）

核对发现此前 `build/unified` 与游戏安装目录的 PCK 仍包含旧地图，三段导入资源均与选定的第一版不符。已重新导入、导出完整 PCK，沿用当前 1.11.2 的统一入口 DLL 与可选 BaseLib 桥。

- 包内核对：在隔离工程挂载最终 PCK，三段均能以 2036×1440 加载；导入纹理与工程选定资源逐字节一致。
- 原生渲染：从最终 PCK 加载，使用与原版相同的背景布局，104 项检查通过。完整母图应用相同的 `fix_alpha_border` 导入处理后，分段和整图最大差异为 1/255；两条接缝同为 1/255。
- 章节加载：v107.1 / v111 原生探针分别通过 753 / 754 项检查；统一入口各识别 83 个模型。
- 完整包：`build/depths_stone_map/delivery/STS2_Things_Depths_Stone_Map_v1_1.11.2.zip`。
- 详细记录：`build/depths_stone_map/integration/verification.json`；源贴图资源包继续单独保留。

使用 `scripts/verify_depths_map_pck.gd` 从隔离 Godot 项目核对包内贴图。`scripts/test-depths-stone-map.ps1` 支持 `-PackagePck` 与 `-OutputDir`，可直接检查准备交付的 PCK。通过检查后运行 `scripts/package_depths_stone_map_integrated.py` 整理完整包。

本地安装由 STS2 Workbench 备份并更新；备份地址记录在 `build/depths_stone_map/integration/install-result.json`。截图仍是隔离布局与示意路线，不代表实际存档中的完整 `NMapScreen` 验证。

实际 v0.111.0 启动已确认：1.11.2 模组完成初始化，桥接在线，画面进入主菜单。未继续现有对局，检查后正常关闭本次启动的游戏窗口。`integration/startup-check.json` 与 `startup-main-menu.png` 保存证据；日志中第三方联机模组的信号断连及 Godot 预加载 `Invalid Task ID` 另行记录，不将此描述为全游戏零错误测试。

## 1.11.3 实机地图复核

上述 1.11.2 记录之后，修复了横路在章节切换时读取等待删除的旧节点而造成黑屏的问题。第一版石板资源保持相同，现已在真实 `NMapScreen` 中查看底、中、顶三段及首领区域，检查滚动与拼接。实机截图位于 `build/act_map_black_screen/map-bottom`、`map-middle`、`map-top`，操作步骤和复现记录见 `docs/act-map-black-screen-20261004.md`。
