using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Powers;
using STS2_Things.Monsters;

namespace STS2_Things.Powers;

public sealed class CaveMawAppetitePower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.None;
    public void ShowMeal() => Flash();
    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new IntVar("BlockPerCard", CaveMaw.BlockPerCard), new IntVar("StrengthCap", CaveMaw.StrengthPerMeal)];
    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        HoverTipFactory.FromCardWithCardHoverTips<Debris>().Concat([
            HoverTipFactory.FromKeyword(CardKeyword.Retain),
            HoverTipFactory.FromPower<StrengthPower>()]);
}
