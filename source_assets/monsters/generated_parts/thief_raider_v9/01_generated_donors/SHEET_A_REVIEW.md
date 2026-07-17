# Thief Raider v9 — Sheet A 严格视觉审查

## 结论

**整张 Sheet：退回，仅保留局部 donor。**

- Chroma/alpha 处理：PASS
- 连通域抽取：PASS，`12` 个有效 alpha island
- 语义分件：FAIL
- 闭合实体接口：FAIL
- current master 身份一致性：FAIL
- 左向近/远侧透视：FAIL
- 全套部件覆盖：FAIL
- 正式动画、PCK、Steam：均未触碰

状态统计：

| 状态 | 数量 | 含义 |
|---|---:|---|
| `usable` | 2 | 可进入下一轮 bind reconstruction 候选；仍需对照母图校准，尚非发布件 |
| `donor-only` | 8 | 只取局部绘制信息；必须重新拆分、补隐藏重叠或重绘 |
| `reject` | 2 | 从重建输入中剔除 |

## 审查基准与证据

正式身份母图：

`D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\00_reference\current_master.png`

Sheet A 原始生成图保留于：

`C:\Users\adner\.codex\generated_images\019f5afb-1b58-7441-967a-79eb6687c915\exec-ae253b38-fbd6-4f64-8e4d-1b0a9fd5388b.png`

项目内副本与处理结果：

```text
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\01_generated_donors\sheet_a_chroma.png
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\01_generated_donors\sheet_a_alpha.png
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\01_generated_donors\sheet_a.components.json
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\01_generated_donors\sheet_a.review.json
D:\Things\Things-Workspace\STS2_Things\source_assets\monsters\generated_parts\thief_raider_v9\01_generated_donors\sheet_a_components_contact.png
```

SHA256：

| 文件 | SHA256 |
|---|---|
| 原始生成图 / chroma 副本 | `BA8A4121078FA6EA74A42E7000E045389F68290CC8385F6C00A42497FBC75AFC` |
| alpha | `78ADDF1C5FD86E1A7D3A5C8696CDB77E112935090F754C0AB819D25DCF4901C2` |
| current master | `643A86C7D8B9BB885161AC6ABAD39F8C3B8AF09FCB8AD8E016B90FEEE73B06FB` |

Alpha 提取参数：自动边界取色 `#0AF90B`、soft matte、despill、透明阈值 `12`、不透明阈值 `220`。连通域使用 `alpha > 8`、8-connectivity；没有发现背景碎屑。

## 逐件判定

### 01 — `head_scarf_composite` — `donor-only`

文件：`sheet_a_components\01_head_scarf_composite.png`

- 兜帽、黑色面孔和整圈围巾粘成一个刚性复合件，头与围巾失去独立旋转关系。
- 兜帽体量比 current master 更膨大，头顶、开口和下颌比例发生身份漂移。
- alpha 轮廓闭合，没有透明空洞；问题属于语义融合而非抠图破损。
- 仅可从中提取兜帽/面孔的局部绘制信息，围巾需重新独立制作。

### 02 — `torso_belts_cape_composite` — `reject`

文件：`sheet_a_components\02_torso_belts_cape_composite.png`

- 右肩接口画成明显的**空心袖筒/插口**，直接违反闭合实体与隐藏重叠约束。
- 躯干、颈后围巾、披风尾、斜跨带、胸前扣、腰带、腰扣和下摆全部融合。
- 视角趋向正面、左右近似对称；current master 是低重心、稳定朝左的三分之二侧视。
- 新增双层腰带/扣具组合，斜带结构也与母图握住背袋带的关系不同，身份漂移显著。
- 该件不进入 bind reconstruction。

### 03 — `shoulder_plate_b` — `donor-only`

文件：`sheet_a_components\03_shoulder_plate_b.png`

- 独立、实体、边缘完整，基础材质可用作银甲 donor。
- 与 04 基本是同视角、同体量的复制件，缺少 near/far 尺寸与明暗差。
- 高光和银色亮度高于 current master，质感偏抛光。
- 需要重新定 near/far ownership、透视、缩放和哑光明度。

### 04 — `shoulder_plate_a` — `donor-only`

文件：`sheet_a_components\04_shoulder_plate_a.png`

- 独立、实体、边缘完整，基础材质可用作银甲 donor。
- 与 03 的透视和形状过近，未表达母图三分之二侧视中的近远不对称。
- 甲片底边和铆钉位置也没有对应 current master 的实际遮挡。

### 05 — `eye_left_sheet` — `usable`

文件：`sheet_a_components\05_eye_left_sheet.png`

- 单一语义、独立 alpha island、无复合结构和接口问题。
- 黄眼颜色与 current master 接近。
- 进入重建前仍需按母图重新校准尺寸、间距和开口内位置。

