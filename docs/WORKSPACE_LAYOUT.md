# 项目目录与清理约定

`STS2_Things` 是模组工程；上层工作区的 `STS2-V*` 是游戏 API / 资源参考，
`research`、`handoff` 等目录保存研究资料和交接记录。它们不属于本模组的构建垃圾。

| 路径 | 用途 |
| --- | --- |
| `STS2_Things/` | C# 模型、视觉、Hook、兼容层、本地化，以及按既有路径加载的 Spine 发布资源 |
| `bootstrap/`、`bridges/`、`manifests/` | 双版本入口、可选桥接和版本清单 |
| `scenes/`、`images/`、`animations/`、`materials/`、`audios/`、`sfx/`、`music/` | 游戏运行资源，路径有引用关系 |
| `source_assets/` | 原画和编辑源；`.gdignore` 阻止 Godot 导入，导出配置也排除此目录 |
| `source_assets/archive/` | 从运行资源目录移出的编辑备份，例如 CaveGod 的 `.bak*` 文件 |
| `tools/` | 骨骼生成器与运行时探针；`.gdignore` 阻止编辑器扫描独立小项目 |
| `tools/OriginFogmogRig/v3/` | 当前雾菇的可重建蒙皮、锁定的 Spine 依赖和接缝回归检查 |
| `tools/ScaleBeetleRig/` | 放缩巨甲虫分件、动作、官方运行时和引擎轮廓检查 |
| `source_assets/monsters/scale_beetle_rig_patches/` | 巨甲虫已选用的局部补绘、限定蒙版与来源清单 |
| `tools/OriginFogmogRig/legacy_v2/` | 旧雾菇生成源码，仅供历史编辑参考 |
| `scripts/` | 构建、验证、资产处理及清理入口 |
| `docs/`、`design/` | 架构、版本差异、设计与维护说明 |
| `build/v107.1/`、`build/v111/`、`build/unified/` | 支持版本的诊断构件与统一发布包 |
| `build/*backup*`、`build/**/before`、`build/**/original` 等 | 可能保存唯一源码的回滚材料，清理器保留 |
| `.tmp/`、`tmp/`、`output/` | 本地工具、实验与中间产物；其中仍有独有脚本和候选原画，不能整体删除 |

## 清理

```powershell
.\scripts\clean_workspace.ps1         # 预览删除清单和大小
.\scripts\clean_workspace.ps1 -Apply  # 执行已分类的清理
```

清理器仅移除已识别的动画截图序列、旧诊断构件、探针编译缓存、日志、
根目录过期 DLL/PCK、无源文件的导入描述，以及被 `.gdignore` 排除的
`source_assets` 下的 `.import` 文件。删除清单保存在 `build/workspace-cleanup/`。
执行时检查绝对路径必须在工程内，拒绝链接目标，并逐文件删除。

保留原画、历史源码/回滚副本、`.tmp/dotnet9` 等测试依赖和当前构建目录。
`node_modules`、当前雾菇生成器的 `out` 及 `.tmp` 已加入 Git 忽略规则。
新增构建证据放入 `build/<任务名>/`；临时输出不再放在工程根目录。

## 2026-10-02 维护

- 修复 Origin Fogmog 分件权重不一致造成的爪根、脚踝接缝，并提供从恢复输入重建的流程。
- 将旧雾菇生成器归入 `legacy_v2`，清除其可再生成输出。
- 将 CaveGod 的原地 `.bak*` 编辑备份归入 `source_assets/archive/cave_god`。
- 首轮清理删除 3,926 个文件，约 1,427.74 MiB；保留仍有独有内容的历史目录。
