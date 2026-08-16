using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;

namespace STS2_Things.Relics;

public sealed class ThingsMagicGlove : RelicModel
{
    public override RelicRarity Rarity => RelicRarity.Ancient;

    public override bool HasUponPickupEffect => true;

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new CardsVar(2),
        new HpLossVar(9)
    ];

    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
    [
        HoverTipFactory.FromCard<Finesse>(),
        HoverTipFactory.FromCard<FlashOfSteel>()
    ];

    public override async Task AfterObtained()
    {
        await CreatureCmd.LoseMaxHp(
            new ThrowingPlayerChoiceContext(),
            Owner.Creature,
            DynamicVars.HpLoss.BaseValue,
            false
        );
        CardModel finesse = Owner.RunState.CreateCard<Finesse>(Owner);
        CardModel flashOfSteel = Owner.RunState.CreateCard<FlashOfSteel>(Owner);
        var list = (await CardSelectCmd.FromDeckForTransformation(
            prefs: new CardSelectorPrefs(CardSelectorPrefs.TransformSelectionPrompt, DynamicVars.Cards.IntValue),
            player: Owner)).ToList();
        if (list.Count < 2) return;
        await CardCmd.Transform(list[0], finesse);
        await CardCmd.Transform(list[1], flashOfSteel);
    }
}