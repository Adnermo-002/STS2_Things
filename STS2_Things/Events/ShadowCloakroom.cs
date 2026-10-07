using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Gold;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;
using STS2_Things.Relics;

namespace STS2_Things.Events;

/// <summary>A per-player deposit, carried between rooms by a native saved relic.</summary>
public sealed class ShadowCloakroom : EventModel
{
    private const int DepositCost = 25;
    private Player EventOwner => Owner
        ?? throw new InvalidOperationException("Shadow Cloakroom has no owner.");

    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new GoldVar(DepositCost), new CardsVar(1), DepthsEventDefaults.SmallGoldVar()];

    public override IEnumerable<LocString> GameInfoOptions => DepthsEventDefaults.DescribeOptions(this, "DEPOSIT", "COINS");

    private static bool CanDeposit(CardModel card) => card.IsRemovable && card.IsUpgradable &&
        card.Type is CardType.Attack or CardType.Skill or CardType.Power;

    private static bool HasEligibleCard(Player player) =>
        player.Deck.Cards.Count > 1 && player.Deck.Cards.Any(CanDeposit);

    public override bool IsAllowed(IRunState runState) => runState.Players.Any(player => !player.Creature.IsDead);

    protected override IReadOnlyList<EventOption> GenerateInitialOptions()
    {
        string key = EventOwner.GetRelic<ShadowClaimTicket>() != null ? "ALREADY_STORED" :
            !HasEligibleCard(EventOwner) ? "NO_CARD" :
            EventOwner.Gold < DynamicVars.Gold.IntValue ? "NO_GOLD" : "DEPOSIT";
        return
        [
            new EventOption(this, key == "DEPOSIT" ? Deposit : null, InitialOptionKey(key),
                ModelDb.Relic<ShadowClaimTicket>().HoverTips),
            new EventOption(this, TakeCoins, InitialOptionKey("COINS")),
        ];
    }

    private async Task Deposit()
    {
        if (IsFinished) return;
        Player player = EventOwner;
        var selected = (await CardSelectCmd.FromDeckForRemoval(player,
            new CardSelectorPrefs(L10NLookup("SHADOW_CLOAKROOM.selectionPrompt"), 1),
            CanDeposit)).FirstOrDefault();

        // Revalidate after the synchronized selection; nothing is charged on cancel.
        if (selected == null || player.Creature.IsDead || !HasEligibleCard(player) ||
            !player.Deck.Cards.Contains(selected) || !CanDeposit(selected) ||
            player.Gold < DynamicVars.Gold.IntValue || player.GetRelic<ShadowClaimTicket>() != null)
        {
            if (player.Creature.IsDead) Finish("ABORTED");
            else SetEventState(InitialDescription, GenerateInitialOptions());
            return;
        }

        var ticket = (ShadowClaimTicket)ModelDb.Relic<ShadowClaimTicket>().ToMutable();
        ticket.Store(selected, player.RunState.CurrentActIndex);
        await RelicCmd.Obtain(ticket, player);
        await CardPileCmd.RemoveFromDeck(selected);
        await PlayerCmd.LoseGold(DynamicVars.Gold.BaseValue, player, GoldLossType.Spent);
        Finish("DEPOSITED");
    }

    private async Task TakeCoins()
    {
        if (IsFinished) return;
        await DepthsEventDefaults.TakeSmallReward(EventOwner);
        Finish("COINS");
    }

    private void Finish(string page)
    {
        if (!IsFinished) SetEventFinished(L10NLookup($"SHADOW_CLOAKROOM.pages.{page}.description"));
    }
}
