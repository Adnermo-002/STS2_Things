# Thief Raider v10 / near-arm weighted mesh v05 视觉复盘

## 最终判定

**HARD FAIL。立即停止把 v05 微调成 v06。**

实际看过母图、`contact.jpg`、六张独立姿势、base/fold debug、elbow-fold 图生图结果和原版 Raider motion overview 后，v05 的成品观感就是一截被切下来的玩具手臂：bind 姿势勉强依赖原图遮挡成立，一旦肩或肘旋转，裁切口、空洞、尖刺、重复边缘和漂浮补片全部暴露。它不适合作为 Thief Raider 全角色骨骼动画的生产基础。

本轮只写复盘；正式怪物资源、PCK 与 Steam 安装均未触碰。

## 实际审阅对象

| 对象 | 路径 / SHA256 |
|---|---|
| 身份母图 | `images/monsters/thief_raider.png` / `643A86C7D8B9BB885161AC6ABAD39F8C3B8AF09FCB8AD8E016B90FEEE73B06FB` |
| v05 总览 | `05_spine_prototype/near_arm_weighted_mesh_v05/contact.jpg` / `69503ABF9ACC205BAE2600E39E6970D8CD73B4E9F5226FB7F82C19604987C7B2` |
| elbow-fold 图生图 | `01_image_to_image_families/near_elbow_fold_candidate_01_alpha.png` / `04F6664D83FB2C452797ED7A4971CEF26AC6335299546B39944A258D068DDDB5` |
| 原版 Raider 动作总览 | `build/thief_v10_raider_motion_blueprint/renders/contacts/all_raiders_motion_overview.png` / `8EE2EB2DED92CFF4CDAA8319C763F1E552C65EC1F4D58B7E18D08AA5CEAF934A` |

另逐张查看了：

- `bind.png`
- `shoulder_back_45.png`
- `shoulder_forward_45.png`
- `elbow_open_55.png`
- `elbow_close_75.png`
- `elbow_close_110.png`
- 全部对应的 `debug_base_*` 与 `debug_fold_*`
- `near_arm_cloth_base.png`、`near_elbow_fold_patch.png`
- 上下文揭示母图、aligned 图、hidden-only、attachment 与 extraction contact
- Assassin 的 attack / hurt / die 关键帧，以及 Crossbow / Tracker 的动作帧

## 一眼可见的失败点

### 1. `bind`

- 只在原始角度看似完整，原因是所有缺口仍被原来的肩甲、护臂和手遮住。
- 肩端轮廓本身已经是撕裂状裁切口，不是可旋转的肩部结构。
- 这张图证明的只是“原图碎片可以重叠回原图”，没有证明它能动画。

### 2. `shoulder_back_45`

- 肩甲像一枚松动徽章浮在袖子顶部，和真实肩窝没有结构关系。
- 袖口顶部出现明显锯齿、黑色缺口和硬切边。
- 整条手臂像围绕一个屏幕坐标旋转，而不是从胸腔、锁骨和肩带发力。
- 刀刃在画布底边被截断；`audit.json` 的 alpha bbox 底边正好为 `420`。

### 3. `shoulder_forward_45`

- 肘附近出现一圈圆形压痕/塞子式暗纹，正是用户已经明确排除的“圆帽、圆塞”观感。
- 上臂外轮廓在关节处鼓成球，前臂却突然变细，体积连续性消失。
- 肩甲继续以任意比例漂移，未跟随真实锁骨—上臂链。
- 刀刃被画布左边截断；alpha bbox 左边为 `0`，所以这张压力测试本身已失效。

### 4. `elbow_open_55`

- 内肘塌成黑色三角凹口，像折断的铰链。
- 护臂、手和刀柄在狭窄区域互相挤压，手腕读不出来。
- 刀刃再次被画布底边截断；alpha bbox 底边为 `420`。
- 这不是自然伸肘，而是纹理条带被拉弯后露出缺像素区域。

### 5. `elbow_close_75`

- 上臂末端出现尖锐布片和暗色楔形洞，前臂像从袖子旁边插进去。
- 金属护片压在弯曲布料上，但布料没有被压缩形成可信褶皱；两者像两张贴纸相交。
- 肘窝形状过窄，失去手臂厚度，轮廓接近夹钳。
- 所谓 elbow fold 只在后方露出一点蓝灰碎片，既未补体积，也未遮接缝。

### 6. `elbow_close_110`

- 最严重的一张：上臂和前臂之间出现大面积黑洞，肩袖像被撕开。
- 肩甲、袖体、护臂的连接关系全部断开；底部还有一块悬空的蓝灰碎片。
- 手与刀保持刚性，但整段前臂穿过了已塌陷的肘窝，像坏掉的可动人偶。
- 这张图已经直接否定“只调补片大小、亮度和层序即可修好”的判断。

