# 灯笼鱼原生探针

此项目引用目标游戏的 `sts2.dll` 和本项目测试 DLL，运行真实 `ModelDb`、遭遇与怪物状态机、`PowerCmd`、`CardPileCmd.Draw`、费用修正与清理；没有另写一套规则来模拟结果。

```powershell
.\scripts\test-lantern-fish.ps1 -TargetVersion v111
.\scripts\test-lantern-fish.ps1 -TargetVersion v111 -Visual
.\scripts\test-lantern-fish.ps1 -TargetVersion v107.1 -DataDir .tmp\things-collision-v107-data
```

先编译对应 `build/lantern_fish/<版本>/STS2_Things.dll`，视觉测试另需 `build/lantern_fish/v111/STS2_Things.pck`。工具脚本允许传入 Godot、游戏程序集和运行库路径。视觉入口使用本机 `D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck`，修改机器位置时同步调整该常量。

玩法：每个目标版本 65 项断言，包含三怪起手／循环／生命值、实抽计数、原生 RNG、复制和重抽、全局免费修正、回合末全牌堆恢复、X费／不可打出／星能、人工制品、跨玩家隔离与群体耀闪、不能抽牌与满手，以及四招真实命令结算。

视觉：加载真实 `NCreature`、`NCard`、SpineSprite 与原生图集加载器。验证原生动画触发器、牌面遮挡／乱码变化、模型描述不变、视觉不消耗游戏 RNG、回合末恢复、节点复用，保存运行时 PNG。探针只为测试宿主屏蔽了后端禁止订阅 UI 通知的保护，并由原生节点自行更新；没有跳过卡牌与战斗规则。

这属于游戏程序集／原生渲染测试宿主验证，未声称完成真人长局平衡测试或双机在线实测。V111 的正式联机界面禁止局中加入，故未扩展原游戏的重连协议。日志和画面位于 `build/lantern_fish/`。
