using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Factories;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.ValueProps;

namespace STS2_Things.Events;

/// <summary>Personal, seeded risk. Only the chosen reward pulls from the native bag.</summary>
public sealed class BitingChest : EventModel
{
    public const int BiteDamage = 20;
    public const int WedgeDamage = 16;
    public const int LooseGold = 25;
    private bool _settling;

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new DamageVar("BiteDamage", BiteDamage, ValueProp.Unblockable | ValueProp.Unpowered),
        new DamageVar("WedgeDamage", WedgeDamage, ValueProp.Unblockable | ValueProp.Unpowered),
        new GoldVar(LooseGold), new IntVar("Chance", 50),
        new StringVar("Curse", new LocString("cards", "INJURY.title").GetFormattedText()),
    ];

    public override bool IsAllowed(IRunState runState) => runState.Players.Any(p => !p.Creature.IsDead);
    public override IEnumerable<LocString> GameInfoOptions =>
        DepthsEventDefaults.DescribeOptions(this, "REACH", "WEDGE", "COINS");

    private bool HasRelic(RelicRarity rarity) => ModelDb.AllRelics.Any(relic =>
        relic.Rarity == rarity && relic.IsAllowed(Owner!.RunState) && Owner.RelicGrabBag.Contains(relic) &&
        Owner.Relics.All(owned => owned.Id != relic.Id));

    protected override IReadOnlyList<EventOption> GenerateInitialOptions() =>
    [
        new EventOption(this, HasRelic(RelicRarity.Rare) ? Reach : null,
            InitialOptionKey(HasRelic(RelicRarity.Rare) ? "REACH" : "EMPTY"),
            HoverTipFactory.FromCardWithCardHoverTips<Injury>()).ThatDoesDamage(BiteDamage),
        new EventOption(this, HasRelic(RelicRarity.Common) ? Wedge : null,
            InitialOptionKey(HasRelic(RelicRarity.Common) ? "WEDGE" : "EMPTY")).ThatDoesDamage(WedgeDamage),
        new EventOption(this, TakeCoins, InitialOptionKey("COINS")),
    ];

    private bool BeginSettlement()
    {
        if (IsFinished || _settling || Owner!.Creature.IsDead) return false;
        _settling = true;
        return true;
    }

    private async Task Reach()
    {
        if (!BeginSettlement()) return;
        if (Rng.NextInt(2) == 0)
        {
            await Obtain(RelicRarity.Rare);
            SetEventFinished(L10NLookup("BITING_CHEST.pages.RELIC.description"));
            return;
        }
        await CreatureCmd.Damage(new ThrowingPlayerChoiceContext(), Owner!.Creature,
            DynamicVars["BiteDamage"].BaseValue, ValueProp.Unblockable | ValueProp.Unpowered, null, null);
        if (!Owner.Creature.IsDead) await CardPileCmd.AddCurseToDeck<Injury>(Owner);
        SetEventFinished(L10NLookup(Owner.Creature.IsDead ? "GENERIC.youAreDead.description" : "BITING_CHEST.pages.BITTEN.description"));
    }

    private async Task Wedge()
    {
        if (!BeginSettlement()) return;
        await CreatureCmd.Damage(new ThrowingPlayerChoiceContext(), Owner!.Creature,
            DynamicVars["WedgeDamage"].BaseValue, ValueProp.Unblockable | ValueProp.Unpowered, null, null);
        if (!Owner.Creature.IsDead) await Obtain(RelicRarity.Common);
        SetEventFinished(L10NLookup(Owner.Creature.IsDead ? "GENERIC.youAreDead.description" : "BITING_CHEST.pages.WEDGED.description"));
    }

    private async Task Obtain(RelicRarity rarity)
    {
        var relic = RelicFactory.PullNextRelicFromFront(Owner!, rarity,
            candidate => Owner!.Relics.All(owned => owned.Id != candidate.Id));
        await RelicCmd.Obtain(relic.ToMutable(), Owner!);
    }

    private async Task TakeCoins()
    {
        if (!BeginSettlement()) return;
        await PlayerCmd.GainGold(LooseGold, Owner!);
        SetEventFinished(L10NLookup("BITING_CHEST.pages.COINS.description"));
    }
}
