# Thief Raider v9 limb underlap — VISUAL GATE REJECTED

## 结论

**硬 FAIL。当前 10 个 limb underlap / combined attachment 全部不得进入 Spine、PCK 或 Steam。**

这不是“再微调几像素”即可通过的版本。当前输出把 B2 的圆帽、填塞块和错误材质裁成了关节附近的碎片；它们在 bind pose 里可能被邻件遮住，但一旋转就会出现圆帽、黑洞、橄榄条纹、断肢、鞋面鱼鳍和漂浮肉块。

审查时已实际逐图查看并对比：

- `04_production_attachments/limb_underlap.contact.png`
- `04_production_attachments/combined_limb_preview.contact.png`
- `00_reference/current_master.png`
- 正式资源 `D:/Things/Things-Workspace/STS2_Things/images/monsters/thief_raider.png`

两张身份图 SHA256 完全相同：

`643A86C7D8B9BB885161AC6ABAD39F8C3B8AF09FCB8AD8E016B90FEEE73B06FB`

因此本报告中的偏差来自 underlap/combined 输出，不是参考图不同。

## 根因（构建逻辑级）

`build_limb_underlaps.py:254-262` 的核心掩码是：

```python
joint_zone = _capsule_mask((height, width), JOINT_ZONES[semantic])
hidden_mask = joint_zone & master_foreground & ~visible
warped = _nearest_rgba_fill(warped, hidden_mask)
```

这会把“关节圆域内、属于任意其他母图前景层的像素形状”直接当成本附件的隐藏延伸。结果不是解剖连续的 sleeve/socket，而是复制邻件轮廓形成豆子、圆帽、分离岛和弯月碎片。随后 `_nearest_rgba_fill` 又把最近 donor 像素强行延伸进这些形状，黑色/橄榄色/错误高光也一并被灌进去。

`build_limb_underlaps.py:292-305` 只凭总隐藏面积 `8.10%` 落在任意的 `4%-18%` 区间，就给出 `area_pass`。它没有检查：

- underlap 与本体的语义连通；
- 两端是否各有足够 joint socket；
- 是否仍有圆帽、平切口、背景污染；
- 旋转后是否露出邻件轮廓形的碎片；
- full-chain draw order；
- shoulder/elbow/hip/knee/ankle 极限姿势。

所以当前 `limb_underlap_area_pass_extreme_pose_pending` 只是面积统计通过，**不构成视觉通过**。

## 逐附件硬 FAIL

### 00 `near_upper_arm`

- underlap 本身有 **2 个大连通岛**：肩部一枚漂浮的灰紫圆帽，肘部一枚梨形/手套形填塞块。
- 肘端有明显黑绿污染边；材质比母图袖子更紫、更亮、更像充气橡胶。
- combined 看起来像“袖子上贴一枚硬币、下接一只肿胀拳套”，不是连续上臂。
- 两端都是帽状封口，±45° 肩旋转或大屈肘时必露圆盖。

**处理：整份 underlap 丢弃。** 重做一条连续的暗灰布质上臂隐藏体：肩端藏入 `near_shoulder_plate` 12–16 px，肘端藏入 bracer 10–14 px；union 必须是单一语义轮廓，不得出现黑绿边。

### 01 `near_forearm`

- 497 个 underlap 像素中约 **369 px 是纯黑**，另有橄榄黄斜条；它看起来是黑色冰球/空洞，不是皮革、布或手腕。
- alignment coverage 只有 `0.496`，是本批最差之一，却仍被面积 Gate 接受。
- combined 仍有 **2 个连通岛**：主护臂与右下方 17×18 px 弯月碎片没有桥接。
- 黑圆块被放在腕端，视角和材质都与母图暖色手部、棕色护腕冲突。

**处理：整份 underlap 丢弃。** 先确认右下弯月属于护腕背沿还是 `near_dagger_hand`；若属于护腕，用母图棕皮/肤色做隐藏 wrist bridge，把它与主护臂连成一个可弯曲腕口；肘端另做暗灰布 overlap。禁止任何纯黑填塞。

### 02 `near_thigh`

- underlap 主要只剩膝下的一枚灰紫豆子，另有 1 px 噪点；没有形成可信的髋部 socket。
- combined 的膝下像长出一颗肉瘤/膝盖垫，形状和母图裤腿的低频布褶不一致。
- underlap 亮度、紫度高于母图炭灰裤料；弯曲后会露出胶囊切面。
- 当前小豆的覆盖范围远低于髋 ±35°、膝 55–155° 的真实链路需求。

