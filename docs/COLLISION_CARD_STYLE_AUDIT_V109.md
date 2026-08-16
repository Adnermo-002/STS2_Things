# 对撞卡图风格审计（v0.109.0）

## 审计范围

目标资源类型为战士（Ironclad）卡池的 `Attack + Uncommon` 卡牌肖像。源码与资源基线为
`D:\Things\Things-Workspace\STS2-V109`，对应 `v0.109.0 / c12f634d`。

筛选方式：从 `IroncladCardPool.GenerateAllCards()` 取全部模型，再以每个模型构造器中的
`CardType.Attack, CardRarity.Uncommon` 过滤。得到 15 个卡牌模型，及以下 18 个同类型原版
资源（其中 4 个为 beta 迭代图）。所有正式肖像均为 `1000 x 760` PNG。

| 模型 | 正式资源 | Beta 资源 |
| --- | --- | --- |
| AshenStrike | `images/packed/card_portraits/ironclad/ashen_strike.png` | - |
| Bludgeon | `images/packed/card_portraits/ironclad/bludgeon.png` | - |
| Bully | `images/packed/card_portraits/ironclad/bully.png` | - |
| Dismantle | `images/packed/card_portraits/ironclad/dismantle.png` | - |
| FightMe | `images/packed/card_portraits/ironclad/fight_me.png` | `images/packed/card_portraits/ironclad/beta/fight_me.png` |
| Hemokinesis | `images/packed/card_portraits/ironclad/hemokinesis.png` | - |
| HowlFromBeyond | `images/packed/card_portraits/ironclad/howl_from_beyond.png` | - |
| Outrage | beta fallback only | `images/packed/card_portraits/ironclad/beta/outrage.png` |
| Pillage | `images/packed/card_portraits/ironclad/pillage.png` | `images/packed/card_portraits/ironclad/beta/pillage.png` |
| Rampage | `images/packed/card_portraits/ironclad/rampage.png` | - |
| Spite | `images/packed/card_portraits/ironclad/spite.png` | `images/packed/card_portraits/ironclad/beta/spite.png` |
| Stomp | `images/packed/card_portraits/ironclad/stomp.png` | - |
| Unrelenting | `images/packed/card_portraits/ironclad/unrelenting.png` | - |
| Uppercut | `images/packed/card_portraits/ironclad/uppercut.png` | - |
| Whirlwind | `images/packed/card_portraits/ironclad/whirlwind.png` | - |

## 视觉总结

- **构图**：完整画面只承载一个可立即读出的攻击瞬间。主体通常在画面边缘被大胆裁切，动作沿
  对角线推进，冲击点位于画面中心或三分线附近；背景只用大面积剪影形状支撑运动方向。
- **轮廓与形体**：外轮廓使用近黑色粗线，内部用不规则黑色裂缝分隔甲片、武器和肌肉。形体由
  3 到 5 个硬边色块组成，优先保证小尺寸下的剪影识别，不使用写实软渐变或细密材质纹理。
- **明暗与配色**：深酒红、砖红、橙色构成主背景，偶尔以紫色制造对比。主体以深褐、黑、军绿
  与蓝灰为主，碰撞处使用琥珀黄、橙黄或白黄高光。深影与高光的明度跨度很大。
- **动势语言**：挥砍、重拳、撞击和旋风通过放射状楔形光束、少量几何碎片、喷溅状能量或拖尾
  来传达力度；每张图只保留一个焦点，不让特效覆盖主体轮廓。
- **风格边界**：beta 图是低保真草图和占位探索，只作为“从概念到定稿”的证据。成图只吸收正式
  肖像的平面化、强轮廓、块面光影和暖色冲击关系，不复制任何原图中的角色、武器、姿势、场景或
  特效形状。

## 对撞资产约束

`ThingsCollision` 的最终原创 `1000 x 760` 纯卡图位于
`images/packed/card_portraits/ironclad/things_collision.png`。最终采用 ImageGen `v8`：Ironclad 从左侧
以肩甲和面甲正面撞向始源雾菇，双方被画面边缘大胆裁切，中央只有一个明确碰撞点。红、橙几何冲击
背景强化方向，角色仍由粗近黑轮廓和少量硬边块面构成；不使用文字、卡框、徽标或水印。发布图仅对
ImageGen 源图做居中裁切和缩放，不补画或重绘内容。

## 参考输入

成图的视觉输入使用以下原版资源：

- `images/packed/card_portraits/ironclad/fight_me.png`
- `images/packed/card_portraits/ironclad/bully.png`
- `images/packed/card_portraits/ironclad/uppercut.png`
- `images/packed/card_portraits/ironclad/stomp.png`
- `animations/character_select/ironclad/characterselect_ironclad.png`
- `images/monsters/origin_fogmog.png`

前四张锁定 Ironclad Uncommon Attack 的粗黑轮廓、平面分色语言和紧凑的单焦点构图；角色选择立绘锁定
Ironclad 的实际面甲结构；`Fight Me` 锁定战士与大型敌人对峙时的尺度关系，始源雾菇成图锁定其红褐
菌盖、绿色孢泡、木质躯干和黑色面孔。生成提示要求新的正面对撞姿势，避免复刻任一参考图构图。

用于生成的风格提示应保持：原创的二维幻想 roguelike 卡牌插画、粗近黑轮廓、硬边低面数块面、
酒红背景剪影、琥珀边缘光、单一高可读碰撞焦点、无文字、无卡框、无徽标、无水印。
