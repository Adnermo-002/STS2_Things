using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Godot.Bridge;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Acts;
using MegaCrit.Sts2.Core.Models.CardPools;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Models.RelicPools;
using STS2_Things.Cards;
using STS2_Things.Compatibility;
using STS2_Things.Config;
using STS2_Things.Encounters;
using STS2_Things.Events;
using STS2_Things.Hooks;
using STS2_Things.Modifiers;
using STS2_Things.Relics;

[ModInitializer(nameof(Initialize))]
public static class STS2_ThingsInit
{
    private const string HarmonyId = "Adnermo.STS2_Things";
    private static bool _initialized;

    public static void Initialize()
    {
        if (_initialized)
        {
            Log.Warn("STS2_Things - duplicate initialization ignored.");
            return;
        }

        try
        {
            var assembly = Assembly.GetExecutingAssembly();
            ScriptManagerBridge.LookupScriptsInAssembly(assembly);
            Sts2VersionCompatibility.InitializeBeforeModelDatabase();

            // 可配置门控：读取 user://mod_configs/STS2_Things.cfg（缺失时生成默认值），
            // 并尝试接入外部模组配置页框架（可选，非前置依赖）。
            ThingsModConfig.Load();
            MultiplayerConfig.Initialize();
            STS2_Things.Audio.ModMusicPolicy.Initialize();
            LibraryIntegration.Initialize();
            STS2_Things.Diagnostics.BugRunRecorder.Initialize();

            // ---- 卡牌 & 遗物 模型池注册 ----
            ModHelper.AddModelToPool<IroncladCardPool, ThingsCollision>();
            ModHelper.AddModelToPool<DefectCardPool, ThingsReuse>();
            ModHelper.AddModelToPool<EventCardPool, ThingsSurrender>();
            ModHelper.AddModelToPool<SilentCardPool, SoulfyshDisease>();
            ModHelper.AddModelToPool<SilentCardPool, ThingsRecall>();
            ModHelper.AddModelToPool<SilentCardPool, ThingsPackUp>();
            ModHelper.AddModelToPool<TokenCardPool, CaveGodBrokenBladeTrial>();
            ModHelper.AddModelToPool<TokenCardPool, CaveGodShatteredShieldTrial>();
            ModHelper.AddModelToPool<TokenCardPool, CaveGodMartialTrial>();
            ModHelper.AddModelToPool<TokenCardPool, CaveGodArcaneTrial>();
            ModHelper.AddModelToPool<TokenCardPool, ThingsCaveGodCrystalShard>();
            ModHelper.AddModelToPool<TokenCardPool, LeechParasite>();
            ModHelper.AddModelToPool<TokenCardPool, SnailCrystalChip>();
            ModHelper.AddModelToPool<EventRelicPool, ThingsWhiteFlag>();
            ModHelper.AddModelToPool<EventRelicPool, ThingsCurseRemover>();
            ModHelper.AddModelToPool<EventRelicPool, ThingsMagicGlove>();
            ModHelper.AddModelToPool<EventRelicPool, ThingsAlmondWater>();
            ModHelper.AddModelToPool<EventRelicPool, ThingsMedusaHair>();
            ModHelper.AddModelToPool<EventRelicPool, ShadowClaimTicket>();
            ModHelper.AddModelToPool<EventRelicPool, BottledEcho>();
            ModHelper.AddModelToPool<EventRelicPool, MycelialDeposit>();
            ModHelper.AddModelToPool<EventRelicPool, BorrowedEmber>();
            // Register deterministically on every peer, even when its local
            // preference disables this encounter. The policy already checks the
            // actual room, including encounters restored from a saved run.
            ModHelper.SubscribeForRunStateHooks(
                "Adnermo.STS2_Things.QuirkyHopperRewardPolicy",
                static _ => [ModelDb.Modifier<QuirkyHopperRewardPolicy>()]);
            ModHelper.SubscribeForRunStateHooks(
                "Adnermo.STS2_Things.SpentEmberRestPolicy",
                static _ => [ModelDb.Modifier<SpentEmberRestPolicy>()]);

            // ---- Harmony 初始化 ----
            var harmony = new Harmony(HarmonyId);

            // MonsterModel/EncounterModel 由当前目标的 ModelDb 自动发现。这里只安装固定 Act
            // 候选池等原版没有公开注册 API 的窄 Harmony 补丁；视觉、背景和槽位均由
            // MonsterModel/EncounterModel 的原生路径约定与 Godot 场景负责。
            harmony.PatchAll(assembly);

            _initialized = true;
            Log.Info("STS2_Things - 加载成功!");
        }
        catch (Exception e)
        {
            Log.Error("STS2_Things - 加载失败");
            Log.Error(e.ToString());
            throw;
        }
    }
}

// ==================== 事件注册 ====================

/// <summary>事件目录：按 Act 分组并受 ThingsModConfig 启用门控。</summary>
internal static class ThingsEventCatalog
{
    public static IEnumerable<EventModel> AddOvergrowthAndUnderdocksEvents(IEnumerable<EventModel> source)
    {
        return Add(source,
            (ThingsModConfig.EventRobberyFakeMerchantEnabled, ModelDb.Event<RobberyFakeMerchant>()),
            (ThingsModConfig.EventBackroomsEnabled, ModelDb.Event<ThingsBackrooms>()),
            (ThingsModConfig.EventCuttingItCloseEnabled, ModelDb.Event<CuttingItClose>()));
    }

