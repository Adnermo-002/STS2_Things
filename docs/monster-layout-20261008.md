# 怪物血条被结束回合按钮遮挡：1.25.11

## 问题与修复

玩家反馈部分怪物生成在右侧低位，血条被结束回合按钮盖住。2026-10-08 在真实 v0.107.1、模组 1.25.10 的蜗牛三人组中通过只读场景数据和截图确认：1920×1080 下，爬岩蜗牛站位为 `(1720,842)`，血条矩形为 `(1606.5,849,222,16)`，生命数字为 `(1606.5,839.5,222,36)`；结束回合按钮图像占 `(1586,827,256,128)`，两者重叠。

原版 `NCombatRoom.AdjustCreatureScaleForAspectRatio` 约束屏幕边界，不会自动为按钮预留区域。v107.1 与 v111 的 `NEndTurnButton` 均使用 `(1604,846)/NGame.devResolution` 作为显示位置比例。

本轮直接调整原生遭遇场景的 Marker2D 站位，未增加运行时 UI 补丁。右侧怪物向内、向上收拢；宽血条的单怪遭遇也适度左移。同步更新九份现有生成脚本，避免以后生成场景时恢复旧位置。

| 遭遇场景 | 修改的站位（旧 → 新） |
| --- | --- |
| snail_trio_weak | rock `(1720,842)` → `(1680,738)` |
| cave_maw_encounter | leech `(1780,809)` → `(1740,740)` |
| cave_maw_weak | maw `(1435,824)` → `(1320,800)` |
| fleeting_echo_weak | echo `(1435,832)` → `(1320,800)` |
| radio_jellyfish_elite | jellyfish `(1450,819)` → `(1320,775)` |
| reverse_salamander_elite | salamander `(1365,800)` → `(1280,770)` |
| mycorrhizal_twins_elite | vanguard `(1235,800)` → `(1210,775)`；bulwark `(1635,790)` → `(1610,740)` |
| origin_fogmog_boss_encounter | fogmog `(1359,795)` → `(1320,775)` |
| gravetide_slug_boss_encounter | corpse_slug_6 `(1770,805)` → `(1710,740)` |
| sanguine_leech_encounter | third `(1730,789)` → `(1690,740)` |
| sponge_leech_encounter | leech_2 `(1730,789)` → `(1690,740)` |
| silk_moth_weak | leech_1 `(1615,800)` → `(1615,740)` |
| lantern_moth_encounter | crystal `(1760,768)` → `(1720,736)` |
| lantern_sponge_encounter | crystal `(1760,768)` → `(1720,736)` |
| bowlbug_progenitor_boss_encounter | bowlbug_14 `(1759,835)` → `(1740,740)`；bowlbug_9 `(1872,896)` → `(1760,610)`；bowlbug_7 `(1621,915)` → `(1460,905)`；bowlbug_3 `(1612,788)` → `(1580,740)` |
| soul_roes_encounter | soul_roe_7 `(1533,833)` → `(1505,810)` |

## 验证证据

证据根目录：`build/monster-layout-20261008/`。

- 基线来自已发布 `dist/v1.25.10/STS2_Things-v1.25.10.zip`，不是共享构建目录里的旧 DLL。基线 PCK SHA256：`61a635efcfff81233395f850f3fb2eeb3c9b8404c1bfd59c6d44e17511524af8`。
- `scripts/test-encounter-layout.ps1` 使用独立复制的探针工程，加载真实游戏 DLL/PCK、原生 NCreature 血条/格挡/能力图标、原生结束回合按钮图像及其显示位置。覆盖当前已发布实现注册的 **29 个**有场景遭遇，并补齐盛碗虫始祖、墓潮蛞蝓、魂卵的备用召唤位置。此前进度说明中的 30 个是计数误差，以测量 JSON 为准。
- `baseline-isolated-v107/layout/measurements.json`：216 个 HUD 矩形中，34 个与按钮及外扩 12 像素的区域重叠。
- `after-source-v107/` 与 `final-package-v107/`：同样 29 个遭遇、216 个矩形，重叠均为 **0**；最终包 PASS（35 项断言），标准错误无引擎 ERROR/SCRIPT ERROR。
- 已实际查看最终包的蜗牛、菌根双生子和盛碗虫备用站位渲染图；源场景回归还查看了逆流蝾螈。蜗牛血条清晰，双生子连根仍连接。召唤测试会同时填满所有预留位置，截图不是自然战斗的实际阵容。
- 由同一已发布源码基线分别编译 v107.1/v111 和统一引导，均为 0 警告、0 错误。`unified-verify.log` 两目标均 PASS，各注册 150 个模型，内嵌实现与输入 DLL 哈希一致。
- `scripts/pack-encounter-layout.gd` 复制基线 PCK 原始资源，仅替换 16 个遭遇场景；重新挂载后逐一校验全部 1226 个资源。回执 `pck-receipt.json`。

渲染回归是 1920×1080 单人原生组件场景，未运行安装后的完整客户端战斗、宽屏比例或多机联机。v111 本轮完成编译和结构兼容性校验，未用 v107 PCK 冒充 v111 完整实机验证。检查聚焦按钮遮挡；不宣称消除满召唤阵容的所有相互遮挡或其他界面问题。

## 交付范围

工作区同时出现其他任务的新垂丝蛾内容。完整安装包的生产 C# 因而采用已发布提交 `3df036d3064370fad5c5b79f5da2e504f584474e` 的隔离副本，仅将程序集版本更新为 1.25.11；本轮不混入那些开发中的代码，也未回退共享源码。源码档案 `baseline-build-source.zip`、清单 `baseline-build-source-files.txt`、隔离输出 `isolated-impl/` 与 `isolated-bootstrap/` 可用于核对来源。共享目录下早先生成的 `impl/` 和 `bootstrap/` 不是此次交付输入。

运行包为 `dist/v1.25.11/STS2_Things-v1.25.11.zip`，包含统一 DLL、PCK、manifest、BaseLibBridge 四文件；校验文件为同目录 `SHA256SUMS.txt`。最终 PCK SHA256：`6b20c0974a32d98b364239236b48eb196a9485a9c4583817c11268c3ccace3e7`。

游戏仍在运行，本轮没有覆盖本地安装、关闭其他任务的测试进程或发布 Steam/GitHub。安装需等待游戏退出。
