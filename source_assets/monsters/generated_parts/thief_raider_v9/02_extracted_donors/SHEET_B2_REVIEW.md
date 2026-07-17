# Thief Raider v9 — Sheet B2 修正版复审

## 总判定

**B2 完成了“去掉可见空洞”这一项，但整张仍退回。**

- 原 6 个空心口：`6/6` 已变成不透明闭合表面
- 仍可见的洞口/管口：`0`
- 已验证的 10–18 px 自然 underlap：`0/6`
- `near_dagger_hand` grip：FAIL
- `far_strap_hand` grip：FAIL
- near/far 层次：FAIL
- 材质与身份：FAIL
- 正式 animations、PCK、Steam：均未触碰

逐件结果：

| 状态 | 数量 |
|---|---:|
| `usable` | 1 |
| `donor-only` | 10 |
| `reject` | 2 |

这次修正把洞“盖住了”，但多数端面仍是圆帽或深色填塞块。它们只有在 bind 中被相邻部件完整遮住、并通过极限旋转测试后，才可作为隐藏像素 donor。

## 审查文件

```text
身份母图：
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\00_reference\current_master.png

B2 alpha：
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\01_generated_sheets\sheet_b2_closed_corrections_alpha.png

抽取 manifest：
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\02_extracted_donors\sheet_b2.manifest.json

抽取 contact：
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\02_extracted_donors\sheet_b2.contact.png

结构化复审：
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\02_extracted_donors\sheet_b2.review.json
```

SHA256：

| 文件 | SHA256 |
|---|---|
| B2 alpha | `305540F0723C352F2ED4B694A507AAAFCE31675B6EA34DE2107C606A98633882` |
| current master | `643A86C7D8B9BB885161AC6ABAD39F8C3B8AF09FCB8AD8E016B90FEEE73B06FB` |
| B2 manifest | `522A603595BC97F5581583EB7E78657A2D09EE9C91BA96498621675A78B9E37C` |
| B2 contact | `F11B6F1440268A1E8397A899D4323DB88F4A455670FD5D98A6B3817692DCD1C1` |

## 六个原空心口复查

| 部件 | 空洞是否消失 | 当前端面 | 判定 |
|---|---|---|---|
| `near_upper_arm` | 是 | 同色圆帽式布面 | `donor-only`，等待肘部 overlap 注册 |
| `near_forearm` | 是 | 深色不透明腕帽 | `donor-only`，等待手腕 nesting |
| `far_upper_arm` | 是 | 同色圆帽式布面 | `donor-only`，等待肘部 overlap 注册 |
| `far_forearm` | 是 | 深色不透明腕帽 | `donor-only`，等待手腕 nesting |
| `near_boot` | 是 | 靴口上方增加深色布质圆顶 | `donor-only`，圆顶必须隐藏在 near_shin 下 |
| `far_boot` | 是 | 靴口上方增加深色布质圆顶 | `donor-only`，圆顶必须隐藏在 far_shin 下 |

结论：六处在 alpha 和视觉上都没有残留透明洞、内壁、环形口沿或凹入管腔；“空心修正”本身通过。它们尚未证明 underlap 的长度、遮挡和 pivot 正确，因此闭合关节 Gate 仍未通过。

## Grip 语义复查

### `near_dagger_hand` — `reject`

- 已从普通拳改成张开的弯指手，但目前更像四指分开的“爪形”。
- 空通道过宽，未围绕真实匕首柄注册；拇指与食指也未形成护手后的夹持锁点。
- 掌面朝向观察者，current master 的匕首手需要顺着向左的水平握柄收紧。
- 即使把 B2 匕首直接放入，手指与柄之间也会出现空隙或穿插；该几何不进入 `near_dagger_hand`。

### `far_strap_hand` — `reject`

- 同样是张开的爪形，未围绕 `strap_front` 实际宽度和受力方向制作。
- 指缝过宽，没有指尖压带、拇指扣带和带子前后遮挡关系。
- current master 的手在胸前紧握近竖直背带；B2 的掌面、腕角和手指扇形展开均不匹配。
- 该几何不进入 `far_strap_hand`。