    public static IEnumerable<EventModel> AddHiveEvents(IEnumerable<EventModel> source)
    {
        return Add(source,
            (ThingsModConfig.EventMedusaEnabled, ModelDb.Event<ThingsMedusa>()));
    }

    public static IEnumerable<EventModel> AddDepthsEvents(IEnumerable<EventModel> source)
    {
        return Add(source,
            (ThingsModConfig.EventRealityAlignedHousesEnabled, ModelDb.Event<RealityAlignedHouses>()),
            (ThingsModConfig.EventShadowCloakroomEnabled, ModelDb.Event<ShadowCloakroom>()),
            (ThingsModConfig.EventEchoingWellEnabled, ModelDb.Event<EchoingWell>()),
            (ThingsModConfig.EventPoliteMawEnabled, ModelDb.Event<PoliteMaw>()),
            (ThingsModConfig.EventMycelialBankEnabled, ModelDb.Event<MycelialBank>()),
            (ThingsModConfig.EventUnlitFireEnabled, ModelDb.Event<UnlitFire>()),
            (ThingsModConfig.EventRelicWorkshopEnabled, ModelDb.Event<RelicWorkshop>()),
            (ThingsModConfig.EventPotionTastingEnabled, ModelDb.Event<PotionTasting>()),
            (ThingsModConfig.EventNarrowGateEnabled, ModelDb.Event<NarrowGate>()));
    }

    private static IEnumerable<EventModel> Add(
        IEnumerable<EventModel> source,
        params (string EnabledKey, EventModel Event)[] candidates)
    {
        return DeterministicContentOrder.SortBaseThenMods(
            source.Concat(candidates
                    .Where(candidate => ThingsModConfig.IsEnabled(candidate.EnabledKey))
                    .Select(candidate => candidate.Event))
                .Distinct());
    }
}

[HarmonyPatch(typeof(Overgrowth), "get_AllEvents")]
public static class OvergrowthAllEventsPatch
{
    [HarmonyPriority(Priority.Last)]
    private static void Postfix(ref IEnumerable<EventModel> __result)
    {
        __result = ThingsEventCatalog.AddOvergrowthAndUnderdocksEvents(__result);
    }
}

[HarmonyPatch(typeof(Underdocks), "get_AllEvents")]
public static class UnderdocksAllEventsPatch
{
    [HarmonyPriority(Priority.Last)]
    private static void Postfix(ref IEnumerable<EventModel> __result)
    {
        __result = ThingsEventCatalog.AddOvergrowthAndUnderdocksEvents(__result);
    }
}

[HarmonyPatch(typeof(Hive), "get_AllEvents")]
public static class HiveAllEventsPatch
{
    [HarmonyPriority(Priority.Last)]
    private static void Postfix(ref IEnumerable<EventModel> __result)
    {
        __result = ThingsEventCatalog.AddHiveEvents(__result);
    }
}

// ==================== 涅奥遗物 ====================

[HarmonyPatch]
public static class NeowCurseOptionsPatch
{
    [HarmonyTargetMethod]
    public static MethodBase Target(HarmonyPatchType p, Harmony instance)
    {
        return AccessTools.PropertyGetter(typeof(Neow), "CurseOptions");
    }

    private static void Postfix(Neow __instance, ref IEnumerable<EventOption> __result)
    {
        var list = __result.ToList();
        if (ThingsModConfig.IsEnabled(ThingsModConfig.NeowRelicCurseRemoverEnabled))
            AddRelicToList<ThingsCurseRemover>(__instance, list);
        if (ThingsModConfig.IsEnabled(ThingsModConfig.NeowRelicWhiteFlagEnabled))
            AddRelicToList<ThingsWhiteFlag>(__instance, list);
        if (ThingsModConfig.IsEnabled(ThingsModConfig.NeowRelicMagicGloveEnabled))
            AddRelicToList<ThingsMagicGlove>(__instance, list);
        // This conflict belongs to our Neow options, not every relic picker.
        if (list.Any(option => option.Relic is ThingsMagicGlove))
            list.RemoveAll(option => option.Relic?.Id.Entry == "PRECARIOUS_SHEARS");
        __result = list;
    }

    private static void AddRelicToList<T>(Neow neow, List<EventOption> list) where T : RelicModel
    {
        var relic = ModelDb.Relic<T>().ToMutable();
        if (neow.Owner is { } owner)
        {
            relic.Owner = owner;
        }

        var option = new EventOption(
            neow,
            async () =>
            {
                var currentOwner = neow.Owner
                    ?? throw new InvalidOperationException("Neow relic option was selected without an event owner.");
                await RelicCmd.Obtain(relic, currentOwner);
                var doneMethod = typeof(AncientEventModel)
                    .GetMethod("Done", BindingFlags.NonPublic | BindingFlags.Instance);
                doneMethod?.Invoke(neow, null);
            },
            relic.Title,
            relic.DynamicEventDescription,
            "INITIAL",
            relic.HoverTipsExcludingRelic
        ).WithRelic(relic);
        list.Add(option);
    }
}
