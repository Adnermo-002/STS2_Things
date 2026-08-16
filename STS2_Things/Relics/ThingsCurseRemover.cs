using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Saves.Runs;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Enchantments;
using static MegaCrit.Sts2.Core.Entities.Cards.PileType;

namespace STS2_Things.Relics;

public sealed class ThingsCurseRemover : RelicModel
{
    private int _timesUsed;

    public override RelicRarity Rarity => RelicRarity.Ancient;

    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        HoverTipFactory.FromEnchantment<ThingsDisperse>();

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new HpLossVar(11m),
        new CardsVar(2)
    ];

    public override bool ShowCounter =>
        TimesUsed < DynamicVars.Cards.IntValue;

    public override int DisplayAmount => DynamicVars.Cards.IntValue - TimesUsed;

    [SavedProperty]
    private int TimesUsed
    {
        get => _timesUsed;
        set
        {
            AssertMutable();
            _timesUsed = value;
            InvokeDisplayAmountChanged();
            CheckIfUsedUp();
        }
    }

    public override bool IsUsedUp => TimesUsed >= DynamicVars.Cards.IntValue;

    private void CheckIfUsedUp()
    {
        if (IsUsedUp)
            Status = RelicStatus.Disabled;
    }

    public override async Task AfterObtained()
    {
        await CreatureCmd.Damage(
            new ThrowingPlayerChoiceContext(),
            Owner.Creature,
            DynamicVars.HpLoss.BaseValue,
            ValueProp.Unblockable | ValueProp.Unpowered,
            null, null
        );
    }

    // 给诅咒附上 ThingsDisperse（虚无）
    public override Task AfterCardChangedPiles(CardModel card, PileType oldPileType, AbstractModel? source)
    {
        if (IsUsedUp) return Task.CompletedTask;

        var pile = card.Pile;
        if (pile != null && pile.Type == Deck && card.Owner == Owner && card.Type == CardType.Curse)
        {
            CardCmd.Enchant<ThingsDisperse>(card, 1m);
            TimesUsed++;
        }
        return Task.CompletedTask;
    }
}
