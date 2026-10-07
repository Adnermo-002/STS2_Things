using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Visuals;

namespace STS2_Things.Powers;

public sealed class BorrowedShadowPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.None;
    protected override IEnumerable<IHoverTip> ExtraHoverTips => [HoverTipFactory.Static(StaticHoverTip.Block)];

    public override async Task AfterDamageGiven(PlayerChoiceContext choiceContext, Creature? dealer,
        DamageResult result, ValueProp props, Creature target, CardModel? cardSource)
    {
        // Unlike AfterDamageReceived, the native damage-given hook also runs
        // for lethal hits. Native GainBlock decides whether combat has ended.
        if (target != Owner || result.UnblockedDamage <= 0 || !props.IsPoweredAttack()) return;
        var player = dealer?.Player ?? dealer?.PetOwner;
        if (player?.Creature is not { IsAlive: true } recipient || recipient.CombatState != Owner.CombatState) return;
        Flash();
        NFleetingShadowVfx.Play(Owner, recipient);
        await CreatureCmd.GainBlock(recipient, result.UnblockedDamage, ValueProp.Unpowered, null, fast: true);
    }
}