**处理：丢弃豆状 underlap。** 分别制作“髋部宽 crescent”和“膝部窄圆柱 overlap”，都以母图炭灰裤料为可见边界；两端隐藏长度单独验算，不用一个胶囊块同时敷衍髋和膝。

### 03 `near_shin`

- underlap 是 **2 个分离岛**：上端为黑绿三角 + 灰紫塞块，下端为高饱和橙棕饼。
- combined 的靴筒上口仍像空心管，里面露出黑绿背景残片和灰紫塞子。
- 下端橙棕饼与靴筒不连接，像悬浮鞋舌；主件底部仍保留明显水平平切口。
- 同一 attachment 内同时混入错误“裤料”和过亮皮革，极限姿势必出现拼贴感。

**处理：整份 underlap 丢弃。** 上端只做母图炭灰裤腿，连续插入靴筒；下端只做与母图靴筒一致的哑光棕皮 ankle overlap，并真正连接到 shaft。膝、踝分别测试，不得用两个漂浮岛。

### 04 `near_boot`

- underlap 是一枚 23×14 px 的橙棕竖鳍/鸡冠，位置在鞋面上方而不是完整踝 socket。
- combined 像鞋子长出鱼鳍；原本 50 px 左右的平顶切口绝大部分仍裸露。
- 该体积不足以覆盖 ±25° 踝旋转，稍转即露水平切面和断腿。

**处理：丢弃竖鳍。** 从 boot 顶边向上制作宽、圆、同材质的踝筒 underlap，宽度覆盖真实 shaft 接触面，并由 `near_shin` 在 bind pose 完整压住 10–14 px。

### 05 `far_upper_arm`

- 正式可见 ownership 为 **0 像素**；combined 其实 100% 是 donor，并非“母图可见像素 + 少量 underlap”。
- 当前形状是灰紫双球哑铃/鸡腿：上端大圆头、腰部收窄、下端小圆头，没有肩袖结构。
- 边缘有黑绿污染，体积过亮、过鼓，与母图远侧暗化、近大远小规律相反。
- 它属于完整缺失附件，却被同一局部 underlap 流程处理，这是分类错误。

**处理：最高优先级从零重生。** 单独图生图一条左向三分之二视角、较近臂更窄更暗的完整 far upper arm；肩端藏于远肩甲，肘端藏于 far forearm。生成后再由母图邻接色/阴影校准，不沿用当前哑铃 donor。

### 06 `far_forearm`

- underlap 形成一枚左侧灰紫拳头/棒槌，接缝处还有白色“牙齿/拉链/骨片”状伪影和小块肉色尖角。
- combined 让前臂在手腕侧突然多出拳套，横向比例过长，和胸前握带动作的受力方向不一致。
- 白色锯齿高光不属于母图任何腕部材质；一旦手 IK 拉开就直接暴露。

**处理：整份 underlap 丢弃。** 腕端围绕 `far_strap_hand` 的真实接触线制作棕色手套/皮腕隐藏桥；肘端做暗灰布 overlap。先锁定 strap 宽度、手掌遮挡和 wrist pivot，再画 underlap，禁止用完整 donor 前臂反向缩放。

### 07 `far_thigh`

- underlap 有 **2 个巨型分离岛**：髋部大圆球和膝后梨形挂件。
- combined 变成明显“雪人/三节葫芦”：上球 + 母图大腿 + 下球。
- 上球带黑绿污染；两球比母图裤料更紫、更亮，视角和体积都不服从远侧缩窄。
- `outside_ratio=0.221` 为本批最高，已经说明 donor 轮廓与目标严重不匹配。

**处理：整份 underlap 丢弃。** 只保留髋、膝各一条薄而宽的暗灰 crescent；远腿必须比 near thigh 更窄更暗，严禁完整圆球。用完整腿链极限姿势判定，而不是以 donor IoU 判定。

### 08 `far_shin`

