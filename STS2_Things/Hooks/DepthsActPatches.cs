using HarmonyLib;
using MegaCrit.Sts2.Core.Achievements;
using MegaCrit.Sts2.Core.Models;
using STS2_Things.Acts;

namespace STS2_Things.Hooks;

// Models are discovered automatically, but the native list of selectable acts is explicit.
[HarmonyPatch(typeof(ModelDb), nameof(ModelDb.Acts), MethodType.Getter)]
internal static class DepthsActCatalogPatch
{
    [HarmonyPriority(Priority.Last)]
    private static void Postfix(ref IEnumerable<ActModel> __result)
    {
        __result = __result.Append(ModelDb.Act<Depths>()).Distinct()
            .OrderBy(act => act.Index).ThenBy(act => act.IsDefault ? 0 : 1).ToArray();
    }
}

// Vanilla derives its achievement enum from the act ID. A mod act has no matching
// platform achievement; do not map it onto Hive's completion or parse a nonexistent enum.
[HarmonyPatch(typeof(AchievementsHelper), nameof(AchievementsHelper.CheckForDefeatedAllEnemiesAchievement))]
internal static class DepthsVanillaAchievementPatch
{
    private static bool Prefix(ActModel act) => act is not Depths;
}
