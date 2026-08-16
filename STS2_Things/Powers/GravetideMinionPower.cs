using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Things.Powers;

/// <summary>
/// Hidden ownership marker for the attendants and corpses in the Gravetide
/// Slug encounter. Secondary enemies never keep the fight alive after the boss
/// dies and do not trigger Fatal rewards.
/// </summary>
public sealed class GravetideMinionPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;

    public override PowerStackType StackType => PowerStackType.Single;

    protected override bool IsVisibleInternal => false;

    public override bool ShouldPlayVfx => false;

    public override bool OwnerIsSecondaryEnemy => true;

    public override bool ShouldPowerBeRemovedAfterOwnerDeath() => false;

    public override bool ShouldOwnerDeathTriggerFatal() => false;
}
