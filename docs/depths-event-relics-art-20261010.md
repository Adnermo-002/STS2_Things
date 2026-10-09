# 深处事件遗物重绘（2026-10-10）

本轮重制深处事件中五件固定的自制遗物。新图已接入项目，完整开发包已准备；游戏仍在运行，本轮没有覆盖安装，也没有执行 Steam 或 GitHub 发布。版本沿用当前开发线 `1.25.13`，用独立目录和 SHA256 区分同号构件。

| 遗物 | 来源事件 | 本轮图案 |
| --- | --- | --- |
| 瓶中回声 | 收音井 | 青蓝矮瓶、粗木塞、一条浅色回声弧 |
| 寄存收据 | 影子寄存处 | 旧纸寄存牌、外套印记、短蓝绳 |
| 菌根存单 | 菌根借贷所 | 折叠纸叶、蘑菇印记、根绳和单颗红色种子 |
| 余烬约定 | 还没烧起来的火 | 焦木沙漏、浅色玻璃、底部一点余烬 |
| 美杜莎之发 | 蛇发女妖 | 用布条扎起的橄榄色蛇发，圆钝的蛇头 |

蛇发女妖同时属于巢穴与深处；两处引用同一遗物，均显示新图。遗物修补摊、礼貌的洞胃给出的原版随机遗物沿用原版图；第一章的杏仁水不属于本轮范围。玩法、数值、文本和原生遗物状态结算没有改动。

## 画风与原画

实际查看当前 V111 解包中的 Ink Bottle、Meal Ticket、Membership Card、Lantern、Maw Bank、Ember Tea、Silken Tress、Arcane Scroll 图案，按同类遗物的轮廓、色块和细节密度重绘。收敛旧图的亮金属、零碎饰物与高反射；保留粗而不规则的暗色轮廓，简化为少量手绘明暗块。32／48px 下仍能辨认瓶、纸牌、蘑菇印记、余烬与蛇发。

五张选定原画由本轮已授权的**内置 `image_gen`**生成，准确模型名未由工具提供，不能标为 Sunburst。原画均为 1254×1254 RGBA，周边是真实透明 alpha。完整提示词、选定原图、加工记录和哈希保存在：

- [`source_assets/relics/depths_event_refresh_20261009/`](../source_assets/relics/depths_event_refresh_20261009/)
- [`generation.json`](../source_assets/relics/depths_event_refresh_20261009/generation.json)
- [`export-record.json`](../source_assets/relics/depths_event_refresh_20261009/export-record.json)

旧版资源备份在 `build/depths-event-relics-20261009/before/`。未将凭据写入提示词、生成记录或运行包。

## 原生资源接入

核对 `RelicModel.Icon / IconOutline / BigIcon`、`NRelic.Reload` 与 `NRelicInventoryHolder` 的实际路径。原版大图为 256×256；小图使用逻辑 85×85 的 AtlasTexture，原版示例包含 atlas 裁区与透明 margin。此前五件自制遗物的小图直接引用 256 图，本轮改为独立导出：

- `images/relics/<key>.png`：256×256 大图。
- `images/relics/<key>_packed.png`：85×85 小图。
- `images/atlases/relic_atlas.sprites/<key>.tres`：原生小图入口。
- `images/atlases/relic_outline_atlas.sprites/<key>_outline.png` 和对应 `.tres`：85×85 白色轮廓。

白色轮廓来自小图 alpha 的 2px 扩展，由原版界面着色。原生遗物组件继续承担描边、计数、聚焦放大、灰置和 shader；没有增加自定义 UI 补丁。

导出入口：[`scripts/export-depths-event-relic-icons.gd`](../scripts/export-depths-event-relic-icons.gd)。用 Godot 原生 PNG／AtlasTexture 操作裁取、居中、缩放和透明边缘准备；Python 只负责联系图、记录与 ZIP，不重画运行资产。

## 本轮验证与自审

1. 深／浅底色联系图，旧版／重绘／原版参考，以及 48／32px 对照均已实际查看。没有矩形底色、明显透明光晕或过细的主体；五件使用一致的图标语言。
2. V111：使用当前真实 `sts2.dll` 和客户端 PCK，实例化原生 `NRelic`、`NRelicInventoryHolder`，**70 项通过**。最终包的大小图与轮廓像素与选定 PNG 经原生 `FixAlphaEdges` 后完全一致；计数、真实聚焦 tween、灰置 shader 均正确。原生渲染图已实际查看，画风和界面尺寸自审通过。
3. V107.1：保存的真实 V107 程序集及对应模组实现，配合当前 V111 PCK／共享依赖进行同一组件检查，**70 项通过**。这是旧 API 组件兼容验证，**不是完整 V107 客户端实测**。
4. 独立组件宿主中用原版 `shouldBlockHoverTips` 阻止浮窗；测试了聚焦动画，没有验证完整提示面板、真实事件领取或联机。
5. 最终 PCK 挂载后逐一验证 **1269 项资源**的哈希；仅五件遗物相关的 **40 项**导入／纹理／AtlasTexture 发生变化。其他资源及三个程序集／清单运行文件与安装基线保持一致。
6. ZIP 四个运行文件的 CRC、条目清单和 SHA256 全部通过。

入口：[`scripts/test-depths-relic-art.ps1`](../scripts/test-depths-relic-art.ps1)、[`scripts/pack-depths-event-relics.gd`](../scripts/pack-depths-event-relics.gd)、[`scripts/package-depths-event-relics.py`](../scripts/package-depths-event-relics.py)。记录在 `build/depths-event-relics-20261009/native/{v111,v107.1}/`、`pack-report.json` 和 `delivery.json`。

## 开发包与安装状态

基底为当前已安装的 `build/bug-report-fix-20261009/package/`，PCK SHA256：
`0f589289a22f3c722f0af9c5081b0a80000a36dfc8aa02831e6cbfcf32498469`。

独立开发包：`dist/v1.25.13/depths-event-relics/STS2_Things-v1.25.13-event-relic-art.zip`，包含清单、统一 DLL、PCK、BaseLib 可选桥接四个运行文件。

- ZIP SHA256：`85f32ac86fe1d1c82ea3cc3f5fe30977428feb6b9639626dae5c3502e0cf601e`。
- 新 PCK SHA256：`b51504b1378e55646aa47bf8ebd729943ec4f994357db8f31b4e988294a8213d`。
- 安装指纹：`74154a7c68fdd8197c0cb8a8b34262f3d22ecac2033e5f92e1bd83e117239ba1`。

本包仅在上述基线之上替换遗物美术，不用于覆盖其他聊天随后产生的独立构件；正式统一发布时按当前源码构建并再次核验。当前游戏进程仍在运行，未安装本包。没有修改 Steam／GitHub 页面或执行发布。

## 预览

![五件重绘遗物](../build/depths-event-relics-20261009/final-preview.png)

![原生遗物组件渲染](../build/depths-event-relics-20261009/native/v111/native-relic-components.png)

旧版／新图／原版／小尺寸／浅色边缘对照：`build/depths-event-relics-20261009/style-comparison.jpg`。
