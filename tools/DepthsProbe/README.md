# 深处章节探针

引用当前目标版本的游戏程序集，安装真实模组初始化／Harmony，调用原生章节候选、房间生成、地图、存档二进制与 `RunManager.SetActInternal`。探针使用独立 `Depths Act Probe` 用户数据目录。

构建后运行 Godot 项目：

```powershell
dotnet build tools/DepthsProbe/DepthsProbe.csproj /p:ImplementationDll=<对应的当前构建DLL>
godot --headless --path tools/DepthsProbe
godot --path tools/DepthsProbe --rendering-method gl_compatibility -- --visual
godot --path tools/DepthsProbe --rendering-method gl_compatibility -- --camp-only
```

v107.1 探针另外传入 `/p:Sts2TargetVersion=v107.1` 和 `/p:Sts2DataDir=<v107.1游戏程序集目录>`。v111 使用当前游戏目录。图像验证从 `build/depths/v111/STS2_Things.pck` 读取共享资源；游戏 PCK 的本机位置定义在探针入口。

程序集需在 .NET 9 中运行；本机通过 `.tmp/dotnet9` 的 `DOTNET_ROOT` 选择运行库，避免 Harmony 不支持 .NET 10 的探针宿主。运行脚本见 `scripts/test-depths.ps1`。

覆盖内容：两个第二章候选、种子确定性、默认路线不变、两鱼／三鱼分池及起手、原版精英、巨岩共享、禁用回退、单人／多人房间数、前两场弱遭遇、地图节点、32 次二进制保存恢复、原生第一章 → 深处 → 第三章、背景／营地／地图资源合同。视觉模式使用原生人物、怪物、意图、章节标题；座位模式保持原版四个角色根节点与坐姿动画不变。路线总览明确标记为预览，并非完整原生地图 UI。

`build/depths/visuals` 保存场景截图；`build/depths/camp_review` 保存单人、四人、熄火与透明原版人物参考。后端与渲染日志保留在 `build/depths`。这不代替长局平衡或双机实际游玩。
