# STS2_Things 怪物材质与骨骼管线（V108）

## 目标与边界

本管线覆盖项目当前全部自有怪物视觉，并以 STS2 `v0.108.0`、Godot
`4.5.1 Mono` 为运行基线。原则如下：

- **原图色系是美术契约**：不做全局色相、饱和度、对比度、Gamma、亮度或替换色板处理。
- 材质优化只使用轻量轮廓分离、同值乘数表面纹理和透明区外描边。
- 自定义静态怪物使用 Godot `Skeleton2D + Bone2D + Polygon2D` 加权网格。
- Origin Eye With Teeth 保留原版 Spine、原版 atlas 色系和原版动画。
- 所有动画只改变本地视觉，不读取玩法 RNG，不写共享战斗状态，也不参与网络输入。

## 覆盖清单

| 视觉 | 场景 | Rig | 骨数 |
|---|---|---:|---:|
| Origin Fogmog | `scenes/creature_visuals/origin_fogmog.tscn` | Humanoid | 9 |
| Thief Raider | `scenes/creature_visuals/thief_raider.tscn` | Humanoid | 9 |
| Scale Beetle | `scenes/creature_visuals/scale_beetle.tscn` | Wide | 10 |
| Bowlbug Progenitor | `scenes/creature_visuals/bowlbug_progenitor.tscn` | Wide | 10 |
| Soul Roes | `scenes/creature_visuals/soul_roes.tscn` | Cluster | 10 |
| The Legacy | `scenes/creature_visuals/the_legacy.tscn` | Cluster | 10 |
| Soul Roe 1/2/3 | `soul_roe*.tscn` | Orb | 3 |
| Origin Eye With Teeth | 原版 `eye_with_teeth` 场景 | 原版 Spine | 原版 |

每个自有 TSCN 独立设置：

- `rig_profile`
- `rig_motion_scale`
- `rig_grid_size`
- `rig_stiffness`

硬壳、武器和管道类视觉使用更高 stiffness 与更锐利的局部权重，避免明显橡皮形变。
`%Bounds` 已包含动作包络，`%CenterPos` 与 `%IntentPos` 继续遵循原生
`NCreatureVisuals` 合同。

## 源图与确定性构建

可编辑源图保存在：

```text
source_assets/monsters/
```

发布贴图由下列脚本确定性生成：

```powershell
python scripts/stylize_monster_textures.py
```

脚本保持画布尺寸与 RGBA 语义，只对三个通道同时乘以相同系数，因此不改变色相和
通道比例。Soul Roe 与 Soul Roes 同样使用其原始橄榄/金色透明球色系，不再重绘成另一
套色板。`source_assets/**` 被排除在 PCK 外，发布包只携带运行时贴图。

`scripts/verify_project.py` 会检查：

1. 源图和发布图集合完全一致；
2. 发布图确实经过构建但画布尺寸不变；
3. 每张发布图 RGBA 与 alpha 非空；
4. 可见源像素的 RGB 通道偏移及平均绝对差不超过门限；
5. 构建脚本再次运行后产物可复现。

## 共享材质

资源：

```text
STS2_Things/materials/monster_inked.tres
STS2_Things/shaders/monster_inked.gdshader
```

Godot CanvasItem 的 fragment 输入 `COLOR` 已经包含纹理采样和
vertex/modulate/self-modulate。identity shader 因此保持 `COLOR` 原值，不能再次执行
`texture(TEXTURE, UV) * COLOR`，否则会产生近似 `TEXTURE²`、压暗 RGB 并平方 alpha。

当前 shader 明确禁止运行时色彩分级；自动门禁会拒绝 saturation、contrast、poster、
pigment 等调色参数及二次纹理采样。

## 运行时骨骼

核心实现：

```text
STS2_Things/Visuals/NThingsCreatureVisuals.cs
STS2_Things/Hooks/RiggedMonsterVisualPatches.cs
```

`NThingsCreatureVisuals._Ready()` 执行以下步骤：

1. 读取 `%Visuals` 的原始纹理和尺寸；
2. 根据 Rig profile 创建独立加权控制骨；
3. 生成 6–24 格可调的 `Polygon2D` 网格、UV 和三角形；
4. 以高斯距离和 stiffness 生成归一化顶点权重；
5. 复制当前实例材质，隐藏原 Sprite2D 本体并显示加权网格；
6. 保留 Sprite2D 作为原生朝向、缩放、液体覆盖与 body 合同节点。

独立控制骨会在入树前调用：

```csharp
SetAutocalculateLengthAndAngle(false);
SetLength(...);
SetBoneAngle(0f);
```

这避免 Godot 4.5.1 对无子骨骼叶节点自动推导长度时产生警告。

## 动画触发桥

支持语义触发：

```text
Idle / Attack / Cast / Summon / PowerUp / Hit / Dead / Revive
```

Harmony 仅镜像原生 `NCreature` 动画触发流。`Summon` 与 `PowerUp` 复用 Cast 姿态；
死亡与复活另行桥接，是因为无 Spine 的自定义视觉在原生 `StartDeathAnim` /
`StartReviveAnim` 中不会进入 `_spineAnimator` 分支。怪物模型提供死亡动画时长覆盖，确保
战斗命令等待、淡出和实际姿态长度一致。

## Origin Eye With Teeth

Origin Eye 继续使用 V108 原版 Spine：

- 场景：`SceneHelper.GetScenePath("creature_visuals/eye_with_teeth")`
- 动画：`idle_loop`、`attack`、`die`
- `Modulate = Colors.White`

其幻象身份由原生 Illusion/Minion power、VFX 和玩法表现表达，不再用紫色乘色破坏原版
atlas 的灰阶、描线与透明度。

## 构建、安装与验收

```powershell
cd D:\Things\Things-Workspace\STS2_Things
.\scripts\build.ps1 -Configuration Release -Install
```

自动验收包括：

- source audit；
- FMOD audit；
- C# Release 0 warning / 0 error；
- Godot 4.5.1 import/export；
- mounted-PCK runtime contract；
- `validate_mod.py --require-artifacts`。

实机回归命令：

```text
fight ORIGIN_FOGMOG_BOSS_ENCOUNTER
fight RAID_PARTY
fight SCALE_BEETLE_BOSS_ENCOUNTER
fight SOUL_ROES_ENCOUNTER
fight THE_LEGACY_BOSS_ENCOUNTER
fight BOWLBUG_PROGENITOR_BOSS_ENCOUNTER
```

每次检查 Idle、攻击/施法/召唤、受击、死亡、点击包络、硬质部位形变以及
`godot.log` 中的 Bone2D、Polygon2D、shader、资源和脚本错误。运行时生成的骨骼只属于
本地表现，不影响 fastmp 或多人确定性。
