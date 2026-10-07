# 放缩巨甲虫 · Native Spine 4.2

保留 `source_assets/monsters/scale_beetle.png` 原画，以源像素作为骨骼单位。
工程使用 54 根骨骼、24 个槽位：六足、两条七节触角、头颈、双颚、分层甲壳，
以及与宿主网格完全一致的发光层。原点 `(563.5, 883)`，场景位置 `(0, 0)`、
缩放 `0.52`，与原静态图的战斗位置一致。

参考了现有三套 Boss：腐化之遗的动作滞后，盛碗虫族母的负重与落足，
始源雾菇的接缝处理。网格/导出工具从已有 rigkit 独立继承；本目录修改不影响参考 Boss。

## 动作

| 动画 | 秒 | 设计与接入 |
| --- | ---: | --- |
| `idle_loop` | 4.8 | 负重呼吸、错相触角探测、颚部活动与轮流调足 |
| `attack` | 1.95 | 后撤张颚、蹬地前冲、六足跟进；**0.68 s** 咬合，三组分步退回 |
| `whip` | 2.75 | 一段连续三连击：近触角抽打、远触角反抽、双触角重扫；**0.60 / 1.12 / 1.68 s** 命中 |
| `cast` | 2.3 | 深蹲、抬头与抬前足、张开触角；**0.76 s** 开始重构化 |
| `molt` | 2.65 | 分组调足稳定支撑、胸甲抬升、硬甲明显张开并回落；**0.80 s** 获得格挡，随后放大 |
| `power_up` | 2.2 | 压低后昂首、双颚大幅张开、能量从眼部向背甲传播 |
| `hurt` | 0.85 | 明显回缩、前足缓冲、硬甲与触角惯性 |
| `die` | 2.8 | 两阶段屈足、伏地、触角落地、最后抽动后保持尸体姿态 |
| `revive` | 2.2 | 从死亡终姿开始，恢复光泽、撑足起身 |
| `summon` | 2.2 | 低伏、抬头抬前足，**0.88 s** 落足后身体继续下沉缓冲 |

`ThingsScaleBeetle` 继承 `ThingsSpineMonster`，通过 `Whip`、`Molt` 触发器接入。
伤害、命中次数、格挡、放缩层数、音效与一次原生多段攻击的语义保持一致。
命中和释放对齐 Spine 的绝对时间；快速／即时模式同样提交关键姿态。
行动结束前完成回位，外部 `ScaleTo` 继续控制实际放大。
`NThingsScaleBeetleMotion` 在两次后续鞭击的蓄力点等待上一击的原生效果结算；
命中后的缩小、多人目标或其他伤害 Hook 不会让后续命中提前空播。受击、死亡与离场会解除等待。

## 美术来源和局部编辑

`parts.py` 先拆分原画并补齐遮挡区。触角和每条腿各自使用连续索引网格，
关节附近平滑混合权重，长骨段及甲壳保持刚性。六足通过固定朝向的双骨 IK 烘焙，
触角的附加惯性以 240 Hz 模拟，最后导出 60 Hz 关键帧并在误差范围内精简。

按用户授权，通过所提供接口调用 **CLI Image API `gpt-image-2 edit` / high**，
局部补绘了 `head`、`shell_near`、`shell_far`、`body` 四张分件。
生成结果经位置校准、局部色彩匹配和蒙版合成；蒙版之外的像素与原 alpha 保持一致。
后续抠图归属修正直接搬移原画像素，例如把远前腿误带的下颌碎片归还给头部。

- 最终补绘输入：`source_assets/monsters/scale_beetle_rig_patches/`（四张 PNG、四张蒙版、清单）。
- 完整提示词：本目录 `art_edits/head.txt`、`shell_near.txt`、`shell_far.txt`、`body.txt`。
- `prepare_edits.py` / `integrate_edits.py`：准备编辑输入，以及只接收蒙版内改动。
- API 密钥不写入仓库；**正常重建无需任何图像 API 或密钥**。

## 重建

依赖：Python 3、`numpy opencv-python scipy pillow`，以及 Node.js/npm。
Spine 官方运行时锁定在 `package-lock.json` 的 `4.2.43`。

```powershell
.\tools\ScaleBeetleRig\rebuild.ps1          # 生成并验证 pkg/
.\tools\ScaleBeetleRig\rebuild.ps1 -Deploy  # 验证后更新工程内资源
.\scripts\build.ps1 -TargetVersion v111    # 导入、编译、导出并验证 PCK
```

生成目录 `parts/`、`out/`、`pkg/`、`prev/` 均已忽略，可再生成。
发布目录为 `STS2_Things/animations/monsters/scale_beetle/`。
静态场景生成器和旧切片骨架生成器均已保护当前场景，避免重建时覆盖新动画。

如需重新进行图像编辑，先运行 `python parts.py --raw` 和 `python prepare_edits.py`，
按提示词调用 imagegen 技能的 `image_gen.py edit`，再运行 `python integrate_edits.py`。
重新编辑输入使用 `tmp/imagegen/scale-beetle/`，原始生成输出使用
`output/imagegen/scale-beetle/`；最终选定补绘保存到上述 `source_assets` 子目录。

## 验证与预览

`verify.mjs` 读取实际打包的 Spine 数据，通过官方运行时采样全部动画（120 Hz），
检查待机闭环、死亡/复起衔接、足爪目标、至少三足支撑、地面滑动、头部与触角离地、甲壳刚性、发光层贴合、命中时间、动作幅度及触角出手方向。

使用项目现有的 Spine-enabled Godot 4.5.1 Mono 可执行文件：

```powershell
godot --headless --path . --script res://scripts/verify_scale_beetle_spine_scene.gd -- build/v111/STS2_Things.pck
godot --path . --rendering-method gl_compatibility --script res://scripts/render_scale_beetle_visual_probe.gd -- build/beetle-review 20 all
godot --path . --rendering-method gl_compatibility --script res://scripts/render_scale_beetle_visual_probe.gd -- build/beetle-mask 20 all silhouette
python tools/ScaleBeetleRig/verify_render.py build/beetle-mask
```

更新 PNG 后须先运行 Godot import。轮廓模式在真实网格上检查透明度，排除阴影和发光，
用于发现断开的分件及镜头裁切；最终外观仍以彩色帧和动画预览为准。
当前大幅动作的证据位于 `build/scale-beetle-impact-20261003/`，初版素材制作记录保存在 `build/scale-beetle-animation-20261002/`。

原生战斗检查：`.\scripts\test-scale-beetle-actions.ps1`。状态栏图标可由 `python scripts/build_scale_beetle_power_icons.py` 从现有原图重建。