## elbow-fold 资产为什么是“布料枕头”

`near_elbow_fold_candidate_01_alpha.png` 不是局部肘褶，而是一块巨大的、四边鼓起的软垫：

- 原始 alpha bbox 为 `972 × 685 px`，主体占据 1280 画布的大半。
- 它有完整的中央隆起、四周坡面和独立物体照明，读感是靠垫/枕头，而不是贴在弯肘内侧的布褶。
- 原始蓝通道均值 `74.05`，目标袖布均值 `53.64`。脚本随后进行了逐通道重映射，这已经偏离“保留原版色系、禁止靠后处理调色修素材”的约束。
- 缩放旋转后补片仍有 `1520` 个像素，占整条 cloth base `3879` 像素的约 **39%**。一个“局部隐藏褶”不应接近整条袖布面积的四成。
- 上下文揭示真正新增的隐藏像素只有 `694`；准备后的补片约为其 **2.2 倍**。
- v05 又把它放在 upper/forearm cloth 下方。把它提到上层只会让枕头更显眼，不会恢复肘部解剖体积。

问题不在负面词写得还不够多，而在任务形式本身：提示要求生成“一个孤立 overlay”，模型缺少完整人物、具体弯曲角度、邻接袖片和最终遮挡关系，于是只能发明一个自洽的独立软物体。

## 根因

### A. 审核对象选错了

当前接触表展示的是被自动放大的孤立断臂，每张卡片还按自身 bbox 重新缩放。它同时隐藏了四件关键事实：

1. 手臂是否真正连接胸腔与肩带；
2. 全身重心是否参与攻击；
3. 固定战斗尺度下的接缝是否仍显眼；
4. 怪物是否侵入 intent、血条、卡牌和相邻怪物区域。

原版 Raider overview 显示，攻击不是“肩 45° + 肘 75°”的局部机械旋转。Assassin 在接触帧有完整的胸腔前压、重心推进、披风滞后和脚下支撑；hurt 与 die 也由全身轮廓变化主导。v05 把最重要的全身链路全部排除在测试之外。

### B. bind-only 上下文揭示提供的像素远远不够

`near_arm_cloth_base.png` 实际是一条狭窄的斜向布带，不是具有前后厚度的完整手臂表面：

- 肩后侧、腋下、内肘与外肘的隐藏面缺失；
- 原 bind crease 已经烘焙在纹理里，旋转后仍跟着拉伸；
- 只有一个 bind 姿势的 694 个新增隐藏像素，却拿去覆盖 -55° 至 +110° 的所有形变。

网格只能搬运已有像素，不能凭空补出弯肘时应出现的内侧体积。

### C. 这不是足以生产的 2D 权重网格

`_deform_point()` 只依据像素沿肩—肘—腕链的一维坐标，在固定 `24 px` 区间内把上臂与前臂两个结果做 smoothstep 混合。它没有：

- 横截面权重；
- 肘内侧/外侧不同的压缩与拉伸；
- 面积或体积保持；
- 肩胛/锁骨权重；
- 针对 contact、hurt、die 的 corrective deformation。

所以大角度下必然出现 pinch、尖刺和空洞。

### D. 重复图层与层序制造了额外伪影

当前顺序是：

`base → fold → upper → full forearm mesh → rigid metal duplicate → plate → dagger → hand`

直接后果：

- `base`、`upper` 和 `full forearm` 重复覆盖相同抗锯齿边缘，产生暗边与模糊边；
- full forearm 中的金属已经被网格弯曲，随后又叠一份 rigid metal；底层副本仍会在边缘漏出；
- leather 并未使用已计算的 rigid 分区，仍跟随 full forearm 一起橡皮化；
- fold 在两层袖布下面，承担不了修复轮廓的职责；
- shoulder plate 用 `shoulder_deg * 0.42` 这个经验比例单独旋转，缺少真正的 clavicle/torso 父链与遮挡约束。

### E. 压力测试画布已经裁切结果

六张图里至少三张 alpha bbox 触边：

- `shoulder_back_45`: bottom = `420`
- `shoulder_forward_45`: left = `0`
- `elbow_open_55`: bottom = `420`

触边意味着轮廓数据已被丢失。这样的 contact sheet 既不适合判断武器轨迹，也不适合判断最终战斗 envelope。

## 资产处置

### 立即淘汰为生产资产

以下文件保留在隔离目录仅用于失败复盘，后续构建不得引用：

1. `01_image_to_image_families/near_elbow_fold_candidate_01_alpha.png`
2. `01_image_to_image_families/near_elbow_fold_candidate_01_chroma.png`
3. `05_spine_prototype/near_arm_weighted_mesh_v05/near_elbow_fold_patch.png`
4. `05_spine_prototype/near_arm_weighted_mesh_v05/near_arm_cloth_base.png`
5. `05_spine_prototype/near_arm_weighted_mesh_v05/*.png`
6. `05_spine_prototype/near_arm_weighted_mesh_v05/contact.jpg`
7. 当前 `build_near_arm_weighted_mesh_prototype.py` 的 v05 合成/变形方案

