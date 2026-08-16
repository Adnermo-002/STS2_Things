using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using STS2_Things.Compatibility;
using STS2_Things.Monsters;

namespace STS2_Things.Powers;

/// <summary>
/// At the end of the enemy turn, consumes every eligible slug corpse, heals
/// the boss once for five percent of its maximum HP, and grants one Strength.
/// Corpses created by Goop become eligible on the following enemy turn.
/// Amount stores the exact healing shown in the hover text; the power icon has
/// no stack label.
/// </summary>
public sealed class GravetideDigestionPower : PowerModel
{
    // Match the native Corpse Slug Ravenous sequence so the boss fully drops
    // into devour_loop before the corpses resolve, then cleanly rises again.
    private const float CorpseGatherDuration = 0.45f;
    private static readonly Vector2 CorpseGatherOffset = new(-70f, 10f);
    private const float DevourDownDuration = 0.5f;
    private const float DevourUpDuration = 0.5f;

    public override PowerType Type => PowerType.Buff;

    public override PowerStackType StackType => PowerStackType.None;

    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        [HoverTipFactory.FromPower<StrengthPower>()];

    public override async Task AfterSideTurnEnd(
        PlayerChoiceContext choiceContext,
        CombatSide side,
        IEnumerable<Creature> participants)
    {
        if (side != CombatSide.Enemy || Owner.IsDead)
            return;

        Creature[] allCorpses = CombatState.Enemies
            .Where(creature => creature.IsAlive && creature.Monster is GravetideSlugCorpse)
            .OrderBy(creature => creature.SlotName, System.StringComparer.Ordinal)
            .ToArray();
        Creature[] corpses = allCorpses
            .Where(creature => !((GravetideSlugCorpse)creature.Monster!)
                .DelayDigestionUntilNextEnemyTurn)
            .ToArray();
        foreach (Creature deferredCorpse in allCorpses)
        {
            var corpse = (GravetideSlugCorpse)deferredCorpse.Monster!;
            if (corpse.DelayDigestionUntilNextEnemyTurn)
                corpse.DelayDigestionUntilNextEnemyTurn = false;
        }
        if (corpses.Length == 0)
            return;

        Flash();
        GatherCorpseVisuals(corpses);

        // This wait is intentionally shared gameplay timing rather than a
        // local tween await. Every peer reaches the devour command after the
        // same interval, while clients with a combat room see the pull finish.
        await Cmd.CustomScaledWait(CorpseGatherDuration, CorpseGatherDuration);

        if (Owner.IsDead)
            return;

        SfxCmd.Play(GravetideSlug.GravetideDevourSfx);

        var slug = Owner.Monster as GravetideSlugBase;
        if (slug != null)
        {
            await CreatureCmd.TriggerAnim(
                Owner,
                GravetideSlugBase.DevourStartTrigger,
                DevourDownDuration);
            slug.IsDevouring = true;
        }

        foreach (Creature corpse in corpses)
            Sts2VersionCompatibility.RemoveCreatureWithoutDeathOrEscape(corpse);

        await CreatureCmd.Heal(Owner, Amount);
        await PowerCmd.Apply<StrengthPower>(
            choiceContext, Owner, 1m, Owner, null);

        if (slug != null && !Owner.IsDead)
        {
            SfxCmd.Play(GravetideSlug.GravetideDevourEndSfx);
            await CreatureCmd.TriggerAnim(
                Owner,
                GravetideSlugBase.DevourEndTrigger,
                DevourUpDuration);
            slug.IsDevouring = false;
        }
    }

    private void GatherCorpseVisuals(IEnumerable<Creature> corpses)
    {
        NCombatRoom? combatRoom = NCombatRoom.Instance;
        NCreature? bossNode = combatRoom?.GetCreatureNode(Owner);
        if (combatRoom == null || bossNode == null)
            return;

        // This is the lower-left mouth position in the boss art's devour pose.
        // Node motion is visual-only: Creature.SlotName and combat state stay
        // untouched until the normal post-devour removal below.
        Vector2 destination = bossNode.GlobalPosition + CorpseGatherOffset;
        Tween? gatherTween = null;
        foreach (Creature corpse in corpses)
        {
            NCreature? corpseNode = combatRoom.GetCreatureNode(corpse);
            if (corpseNode == null)
                continue;

            gatherTween ??= combatRoom.CreateTween().SetParallel();
            gatherTween.TweenProperty(
                    corpseNode,
                    "global_position",
                    destination,
                    CorpseGatherDuration)
                .SetEase(Tween.EaseType.In)
                .SetTrans(Tween.TransitionType.Cubic);
        }
    }
}
