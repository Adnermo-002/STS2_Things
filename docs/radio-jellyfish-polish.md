# 收音水母文案与动作 · 1.17.1

本次调整「收音」的中英文悬浮说明和现有 Spine 动作。继续使用原画、96 根骨骼和 24 个动作；收音规则、多人结算、伤害及动画结算时点沿用 1.17.0。

## 能力说明

主说明改为：

> 每回合记录每名玩家前 2 张攻击或技能牌，行动时回放。
> 回放两格录音后，获得 1 点力量。

沿用原版数字、力量和格挡高亮。攻击回音与技能回音使用原生附加悬浮说明：

- **攻击回音**：每格攻击录音对所有玩家造成 7／8 点伤害。回放结束时，再攻击一次。
- **技能回音**：每个技能录音使其获得 10／12 点格挡。

移除了 16 份动态长说明，以及“本轮：空拍／混声”“攻击次数／格挡合计”等重复统计。当前回放继续由两个收音腔和原生意图显示；隐藏的多人收音状态校验仍保留。

## 动作

- **待机**：六秒循环中的两次游动，由缓慢舒张、快速收缩和滑行组成；触腕滞后于身体上浮，并加入轻微侧倾、视线移动和错开的眨眼。
- **回放**：两拍交替带动前后触腕，攻击有蓄势、抽击和回摆；护罩通过膨起钟罩、抬起并收拢触腕表达。末尾震波单独蓄力，双天线延迟回弹。
- **软体变形**：增加触腕中段的弧线控制、沿长度传递的波动，保留触腕顶部的直线连接，短触腕按长度减少位移，避免根部切口暴露与末端折叠。
- **受击与退场**：受击加入身体后仰和逐条触腕的延迟回弹；死亡时钟罩失去支撑、天线垂落，复起和出现动作补上过冲与收势。
- **眼部衔接**：将遮挡区的纯色填充替换为连续的周围皮肤，消除眨眼和眼神移动时露出的硬边。

动作仍在 0.50、1.00、1.55 秒配合原生结算，强化仍在 1.82 秒，回放总长仍为 2.30 秒。

[前后关键帧对照](../build/radio_jellyfish_polish/authoring/comparison.jpg) · [主动作预览](../build/radio_jellyfish_polish/authoring/motion.gif) · [受击与退场预览](../build/radio_jellyfish_polish/authoring/reactions.gif)

预览由制作工具生成，不包含原生战斗界面、收音灯光和音波特效，不是游戏实录。遵照用户要求，不运行游戏、战斗测试、原生渲染探针或联机测试。

## 文件与构建

- 动作源：`tools/RadioJellyfishRig/anims.py`。
- 曲线绑定：`tools/RadioJellyfishRig/rigdef.py`。
- 本地化源：`scripts/integrate_radio_jellyfish.py`、`STS2_Things/localization/{zhs,eng}/powers.json`。
- 能力显示：`STS2_Things/Powers/RadioReceptionPower.cs`。
- 构建：`scripts/build-reverse-salamander-release.ps1 -LogDirectory build/radio_jellyfish_polish`，只编译、导入、导出。
- 安装包：`dist/v1.17.1/STS2_Things-1.17.1.zip`。
- 交付状态、哈希及安装备份：`build/radio_jellyfish_polish/delivery.json`。

v107.1、v111 均编译通过，零警告、零错误，Godot 资源导入、PCK 导出及统一入口构建完成。用户关闭游戏后已安装 1.17.1，清单、DLL、PCK 和设置桥四个文件的 SHA256 与交付包一致。旧版备份位于 `D:/Things/Things-Workspace/STS2-MCP/.state/install-backups/STS2_Things-20261005T030357-37fe81`；未启动游戏或运行测试。
