# 血蛭之母 Spine 维护源

采用宽腹、低伏兜头、三瓣厚吸盘与小金色眼缝，区分现有小血蛭。选定原画和生成记录位于 `source_assets/monsters/leech_mother/`；第一版仅为比较保留，不用于运行资源。

该骨架有 19 根骨骼、整体蒙皮及双眼皮三个加权网格，包含睡眠、苏醒、待机、吸附攻击、压击、召唤、施法、蜷缩、强化、受击、死亡和退场十二套动作。

从项目根目录运行 `scripts/prepare_leech_mother.py` 准备分件；随后在本目录依次运行 `python rigkit.py build`、`python rigkit.py export`、`python verify.py` 和 `python package.py`。骨架与动作定义分别在 `rigdef.py`、`anims.py`。需要 Python、Pillow、NumPy 和 OpenCV。这些制作脚本会写入维护源、场景或运行资源，重建后应查看 diff，再重新构建完整包。

`render_native.gd` 在项目 Godot／Spine 环境中输出连续帧和动作混合片段；参数为输出目录及可选 FPS。离线帧检查不能替代实际动作与画风审核。历史制作记录中，1416 帧无蒙皮翻面，睡眠闭环、睡→醒及收招姿态连续；原生渲染补查了 506 帧及混合片段。

运行资产位于 `STS2_Things/animations/monsters/leech_mother/`，玩法与边界测试入口为 `scripts/test-leech-mother.ps1`。最终发布验证与机制见 `docs/release-1.25.13.md`。`out/`、`pkg/` 和预览目录是生成物，不提交 Git。
