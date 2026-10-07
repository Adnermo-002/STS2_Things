using HarmonyLib;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Acts;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Config;
using STS2_Things.Encounters;

namespace STS2_Things.Hooks;

/// <summary>
/// V110/V111 会自动发现所有具体 MonsterModel/EncounterModel。Act 的候选遭遇仍是原版
/// 硬编码列表，因此只在这些消费点追加 canonical EncounterModel，并保持原版前缀
/// 顺序不变、对所有 Mod 后缀使用官方 ContentSorter 排序。
///
/// 可配置门控（ThingsModConfig）：
///   - enabled=false 的遭遇/Boss 从对应 Act 的候选池移除；
///   - 强制/仅模组 Boss 筛选作用于实际候选池，发现顺序不会覆盖自定义权重；
///   - 槽位冲突裁决（同槽位多个强制）由 ThingsModConfig 在加载/写入时完成。
/// </summary>
internal static class MonsterEncounterCatalog
{
    public static IEnumerable<EncounterModel> AddOvergrowthEncounters(IEnumerable<EncounterModel> source)
    {
        return FilterBossPool(Add(source,
            (ThingsModConfig.BossOriginFogmogEnabled, ModelDb.Encounter<OriginFogmogBossEncounter>()),
            (ThingsModConfig.BossScaleBeetleEnabled, ModelDb.Encounter<ScaleBeetleBossEncounter>())), ThingsModConfig.SlotOvergrowth);
    }

    public static IEnumerable<EncounterModel> AddUnderdocksEncounters(IEnumerable<EncounterModel> source)
    {
        return FilterBossPool(Add(source,
            (ThingsModConfig.BossGravetideSlugEnabled, ModelDb.Encounter<GravetideSlugBossEncounter>()),
            (ThingsModConfig.EncounterSoulRoesEnabled, ModelDb.Encounter<SoulRoesEncounter>()),
            (ThingsModConfig.BossTheLegacyEnabled, ModelDb.Encounter<TheLegacyBossEncounter>())), ThingsModConfig.SlotUnderdocks);
    }

    public static IEnumerable<EncounterModel> AddHiveEncounters(IEnumerable<EncounterModel> source)
    {
        // Quirky Hopper 是 Act 2 走廊遭遇，位于原生 ThievingHopperWeak 旁。IsWeak
        // 控制早期走廊子集；它仍是 RoomType.Monster，不进入精英/Boss 目录。
        return FilterBossPool(Add(source,
            (ThingsModConfig.EncounterQuirkyHopperEnabled, ModelDb.Encounter<QuirkyHopperWeak>()),
            (ThingsModConfig.BossBowlbugProgenitorEnabled, ModelDb.Encounter<BowlbugProgenitorBossEncounter>()),
            (ThingsModConfig.BossCaveGodEnabled, ModelDb.Encounter<CaveGodBossEncounter>())), ThingsModConfig.SlotHive);
    }

    public static IEnumerable<EncounterModel> AddOvergrowthBosses(IEnumerable<EncounterModel> source)
    {
        return AddBosses(source, ThingsModConfig.SlotOvergrowth,
            (ThingsModConfig.BossOriginFogmogEnabled, ThingsModConfig.BossOriginFogmogForced,
                ModelDb.Encounter<OriginFogmogBossEncounter>()),
            (ThingsModConfig.BossScaleBeetleEnabled, ThingsModConfig.BossScaleBeetleForced,
                ModelDb.Encounter<ScaleBeetleBossEncounter>()));
    }

    public static IEnumerable<EncounterModel> AddUnderdocksBosses(IEnumerable<EncounterModel> source)
    {
        return AddBosses(source, ThingsModConfig.SlotUnderdocks,
            (ThingsModConfig.BossGravetideSlugEnabled, ThingsModConfig.BossGravetideSlugForced,
                ModelDb.Encounter<GravetideSlugBossEncounter>()),
            (ThingsModConfig.BossTheLegacyEnabled, ThingsModConfig.BossTheLegacyForced,
                ModelDb.Encounter<TheLegacyBossEncounter>()));
    }