### 只保留为参考或测量依据

- `01_image_to_image_families/near_upper_arm_context_reveal_candidate_01_*`
- `02_semantic_parts/near_upper_arm_context_01/*`
- `00_reference/near_arm_ownership_v2/*`

其中 ownership v2 的价值是“bind 可见像素归属正确”，不是“这些裁片已经可旋转”。context reveal 的价值是证明 full-character 局部揭示可行，但当前单一 bind 结果仍不够生产。

### 继续保留为正式基准

- `00_reference/current_master.png`
- 正式 `images/monsters/thief_raider.png`
- `build/thief_v10_raider_motion_blueprint/*`

## 修正方案：完整角色关键姿势 → 上下文揭示 → 全身绑定

### 第 1 步：先做完整角色关键姿势，不再生成孤立肢体

以锁定母图为 Image 1，原版 Raider 关键帧只作为动作与重心参考，生成固定画布、固定比例、固定朝向的完整 Thief Raider 姿势：

1. bind / idle 中性帧；
2. attack windup；
3. attack contact；
4. attack recoil；
5. hurt peak；
6. die collapse。

每张输出必须是完整角色，保留原版色系、紧凑蹲伏比例、朝左三分之四视角。动作目标先审全身剪影、脚底、重心和武器轨迹；未通过前不拆件。

### 第 2 步：在每个已通过的完整姿势里做局部遮挡揭示

针对每个姿势，仍编辑完整角色：

- 临时移除肩甲，揭示胸腔—锁骨—上臂连续布面；
- 临时移除护臂近端，揭示该姿势真实的内肘/外肘布面；
- 必要时临时移除手、刀柄或围巾覆盖，只补邻接部件下方的 concealed underlap；
- 锁住编辑区外像素，生成后只抽取新增隐藏像素。

这样得到的是“该角色在该姿势里的真实隐藏面”，不是独立软垫、袖筒或圆帽。

### 第 3 步：用全身结构绑定，肩部跨过 torso 边界

建议骨链：

`root → pelvis → torso → clavicle_near → upper_arm_near → forearm_near → hand_near → dagger`

生产层次：

- torso 与上臂之间使用一块跨肩的连续 cloth mesh，权重分给 torso / clavicle / upper arm，避免肩端切口暴露；
- 上臂与前臂使用真正二维 painted weights；内肘与外肘采用不同权重梯度；
- 肩甲、护臂金属、皮带、手、刀保持独立刚性 attachment；
- attack contact 与高弯肘姿势使用由完整角色关键帧提取的 corrective mesh/attachment；通过双 slot alpha 混合或短时 attachment swap 接入，不使用通用“肘部补丁”；
- 围巾、披风、包袋等前后遮挡必须与整条攻击链一起确定 draw order。

### 第 4 步：按 Raider 的全身运动做动画

动作蓝图继续沿用：

- attack：`0.10s` 蓄力、`0.333s` 推进、`0.450s` 接触、`0.650s` 回弹、`1.10s` 复位；
- 接触帧由 pelvis/torso/clavicle 推进，手臂只完成最后的武器方向，不单独做 110° 铰链弯折；
- hurt 以短促旋转与局部收缩为主；
- die 必须由 pelvis、膝、torso 和头共同塌落；
- idle 只保留呼吸、围巾/披风轻微惯性，脚底锁定。

### 第 5 步：改用全角色、固定尺度的视觉门

每个关键姿势同时输出：

1. 完整角色固定尺度 contact；
2. 肩/肘 4× 局部放大；
3. alpha 轮廓；
4. draw-order 分色图；
5. 与批准关键姿势的半透明叠加；
6. Godot 战斗场景实载截图，带 intent、血条、卡牌与相邻怪物安全框。

所有姿势使用同一画布与同一缩放，禁止按 bbox 自动放大。任何 alpha bbox 触边、黑洞、尖刺、裁片口、漂浮金属、手腕断裂或 UI 越界都直接退回对应的完整角色 reveal/mesh，而不是再塞一张补丁。

## 下一步唯一合理入口

冻结 `near_arm_weighted_mesh_v05`，先制作并审查 **完整 Thief Raider attack windup / contact / recoil 三张关键姿势**。三张全身剪影通过后，再分别做 shoulder 与 elbow 的上下文揭示；随后构建 torso—clavicle—arm 的整链原型。

继续在 v05 上缩小、提亮、上移 elbow fold，只会把“藏在后面的布料枕头”变成“盖在前面的布料枕头”。
