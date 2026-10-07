using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Acts;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using STS2_Things.Config;
using STS2_Things.Encounters;

namespace STS2_Things.Hooks;

/// <summary>Settings act at selection, using the original seeded RNG and canonical IDs.</summary>
public static class EncounterSelectionPolicy
{
    private static readonly Action<ICollection<EncounterModel>, GrabBag<EncounterModel>, Rng> VanillaDraw =
        AccessTools.Method(typeof(ActModel), "AddWithoutRepeatingTags")
            .CreateDelegate<Action<ICollection<EncounterModel>, GrabBag<EncounterModel>, Rng>>();

    public static string? EnabledKey(EncounterModel encounter) => encounter switch
    {
        OriginFogmogBossEncounter => ThingsModConfig.BossOriginFogmogEnabled,
        ScaleBeetleBossEncounter => ThingsModConfig.BossScaleBeetleEnabled,
        GravetideSlugBossEncounter => ThingsModConfig.BossGravetideSlugEnabled,
        TheLegacyBossEncounter => ThingsModConfig.BossTheLegacyEnabled,
        BowlbugProgenitorBossEncounter => ThingsModConfig.BossBowlbugProgenitorEnabled,
        CaveGodBossEncounter => ThingsModConfig.BossCaveGodEnabled,
        SoulRoesEncounter => ThingsModConfig.EncounterSoulRoesEnabled,
        QuirkyHopperWeak => ThingsModConfig.EncounterQuirkyHopperEnabled,
        _ => null,
    };

    public static string? WeightKey(EncounterModel encounter) => encounter switch
    {
        OriginFogmogBossEncounter => ThingsModConfig.BossOriginFogmogWeightPercent,
        ScaleBeetleBossEncounter => ThingsModConfig.BossScaleBeetleWeightPercent,
        GravetideSlugBossEncounter => ThingsModConfig.BossGravetideSlugWeightPercent,
        TheLegacyBossEncounter => ThingsModConfig.BossTheLegacyWeightPercent,
        BowlbugProgenitorBossEncounter => ThingsModConfig.BossBowlbugProgenitorWeightPercent,
        CaveGodBossEncounter => ThingsModConfig.BossCaveGodWeightPercent,
        SoulRoesEncounter => ThingsModConfig.EncounterSoulRoesWeightPercent,
        _ => null,
    };

    public static string? ForcedKey(EncounterModel encounter) =>
        IsOwnedBoss(encounter) && EnabledKey(encounter) is { } enabled
            ? enabled[..^"Enabled".Length] + "Forced" : null;

    public static bool IsOwnedBoss(EncounterModel encounter) =>
        encounter is ModBossEncounter && encounter.GetType().Assembly == typeof(EncounterSelectionPolicy).Assembly;

    public static string? Slot(ActModel act) => act switch
    {
        Overgrowth => ThingsModConfig.SlotOvergrowth,
        Underdocks => ThingsModConfig.SlotUnderdocks,
        Hive => ThingsModConfig.SlotHive,
        _ => null,
    };

    public static bool IsAvailable(EncounterModel encounter)
    {
        string? enabled = EnabledKey(encounter);
        return enabled is null || ThingsModConfig.IsEnabled(enabled) && GetWeight(encounter) > 0;
    }

    public static double GetWeight(EncounterModel encounter)
    {
        if (ForcedKey(encounter) is { } forced && ThingsModConfig.IsForced(forced))
            return 1.0;
        return WeightKey(encounter) is { } key ? ThingsModConfig.GetInt(key) / 100.0 : 1.0;
    }

    public static EncounterModel? ChooseBoss(Rng rng, IEnumerable<EncounterModel> source)
    {
        EncounterModel[] candidates = source.ToArray();
        // Identical settings retain the original RNG operation and consumption.
        if (candidates.All(encounter => GetWeight(encounter) == 1.0))
            return rng.NextItem(candidates);
        var bag = new GrabBag<EncounterModel>();
        foreach (EncounterModel encounter in candidates)
            if (GetWeight(encounter) is var weight && weight > 0)
                bag.Add(encounter, weight);
        return bag.Any() ? bag.Grab(rng) : null;
    }

    public static void AddWeighted(GrabBag<EncounterModel> bag, EncounterModel encounter, double weight)
    {
        double configuredWeight = weight * GetWeight(encounter);
        if (configuredWeight > 0)
            bag.Add(encounter, configuredWeight);
    }

