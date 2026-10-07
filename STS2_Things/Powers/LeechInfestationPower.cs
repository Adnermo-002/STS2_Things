using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using STS2_Things.Cards;
using STS2_Things.Monsters;

namespace STS2_Things.Powers;

public sealed class LeechInfestationPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.None;
    protected override bool IsVisibleInternal => false;
    protected override IEnumerable<IHoverTip> ExtraHoverTips => [HoverTipFactory.FromCard<LeechParasite>()];

    public override Task AfterCardExhausted(PlayerChoiceContext choiceContext, CardModel card, bool causedByEthereal)
    {
        if (card is LeechParasite && card.CombatState == CombatState && Owner.IsAlive &&
            !CombatManager.Instance.IsOverOrEnding && Owner.Monster is SanguineLeech leech)
        {
            leech.RequestReinfestation();
        }
        return Task.CompletedTask;
    }
}
