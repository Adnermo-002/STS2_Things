using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using STS2_Things.Cards;

namespace STS2_Things.Relics;

public sealed class WhiteFlag : RelicModel
{
    public override RelicRarity Rarity => RelicRarity.Ancient;

    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        HoverTipFactory.FromCardWithCardHoverTips<Surrender>()
            .Concat(HoverTipFactory.FromCardWithCardHoverTips<Shame>());

    public override async Task AfterObtained()
    {
        CardModel surrender = Owner.RunState.CreateCard<Surrender>(Owner);
        CardModel shame = Owner.RunState.CreateCard<Shame>(Owner);

        var surrenderResult = await CardPileCmd.Add(surrender, PileType.Deck);
        var shameResult = await CardPileCmd.Add(shame, PileType.Deck);

        CardCmd.PreviewCardPileAdd(
            new List<CardPileAddResult> { surrenderResult, shameResult },
            2.5f
        );
    }
}
