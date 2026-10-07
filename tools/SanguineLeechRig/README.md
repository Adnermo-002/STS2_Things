# 吸血血蛭 Spine 4.2

连续蒙皮来自原创 `source_assets/monsters/sanguine_leech/character_final.png`，17 骨骼、10 动作，嘴唇／双眼／颈部／腹部／卷尾独立驱动。

1.12.4 细化颈部与腹部的波动传递、攻击吸附停留和吞咽节奏，并补偿身体位移，保持后吸盘贴地。逐帧验证新增动作结束回位、攻击方向和后吸附点漂移检查。

在本目录运行 `python -m rigkit build`、`python -m rigkit export`、`python package.py`、`node verify.mjs`，验证通过后 `python package.py --deploy`。
`rigkit.py` 和 `rigutil.py` 来自本项目既有工具的独立副本，修改本目录不影响其他怪物。

官方 Spine 4.2.43 采样报告位于 `pkg/verification.json`。该检查针对实际运行时蒙皮、动画连续性、有限坐标、事件与三角形翻折；画风和战斗尺寸以原生视觉探针为准。

具体玩法、美术来源与自审见 `design/sanguine_leech.md`。
