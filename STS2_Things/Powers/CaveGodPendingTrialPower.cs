using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using STS2_Things.Monsters;

namespace STS2_Things.Powers;

/// <summary>Native per-player state deferring the capture choice until opening draws finish.</summary>
public sealed class CaveGodPendingTrialPower : PowerModel
{
    // This is scheduling state, not another debuff for Artifact to consume.
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.None;
    public override bool ShouldPlayVfx => false;
    protected override bool IsVisibleInternal => false;

    public override async Task AfterPlayerTurnStart(PlayerChoiceContext choiceContext, Player player)
    {
        if (player.Creature != Owner || !ReferenceEquals(Owner.GetPower<CaveGodPendingTrialPower>(), this)) return;
        var owner = Owner;
        var hand = Applier?.Monster as ThingsCaveGodHand;
        // Consume before waiting for input: extra turns cannot repeat the choice.
        await PowerCmd.Remove(this);
        if (owner.IsAlive && hand != null)
            await hand.ChooseTrialAfterDraw(choiceContext, owner);
    }
}