## Near/Far 复查

按 manifest 的 alpha area 计算 `far / near`：

| 配对 | far/near 面积比 | 结果 |
|---|---:|---|
| upper arm | `1.1347` | far 反而大 13.5%，方向错误 |
| forearm | `1.0226` | far 大 2.3%，方向错误 |
| hand | `1.0478` | far 大 4.8%，方向错误 |
| thigh | `1.0683` | far 大 6.8%，方向错误 |
| shin | `0.9343` | far 小 6.6%，方向正确 |
| boot | `0.9361` | far 小 6.4%，方向正确 |

上臂、前臂、手和大腿仍违背“近侧略大、远侧略窄略暗”的家族透视。两条大腿继续使用高度相似的弯曲胶囊轮廓；两块前臂护甲也接近同视角复制。

## 材质与朝向

- 深灰布比 current master 更平滑、更鼓，体积接近充气胶囊，低频块面虽统一但缺少母图压缩折叠。
- B2 皮革出现显著亮橙色簇（约 `#C97C51`）；current master 的主皮革簇集中在更暗的 `#633E33 / #7D524A / #967766`。
- 护臂和匕首高光更白、更抛光；母图银甲更灰、更哑光。
- 匕首和双靴朝左较明确；手、前臂和大腿仍是独立陈列视角，未形成同一个左向三分之二 bind pose。

## 逐件最终状态

| index | semantic | 状态 | 核心原因 |
|---:|---|---|---|
| 00 | `near_upper_arm` | `donor-only` | 洞已闭合；圆帽端与肘 overlap 尚未注册 |
| 01 | `near_forearm` | `donor-only` | 洞已闭合；腕帽、手腕 nesting、护臂明度待修 |
| 02 | `near_dagger_hand` | `reject` | 爪形张手，未形成真实匕首 grip |
| 03 | `far_upper_arm` | `donor-only` | 洞已闭合；far 比 near 更大，端面仍为帽状 |
| 04 | `far_forearm` | `donor-only` | 洞已闭合；腕部 underlap 与 near/far 透视待修 |
| 05 | `far_strap_hand` | `reject` | 爪形张手，未抓住实际 strap |
| 06 | `near_shin` | `donor-only` | 布帽与皮革融合；膝踝 overlap 待注册 |
| 07 | `near_thigh` | `donor-only` | 胶囊轮廓；髋膝 ownership 不清 |
| 08 | `far_thigh` | `donor-only` | 与 near 高度重复且更大 |
| 09 | `far_shin` | `donor-only` | 膝踝 nesting 与角度待注册 |
| 10 | `near_boot` | `donor-only` | 靴筒已闭合；深色圆顶必须成为隐藏 underlap |
| 11 | `dagger` | `usable` | 单一完整语义；仍需母图像素覆盖、比例和哑光校准 |
| 12 | `far_boot` | `donor-only` | 靴筒已闭合；深色圆顶必须成为隐藏 underlap |

## 下一步准入条件

1. 两只手围绕**实际** `dagger` 和 `strap_front` 建立 grip，再重新抽离对象；必须保留接触位置、指缝遮挡和 wrist pivot。
2. 六个闭合端在 bind 中与相邻件重叠 10–18 px，端帽全部落入真实遮挡区。
3. 执行肩 ±45°、肘 25–145°、踝 ±25° 极限姿势；逐帧确认无圆帽暴露、无缝、无穿插。
4. 调整 near/far 尺寸层次：upper arm、forearm、hand、thigh 至少恢复近大远小及远侧偏暗。
5. current master 可见像素覆盖回 donor；B2 仅贡献母图原本不可见的关节背面和隐藏 underlap。
6. 完成 bind Gate（alpha IoU ≥ 0.995、area ratio 0.99–1.01、centroid ≤ 1 px、RGB MAE ≤ 2/255）后，再进入 Spine。
