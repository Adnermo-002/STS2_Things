# Thief Raider v9 — Sheet B 严格视觉审查

## 结论

**整张 Sheet：退回，仅匕首保留为可继续校准的 donor。**

- Chroma/alpha 处理：PASS
- 连通域抽取：PASS，`13` 个有效 alpha island
- 语义分件：PARTIAL FAIL
- 闭合实体与关节 underlap：FAIL
- current master 身份一致性：FAIL
- near/far 视角与体量差：FAIL
- 正式动画、PCK、Steam：均未触碰

| 状态 | 数量 | 含义 |
|---|---:|---|
| `usable` | 1 | 可进入下一轮 donor 覆盖与 bind 校准；尚非发布件 |
| `donor-only` | 6 | 仅保留材质或局部绘制信息，几何与 ownership 需重建 |
| `reject` | 6 | 从 production attachment 输入中剔除 |

## 证据文件

```text
身份母图：
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\00_reference\current_master.png

原始生成图：
C:\Users\adner\.codex\generated_images\019f5afb-1b58-7441-967a-79eb6687c915\exec-b20e2005-7db5-49a8-8874-b8460bd6db2c.png

项目内副本与结果：
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\01_generated_donors\sheet_b_chroma.png
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\01_generated_donors\sheet_b_alpha.png
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\01_generated_donors\sheet_b.components.json
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\01_generated_donors\sheet_b.review.json
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\01_generated_donors\sheet_b_components_contact.png
```

SHA256：

| 文件 | SHA256 |
|---|---|
| 原图 / chroma 副本 | `35BB1E560778A00BCF72A664BF19823C6848B82FCDAA3A2CB431B6EB152B5F15` |
| alpha | `06AD22A4A6895F956DB167772DF55E25F23B51787393B1ADD71589DB81686BB0` |
| current master | `643A86C7D8B9BB885161AC6ABAD39F8C3B8AF09FCB8AD8E016B90FEEE73B06FB` |

Alpha 使用自动边界取色 `#03F902`、soft matte、despill；连通域使用 `alpha > 8` 与 8-connectivity。抠图边缘未发现绿幕残留。

## 逐件审查

### 01 — `upper_arm_a_hollow_cuff` — `reject`

文件：`sheet_b_components\01_upper_arm_a_hollow_cuff.png`

- 下端画成明显的黑色空心袖口，属于插筒式接口。
- 肢体像一根软管，缺少实体肘区和 10–18 px 自然 underlap。
- 圆柱体视角是独立陈列角度，未锁定 current master 的左向肩肘关系。

### 02 — `forearm_b_bracer_hollow_cuff` — `reject`

文件：`sheet_b_components\02_forearm_b_bracer_hollow_cuff.png`

- 腕端为黑色空心袖筒，旋转后会直接看到洞口。
- 布前臂、皮革缠带与金属护臂融合，腕部仍缺闭合重叠区。
- 银甲比母图更亮、更抛光；near/far ownership 与 03 含混。

### 03 — `forearm_a_bracer_hollow_cuff` — `reject`

文件：`sheet_b_components\03_forearm_a_bracer_hollow_cuff.png`

- 与 02 同类：空心腕口、管状结构、无闭合手腕 underlap。
- 护臂几乎是另一张同视角复制，缺少近远侧尺寸、明暗和透视差。
- 不进入 production forearm。

### 04 — `upper_arm_b_hollow_cuff` — `reject`

文件：`sheet_b_components\04_upper_arm_b_hollow_cuff.png`

- 弯曲软管末端仍是完整可见的黑色空洞。
- 轮廓把关节做成管体折弯，没有明确肩、肘及隐藏连接面。
- 与 01 没有可靠 near/far ownership，只是换了弯曲幅度。

### 05 — `closed_fist_b` — `donor-only`

文件：`sheet_b_components\05_closed_fist_b.png`

- alpha 实体完整，手套、皮革和肤色绘制可作局部参考。
- 这是普通握拳；母图远手必须真实抓住 `strap_front`，指缝中需要带子与受力关系。
- 腕角、指节和掌面方向无法对应 `far_strap_hand`，几何需重做。

### 06 — `closed_fist_a` — `donor-only`

文件：`sheet_b_components\06_closed_fist_a.png`

- 是完整独立手形，没有 alpha 洞。
- 普通握拳没有匕首柄通道，手指也未包住护手后的握柄。
- 可取肤色/手套材质；`near_dagger_hand` 必须基于母图重新构造。

### 07 — `bent_thigh_b` — `donor-only`

文件：`sheet_b_components\07_bent_thigh_b.png`