    public static IEnumerable<EncounterModel> AddHiveBosses(IEnumerable<EncounterModel> source)
    {
        return AddBosses(source, ThingsModConfig.SlotHive,
            (ThingsModConfig.BossBowlbugProgenitorEnabled, ThingsModConfig.BossBowlbugProgenitorForced,
                ModelDb.Encounter<BowlbugProgenitorBossEncounter>()),
            (ThingsModConfig.BossCaveGodEnabled, ThingsModConfig.BossCaveGodForced,
                ModelDb.Encounter<CaveGodBossEncounter>()));
    }

    private static IEnumerable<EncounterModel> Add(
        IEnumerable<EncounterModel> source,
        params (string EnabledKey, EncounterModel Encounter)[] candidates)
    {
        // Keep this deferred: ActModel caches the enumerable before it generates
        // rooms (for asset discovery), but settings may change in the meantime.
        foreach (EncounterModel encounter in DeterministicContentOrder.SortBaseThenMods(
            source.Where(EncounterSelectionPolicy.IsAvailable).Concat(candidates
                    .Where(candidate => ThingsModConfig.IsEnabled(candidate.EnabledKey))
                    .Select(candidate => candidate.Encounter)
                    .Where(EncounterSelectionPolicy.IsAvailable))
                .Distinct()))
            yield return encounter;
    }

    private static IEnumerable<EncounterModel> FilterBossPool(IEnumerable<EncounterModel> source, string slot)
    {
        List<EncounterModel> all = source.ToList();
        string? forced = ThingsModConfig.GetForcedBossKeyForSlot(slot);
        List<EncounterModel> bosses = all.Where(encounter => encounter.RoomType == RoomType.Boss).ToList();
        List<EncounterModel> selected = forced is not null
            ? bosses.Where(encounter => EncounterSelectionPolicy.ForcedKey(encounter) == forced).ToList()
            : ThingsModConfig.GetBool(ThingsModConfig.BossOnlyModBosses)
                ? bosses.Where(EncounterSelectionPolicy.IsOwnedBoss).ToList()
                : bosses;
        // A contradictory all-disabled / only-mod configuration must stay playable.
        if (selected.Count == 0)
            selected = bosses;
        foreach (EncounterModel encounter in all)
            if (encounter.RoomType != RoomType.Boss || selected.Contains(encounter))
                yield return encounter;
    }

    private static IEnumerable<EncounterModel> AddBosses(
        IEnumerable<EncounterModel> source,
        string slot,
        params (string EnabledKey, string ForcedKey, EncounterModel Encounter)[] bosses)
    {
        string? forced = ThingsModConfig.GetForcedBossKeyForSlot(slot);
        if (forced is not null)
        {
            foreach ((_, string forcedKey, EncounterModel encounter) in bosses)
            {
                if (forcedKey == forced)
                    return [encounter];
            }

            // 防御：配置被外部破坏（强制键不属于该槽位）。退回常规过滤，避免空候选。
            MegaCrit.Sts2.Core.Logging.Log.Warn(
                $"STS2_Things config: forced boss key '{forced}' does not belong to slot '{slot}'; ignoring force.");
        }

        IEnumerable<EncounterModel> eligible = FilterBossPool(Add(source, bosses
            .Select(boss => (boss.EnabledKey, boss.Encounter))
            .ToArray()), slot);
        // Otherwise an unseen boss replaces the weighted draw during tutorial
        // discovery. Preserve vanilla discovery only with the default selection.
        if (ThingsModConfig.GetBool(ThingsModConfig.BossOnlyModBosses) || ThingsModConfig.HasBossWeightOverrides(slot))
            return [];
        return eligible;
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
