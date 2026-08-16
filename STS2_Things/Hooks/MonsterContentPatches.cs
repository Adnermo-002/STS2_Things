using HarmonyLib;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Acts;
using STS2_Things.Encounters;

namespace STS2_Things.Hooks;

/// <summary>
/// V110 会自动发现所有具体 MonsterModel/EncounterModel。Act 的候选遭遇仍是原版
/// 硬编码列表，因此只在这些消费点追加 canonical EncounterModel，并保持原版前缀
/// 顺序不变、对所有 Mod 后缀使用官方 ContentSorter 排序。
/// </summary>
internal static class MonsterEncounterCatalog
{
    public static IEnumerable<EncounterModel> AddOvergrowthEncounters(IEnumerable<EncounterModel> source)
    {
        return Add(source,
            ModelDb.Encounter<OriginFogmogBossEncounter>(),
            ModelDb.Encounter<ScaleBeetleBossEncounter>());
    }

    public static IEnumerable<EncounterModel> AddUnderdocksEncounters(IEnumerable<EncounterModel> source)
    {
        return Add(source,
            ModelDb.Encounter<GravetideSlugBossEncounter>(),
            ModelDb.Encounter<SoulRoesEncounter>(),
            ModelDb.Encounter<TheLegacyBossEncounter>());
    }

    public static IEnumerable<EncounterModel> AddHiveEncounters(IEnumerable<EncounterModel> source)
    {
        // Quirky Hopper is an Act 2 hallway encounter, beside the native
        // ThievingHopperWeak.  IsWeak controls the early hallway subset; it is
        // still RoomType.Monster and never enters the elite/boss catalogs.
        return Add(source,
            ModelDb.Encounter<QuirkyHopperWeak>(),
            ModelDb.Encounter<BowlbugProgenitorBossEncounter>(),
            ModelDb.Encounter<LivingRockBossEncounter>());
    }

    public static IEnumerable<EncounterModel> AddOvergrowthBosses(IEnumerable<EncounterModel> source)
    {
        return Add(source,
            ModelDb.Encounter<OriginFogmogBossEncounter>(),
            ModelDb.Encounter<ScaleBeetleBossEncounter>());
    }

    public static IEnumerable<EncounterModel> AddUnderdocksBosses(IEnumerable<EncounterModel> source)
    {
        return Add(source,
            ModelDb.Encounter<GravetideSlugBossEncounter>(),
            ModelDb.Encounter<TheLegacyBossEncounter>());
    }

    public static IEnumerable<EncounterModel> AddHiveBosses(IEnumerable<EncounterModel> source)
    {
        return Add(source,
            ModelDb.Encounter<BowlbugProgenitorBossEncounter>(),
            ModelDb.Encounter<LivingRockBossEncounter>());
    }

    private static IEnumerable<EncounterModel> Add(
        IEnumerable<EncounterModel> source,
        params EncounterModel[] additions)
    {
        return DeterministicContentOrder.SortBaseThenMods(source.Concat(additions).Distinct());
    }
}

[HarmonyPatch(typeof(Overgrowth), nameof(Overgrowth.GenerateAllEncounters))]
internal static class OvergrowthEncounterPoolPatch
{
    [HarmonyPostfix]
    [HarmonyPriority(Priority.Last)]
    private static void Postfix(ref IEnumerable<EncounterModel> __result)
    {
        __result = MonsterEncounterCatalog.AddOvergrowthEncounters(__result);
    }
}

[HarmonyPatch(typeof(Underdocks), nameof(Underdocks.GenerateAllEncounters))]
internal static class UnderdocksEncounterPoolPatch
{
    [HarmonyPostfix]
    [HarmonyPriority(Priority.Last)]
    private static void Postfix(ref IEnumerable<EncounterModel> __result)
    {
        __result = MonsterEncounterCatalog.AddUnderdocksEncounters(__result);
    }
}

[HarmonyPatch(typeof(Hive), nameof(Hive.GenerateAllEncounters))]
internal static class HiveEncounterPoolPatch
{
    [HarmonyPostfix]
    [HarmonyPriority(Priority.Last)]
    private static void Postfix(ref IEnumerable<EncounterModel> __result)
    {
        __result = MonsterEncounterCatalog.AddHiveEncounters(__result);
    }
}

[HarmonyPatch(typeof(Overgrowth), nameof(Overgrowth.BossDiscoveryOrder), MethodType.Getter)]
internal static class OvergrowthBossDiscoveryPatch
{
    [HarmonyPostfix]
    [HarmonyPriority(Priority.Last)]
    private static void Postfix(ref IEnumerable<EncounterModel> __result)
    {
        __result = MonsterEncounterCatalog.AddOvergrowthBosses(__result);
    }
}

[HarmonyPatch(typeof(Underdocks), nameof(Underdocks.BossDiscoveryOrder), MethodType.Getter)]
internal static class UnderdocksBossDiscoveryPatch
{
    [HarmonyPostfix]
    [HarmonyPriority(Priority.Last)]
    private static void Postfix(ref IEnumerable<EncounterModel> __result)
    {
        __result = MonsterEncounterCatalog.AddUnderdocksBosses(__result);
    }
}

[HarmonyPatch(typeof(Hive), nameof(Hive.BossDiscoveryOrder), MethodType.Getter)]
internal static class HiveBossDiscoveryPatch
{
    [HarmonyPostfix]
    [HarmonyPriority(Priority.Last)]
    private static void Postfix(ref IEnumerable<EncounterModel> __result)
    {
        __result = MonsterEncounterCatalog.AddHiveBosses(__result);
    }
}
