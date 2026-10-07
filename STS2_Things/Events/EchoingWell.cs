using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;
using STS2_Things.Relics;

namespace STS2_Things.Events;

public sealed class EchoingWell : EventModel
{
    private Player EventOwner => Owner ?? throw new InvalidOperationException("Echoing Well has no owner.");
    protected override IEnumerable<DynamicVar> CanonicalVars => [new IntVar("Combats", 3), DepthsEventDefaults.SmallGoldVar()];
    public override IEnumerable<LocString> GameInfoOptions => DepthsEventDefaults.DescribeOptions(this, "RECORD", "COINS");

    // Native free-cost modifiers do not turn either kind of X cost into zero.
    private static bool CanRecord(CardModel card) => card.IsRemovable &&
        (card.Type is CardType.Attack or CardType.Skill) &&
        !card.EnergyCost.CostsX && !card.HasStarCostX && card.EnergyCost.Canonical >= 0;

    private static bool CanUse(Player player) => !player.Creature.IsDead &&
        player.Deck.Cards.Count > 1 && player.Deck.Cards.Any(CanRecord) &&
        player.GetRelic<BottledEcho>() == null;

    public override bool IsAllowed(IRunState runState) => runState.Players.Any(player => !player.Creature.IsDead);

    protected override IReadOnlyList<EventOption> GenerateInitialOptions() =>
    [
        new EventOption(this, CanUse(EventOwner) ? Record : null,
            InitialOptionKey(CanUse(EventOwner) ? "RECORD" : "LOCKED"),
            ModelDb.Relic<BottledEcho>().HoverTips),
        new EventOption(this, TakeCoins, InitialOptionKey("COINS")),
    ];

    private async Task Record()
    {
        if (IsFinished) return;
        Player player = EventOwner;
        var card = (await CardSelectCmd.FromDeckForRemoval(player,
            new CardSelectorPrefs(L10NLookup("ECHOING_WELL.selectionPrompt"), 1)
                { Cancelable = true }, CanRecord)).FirstOrDefault();
        if (card == null || !CanUse(player) || !player.Deck.Cards.Contains(card) || !CanRecord(card))
        {
            SetEventState(InitialDescription, GenerateInitialOptions());
            return;
        }
        var echo = (BottledEcho)ModelDb.Relic<BottledEcho>().ToMutable();
        echo.Record(card);
        await RelicCmd.Obtain(echo, player);
        await CardPileCmd.RemoveFromDeck(card);
        Finish("RECORDED");
    }

    private async Task TakeCoins()
    {
        if (IsFinished) return;
        await DepthsEventDefaults.TakeSmallReward(EventOwner);
        Finish("COINS");
    }
    private void Finish(string page)
    {
        if (!IsFinished) SetEventFinished(L10NLookup($"ECHOING_WELL.pages.{page}.description"));
    }
}
