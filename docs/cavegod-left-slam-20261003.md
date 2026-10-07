# Cave God 左手下砸时右臂抽搐 · 1.10.4

## 根因与修复

`idle_front` / `idle_front_angry` 中控制右臂的 IK 约束 `arm1_IK` 未指定 `bendPositive`，Spine 时间线默认为 true。下砸动作使用 false；切入待机时，IK 权重尚未降到 0，方向却立即改变，右肘瞬间反折。普通模式释放玩家时提前进入待机、以及完整动画自然结束，都会触发。

仅给这两个待机关键帧补上 `bendPositive: false`。保持 FK/IK 权重、动作时长、伤害时序、释放流程与美术资源不变。之前修好的左右抓取/下砸关键帧与手腕烘焙无需重建。

## 复现与回归

```powershell
.\scripts\test-cavegod-actions.ps1 -NoImages -OutputDirectory 'build\cavegod-actions-20261003-left-slam\check'
```

回归在原生 Spine 与实际背景控制器中以 120 Hz 跟踪肩、肘、腕。此前检查只监测主攻拳，且停在 0.75 秒触地；现延伸至 2.2 秒，覆盖非主攻臂及回待机阶段。另调用实际 `ThingsCaveGodHand.Slam`，覆盖伤害、释放与提前回待机；组合左右手、普通/愤怒形态、普通/快速/即时速度，共 12 个释放场景。

| 场景 | 修复前右臂最大单帧位移 / 角度 | 修复后 |
| --- | --- | --- |
| 左手下砸自然结束 | 495.34 px / 103.62° | 36.55 px / 5.40° |
| 左手下砸实际释放，普通速度 | 464.66 px / 95.20° | 14.23 px / 2.64° |
| 左手下砸实际释放，快速速度 | 448.79 px / 91.02° | 14.23 px / 2.64° |

位移使用 1920×1080、0.75 倍遭遇缩放下的世界坐标；最大值覆盖完整动作，包含正常蓄力、下砸与回收运动。旧包测试确定失败，修复后测试通过。蓝色与愤怒形态结果一致，右手抓取定位、悬停衔接、三连击命中时序与试炼资源检查也通过。

修复前数据在 `build/cavegod-actions-20261003-left-slam/baseline-release/`；修复后完整数据与连续帧在 `fixed-idle/`，其中 `contact-and-idle.png` 展示触地与待机切换。测试使用实际游戏资源和命令的可控场景，不替代真实多人联机实战。

## 构建

V107.1 / V111 Release 构建与统一包加载验证通过，源码/PCK 审计通过。Cave God 完整战斗行为与 UI 回归通过，包含多人抓取、破爪取消、转阶段和死亡清理。

统一包：`build/deliverables/STS2_Things-1.10.4.zip`，仅包含模组的四个发布文件，已逐文件核对 SHA256。DLL 为 `40332D523E97AC35FC244AFF857C400A53E72AE31DFCC2DA5B92227AAED27322`；PCK 为 `47E0880E6412A5E12CCB8E3AFC4FE3CD384073413460C6FCC3AE5D71984C5C3C`。未提交 Git 或发布创意工坊。

用户正常退出游戏后，已安装到 `D:\Steam\steamapps\common\Slay the Spire 2\mods\STS2_Things` 并验证四个文件哈希；旧版备份在本次检查目录的 `installed-before/`，安装凭据在 `installed-sha256.json`。
