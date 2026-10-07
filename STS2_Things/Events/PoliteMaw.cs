using Godot;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Factories;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Potions;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using STS2_Things.Encounters;

namespace STS2_Things.Events;

/// <summary>Shared menu choice, individual meals and rewards, synchronized curse combat.</summary>
public sealed class PoliteMaw : EventModel
{
    private const int DescriptionMinimumHeight = 144;
    private RelicModel? _offeredRelic;
    private bool _combatRequested;
    private Player EventOwner => Owner ?? throw new InvalidOperationException("Polite Maw has no owner.");

    public override bool IsShared => true;
    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new GoldVar(50), new StringVar("Relic", L10NLookup("POLITE_MAW.uncommonRelic").GetFormattedText()),
            DepthsEventDefaults.SmallGoldVar()];

    public override void OnRoomEnter()
    {
        base.OnRoomEnter();
        // Five native buttons plus the multiplayer label need less empty space
        // below this short description. Preserve native fonts and button sizes.
        if (Node?.GetNodeOrNull<Control>("%EventDescription") is { } description)
            description.CustomMinimumSize = new Vector2(description.CustomMinimumSize.X, DescriptionMinimumHeight);
    }

    private static bool HasFood(Player player, CardType type) => !player.Creature.IsDead &&
        player.Deck.Cards.Count > 1 && player.Deck.Cards.Any(card => card.IsRemovable && card.Type == type);

    private bool CanEveryoneFeed(CardType type)
    {
        var diners = EventOwner.RunState.Players.Where(player => !player.Creature.IsDead).ToArray();
        return diners.Length > 0 && diners.All(player => HasFood(player, type));
    }

    private bool CanFeedCurse => EventOwner.RunState.Players.Any(player => HasFood(player, CardType.Curse));

    public override bool IsAllowed(IRunState runState)
    {
        return runState.Players.Any(player => !player.Creature.IsDead);
    }

    protected override Task BeforeEventStarted(bool isPreFinished)
    {
        // Reserve once, like native Wongo's featured relic. Revisiting the menu
        // never rolls another relic or consumes another grab-bag entry.
        if (!isPreFinished && _offeredRelic == null && CanEveryoneFeed(CardType.Power))
        {
            _offeredRelic = RelicFactory.PullNextRelicFromFront(EventOwner, RelicRarity.Uncommon).ToMutable();
            _offeredRelic.Owner = EventOwner;
            ((StringVar)DynamicVars["Relic"]).StringValue = _offeredRelic.Title.GetFormattedText();
        }
        return Task.CompletedTask;
    }

    public override IEnumerable<LocString> GameInfoOptions =>
        DepthsEventDefaults.DescribeOptions(this, "ATTACK", "SKILL", "POWER", "CURSE", "TIP");

    protected override IReadOnlyList<EventOption> GenerateInitialOptions()
    {
        bool attack = CanEveryoneFeed(CardType.Attack), skill = CanEveryoneFeed(CardType.Skill);
        bool power = CanEveryoneFeed(CardType.Power) && _offeredRelic != null;
        return
        [
            new EventOption(this, attack ? FeedAttack : null, InitialOptionKey(attack ? "ATTACK" : "ATTACK_LOCKED"),
                [HoverTipFactory.FromPotion<AttackPotion>()]),
            new EventOption(this, skill ? FeedSkill : null, InitialOptionKey(skill ? "SKILL" : "SKILL_LOCKED")),
            new EventOption(this, power ? FeedPower : null, InitialOptionKey(power ? "POWER" : "POWER_LOCKED"),
                _offeredRelic?.HoverTips ?? Array.Empty<IHoverTip>()),
            new EventOption(this, CanFeedCurse ? FeedCurse : null, InitialOptionKey(CanFeedCurse ? "CURSE" : "CURSE_LOCKED")),
            new EventOption(this, TakeTip, InitialOptionKey("TIP")),
        ];
    }

    private async Task<bool> TakeFood(CardType type)
    {
        if (!HasFood(EventOwner, type)) return false;
        var prompt = L10NLookup($"POLITE_MAW.selection.{type.ToString().ToUpperInvariant()}");
        DynamicVars.AddTo(prompt);
        var card = (await CardSelectCmd.FromDeckForRemoval(EventOwner,
            new CardSelectorPrefs(prompt, 1),
            card => card.Type == type)).FirstOrDefault();
        if (card == null || EventOwner.Creature.IsDead || EventOwner.Deck.Cards.Count <= 1 ||
            !EventOwner.Deck.Cards.Contains(card) || !card.IsRemovable || card.Type != type) return false;
        await CardPileCmd.RemoveFromDeck(card);
        return true;
    }

    private async Task FeedAttack()
    {
        if (!await TakeFood(CardType.Attack)) { Finish("ABORTED"); return; }
        Finish("ATTACK");
        // Native reward screen lets the player discard an old potion if full.
        await RewardsCmd.OfferCustom(EventOwner,
            [new PotionReward(ModelDb.Potion<AttackPotion>().ToMutable(), EventOwner)]);
    }

    private async Task FeedSkill()
    {
        if (!await TakeFood(CardType.Skill)) { Finish("ABORTED"); return; }
        await PlayerCmd.GainGold(DynamicVars.Gold.BaseValue, EventOwner);
        Finish("SKILL");
    }

    private async Task FeedPower()
    {
        if (_offeredRelic == null || !await TakeFood(CardType.Power)) { Finish("ABORTED"); return; }
        await RelicCmd.Obtain(_offeredRelic, EventOwner);
        Finish("POWER");
    }

    private async Task FeedCurse()
    {
        if (_combatRequested) return;
        _combatRequested = true;
        await TakeFood(CardType.Curse);
        // Even players without a curse (and dead players) must report ready.
        // The native synchronizer waits for every event instance before entering.
        EnterCombatWithoutExitingEvent<CaveMawWeak>(Array.Empty<Reward>(), shouldResumeAfterCombat: false);
    }

    private async Task TakeTip()
    {
        if (IsFinished) return;
        await DepthsEventDefaults.TakeSmallReward(EventOwner);
        Finish("TIP");
    }
    private void Finish(string page)
    {
        if (!IsFinished) SetEventFinished(L10NLookup($"POLITE_MAW.pages.{page}.description"));
    }
}
