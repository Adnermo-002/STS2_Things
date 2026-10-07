using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;

namespace STS2_Things.Afflictions;

public sealed class UpstreamRecall : AfflictionModel
{
    public override bool HasExtraCardText => true;
    public override bool CanAfflictUnplayableCards => false;
    public override bool CanAfflictCardType(CardType type) => type is CardType.Attack or CardType.Skill;
    public override bool CanAfflict(CardModel card) => base.CanAfflict(card) && !card.EnergyCost.CostsX &&
        card.EnergyCost.Canonical>=0 && !card.Keywords.Contains(CardKeyword.Exhaust);
    protected override IEnumerable<IHoverTip> ExtraHoverTips => [HoverTipFactory.FromPower<StrengthPower>()];
}
