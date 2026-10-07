# Cave God 攻击后手部抽动修复

本次先处理用户报告的回收抽动。Boss 本体贴图、洞穴背景和玩法数值保持原样；界面图片重绘为独立的后续步骤，尚未执行外部生成。

## 复现与原因

新增原生 `RecoveryReview` 检查，按 120 Hz 测量攻击结束至待机后的肩、肘、腕位置和旋转。最小复现命令：

```powershell
.\scripts\test-cavegod-actions.ps1 -ImplementationDll build\cavegod_contact\v111\STS2_Things.dll -PackagePck build\cavegod_contact\STS2_Things.pck -RecoveryReview -RecoveryClip central_slam -RecoveryNoAim -NoImages -OutputDirectory build\cavegod_renew\minimal
```

1. 双掌攻击的腕部在回收末段单帧跳转 12.514°。清空玩家瞄准目标后仍出现；单独关闭手腕方向约束后降为 0.021°。攻击动画有方向辅助骨轨道，待机没有；混合时辅助骨向默认 0° 回退、约束又同时减弱，造成先偏转再弹回。现为所有动画补齐对应的世界手腕方向轨道。
2. 虚弱攻击切入真正的虚弱待机时，IK 关闭关键帧未指定弯曲方向，默认正向会在权重尚未退净时反折。单独关闭 IK 可消除；现为零权重关键帧明确保留设置姿态的弯曲方向。首次通用入口测到的 64 px 位移不作为该项结论，后续检查使用游戏实际调用的 `StartWeakAttackAnim`。
3. 右侧横扫和抓取下砸的末帧与待机首帧仍有位置／方向差异。只修改回收尾段，使用平滑曲线收束到对应待机姿态，并留出短暂稳定段；蓄力、接触帧和伤害事件不改动。

另外将主轨道包装对象改为每次动画持有一份明确拥有的引用，在替换与退出时于调用线程释放，避免每帧创建原生信号包装对象。

## 验证

- 22 种普通／愤怒攻击回收均通过；修复后的回收末段最大单帧位移 0.654 px、转角 0.114°。
- 最小复现和控制变量结果保存在 `build/cavegod_renew/minimal/`、`hypothesis-wrist/`、`hypothesis-ik/`；临时关闭约束的诊断开关已从测试入口移除。
- 原有攻击时序、左右抓取衔接、抓牌闭合时序与 1–4 人的 120 组接触范围再次检查。
- 对比预览 `build/cavegod_renew/preview/recovery-comparison.mp4` 为原生渲染回收末段的 2 倍慢放，不是实机录像。

生成入口仍为 `scripts/build_cavegod_contact.mjs`，不覆盖原动画基准。正式回归使用 `test-cavegod-actions.ps1 -RecoveryReview`；`-RecoveryNoAim` 可独立检查骨骼衔接，`-OverlayPck` 支持只替换骨骼的快速验证包。

## 安装与交付

修复版 `1.17.7` 已安装至本机游戏的 `mods/STS2_Things`，包括统一引导 DLL、PCK、清单与 BaseLib 兼容 DLL。安装前游戏已关闭，原安装由 Workbench 备份至 `STS2-MCP/.state/install-backups/STS2_Things-20261005T052206-eb179f`。

v0.107.1 与 v0.111.0 两个目标编译和统一包加载检查通过，各加载 114 个模型。本轮验证是原生探针与渲染检查，没有进行实机战斗或多机联机。完整包、使用说明和检查记录保存在 `dist/v1.17.7/STS2_Things-1.17.7.zip`；交付脚本核对四个安装文件、ZIP 内逐项哈希及 CRC。界面资产仍为旧版，不计入本版完成内容。

## 界面重绘准备

用户确认只重绘界面图像。已准备 14 份独立提示词：8 个能力图标、5 张卡面、1 张 Boss 头像母图，并备份原界面文件。完整清单与原版参考见 `source_assets/ui/cavegod_renew/`。

自动审批拒绝了 cpa 生图调用，理由是从本对话读取密钥并发送这些具体参考素材到外部接口，仍缺明确出站授权。已在当前对话请求确认。在获得回复前没有调用图片 API，也没有替换图像文件。密钥不保存在素材或代码文件中。

后续：用户已于 2026-10-05 确认授权；界面重绘在 1.17.8 完成，参见 [重绘、画风自审与原生 UI 验证](cavegod-ui-art-20261005.md)。以上“未重绘”的状态仅描述 1.17.7 动画修复包。
