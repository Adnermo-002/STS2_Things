using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Gold;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Extensions;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;

namespace STS2_Things.Events;

public sealed class NarrowGate : EventModel
{
    private const int RerollCost = 25;
    private const int CandidateCount = 3;
    private const int RestHeal = 4;
    private CardModel[]? _candidates;
    private bool _rerolled;
    private bool _settling;
    private Player EventOwner => Owner ?? throw new InvalidOperationException("Narrow Gate has no owner.");
    private CardModel[] Candidates => _candidates ?? Array.Empty<CardModel>();
    private CardModel[] Removable => EventOwner.Deck.Cards.Count > 1
        ? EventOwner.Deck.Cards.Where(card => card.IsRemovable).ToArray() : Array.Empty<CardModel>();
    private bool CanRemove => Candidates.Any(card => Removable.Contains(card));
    private bool HasAlternatives => Removable.Any(card => !Candidates.Contains(card));

    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new GoldVar(RerollCost), new HealVar(RestHeal)];
    public override bool IsAllowed(IRunState runState) => runState.Players.Any(player => !player.Creature.IsDead);
    public override IEnumerable<LocString> GameInfoOptions
    {
        get
        {
            foreach (var text in DepthsEventDefaults.DescribeOptions(this, "REMOVE_CARD", "REROLL", "REST"))
            {
                text.Add("Card", L10NLookup("NARROW_GATE.card").GetFormattedText());
                yield return text;
            }
        }
    }

    public override void OnRoomEnter()
    {
        base.OnRoomEnter();
        if (Node?.GetNodeOrNull<Control>("%EventDescription") is { } description)
            description.CustomMinimumSize = new Vector2(description.CustomMinimumSize.X, 144);
    }

    protected override Task BeforeEventStarted(bool isPreFinished)
    {
        if (!isPreFinished && _candidates == null)
            _candidates = Removable.ToList().StableShuffle(Rng).Take(CandidateCount).ToArray();
        return Task.CompletedTask;
    }

    protected override IReadOnlyList<EventOption> GenerateInitialOptions()
    {
        string reroll = _rerolled ? "REROLLED" : !HasAlternatives ? "NO_ALTERNATIVES" :
            EventOwner.Gold < RerollCost ? "NO_GOLD" : "REROLL";
        var options = new List<EventOption>();
        for (int i = 0; i < CandidateCount; i++)
        {
            var card = Candidates.ElementAtOrDefault(i);
            if (card != null && Removable.Contains(card))
            {
                string key = InitialOptionKey("REMOVE_CARD");
                var title = L10NLookup(key + ".title");
                var description = L10NLookup(key + ".description");
                title.Add("Card", card.Title);
                description.Add("Card", card.Title);
                options.Add(new EventOption(this, () => RemoveCard(card), title, description, key,
                    [HoverTipFactory.FromCard(card)]).ThatHasDynamicTitle());
            }
            else if (i == 0 && !CanRemove)
            {
                // An empty/one-card deck must still have a way to finish.
                options.Add(new EventOption(this, Rest, InitialOptionKey("REST")));
            }
            else options.Add(new EventOption(this, null, InitialOptionKey("REMOVE_LOCKED")));
        }
        // Retain this position even when fewer than three cards are eligible.
        options.Add(new EventOption(this, reroll == "REROLL" ? Reroll : null, InitialOptionKey(reroll)));
        return options;
    }

    private async Task RemoveCard(CardModel card)
    {
        if (IsFinished || _settling) return;
        if (!Removable.Contains(card) || !Candidates.Contains(card) || EventOwner.Creature.IsDead)
        {
            Refresh();
            return;
        }
        _settling = true;
        await CardPileCmd.RemoveFromDeck(card);
        SetEventFinished(L10NLookup("NARROW_GATE.pages.REMOVED.description"));
    }

    private async Task Reroll()
    {
        if (IsFinished || _settling || _rerolled || !HasAlternatives || EventOwner.Gold < RerollCost) return;
        _settling = true;
        _rerolled = true;
        var old = Candidates;
        var available = Removable;
        // Prefer unseen physical cards. Small decks fill remaining slots from
        // the old set, ensuring the paid reroll always introduces a new card.
        var fresh = available.Where(card => !old.Contains(card)).ToList().StableShuffle(Rng);
        var remaining = available.Where(old.Contains).ToList().StableShuffle(Rng);
        _candidates = fresh.Concat(remaining).Take(CandidateCount).ToArray();
        await PlayerCmd.LoseGold(RerollCost, EventOwner, GoldLossType.Spent);
        _settling = false;
        Refresh();
    }

    private void Refresh()
    {
        if (!IsFinished && !_settling)
            SetEventState(_rerolled ? L10NLookup("NARROW_GATE.pages.REROLLED.description") : InitialDescription,
                GenerateInitialOptions());
    }

    private async Task Rest()
    {
        if (IsFinished || _settling) return;
        _settling = true;
        await CreatureCmd.Heal(EventOwner.Creature, RestHeal);
        SetEventFinished(L10NLookup("NARROW_GATE.pages.REST.description"));
    }
}
