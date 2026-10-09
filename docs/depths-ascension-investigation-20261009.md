# 深处路线通关后进阶未解锁：调查和防回归（2026-10-09）

## 玩家报告

**标准模式**，一局游戏里第二层随机进入深处（Depths），随后完成原版第三层 Glory，正常通关后似乎没有解锁下一进阶。不是玩家从“自定义模式”启动的局。

## 原版代码路径（本地核验）

- `STS2-V111/src/Core/Models/ActModel.cs`：`GetRandomList` 按原生索引生成三个章节；Depths 与 Hive 都占 index 1，Glory 仍占 index 2。
- `STS2-V111/src/Core/Nodes/Screens/CharacterSelect/NCharacterSelectScreen.cs`：标准角色选择启动 `GameMode.Standard`。
- `STS2-V111/src/Core/Models/Events/TheArchitect.cs`：必须在建筑师结局流程进入 `RunManager.WinRun()`，才触发 `OnEnded(true)`。
- `STS2-V111/src/Core/Runs/RunManager.cs`：`OnEnded(true)` 在 `ShouldSave` 为 true 时调用 `SaveManager.UpdateProgressWithRunData`，然后保存历史、删除当前局存档。
- `STS2-V111/src/Core/Saves/Managers/ProgressSaveManager.cs`：标准模式胜利、单人、且 `run.Ascension == character.MaxAscension` 时提升进阶（当前最高为 10）；此处**不根据第二层的章节 ID 决定能否升级**。
- `STS2-V111/src/Core/Helpers/OneTimeInitialization.cs` 和 `Saves/UserDataPathProvider.cs`：原版在有模组时走 `modded/profileX/saves/progress.save`，普通游戏使用 `profileX/saves/progress.save`。**两套进度不会自动互通**。所以“模组内解锁成功，关模组后普通游戏没变”不是 Depths 模型造成的。

## Workbench 实测

新增专用原生探针 `tools/DepthsProbe/DepthsAscensionRegression.cs`、`tools/DepthsProbe/DepthsActualWin.cs`，并为 STS2 Workbench 增加 `depths_ascension`、`depths_real_win` 配方。可通过 Workbench 启动指定 target 后重复。

- **v111：** 原生进阶规则 26 断言通过。Depths A0→A1、A2→A3、当前进阶低于已解锁最高值时不再增加、标准 Hive 对照、自定义模式不会增加。
- **v107.1：** 同一套 26 断言通过。
- **v111：** 独立测试用户目录，原生 `RunManager` 走 Overgrowth→Depths→Glory 后，调用正式 `OnEnded(true)` 结算；13 断言通过：标准模式、A2、获胜历史、modded/progress.save 盘上 A3 和重载 A3、非 modded 存档没有被覆盖、current_run.save 删除。
- **v107.1：** 同一套 13 断言通过。
- **最终证据日志**：`build/workbench/ascension/v111/actual-victory.stdout.log` 和 `build/workbench/ascension/v107.1/actual-victory.stdout.log`；各自对应的 `.stderr.log` 均为空。Workbench job 结果为 `succeeded`，独立可重测。
- Workbench 自身 Python 回归：50 passed、1 skipped，Ruff 全部通过。模组已追踪修改的 `git diff --check` 无空白错误。`STS2-MCP` 并非独立 Git 仓库，所以没有把对它直接运行的 `git diff --check` 结果作为代码质量失败。
- 磁盘写入测试采用 `GodotFileIo` 配合 `SaveManager.MockInstanceForTesting`，路径在 Godot 的 **Depths Act Probe** 隔离测试目录，不读取、不更改玩家正式存档。
- 注意：早期只对 `ProgressSaveManager.UpdateWithRunData` 的测试使用原生测试默认内存型 `MockGodotFileIo`，**不能当作真实磁盘存档已测试**。后续新增的 `DepthsActualWin.cs` 才是盘上路径核验。
- 此测试直接调用正式的 `RunManager.OnEnded(true)`，而非操作真实对局中建筑师事件的按钮、重打一整局或真人联机；结论限定在终局写盘链，不代表玩家现场已成功复现。
- 另外尝试全量 Depths 探针时遇到历史 PCK 缺失 `fleeting_echo.tscn` 及其怪物本地化的独立资源错误，整套旧资源测试未通过；本次按作用域隔离的进阶回归与实际存档链探针均无此错误。

### 范围和结论

在当前两套版本和源码下，没能复现“标准模式经过 Depths 后无法升级”：两版本均由原版例程成功提升进阶并保存到 **modded** 目录。**未发现可证明的 Depths 进阶代码缺陷，因此没有加入会绕过原版条件的强制升级补丁**，也没有改写普通/模组存档之间的隔离规则。

若玩家确实在仍然启用模组的**同一存档**内不能解锁，后续需要从该玩家的对应 modded 运行历史确认 `Win`、`GameMode`、`Ascension`、章节 ID、角色，并对照对应 `progress.save` 的 `max_ascension` 和游戏日志中 `Failed to save progress`、`Not playing on max singleplayer ascension`。先去除 Steam 身份/账号 ID、令牌等个人信息。注意进入第三章后击败 Boss 与完成建筑师的最终结算是不同阶段。

构建/测试不会自动安装或发布模组。单纯复制模组进度到普通游戏进度会跨越原版的刻意隔离，不在本次调查中执行。
