# Cave God 右手抓取动作

`right_grab_bake.json` 保存 Spine 原生运行时以 60 Hz 求解的手腕旋转轨迹。
右臂和左臂的前臂长度、局部坐标不同，不能直接把左手 FK 角度取负当作右手。

生成器将右侧抓取和下砸统一为 IK，明确设置 `arm1_IK` 的负向弯曲和 `arm2_IK` 的正向弯曲。
IK 时间线省略 `bendPositive` 时会使用 true，不能依赖骨架 setup 值。手腕世界朝向从左侧动作镜像后，经真实 Spine 骨架反求本地旋转；连续角度展开避免跨 ±180° 插值时旋转一圈。

待机 `idle_front` / `idle_front_angry` 的 `arm1_IK` 也必须明确 `bendPositive: false`，即使待机键本身的 `mix` 为 0。下砸转待机的混合期间 IK 权重仍大于 0；省略方向会立即把右肘翻到另一侧，再随权重归零恢复，造成单帧抽搐。完整回归包括两条手臂、下砸结束后的待机混合，以及普通/快速/即时模式下实际伤害和释放流程。

左侧动作或骨架 setup 改动后，先构建对应的 `build/v111/STS2_Things.pck`，再执行：

```powershell
.\scripts\test-cavegod-actions.ps1 -BakeRightGrab -NoImages
Copy-Item -LiteralPath build\cavegod-actions-20261002\right_grab_bake.json -Destination source_assets\monsters\cave_god_motion\right_grab_bake.json -Force
python scripts\generate_right_animations.py
```

重新导出 PCK 后运行 `scripts/test-cavegod-actions.ps1`，验证肩、肘、腕的位移/角度连续性、玩家握点、伤害时序和资源显示。原有贴图及左侧动作保持为输入参考。

## 独立偷牌动作

`card_snatch_motion.json` 是偷牌动作的统一编排源，`scripts/build_cavegod_card_snatch.py` 生成 `card_snatch`、`card_snatch_right` 及两种愤怒变体。0–1 秒抬高蓄力，1–1.36 秒快速冲向玩家，1.60 秒合掌收牌，1.68 秒开始沿连续弧线收回，3.08 秒归位，3.2 秒衔接待机。只生成这四段动画，复用原有张掌/握拳贴图。

`card_snatch_bake.json` 保存原生 Spine 以 120 Hz 反求的手腕角度，由 `tools/CaveGodProbe/CaveGodCardSnatchBake.cs` 按两侧骨架分别求解。位置和角度采用保持形状的 Hermite 曲线通过中间关键点，冲刺使用五次缓动，让速度与加速度平滑进入和结束；仅在蓄力顶点、接触与归位等明确节点停顿。活动臂在 IK 下保留待机 FK 角度，避免回待机时混合权重下降造成关节绕行。入场混合在小幅预备下沉期间完成，避免抬臂中途改变速度。实际玩家站位只在表现层调整 IK 落点，卡牌所有权与选择仍由原版 Commands 和战斗随机数管理。

调整轨迹或腕部朝向后：

1. 执行 `python scripts/build_cavegod_card_snatch.py --prepare-bake` 并导出 PCK。
2. 执行 `.\scripts\test-cavegod-actions.ps1 -BakeCardSnatch -NoImages`。
3. 将 `build/cavegod-actions-20261002/card_snatch_bake.json` 复制回本目录，再执行 `python scripts/build_cavegod_card_snatch.py`。
4. 重新构建后执行 `.\scripts\test-cavegod-actions.ps1 -CardSnatch`，验证张掌/握拳、玩家落点、持牌跟随、回待机、伤害与偷牌时序。

回归可加 `-NoImages` 跳过渲染；`-OutputDirectory` 可保存每次验证的独立记录。原有抓取下砸检查继续使用不带 `-CardSnatch` 的命令。

`-SmoothPreview` 输出左手的 30 FPS 连续画面及其他变体的关键帧；测量始终为 120 Hz。预览中的玩家动画使用同一个手动时钟，防止导出耗时改变播放速度。
# 2026-10-05 接触校准

当前运行骨骼的接触控制由 `scripts/build_cavegod_contact.mjs` 生成。基准为本目录 `contact_base.spjson`，输出为游戏使用的 `cave_god.spjson`，同时生成 `contact_profiles.json` 和 `CaveGodContactProfiles.cs`。控制骨追加在原骨骼表末尾，不能插入表中，否则会破坏加权网格的数字索引。

旧的右侧动作或抓牌重建若需再次运行，应在不含接触控制的基准上完成，再运行接触生成脚本。当前实现及验证见 `docs/cavegod-contact-20261005.md`。
