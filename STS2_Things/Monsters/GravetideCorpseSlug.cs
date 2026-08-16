using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using STS2_Things.Compatibility;
using STS2_Things.Powers;

namespace STS2_Things.Monsters;

/// <summary>
/// A low-health Corpse Slug attendant. It keeps the native three-move cycle,
/// native Ravenous behavior, and leaves a destructible corpse in its own slot.
/// </summary>
public class GravetideCorpseSlug : GravetideSlugBase
{
    public override int MinInitialHp => 7;

    public override int MaxInitialHp => 12;

    protected override int WhipSlapDamage => 3;

    protected override int GlompDamage => AscensionHelper.GetValueIfAscension(
        AscensionLevel.DeadlyEnemies, 9, 8);

    private int RavenousStrength => AscensionHelper.GetValueIfAscension(
        AscensionLevel.DeadlyEnemies, 5, 4);

    public override bool ShouldShowInCompendium => false;

    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        await PowerCmd.Apply<GravetideMinionPower>(
            new ThrowingPlayerChoiceContext(), Creature, 1m, Creature, null);
        await PowerCmd.Apply<RavenousPower>(
            new ThrowingPlayerChoiceContext(), Creature, RavenousStrength, Creature, null);
    }

    public override async Task AfterDeath(
        PlayerChoiceContext choiceContext,
        Creature creature,
        bool wasRemovalPrevented,
        float deathAnimLength)
    {
        if (wasRemovalPrevented || creature != Creature)
            return;

        // CreatureCmd.Kill automatically kills every living secondary enemy
        // after the last primary enemy dies. Do not leave a fresh corpse behind
        // while that native boss-death cleanup is walking the attendant list.
        if (!CombatState.Enemies.Any(enemy =>
                enemy.IsAlive && enemy.Monster is GravetideSlug))
            return;

        Creature corpse = await CreatureCmd.Add<GravetideSlugCorpse>(
            CombatState, Creature.SlotName);
        Sts2VersionCompatibility.SetCreatureNodeVisible(corpse, visible: false);
        _ = TaskHelper.RunSafely(RevealCorpseAfterDeathAnimation(corpse, deathAnimLength));
    }

    private static async Task RevealCorpseAfterDeathAnimation(
        Creature corpse,
        float deathAnimLength)
    {
        await Cmd.CustomScaledWait(deathAnimLength, deathAnimLength);
        Sts2VersionCompatibility.SetCreatureNodeVisible(corpse, visible: true);
    }
}
