# 垂丝蛾 Spine 4.2

22 骨骼、9 动作。两片破布翅使用独立网格，头腹、眼睛、触角、短足和三条垂丝使用连续蒙皮；根部蓄力、翅尖跟随与丝结延迟摆动分别控制。

源图与提示词在 `source_assets/monsters/silk_moth/`，使用用户指定的 `gpt-image-2.5-sunburst`。

重建：运行 `scripts/prepare_silk_moth_assets.py`，再在本目录执行 `python -m rigkit build`、`python -m rigkit export`、`python package.py`、`node verify.mjs`。验证后用 `python package.py --deploy` 更新运行资源。

`rigkit.py`、`rigutil.py` 是项目既有工具的独立副本。原生实际帧用于形象、分层接缝和动作审核，官方 Spine 的采样报告用于检查蒙皮翻折与循环连续性。
