using System.Collections.Generic;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models.Powers;
using STS2_Things.Monsters;

namespace STS2_Things.Powers;

/// <summary>
/// Lets the native Ravenous power drive the shared Corpse Slug animation state
/// on the custom low-health attendant. Native Ravenous normally casts its
/// owner to CorpseSlug, while this encounter deliberately uses its own monster
/// model to preserve the corpse-replacement behavior.
/// </summary>
[HarmonyPatch(typeof(RavenousPower), nameof(RavenousPower.AfterDeath))]
internal static class GravetideRavenousPowerPatch
{
    [HarmonyPrefix]
    private static bool Prefix(
        RavenousPower __instance,
        PlayerChoiceContext choiceContext,
        Creature target,
        bool wasRemovalPrevented,
        float deathAnimLength,
        ref Task __result)
    {
        if (__instance.Owner.Monster is not GravetideCorpseSlug)
            return true;

        __result = HandleAfterDeath(
            __instance,
            choiceContext,
            target,
            wasRemovalPrevented);
        return false;
    }

    private static async Task HandleAfterDeath(
        RavenousPower power,
        PlayerChoiceContext choiceContext,
        Creature target,
        bool wasRemovalPrevented)
    {
        Creature owner = power.Owner;
        if (wasRemovalPrevented ||
            target == owner ||
            target.Side != owner.Side ||
            owner.IsDead ||
            owner.Monster is not GravetideSlugBase slug)
        {
            return;
        }

        SfxCmd.Play(GravetideSlugBase.DevourSfx);
        await CreatureCmd.TriggerAnim(
            owner,
            GravetideSlugBase.DevourStartTrigger,
            0.5f);
        slug.IsDevouring = true;
        await CreatureCmd.Stun(owner, _ => EndRavenous(owner, slug));
        await PowerCmd.Apply<StrengthPower>(
            choiceContext,
            owner,
            power.Amount,
            owner,
            null);
    }

    private static async Task EndRavenous(
        Creature owner,
        GravetideSlugBase slug)
    {
        if (owner.IsDead)
            return;

        SfxCmd.Play(GravetideSlugBase.DevourEndSfx);
        await CreatureCmd.TriggerAnim(
            owner,
            GravetideSlugBase.DevourEndTrigger,
            0.5f);
        slug.IsDevouring = false;
    }
}
