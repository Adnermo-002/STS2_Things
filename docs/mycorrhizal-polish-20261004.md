# 1.14.1 · 菌洞站位、连接根与双生子动作

本次根据用户的两张截图修正角色站位与菌根接点，并细化两种专精的动画。精英池、生命交换、丰盛／萎蔫数值和断根狂暴规则沿用 1.14.0。

## 场景与连接根

苔色菌洞 `hollow_grotto_moss` 的 `bg_03` 装饰层中，两簇独立高草正好落在人物与怪物站位内。只清除这两簇高草，保留洞顶、低矮石块、原有洞壁和原创地板。共享此场景的遭遇一起获得站位修正。

原菌根由三条纯色多边形带组成，并使用角色根节点加固定偏移定位。它缺少根足和体态缩放的信息，导致扁平折线、贴进腹部或离开根足。现在改为手绘根茎贴图与原生纹理曲线，端点绑定 `root_socket` 骨骼，使用实际骨骼的世界坐标；在 Spine 更新后重算曲线，随角色体态、根足和位置一起变化。增加柔和地面阴影与养分流光，断根后淡出。

根茎由 imagegen 官方 CLI 的 `edit` 入口调用用户指定的 **gpt-image-2.5-sunburst**，以双生子原画为风格及颜色参考。完整提示词：[root_prompt.txt](../source_assets/monsters/mycorrhizal_twins/root_prompt.txt)。原始输出为同目录 `root_generated.png`，运行贴图为 `images/vfx/mycorrhizal_root.png`。密钥没有写入文件。

## 动作

每只由 20 根骨骼细化为 27 根，保留 8 个独立蒙皮层、12 组动作和 2 种体态。

- 增加菌帽两端的柔性骨骼、四根根指骨骼及专用连接接点。
- 长兄的根鞭增加后撤蓄力、分臂抽击、指端展开与手腕延迟回弹。
- 幼弟的攻击改为压低身体后以菌帽顶撞，双臂配合支撑；防御动作加强撑帽、下压与收回。
- 待机使用不同呼吸和眨眼节奏；施法与狂暴增加菌帽边缘的延迟形变及眼神变化。
- 交换动画延长到 1.55 秒，容纳养分输送和体态过渡。
- 按实际动画进度等待接触与回位；双抽只启动一次动画，分别等待 0.48、0.73 秒的两次接触，再播放命中特效并结算伤害，避免原版快／普通模式不同的默认间隔造成错位。

## 复现与验证

原生回归入口：先设置 `THINGS_GROUNDING_REVIEW=1`，再执行 `scripts/test-mycorrhizal-twins.ps1 -TargetVersion v111 -ImplementationDll build/v111/STS2_Things.dll -PackagePck build/v111/STS2_Things.pck -Visual`。检查真实背景贴图在人物站立区的透明度，以及实际绘制根端与骨骼接点之间的距离。

1. 1.14.0 基线稳定失败：站位内 1,372 个采样点被高装饰占用；根端偏移约 49.73／54.32 像素。
2. 只替换装饰层的隔离检查：占用降为 0，根端偏移仍为原值，确认是两个独立问题。临时纹理覆盖入口已移除。
3. 完整修正：占用 0；两端误差小于 0.001 像素；交换强弱体态后仍通过。
4. 官方 Spine 4.2.43 每只检查 1,304 帧，共 2,608 帧，无非有限坐标或三角形翻折，待机与倒地／复起接缝误差为零。
5. v111 原生机制、画面与连续动作共 502 项通过，输出 404 张动作帧。最终命中等待调整后，v111 与 v107.1 各 83 项机制复检通过。
6. 双版本 Release、资源与 PCK 契约、Harmony／保存缓存检查通过；统一包两版各加载 101 个模型。

实际查看了原生画面与动作联系图：人物脚边已清理，根不再是折线色块，端部落在根足中；正常、强弱互换、攻击、防护及狂暴姿态没有看到旧接点偏移。连续动作与两版行为验证分别记录，不能用骨骼结构检查代替画风判断。

v0.111.0 单人实机重新加载新版，确认背景高草已移除、手绘根可见。打击幼弟后完成两次敌方回合，生命按 82／76 → 76／82 → 82／76 交换，体态和根端同步变化；长兄造成 17 和 4×2 伤害，幼弟正常防护及施加覆甲。实机截图与状态位于 `build/mycorrhizal_polish/live/`。实际网络联机未人工试玩。

## 产物

- [场景与菌根前后对照](../build/mycorrhizal_polish/review/before-after.jpg)
- [28.2 秒新版动作预览](../build/mycorrhizal_polish/review/mycorrhizal-twins.mp4)（原生姿态采样，不是实机战斗录像）
- `dist/v1.14.1/STS2_Things-1.14.1.zip`
- `build/mycorrhizal_polish/final-validation.json`：最终包哈希、安装一致性及验证结果。

旧装饰原图保存在 `source_assets/backgrounds/hollow_grotto_moss/standing_space_original.png`。重建资源使用 `scripts/polish_mycorrhizal_assets.py`、`tools/MycorrhizalTwinsRig/build.py` 和 `scripts/integrate_mycorrhizal_twins.py`；普通重建不调用生图 API。
