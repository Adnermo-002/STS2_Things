# 1.11.3：章节切换黑屏修复

用户在游戏 v0.111.0 中执行 `act 1`、`act 2`、`act 3` 后持续黑屏。实机通过 STS2 Workbench 再次执行 `act 2`，原生命令失败，画面主体黑色像素占比为 100%，异常为 `An item with the same key has already been added. Key: MapCoord (0, 1)`，调用栈进入 `NCrossroadLayer.Attach`。

## 原因与修复

原版 `NMapScreen.SetMap` 调用 `FreeChildren`，后者通过 `QueueFree` 在帧末释放旧地图节点。在 `SetMap` 的 Postfix 中枚举子节点时，旧节点仍然与新节点并存，按坐标调用 `ToDictionary` 因重复键而抛错，中断 `EnterAct`，黑色过场遮罩也没有解除。

`NCrossroadLayer.Attach` 现在排除正在等待释放的节点，并立即从容器中移除旧横路层，再建立新层，避免旧层继续接收事件和占用名称。没有吞掉异常或随意选择重复坐标中的一个节点。

此前的 UI 测试立即 `Free()` 整个容器，未覆盖原版的延迟释放。测试夹具已改为保留容器并 `QueueFree()` 其子节点，增加同一帧连续三次刷新；旧 DLL 在第一次刷新就出现相同重复键异常，修复后通过，随后付款与地图刷新也通过。

## 本次验证

- `scripts/test-crossroads.ps1 -Ui`：相同帧内重复重建、活跃节点引用、唯一横路层，以及原有布局、弹窗、付款与解锁交互通过。
- `scripts/test-crossroads.ps1`：360 张地图、6 组交易及保存／协议检查通过。
- v107.1 与 v111 编译、统一入口各 83 个模型、源码／资源合同检查通过。
- 实机 v0.111.0 已装入 1.11.3，按顺序执行 `act 1` → `act 2` → `act 3` → `act 2` → `act DEPTHS`，五次原生命令完成，画面均不再全黑。
- 已在真实 `NMapScreen` 中检查第一版石板的底端、中段、顶端及首领节点；滚轮、拖动、方向键可滚动，路线和横路锁显示正常，未见分段色带。

证据位于 `build/act_map_black_screen/`。`before-act2/` 为真实失败，`regression-before.log` 为隔离回归失败；`after-act*`、`after-depths`、`map-bottom`、`map-middle`、`map-top` 为修复后的实机记录。`map-*/screen.png` 是本次实际游戏截图，区别于先前的示意路线。

实机复现入口（使用 MCP 工程的 Python 环境，并先进入专用单人测试局）：

```powershell
& '..\STS2-MCP\.venv\Scripts\python.exe' -X utf8 '.tmp\act-map-black-screen\live_probe.py' --act 2 --label act2-repro
```

运行前已备份当前单人存档；安装工具另行备份旧模组。未发布创意工坊。v107.1 本次完成编译与加载检查，实机操作限于当前安装的 v0.111.0。

## 手动查看深处地图

进入单人测试局，打开控制台，依次输入，等待每一步切换完成：

```text
act 2
act DEPTHS
```

数字命令选择第二章槽位，名称命令将当前章替换为「深处」。地图会自动打开；可用滚轮、拖动或上下方向键查看整块石板。已关闭地图时可点击右上角地图按钮重新打开。`act 4` 不存在，当前冒险仍为三章。
