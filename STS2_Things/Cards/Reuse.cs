using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using STS2_Things.Powers;

namespace STS2_Things.Cards;

public sealed class Reuse : CardModel
{
    public Reuse() : base(2, CardType.Power, CardRarity.Rare, TargetType.Self)
    {
    }

    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        HoverTipFactory.FromCardWithCardHoverTips<Fuel>()
            .Concat(HoverTipFactory.FromCardWithCardHoverTips<Soot>())
            .Concat([HoverTipFactory.FromPower<ReusePower>()]);

    protected override List<DynamicVar> CanonicalVars =>
    [
        new IntVar("ReusePowerCount", 1m)
    ];

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        await CreatureCmd.TriggerAnim(Owner.Creature, "Cast", Owner.Character.CastAnimDelay);
        await PowerCmd.Apply<ReusePower>(choiceContext, Owner.Creature,
            DynamicVars["ReusePowerCount"].BaseValue, Owner.Creature, this);
    }

    protected override void OnUpgrade()
    {
        EnergyCost.UpgradeBy(-1);
    }
}