- 外轮廓闭合，但两端是圆帽状胶囊，没有明确髋端与膝端 underlap。
- 形状像整段弯曲软管，膝部 ownership 模糊。
- 与 08 高度重复，未体现 current master 的近大远小、前后遮挡和不同压缩量。

### 08 — `bent_thigh_a` — `donor-only`

文件：`sheet_b_components\08_bent_thigh_a.png`

- 布料大色块可作隐藏区域 donor，alpha 轮廓完整。
- 与 07 几乎是同一视角和同一弯曲结构，near/far 身份不明确。
- 髋、膝连接均需按母图 ownership 重建并补 10–18 px underlap。

### 09 — `wrapped_shin_b` — `donor-only`

文件：`sheet_b_components\09_wrapped_shin_b.png`

- 没有透明洞，但把深色裤腿帽、皮革包裹和整段小腿合成一个钝端件。
- 踝端为平切，未提供与 boot 的双向隐藏重叠。
- 与母图远腿的角度、压缩和遮挡关系不一致。

### 10 — `wrapped_shin_a` — `donor-only`

文件：`sheet_b_components\10_wrapped_shin_a.png`

- 皮革和布料材质可作 donor。
- 顶部圆帽、底部钝切，膝/踝两端都缺生产级 underlap。
- 与 09 的 near/far 区分很弱，正式使用前需重新定尺寸和透视。

### 11 — `dagger` — `usable`

文件：`sheet_b_components\11_dagger.png`

- 单一、完整、独立的武器语义；刀刃、护手、握柄均连续，无空心接口。
- 刀尖方向明确朝左，符合角色攻击方向。
- 仍需覆盖回 current master 的可见像素，并校准长度、刀宽、护手 pivot、旋转角和哑光明度。
- 当前判定仅表示可继续作为 donor，不表示 bind 或发布批准。

### 12 — `boot_a_hollow_cuff` — `reject`

文件：`sheet_b_components\12_boot_a_hollow_cuff.png`

- 靴筒顶部是完整可见的深色空腔，属于明确空心插口。
- 靴子过于直立、独立陈列，未对应母图蹲姿中的胫骨角和脚底支撑。
- 靴口需要闭合实体绘制，并在裤腿下隐藏 10–18 px。

### 13 — `boot_b_hollow_cuff` — `reject`

文件：`sheet_b_components\13_boot_b_hollow_cuff.png`

- 与 12 相同的空心靴筒问题。
- 两只靴几乎同角度、同体量；缺少远侧更窄、更暗、更受遮挡的特征。
- 不进入 far_boot/near_boot 生产候选。

## Sheet 级问题

1. **六处明确空心接口**：01、02、03、04、12、13 都把袖口、腕口或靴筒画成可见洞口；alpha mask 没有透明孔，是因为洞被画成了不透明暗色，这仍属于视觉空心失败。
2. **功能手缺失**：05/06 是普通握拳，既不握匕首也不抓背袋带；架构要求 `near_dagger_hand` 与 `far_strap_hand` 各自包住真实物体。
3. **near/far 弱化**：两条上臂、两条前臂、两只拳、两条大腿、两条小腿和两只靴普遍近似复制，缺少母图三分之二左向的近远差异。
4. **管状/胶囊化**：四个臂件和两条大腿都使用圆管或胶囊体积，轮廓比 current master 更像光滑 3D 模型。
5. **材质漂移**：深色布大体同色，但过于均匀圆润；皮革更亮、更橙，银甲与匕首高光偏抛光。
6. **生产覆盖仍断裂**：即使把 A/B 合看，torso、pelvis、披风、围巾、带子、袋结与四肢依旧需要按 29-attachment 合同重新制作；当前 donor 不直接进入动画 atlas。

## 下一阶段准入条件

- 两条上臂、两条前臂、两条小腿与双靴全部改成闭合实体端面，关节内侧补 10–18 px 自然 underlap。
- `near_dagger_hand` 围绕真实刀柄制作；`far_strap_hand` 围绕 `strap_front` 制作，禁止以普通拳替代。
- near/far 每一对都按 current master 单独定透视、体量、明暗、遮挡与 pivot，避免复制镜像。
- 大腿拆成单一 ownership 的 `near_thigh` / `far_thigh`，髋端与膝端分别闭合并补隐藏像素。
- 匕首完成母图可见像素覆盖和 pivot 校准后，再参加 bind Gate。
- bind reconstruction 继续执行 alpha IoU ≥ 0.995、area ratio 0.99–1.01、centroid ≤ 1 px、可见 RGB MAE ≤ 2/255；通过后再进入 Spine。
