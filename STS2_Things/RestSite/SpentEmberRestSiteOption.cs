using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.RestSite;
using STS2_Things.Relics;

namespace STS2_Things.RestSite;

public sealed class SpentEmberRestSiteOption(Player owner) : RestSiteOption(owner)
{
    public override string OptionId => "THINGS_SPENT_EMBER";
    public override Task<bool> OnSelect()
    {
        Owner.GetRelic<BorrowedEmber>()?.FinishPassing();
        return Task.FromResult(true);
    }
}