    public static void DrawElite(ICollection<EncounterModel> encounters, GrabBag<EncounterModel> bag, Rng rng, ActModel act)
    {
        int rate = ThingsModConfig.GetInt(ThingsModConfig.EncounterSoulRoesWeightPercent);
        if (rate is 0 or 100 || !act.AllEliteEncounters.Any(encounter => encounter is SoulRoesEncounter))
        {
            VanillaDraw(encounters, bag, rng);
            return;
        }
        // With a custom frequency, drawing without replacement would merely
        // reorder a cycle and still guarantee every elite once per bag. Keep
        // the weighted bag, retaining the native no-consecutive-encounter rule.
        EncounterModel? last = encounters.LastOrDefault();
        EncounterModel? selected = bag.Grab(rng, encounter => !encounter.SharesTagsWith(last) && encounter != last)
                                   ?? bag.Grab(rng);
        if (selected is not null)
            encounters.Add(selected);
    }
}

[HarmonyPatch]
internal static class ConfiguredEncounterDrawPatch
{
    private static IEnumerable<MethodBase> TargetMethods()
    {
        yield return AccessTools.Method(typeof(ActModel), nameof(ActModel.GenerateRooms));
        yield return AccessTools.Method(typeof(ActModel), nameof(ActModel.ValidateRoomsAfterLoad));
        yield return AccessTools.Method(typeof(RunManager), nameof(RunManager.GenerateRooms));
    }

    private static IEnumerable<CodeInstruction> Transpiler(IEnumerable<CodeInstruction> instructions, MethodBase original)
    {
        bool generation = original.DeclaringType == typeof(ActModel) && original.Name == nameof(ActModel.GenerateRooms);
        MethodInfo add = AccessTools.Method(typeof(GrabBag<EncounterModel>), nameof(GrabBag<EncounterModel>.Add));
        MethodInfo withoutRepeats = AccessTools.Method(typeof(ActModel), "AddWithoutRepeatingTags");
        int draws = 0, bossCalls = 0, bagAdds = 0;
        foreach (CodeInstruction instruction in instructions)
        {
            if (instruction.operand is MethodInfo method && method.DeclaringType == typeof(Rng) &&
                method.Name == nameof(Rng.NextItem) && method.IsGenericMethod &&
                method.GetGenericArguments().SequenceEqual([typeof(EncounterModel)]))
            {
                instruction.opcode = OpCodes.Call;
                instruction.operand = AccessTools.Method(typeof(EncounterSelectionPolicy), nameof(EncounterSelectionPolicy.ChooseBoss));
                bossCalls++;
            }
            else if (generation && instruction.Calls(add))
            {
                instruction.opcode = OpCodes.Call;
                instruction.operand = AccessTools.Method(typeof(EncounterSelectionPolicy), nameof(EncounterSelectionPolicy.AddWeighted));
                bagAdds++;
            }
            else if (generation && instruction.Calls(withoutRepeats) && ++draws == 3)
            {
                var loadAct = new CodeInstruction(OpCodes.Ldarg_0);
                loadAct.labels.AddRange(instruction.labels);
                instruction.labels.Clear();
                yield return loadAct;
                instruction.opcode = OpCodes.Call;
                instruction.operand = AccessTools.Method(typeof(EncounterSelectionPolicy), nameof(EncounterSelectionPolicy.DrawElite));
            }
            yield return instruction;
        }
        if (bossCalls == 0 || generation && (bagAdds != 3 || draws != 3))
            throw new InvalidOperationException($"Encounter selection API changed: {original.Name} bosses={bossCalls}, bags={bagAdds}, draws={draws}.");
    }
}

[HarmonyPatch(typeof(ActModel), nameof(ActModel.SetSecondBossEncounter))]
internal static class ConfiguredSingleBossSecondEncounterPatch
{
    private static void Prefix(ActModel __instance, ref EncounterModel? encounter)
    {
        if (encounter is not null || EncounterSelectionPolicy.Slot(__instance) is not { } slot)
            return;
        if (ThingsModConfig.GetForcedBossKeyForSlot(slot) is not null || ThingsModConfig.GetBool(ThingsModConfig.BossOnlyModBosses))
            encounter = __instance.BossEncounter;
    }
}
