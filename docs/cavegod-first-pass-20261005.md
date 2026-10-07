# 活体巨岩第一轮调整 · 1.17.9

抓取试炼改为正常抽牌完成后选择，抓取给予的易伤从 2 层降至 1 层。老化采用用户确认的双手共享倒计时：初始 2 层，每次击倒任意手臂扣 1，归零时向每名存活玩家手牌加入一张本场战斗 0 费的岩石铠甲，随后重置为 2。

## 抽牌后选择

抓取行动只施加易伤、生成岩之手，并给各被捕玩家安排一次待选试炼。使用原版 `AfterPlayerTurnStart` 及传入的 `PlayerChoiceContext`，在每名玩家的正常起手抽牌完成后打开原版二选一界面。原版该界面支持查看战场与手牌。

待选记录使用不显示的原生能力，作为调度状态，不额外消耗人工制品。它在等待选择前消耗，因此额外回合不会反复弹出。解救、暴露、转阶段或战斗结束的现有释放流程会清理待选与已选限制；如果等待选择期间被解救，迟到的选择不会重新施加禁牌。只有本机玩家的选择临时调整本机弹窗层级，远端选择仍由原版同步处理。

重摔基础伤害仍为 24／26。1 层易伤覆盖重摔，但不再覆盖随后一记狂暴崩山；零力量时分别是 36／39 与 19／22。

## 共享老化

- 两臂的老化图标均使用原生层数显示，始终展示同一个剩余数值。
- 初始为 2；第一次击倒变为 1；第二次触发一轮赠牌并回到 2。
- 左右臂的击倒次数合并计算，同一手臂恢复后再次被击倒也计数。
- 临时生成的岩之手不计入老化倒计时。
- 一次群攻击倒两臂会合计扣两次，一共赠牌一轮。
- 倒计时跨苏醒与阶段转换保留；不会因转阶段无条件刷新赠牌额度。
- 剩余计数写在原生 Power Amount 中，以左臂为读取来源、右臂同步显示；双臂计数在赠牌的异步流程之前一起更新，避免一轮击倒重复发奖。

老化说明显示“再击倒 X 次手臂”，同时说明双臂共用及归零重置。赠牌仍使用原版生成入手牌流程，手满时沿用原版溢出规则，不改变永久牌组。

## 文件与交付

- 抓取与选择：`STS2_Things/Monsters/ThingsCaveGodHand.cs`、`STS2_Things/Powers/CaveGodPendingTrialPower.cs`。
- 共享计数：`STS2_Things/Monsters/ThingsCaveGodBody.cs`、`STS2_Things/Powers/ThingsCaveGodAgingPower.cs`。
- 中英文说明：`STS2_Things/localization/{zhs,eng}/powers.json`。
- 构建：`scripts/build-reverse-salamander-release.ps1 -LogDirectory build/cavegod_first_pass`。
- 安装包：`dist/v1.17.9/STS2_Things-1.17.9.zip`。
- 交付状态与哈希：`build/cavegod_first_pass/delivery.json`。

按此前要求，不运行测试、原生探针、游戏实战或多机联机。更新了已有探针中受本次规则影响的预期和选择入口，但未执行它们。

v107.1、v111、统一入口和设置桥编译通过，零警告、零错误；Godot 导入与资源导出完成。1.17.9 已安装，四个文件的 SHA256 与交付包一致。旧版备份：`D:/Things/Things-Workspace/STS2-MCP/.state/install-backups/STS2_Things-20261005T080529-176531`。