- underlap 是 **2 个分离岛**：靴筒上口内一枚黑绿/橄榄条纹“眼睛”，下方一枚灰紫肉垫。
- combined 像空心靴筒里塞了橄榄，底部又吊着灰色爪垫；材质、色相和语义全错。
- 主件仍有平切底边，两个 underlap 都没有形成可信的膝/踝连续体。
- visible 自身还有右侧 7×5 px + 1 px 的孤立碎片，视觉上来自披风破口/轮廓噪点；若绑定到 `FarShin`，它会随小腿漂移。

**处理：先修 ownership，把右侧孤立碎片归回 `cape_back` 或删除 1 px 噪点。** 然后重做上端暗灰裤腿、下端同色棕皮 ankle overlap；两端都必须与 shin union 连通，禁止条纹黑洞和灰色豆子。

### 09 `far_boot`

- underlap 约 20% 像素为纯黑，混有橄榄绿和过亮橙色，形成斜向羽毛/蔬菜叶片。
- combined 像鞋口长出彩色羽毛；鞋顶的矩形平切仍大面积存在。
- donor 被旋转约 `-97°` 后截取，透视与远脚朝向不匹配；覆盖量低于踝 ±25° 的需求。

**处理：整份 underlap 丢弃。** 重做一个较 near boot 更窄、更暗的棕皮踝筒 socket，沿鞋口全宽衔接并藏入 `far_shin`；禁止保留任何黑绿 donor 端帽。

## 连通性证据

以 alpha ≥ 32 做 connected-components：

| attachment | underlap 大岛数 | combined 大岛/异常 |
|---|---:|---|
| near_upper_arm | 2 | 靠错误填塞勉强连成 1 |
| near_forearm | 1 | 2；仍有 176 px 孤岛 |
| near_thigh | 1 + 两个 1 px 噪点 | 1；但为豆状拼接 |
| near_shin | 2 | 靠邻件轮廓勉强连成 1 |
| near_boot | 1 | 1；但为竖鳍 |
| far_upper_arm | 1 | 1；100% donor 哑铃 |
| far_forearm | 1 | 1；白色锯齿伪影 |
| far_thigh | 2 | 靠球状填塞勉强连成 1 |
| far_shin | 2 | 3；另有 8 px 与 1 px 孤岛 |
| far_boot | 1 | 1；但为彩色羽毛 |

“combined 连成 1”不代表合格；多项只是 donor 圆帽跨过缺口，机械地把两个错误形状粘在一起。

## 可直接执行的修复顺序

1. **立即标记本批 rejected**：禁止将 `underlap_limbs/` 或 `combined_limb_preview/` 输入 Spine；manifest 状态改成视觉 FAIL 后再重跑生产。
2. **先修 ownership**：处理 `near_forearm` 的 17×18 弯月归属；把 `far_shin` 右侧 7×5 / 1 px 披风碎片移回 `cape_back`。
3. **删除错误掩码策略**：不得再用 `joint_zone & master_foreground & ~visible` 生成附件形状；改为每个关节人工/语义生成的 proximal、distal socket mask。
4. **先重生 far upper arm**：它没有母图可见像素，是完整资产缺口，不属于局部 underlap。
5. **重做腿链**：`near/far thigh → near/far shin → near/far boot`。每端独立生成，先完成髋/膝/踝 nesting，再做姿势测试。
6. **重做手臂链**：`near upper arm → near forearm → dagger hand`，再做 `far upper arm → far forearm → strap hand`。腕部必须围绕真实 dagger/strap 接触线。
7. **逐附件静态 Gate**：母图可见像素逐像素不变；无黑绿背景色；无圆帽、水平切口、白色锯齿；除明确被手/甲遮挡的 rear rim 外，union 应是单一语义连通体。
8. **完整链路极限 Gate**：肩 ±45°、肘 25–145°、髋 ±35°、膝 55–155°、踝 ±25°；每个极限姿势输出 full-chain checker 背景截图，以完整链路为准，跳过孤立 contact 的单独判定。
9. **全身 draw-order Gate**：在完整角色、完整邻接层中检查披风、肩甲、手、武器、背带、裤腿和靴子的遮挡；不得有像素跟错 bone。
10. **全部通过后才进入 Spine/Godot**；正式 `thief_raider.png`、现有 PCK 和 Steam 保持原样。

## 审查辅助图（非正式资源）

逐件世界坐标对齐放大图位于：

`D:/Things/Things-Workspace/STS2_Things/.tmp/thief_v9_visual_audit/00_near_upper_arm_zoom.png` 至 `09_far_boot_zoom.png`
