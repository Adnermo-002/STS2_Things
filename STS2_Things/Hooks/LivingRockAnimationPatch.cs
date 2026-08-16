using HarmonyLib;
using MegaCrit.Sts2.Core.Nodes.Combat;
using STS2_Things.Monsters;
using STS2_Things.Visuals;

namespace STS2_Things.Hooks;

[HarmonyPatch(typeof(NCreature), nameof(NCreature.SetAnimationTrigger))]
internal static class LivingRockAnimationPatch
{
    [HarmonyPrefix]
    private static bool Prefix(NCreature __instance, string trigger)
    {
        if (trigger != NCaveGodVisuals.LeftPunchTrigger &&
            trigger != NCaveGodVisuals.RightPunchTrigger)
            return true;
        if (__instance.Entity.Monster is not ThingsLivingRock)
            return true;
        if (__instance.Visuals is not NCaveGodVisuals visuals)
            return true;
        visuals.TriggerPunch(trigger);
        return false;
    }
}
