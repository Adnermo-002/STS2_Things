# 多召唤物死亡诊断探针

为 2026-10-09 玩家反馈的“多人、多奥提斯或其他召唤物死亡后房主闪退”建立可重复检查。本探针目前未复现该反馈；通过不能作为已修复或完整 Steam 联机通过的证据。

入口为项目根目录的 `scripts/test-pet-death.ps1`。显式提供单目标实现 DLL、资源包与独立输出目录；不接受统一引导 DLL作为编译引用，不安装模组，不操作玩家存档。

```powershell
./scripts/test-pet-death.ps1 -TargetVersion v111 `
  -ImplementationDll ./build/medusa-cutting-refresh-20261007/release12510/v111/STS2_Things.dll `
  -PackagePck ./build/workshop/20261007-event12510/workspace/content/STS2_Things.pck `
  -OutputDir ./build/pet-death-20261009/check `
  -Visual -HostMode -Matrix
```

- 核心用原生 `OstyCmd.Summon`、怪物攻击及 `CreatureCmd.Damage`，检查两／四个拥有者、超额伤害归属、死亡与复苏。
- `-Matrix` 覆盖引用实现的深处非 Boss 遭遇，执行真正的入场 Hook 与四轮怪物行动；另检验每名玩家两个可移除型宠物的死亡与归属。
- `-HostMode` 仅切换测试中的网络服务类型判定，执行房主模式分支；不是建立 Steam 房间。
- 原生状态序列化对比切换本地观察者 ID 后的结果；这是同进程的独立模拟，不是两个完整客户端。
- `-Visual` 在原生 Godot／Spine 组件中完成 24 轮、48 个异步重叠的奥提斯死亡动画。测试只用房间索引替身和计时替身接入独立场景；保留实际动画、Tween与死亡流程。正常的非交互测试会跳过等待，因此用短帧计时恢复异步重叠。音频和完整游戏粒子仍受原版测试模式抑制。
- `-Loopback` 建立本机 ENet 房主和客户端，使用原生握手、消息类型注册与可靠消息传递八份死亡后生成的校验值；不能代替两份客户端独立执行整场战斗。

项目使用独立 Godot 用户目录；运行脚本检查进程退出码、stderr 和结果标记，异常或超时即失败。共享 SDK 构建状态要求不同目标顺序运行。

诊断记录与限制见 `docs/pet-death-investigation-20261009.md`。
