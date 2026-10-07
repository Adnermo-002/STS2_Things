# 创意工坊更新与第一章换章验证

2026-10-06 16:22:37（UTC+8）已更新现有条目：[尖塔：琐事-STS2_Things](https://steamcommunity.com/sharedfiles/filedetails/?id=3747607944)。模组版本保持 **1.25.0**。

## 已发布内容

- 使用官方 ModUploader **v0.2.0**，替换本机旧 v0.1.0；官方发布包 SHA256 已核对。v0.2.0 的内部产品版本仍显示 `1.0.0+4c4db1262cdce6a1c4550a494f2e1088dbeda346`。
- 重写中文及英文简介，介绍深处的进入方式、9 种普通怪物、3 组新精英、模组共 6 个 Boss 和 13 个事件，以及安装、可选设置库和多人版本要求。
- 保留品牌封面，用 6 张游戏实机截图更新图库：洞胃与灯笼鱼、菌根双生子、活体巨岩、对齐之屋、缠丝手牌、深处石板地图。截图未经编辑，单张均小于 1 MB。
- 内容是此前测试通过的 `dist/v1.25.0/STS2_Things` 四文件发布包；逐文件 SHA256 与 `build/depths_strong_variety/delivery.json` 完全一致。没有重新编译或更改版本。
- 标题、公开状态及标签保留；无强制依赖。上传器确认依赖无变动。
- 原上传工作区已备份并同步到本次发布内容，避免继续上传原目录中旧的 1.9.1 文件。

## 第一章至深处的实机验证

游戏 v0.111.0，单人标准模式，独立离线身份 `125008`，种子 `7JDJG14WSWCZ`。没有改动用户 Steam 身份的存档。

1. 从主菜单新开战士局，游戏自行生成 `OVERGROWTH → DEPTHS → GLORY` 章节序列。
2. 用原版 `room Boss` 和 `kill all` 缩短第一章 Boss 战，Boss 为 Vantom。未使用 `act` 命令，未修改当前局保存文件。
3. 实际点击 Boss 奖励页的“前进”，由原版换章流程进入 `ACT.DEPTHS`，`CurrentActIndex = 1`。
4. 石板地图正常显示，点击地图进入特兹卡塔拉事件，选择烫嘴可可并继续。
5. 点击地图首个战斗节点，自然抽到 `SNAIL_TRIO_WEAK`；正常打出打击、破壳生成晶片，并结算敌方回合至玩家第 2 回合。地图、场景、怪物、手牌与回合推进均可用，没有换章黑屏。
6. 后续通过原版命令补拍精英、Boss 和事件用于图库。完成后正常保存退出并关闭本次测试进程。

该检查验证的是换章和首战链路，并非完整第一章平衡通关或真实多机联机测试。深处仍为巢穴之外的第二章候选，正常规则并不保证每局都出现。更新后建议新开局，旧局已经生成的章节不会重抽。

本轮日志在进入深处后显示资源预加载完成。启动的 `Invalid Task ID` 和退出时 RID 释放警告与此前无内容模组基线中的既有现象一致；本次未出现换章失败或黑屏。

## 发布复核

官方上传器退出码为 0，返回 `Successfully uploaded`。随后重新获取公开 API 和页面，确认：

- 条目仍为 `3747607944`，公开且未封禁。
- 公开简介与上传文本完全一致，UTF-8 共 5470 字节。
- 内容句柄已改变，文件总大小为 206,625,125 字节，与四文件之和相符。
- 图库已更新为 6 张新预览，页面同时呈现中英文正文。

完整证据与可复用上传工作区：`build/workshop/20261006/`。

- `description.bbcode.txt` / `changenote.txt`：已发布文案。
- `publication-report.json` / `staging-report.json`：公开复核、内容哈希与截图来源。
- `live-evidence.json` / `transition-first-combat.save` / `transition-game.log`：换章记录。
- `workshop-before.json` / `workshop-after.json` 与同名 HTML：公开页面前后快照。
- `upload.log`：上传终态。
- `previous-uploader-workspace/`：旧工作区备份。
- `workspace/`：本次可直接复用的上传工作区，固定现有条目 ID。

本机上传器：`D:/Download/ModUploader-win-x64/ModUploader.exe`。
日常上传工作区：`D:/Download/ModUploader-win-x64/STS2_Things-workshop`。
