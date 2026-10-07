# 灯笼鱼 · 原生 Spine 4.2

最终形态为漂浮鱼类，不含人形手脚。使用 `source_assets/monsters/lantern_fish/floating_fish_final.png` 的原创绘画。

24 根真实骨骼，连续加权网格，10 组动作：`idle_loop`、`attack`、`tail_swipe`、`cast`、`guard`、`hurt`、`die`、`revive`、`summon`、`power_up`。鱼身悬浮、鳍尾摆动、下颌运动与八节灯须分别驱动。连续网格避免分件接缝；鳍部使用宽权重过渡，避免在大幅摆动时翻折。

啄咬接触点为 0.48 秒，甩尾为 0.36 秒，耀闪为 0.72 秒，收灯格挡为 0.42 秒。双击由两次完整的甩尾动作执行，等待前一击的伤害钩子结束，普通／快速／即时速度使用同一套接触点。灯囊的叠加发光网格与身体使用相同顶点和权重，径向强光挂到 `lamp` 原生 SpineBoneNode。

在本目录运行：

```powershell
python parts.py
python -m rigkit build
python -m rigkit export
python package.py
node verify.mjs
python package.py --deploy
```

Python 依赖 `Pillow`、`numpy`、`opencv-python`；几何验证复用 `../ScaleBeetleRig/runtime.mjs` 和该目录已锁定的官方 `@esotericsoftware/spine-core` 4.2.43。无需 Spine 编辑器。`rigkit.py`、`rigutil.py` 独立复制，修改本目录不改变其他怪物。

`verify.mjs` 在官方运行时采样 982 帧，检查全部动作、有限坐标、网格翻折、待机闭环、死亡／复起衔接、发光层贴合和接触事件。最新报告为 `pkg/verification.json`。

新画通过用户指定接口，以 imagegen 技能的 CLI Image API `gpt-image-2` / high 生成。完整最终提示词为 `floating_lantern_fish_prompt.txt`。原版 `soul_fysh.png` 仅作为画风参考，最终角色是重新生成的像素。`refine_alpha.py` 只修正抠图：保留原始绘画内部不透明度，边界沿用软抠图，避免青绿色皮肤和米黄色腹部被错误变透明。重建不需要 API 或密钥。

早期人形设计保存在 source_assets 中作为制作记录，运行时仅引用最终纯鱼形资产。导出排除了 source_assets 与工具目录。
