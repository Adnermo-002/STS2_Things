# 织茧巨蛾 Spine 维护源

原画与生成记录：`source_assets/monsters/great_silk_moth/`。使用已有小蛾作为形体与笔触参考，新增奶白绒领、淡紫宽翅、羽状触角和两枚丝茧。

从项目根目录运行分件准备：

```powershell
python scripts/prepare_great_silk_moth.py
```

在本目录重建、检查并部署：

```powershell
python -m rigkit build
python -m rigkit export
python verify.py
python package.py
```

`rigdef.py` 保存 39 根骨骼及 8 个加权网格的绑定；`anims.py` 保存九个动作与攻击、丝束释放的时机。两个前肢都有独立肘节，连接丝同时跟随远侧抓握点和近侧丝茧。烘焙惯性区分触角、茧和尾丝；大翼根保留遮挡重叠，完整触角归属头部，避免转动时裂缝或碎片。

离线动作审查示例：

```powershell
python -m rigkit render cast 0,20,37,49,70,92 cast
python -m rigkit render die 0,20,48,76,104 die
```

`verify.py` 检查全部离线采样帧的加权三角形方向、权重归一、回位、待机闭环及死亡到复苏的接续；它不能代替原生渲染或画风判断。

`render_native.gd` 在项目的 Spine 插件中捕获九套动作与攻击／施法／扑翼／受击回待机的实际混合：

```text
godot --path <项目根目录> --script res://tools/GreatSilkMothRig/render_native.gd -- <输出目录>/native 20
python tools/GreatSilkMothRig/make_native_preview.py <输出目录>
```

最终资产位于 `STS2_Things/animations/monsters/great_silk_moth/`，游戏接入场景为 `scenes/creature_visuals/great_silk_moth.tscn`。初版机制见 `docs/great-silk-moth-20261008.md`；当前精修与原生预览见 `docs/great-silk-moth-animation-polish-20261008.md`。
