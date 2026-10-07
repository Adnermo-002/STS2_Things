using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Things.Powers;

public sealed class SpongeRinsePower : PowerModel
{
    public const int MaxCharges = 2;
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    protected override IEnumerable<IHoverTip> ExtraHoverTips => [HoverTipFactory.FromKeyword(CardKeyword.Exhaust)];

    public override Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        ClampCharges();
        return Task.CompletedTask;
    }

    public override Task AfterPowerAmountChanged(PlayerChoiceContext choiceContext, PowerModel power,
        decimal amount, Creature? applier, CardModel? cardSource)
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
        if (Amount <= 0 || !Owner.IsAlive || card.Owner.Creature != Owner ||
            card.Type != CardType.Status || card.Pile?.Type != PileType.Hand) return;
        // Spend before exhausting: native exhaust effects may themselves draw cards.
        Flash();
        await PowerCmd.ModifyAmount(choiceContext, this, -1, null, null);
        await CardCmd.Exhaust(choiceContext, card);
    }
}
