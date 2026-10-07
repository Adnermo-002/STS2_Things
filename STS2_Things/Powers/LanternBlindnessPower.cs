using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using STS2_Things.Cards;
using STS2_Things.Visuals;

namespace STS2_Things.Powers;

/// <summary>Charges count future draws; already blinded cards live until native turn cleanup.</summary>
public sealed class LanternBlindnessPower : PowerModel
{
    public const int MaxCharges = 6;
    public override PowerType Type => PowerType.Debuff;
    public override PowerStackType StackType => PowerStackType.Counter;

    public override Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        ClampCharges();
        return Task.CompletedTask;
    }

    public override Task AfterPowerAmountChanged(PlayerChoiceContext choiceContext,
        PowerModel power, decimal amount, Creature? applier, CardModel? cardSource)
    {
        if (ReferenceEquals(power, this)) ClampCharges();
        return Task.CompletedTask;
    }

    private void ClampCharges()
    {
        if (Amount > MaxCharges) SetAmount(MaxCharges);
    }

    public override async Task AfterCardDrawn(PlayerChoiceContext choiceContext, CardModel card, bool fromHandDraw)
    {
        if (Amount <= 0 || card.Owner.Creature != Owner) return;

        Flash();

        // Use the native combat RNG, once per eligible draw. X/unplayable and stars
        // retain their special semantics. Global discounts still apply normally.
        int? roll = !card.EnergyCost.CostsX && card.EnergyCost.Canonical >= 0
            ? card.Owner.RunState.Rng.CombatEnergyCosts.NextInt(3) + 1 : null;
        LanternBlindness.Mark(card, roll);
        if (roll.HasValue)
        {
            card.EnergyCost.SetThisTurn(roll.Value);
            card.InvokeEnergyCostChanged();
        }
        NBlindCardVeil.RefreshOnTable(card);
        await PowerCmd.ModifyAmount(choiceContext, this, -1, null, null);
    }
}
