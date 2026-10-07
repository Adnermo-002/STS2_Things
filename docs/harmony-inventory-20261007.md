# Harmony 保留清单 — 1.25.6

当前源码共 67 个带 `HarmonyPatch` 声明的补丁类，包含 1.25.5 新增的两个深处事件池补丁。相对同一内容基线，本次移除了四个补丁类。不同目标的条件编译会改变实际启用数。

此外 `LibraryIntegration` 手动安装一个可选设置库加载重试；V107 统一引导手动安装两个程序集归属补丁，V111 改用官方归属 API。它们未计入下面的业务源码声明数。

接口依据和迁移证据见 [主审查记录](native-harmony-20261007.md)。清单不表示这些功能可以完全脱离 Harmony。

| 补丁类 | 源文件 | 保留依据 |
| --- | --- | --- |
| `CombatRoomAudioCleanupPatch` | `STS2_Things/Audio/CombatRoomAudioCleanupPatch.cs:11` | 本地音频节点退出／中止清理，战斗完成 Hook 不覆盖退出 |
| `CustomMusicPlayPatch` | `STS2_Things/Audio/CustomMusicHooks.cs:15` | 原版 FMOD 入口无法直接播放模组 WAV |
| `CustomMusicStartAfterCombatSetupPatch` | `STS2_Things/Audio/CustomMusicHooks.cs:51` | 原版 FMOD 入口无法直接播放模组 WAV |
| `SfxCmdPlayPatch` | `STS2_Things/Audio/SfxHooks.cs:106` | 模组 WAV 路由及原版 FMOD 回退；资源预载已迁回 AssetPaths |
| `SfxCmdPlayDamagePatch` | `STS2_Things/Audio/SfxHooks.cs:132` | 模组 WAV 路由及原版 FMOD 回退；资源预载已迁回 AssetPaths |
| `SfxCmdPlayDeathPatch` | `STS2_Things/Audio/SfxHooks.cs:154` | 模组 WAV 路由及原版 FMOD 回退；资源预载已迁回 AssetPaths |
| `StartDeathAnimPatch` | `STS2_Things/Audio/SfxHooks.cs:177` | 模组 WAV 路由及原版 FMOD 回退；资源预载已迁回 AssetPaths |
| `DrawFromDiscardPatch` | `STS2_Things/Cards/DrawFromDiscardPatch.cs:24` | 原版抽牌 Hook 无法修改取牌来源 |
| `LanternBlindnessTurnCleanupPatch` | `STS2_Things/Cards/LanternBlindness.cs:36` | 每张牌原生清理及复制时同步视觉元数据，费用已用原生临时费用 |
| `LanternBlindnessClonePatch` | `STS2_Things/Cards/LanternBlindness.cs:44` | 每张牌原生清理及复制时同步视觉元数据，费用已用原生临时费用 |
| `ConfigSessionAttachPatch` | `STS2_Things/Config/MultiplayerConfigPatches.cs:11` | 开始／恢复及随机生成前锁定房主配置，覆盖离开／失败会话 |
| `ConfigHostStartPatch` | `STS2_Things/Config/MultiplayerConfigPatches.cs:40` | 开始／恢复及随机生成前锁定房主配置，覆盖离开／失败会话 |
| `ConfigLocalStartPatch` | `STS2_Things/Config/MultiplayerConfigPatches.cs:46` | 开始／恢复及随机生成前锁定房主配置，覆盖离开／失败会话 |
| `ConfigLocalResumePatch` | `STS2_Things/Config/MultiplayerConfigPatches.cs:52` | 开始／恢复及随机生成前锁定房主配置，覆盖离开／失败会话 |
| `ConfigJoinResponseGuardPatch` | `STS2_Things/Config/MultiplayerConfigPatches.cs:58` | 开始／恢复及随机生成前锁定房主配置，覆盖离开／失败会话 |
| `ConfigFailedJoinCleanupPatch` | `STS2_Things/Config/MultiplayerConfigPatches.cs:71` | 开始／恢复及随机生成前锁定房主配置，覆盖离开／失败会话 |
| `ConfigSessionCleanupPatch` | `STS2_Things/Config/MultiplayerConfigPatches.cs:88` | 开始／恢复及随机生成前锁定房主配置，覆盖离开／失败会话 |
| `ConfigLobbyCleanupPatch` | `STS2_Things/Config/MultiplayerConfigPatches.cs:102` | 开始／恢复及随机生成前锁定房主配置，覆盖离开／失败会话 |
| `DynamicVarBaseValuePatch` | `STS2_Things/Enchantments/ThingsSplit.cs:988` | 永久成长／费用直接 setter 与读档还原不由战斗输出 Hook 覆盖 |
| `DynamicVarUpgradePatch` | `STS2_Things/Enchantments/ThingsSplit.cs:1002` | 永久成长／费用直接 setter 与读档还原不由战斗输出 Hook 覆盖 |
| `TheScytheCurrentDamagePatch` | `STS2_Things/Enchantments/ThingsSplit.cs:1026` | 永久成长／费用直接 setter 与读档还原不由战斗输出 Hook 覆盖 |
| `GeneticAlgorithmCurrentBlockPatch` | `STS2_Things/Enchantments/ThingsSplit.cs:1047` | 永久成长／费用直接 setter 与读档还原不由战斗输出 Hook 覆盖 |
| `SovereignBladeCurrentDamagePatch` | `STS2_Things/Enchantments/ThingsSplit.cs:1068` | 永久成长／费用直接 setter 与读档还原不由战斗输出 Hook 覆盖 |
| `SovereignBladeCurrentRepeatsPatch` | `STS2_Things/Enchantments/ThingsSplit.cs:1084` | 永久成长／费用直接 setter 与读档还原不由战斗输出 Hook 覆盖 |
| `EnergyCostUpgradePatch` | `STS2_Things/Enchantments/ThingsSplit.cs:1100` | 永久成长／费用直接 setter 与读档还原不由战斗输出 Hook 覆盖 |
| `EnergyCostCustomBasePatch` | `STS2_Things/Enchantments/ThingsSplit.cs:1125` | 永久成长／费用直接 setter 与读档还原不由战斗输出 Hook 覆盖 |
| `BaseStarCostPatch` | `STS2_Things/Enchantments/ThingsSplit.cs:1140` | 永久成长／费用直接 setter 与读档还原不由战斗输出 Hook 覆盖 |
| `StarCostUpgradePatch` | `STS2_Things/Enchantments/ThingsSplit.cs:1153` | 永久成长／费用直接 setter 与读档还原不由战斗输出 Hook 覆盖 |
| `ClearEnchantmentPatch` | `STS2_Things/Enchantments/ThingsSplit.cs:1177` | 永久成长／费用直接 setter 与读档还原不由战斗输出 Hook 覆盖 |
| `CardDowngradePatch` | `STS2_Things/Enchantments/ThingsSplit.cs:1188` | 永久成长／费用直接 setter 与读档还原不由战斗输出 Hook 覆盖 |
| `CardDeserializationPatch` | `STS2_Things/Enchantments/ThingsSplit.cs:1206` | 永久成长／费用直接 setter 与读档还原不由战斗输出 Hook 覆盖 |
| `CuttingItCloseConsoleReentryPatch` | `STS2_Things/Events/CuttingItClose.cs:133` | 控制台换房前清屏并阻止活动事件重复重入 |
| `MerchantEntryOnTryPurchaseWrapperPatch` | `STS2_Things/Features/MerchantBargain/MerchantBargainPatches.cs:13` | 购买前异步猜拳拦截没有等价 Hook；价格职责可单独迁移 |
| `MerchantEntryCostPatch` | `STS2_Things/Features/MerchantBargain/MerchantBargainPatches.cs:47` | 后续复查发现 `ModifyMerchantPrice` 已存在，可评估迁移；本轮未删除，见全模组复用审查 |
| `MerchantBargainAssetPreloadPatch` | `STS2_Things/Features/MerchantBargain/MerchantBargainPatches.cs:68` | 商人房间的专属资源目录扩展，不能以价格 Hook 替代 |
| `DepthsActCatalogPatch` | `STS2_Things/Hooks/DepthsActPatches.cs:9` | 固定章节目录及原版成就枚举不包含自定义章节 |
| `DepthsVanillaAchievementPatch` | `STS2_Things/Hooks/DepthsActPatches.cs:22` | 固定章节目录及原版成就枚举不包含自定义章节 |
| `DepthsGeneratedEventsPatch` | `STS2_Things/Hooks/DepthsEventPoolPatch.cs:10` | 1.25.5 延续：原版生成追加共享事件和旧池抽取前清理 |
| `DepthsSavedEventsPatch` | `STS2_Things/Hooks/DepthsEventPoolPatch.cs:16` | 1.25.5 延续：原版生成追加共享事件和旧池抽取前清理 |
| `DeterministicCardPoolOrderPatch` | `STS2_Things/Hooks/DeterministicPoolOrderPatches.cs:77` | 原版拼接模组池没有排序，维持多人确定性顺序 |
| `DeterministicRelicPoolOrderPatch` | `STS2_Things/Hooks/DeterministicPoolOrderPatches.cs:87` | 原版拼接模组池没有排序，维持多人确定性顺序 |
| `DeterministicPotionPoolOrderPatch` | `STS2_Things/Hooks/DeterministicPoolOrderPatches.cs:97` | 原版拼接模组池没有排序，维持多人确定性顺序 |
| `ConfiguredEncounterDrawPatch` | `STS2_Things/Hooks/EncounterSelectionPolicy.cs:114` | 原版抽取缺少自定义权重／强制 Boss 与第二 Boss 政策 Hook |
| `ConfiguredSingleBossSecondEncounterPatch` | `STS2_Things/Hooks/EncounterSelectionPolicy.cs:162` | 原版抽取缺少自定义权重／强制 Boss 与第二 Boss 政策 Hook |
| `OvergrowthEncounterPoolPatch` | `STS2_Things/Hooks/MonsterContentPatches.cs:137` | 原版章节遭遇及 Boss 发现目录没有模组注册入口 |
| `UnderdocksEncounterPoolPatch` | `STS2_Things/Hooks/MonsterContentPatches.cs:148` | 原版章节遭遇及 Boss 发现目录没有模组注册入口 |
| `HiveEncounterPoolPatch` | `STS2_Things/Hooks/MonsterContentPatches.cs:159` | 原版章节遭遇及 Boss 发现目录没有模组注册入口 |
| `OvergrowthBossDiscoveryPatch` | `STS2_Things/Hooks/MonsterContentPatches.cs:170` | 原版章节遭遇及 Boss 发现目录没有模组注册入口 |
| `UnderdocksBossDiscoveryPatch` | `STS2_Things/Hooks/MonsterContentPatches.cs:181` | 原版章节遭遇及 Boss 发现目录没有模组注册入口 |
| `HiveBossDiscoveryPatch` | `STS2_Things/Hooks/MonsterContentPatches.cs:192` | 原版章节遭遇及 Boss 发现目录没有模组注册入口 |
| `MycorrhizalPlayerLayoutPatch` | `STS2_Things/Hooks/MycorrhizalPlayerLayoutPatch.cs:10` | Encounter 没有独立玩家队形偏移接口 |
| `SnailCrawlIntentLabelPatch` | `STS2_Things/Hooks/SnailCrawlIntentLabelPatch.cs:13` | 原版只为攻击／状态牌意图显示数字，防御计数无扩展入口 |
| `CrossroadNeowPatch` | `STS2_Things/Map/CrossroadNeowPatch.cs:13` | 横路初始化和恢复绑定原版涅奥生命周期 |
| `CrossroadNeowResumePatch` | `STS2_Things/Map/CrossroadNeowPatch.cs:49` | 横路初始化和恢复绑定原版涅奥生命周期 |
| `CrossroadRunPatch` | `STS2_Things/Map/CrossroadPatches.cs:12` | 同行历史、免费旅行、地图按钮和所有权需要各自原版入口兼容 |
| `CrossroadHistoryRecordPatch` | `STS2_Things/Map/CrossroadPatches.cs:24` | 同行历史、免费旅行、地图按钮和所有权需要各自原版入口兼容 |
| `CrossroadHistoryLookupPatch` | `STS2_Things/Map/CrossroadPatches.cs:35` | 同行历史、免费旅行、地图按钮和所有权需要各自原版入口兼容 |
| `CrossroadFreeTravelPatch` | `STS2_Things/Map/CrossroadPatches.cs:48` | 同行历史、免费旅行、地图按钮和所有权需要各自原版入口兼容 |
| `CrossroadMapDisplayPatch` | `STS2_Things/Map/CrossroadPatches.cs:63` | 同行历史、免费旅行、地图按钮和所有权需要各自原版入口兼容 |
| `CrossroadMapOwnerPatch` | `STS2_Things/Map/CrossroadPatches.cs:73` | 同行历史、免费旅行、地图按钮和所有权需要各自原版入口兼容 |
| `RequiredMonsterMoveTransitionPatch` | `STS2_Things/Monsters/OriginEyeWithTeeth.cs:147` | 原版能力的强制复苏／眩晕调用须越过一次性状态，仅两模型 |
| `GravetideRavenousPowerPatch` | `STS2_Things/Powers/GravetideRavenousPowerPatch.cs:19` | 原版 Ravenous 强转 CorpseSlug，自定义尸体随从不兼容 |
| `OvergrowthAllEventsPatch` | `STS2_Things/STS2_ThingsInit.cs:150` | 原版章节事件目录固定；仅在涅奥选项构建时筛选自定义遗物 |
| `UnderdocksAllEventsPatch` | `STS2_Things/STS2_ThingsInit.cs:160` | 原版章节事件目录固定；仅在涅奥选项构建时筛选自定义遗物 |
| `HiveAllEventsPatch` | `STS2_Things/STS2_ThingsInit.cs:170` | 原版章节事件目录固定；仅在涅奥选项构建时筛选自定义遗物 |
| `NeowCurseOptionsPatch` | `STS2_Things/STS2_ThingsInit.cs:182` | 原版章节事件目录固定；仅在涅奥选项构建时筛选自定义遗物 |
| `LanternBlindnessCardVisualPatch` | `STS2_Things/Visuals/NBlindCardVeil.cs:107` | 原生 NCard 重建时恢复本地花屏／乱码视觉 |
