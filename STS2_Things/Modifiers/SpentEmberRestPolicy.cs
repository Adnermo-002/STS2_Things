using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Models;
using STS2_Things.Relics;
using STS2_Things.RestSite;

namespace STS2_Things.Modifiers;

// Run-state subscribers are enumerated after native relics, so Shovel/Mend and
// normal relic modifiers finish before this spent-camp rule is applied.
public sealed class SpentEmberRestPolicy : ModifierModel
{
    public override bool TryModifyRestSiteOptions(Player player, ICollection<RestSiteOption> options)
    {
        if (player.GetRelic<BorrowedEmber>() is not { IsSpentCampHere: true }) return false;
        options.Clear();
        options.Add(new SpentEmberRestSiteOption(player));
        return true;
    }
}