### 06 — `eye_right_sheet` — `usable`

文件：`sheet_a_components\06_eye_right_sheet.png`

- 单一语义、独立 alpha island、边缘干净。
- 与 05 有轻微尺寸差，可保留 near/far 不对称；实际归属需在母图坐标中确认。
- 进入重建前仍需执行母图像素级位置校准。

### 07 — `scarf_front_crescent` — `donor-only`

文件：`sheet_a_components\07_scarf_front_crescent.png`

- 是独立软质片，alpha 轮廓完整，没有机械式空心插口。
- 形状偏正面、近似对称的新月领，未保留 current master 从头到胸的左向包裹关系。
- Sheet 内 01 和 02 已各自带有围巾，导致三个互相冲突的 scarf ownership。
- 可取酒红布料色块，几何需重做。

### 08 — `pelvis_waist_cloth` — `reject`

文件：`sheet_a_components\08_pelvis_waist_cloth.png`

- 顶部画成黑色空腔和厚口沿，属于**空心腰筒接口**。
- 整件是正面、左右对称的裙筒，与 current master 的左向蹲姿和近远腿遮挡不一致。
- 髋部连接没有隐藏像素延伸，旋转后会暴露切口。
- 该件不进入重建。

### 09 — `belt_pouch_composite` — `donor-only`

文件：`sheet_a_components\09_belt_pouch_composite.png`

- 腰带、扣、垂带和整只腰包融合成单件，无法分别跟随 pelvis、torso 和 pouch sway。
- 水平展开腰带接近正面陈列，母图实际是围绕蹲姿躯干的透视弧线。
- 腰包比母图更大、更鼓、更亮；轮廓身份发生偏移。
- 只保留皮革色块和局部五金参考，需重新分件。

### 10 — `sack_strap_composite` — `donor-only`

文件：`sheet_a_components\10_sack_strap_composite.png`

- 背袋、袋结、肩带环、垂带和底部带全部融合；连通域含 1 个由巨大带环形成的透明孔。
- 带子形成几何上过于完整的环，丢失 current master 中手握带、带受力、袋在背后受牵引的关系。
- 袋体变成平滑梨形，母图轮廓更圆、更有绑结与压缩感。
- 可作为棕革/袋布绘制 donor；袋、结和带必须重新独立。

### 11 — `arm_a_composite` — `donor-only`

文件：`sheet_a_components\11_arm_a_composite.png`

- 上臂、肘、前臂、金属护臂和皮革缠带融合，缺少独立手与腕部 ownership。
- 肩端为圆帽式断端，腕端为钝切口；没有满足旋转所需的自然隐藏重叠。
- 金属护臂位置可作 near-arm 绘制参考，整件不作为单骨骼长臂使用。

### 12 — `arm_b_composite` — `donor-only`

文件：`sheet_a_components\12_arm_b_composite.png`

- 上臂、肘、前臂和皮革端融合，缺少手、腕和独立关节。
- 两端都呈圆帽/钝切形，旋转会暴露不自然接口。
- near/far 归属含混；其体量和弯曲角度无法直接还原 current master 的持带手。

## Sheet 级问题

1. **覆盖严重不足**：12 个连通域中有 2 个只是眼睛；缺少匕首、匕首手、持带手、独立上下臂、完整双腿、双靴、独立披风段、独立袋结/袋带等关键语义件。
2. **复合件过多**：01、02、09、10、11、12 均把多个应独立旋转的语义合并；07/08 也无法直接承担正确的骨骼 ownership。
3. **空心接口**：02 的肩洞、08 的腰筒是明确失败点；11/12 虽未形成透明洞，仍是圆帽和钝切式断端。
4. **身份漂移**：母图的左向低姿态被替换成多个正面陈列部件；双腰带、复制肩甲、新月围巾、梨形袋改变了原角色关系。
5. **图层风险**：同一围巾信息同时出现在 01、02、07；肩甲 03/04 ownership 不明；若直接组装会产生重复绘制、前后侧跳层和遮挡冲突。
6. **材质偏差**：整体色系大致接近，但银甲更亮、更抛光，酒红布更均匀、更鲜；只可作为局部 donor，不作为身份基准。

## 下一阶段准入条件

- 重新生成/制作缺失的手、匕首、双腿、双靴与分段披风。
- torso、pelvis、两条手臂、腰带/腰包、背袋/袋结/袋带必须成为独立语义件。
- 所有关节端使用闭合实体和自然隐藏延伸；肩、肘、腕、髋、膝、踝至少提供可承受约 25° 旋转的重叠像素。
- near/far 件必须以 current master 的左向三分之二视角分别制作，避免镜像复制。
- bind reconstruction 对正式母图执行 alpha IoU ≥ 0.995 与 combat-scale 视觉审查后，再进入 Spine。
