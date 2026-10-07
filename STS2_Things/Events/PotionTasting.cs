using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Gold;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Factories;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;

namespace STS2_Things.Events;

/// <summary>Personal random potion rewards, with a choice of payment for barter.</summary>
public sealed class PotionTasting : EventModel
{
    private const int PairCost = 30;
    private const int WarmWaterHeal = 4;
    private const int PageSize = 3;
    private PotionModel[]? _rolledPotions;
    private bool _previousPotionPermission;
    private bool _permissionCaptured;
    private bool _settling;
    private Player EventOwner => Owner ?? throw new InvalidOperationException("Potion Tasting has no owner.");
    private PotionModel[] ReceivablePotions => (_rolledPotions ?? Array.Empty<PotionModel>()).Where(CanReceive).ToArray();
    private bool PotionPermission
    {
        get
        {
#if STS2_V107_1
            return EventOwner.CanRemovePotions;
#else
            return EventOwner.CanUseOrRemovePotions;
#endif
        }
        set
        {
#if STS2_V107_1
            EventOwner.CanRemovePotions = value;
#else
            EventOwner.CanUseOrRemovePotions = value;
#endif
        }
    }

    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new GoldVar(PairCost), new HealVar(WarmWaterHeal)];
    public override bool IsAllowed(IRunState runState) => runState.Players.Any(player => !player.Creature.IsDead);
    public override IEnumerable<LocString> GameInfoOptions =>
        DepthsEventDefaults.DescribeOptions(this, "SAMPLE", "BUY", "BARTER", "WATER");

    private bool CanReceive(PotionModel potion) => Hook.ShouldProcurePotion(EventOwner.RunState,
        EventOwner.Creature.CombatState, potion.ToMutable(), EventOwner);

    public override void OnRoomEnter()
    {
        base.OnRoomEnter();
        if (Node?.GetNodeOrNull<Control>("%EventDescription") is { } description)
            description.CustomMinimumSize = new Vector2(description.CustomMinimumSize.X, 144);
    }

    protected override Task BeforeEventStarted(bool isPreFinished)
    {
        if (isPreFinished) return Task.CompletedTask;
        // The native factory respects character pools, unlocks and rarity odds.
#if STS2_V107_1
        var options = PotionFactory.GetPotionOptions(EventOwner, Array.Empty<PotionModel>());
#else
        var options = PotionFactory.GetPotionOptions(EventOwner);
#endif
        var nonVanilla = options.Where(potion => potion.GetType().Assembly != typeof(PotionModel).Assembly);
        // Roll once and keep results hidden until the native reward screen.
        // Returning from the payment menu cannot reroll the reward.
        _rolledPotions ??= PotionFactory.CreateRandomPotionsOutOfCombat(EventOwner, 2, Rng, nonVanilla).ToArray();
        _previousPotionPermission = PotionPermission;
        _permissionCaptured = true;
        PotionPermission = false;
        return Task.CompletedTask;
    }

    protected override void OnEventFinished()
    {
        if (_permissionCaptured) PotionPermission = _previousPotionPermission;
    }

    protected override IReadOnlyList<EventOption> GenerateInitialOptions()
    {
        int receivable = ReceivablePotions.Length;
        bool canPair = receivable >= 2;
        bool canBuy = canPair && EventOwner.Gold >= PairCost;
        bool canBarter = canPair && EventOwner.Potions.Any();
        return
        [
            receivable > 0
                ? new EventOption(this, () => Award(1, false, null), InitialOptionKey("SAMPLE"))
                : new EventOption(this, DrinkWater, InitialOptionKey("WATER")),
            new EventOption(this, canBuy ? () => Award(2, true, null) : null,
                InitialOptionKey(!canPair ? "CANNOT_RECEIVE" : canBuy ? "BUY" : "BUY_LOCKED")),
            new EventOption(this, canBarter ? () => ShowPayment(0) : null,
                InitialOptionKey(!canPair ? "CANNOT_RECEIVE" : canBarter ? "BARTER" : "BARTER_LOCKED")),
        ];
    }

    private Task ShowPayment(int page)
    {
        if (IsFinished || _settling) return Task.CompletedTask;
        var potions = EventOwner.Potions.ToArray();
        if (potions.Length == 0 || ReceivablePotions.Length < 2) return Back();
        int pages = (potions.Length + PageSize - 1) / PageSize;
        page %= pages;
        var options = new List<EventOption>();
        foreach (var potion in potions.Skip(page * PageSize).Take(PageSize))
        {
            const string key = "POTION_TASTING.pages.PAYMENT.options.GIVE";
            var title = L10NLookup(key + ".title");
            title.Add("Potion", potion.Title.GetFormattedText());
            var description = L10NLookup(key + ".description");
            description.Add("Potion", potion.Title.GetFormattedText());
            options.Add(new EventOption(this, () => Award(2, false, potion), title, description, key,
                new[] { HoverTipFactory.FromPotion(potion) })
                .ThatHasDynamicTitle());
        }
        if (pages > 1)
        {
            int nextPage = (page + 1) % pages;
            const string key = "POTION_TASTING.pages.PAYMENT.options.MORE";
            var description = L10NLookup(key + ".description");
            description.Add("Page", page + 1);
            description.Add("Pages", pages);
            options.Add(new EventOption(this, () => ShowPayment(nextPage),
                L10NLookup(key + ".title"), description, key, Array.Empty<IHoverTip>()));
        }
        options.Add(new EventOption(this, Back, "POTION_TASTING.pages.PAYMENT.options.BACK"));
        SetEventState(L10NLookup("POTION_TASTING.pages.PAYMENT.description"), options);
        return Task.CompletedTask;
    }

    private async Task Award(int count, bool paid, PotionModel? payment)
    {
        if (IsFinished || _settling) return;
        var potions = ReceivablePotions.Take(count).ToArray();
        if (EventOwner.Creature.IsDead || (paid && EventOwner.Gold < PairCost) ||
            potions.Length != count || (payment != null && !EventOwner.Potions.Contains(payment)))
            { await Back(); return; }
        _settling = true;
        if (payment != null) await PotionCmd.Discard(payment);
        if (paid) await PlayerCmd.LoseGold(PairCost, EventOwner, GoldLossType.Spent);
        // Restore native potion controls before opening rewards, so full slots
        // can be freed normally. Never try to Obtain into an already full belt.
        if (_permissionCaptured) PotionPermission = _previousPotionPermission;
        await RewardsCmd.OfferCustom(EventOwner,
            potions.Select(potion => (Reward)new PotionReward(potion.ToMutable(), EventOwner)).ToList());
        SetEventFinished(L10NLookup($"POTION_TASTING.pages.{(payment != null ? "BARTERED" : paid ? "BOUGHT" : "SAMPLED")}.description"));
    }

    private Task Back()
    {
        if (!IsFinished && !_settling) SetEventState(InitialDescription, GenerateInitialOptions());
        return Task.CompletedTask;
    }

    private async Task DrinkWater()
    {
        if (IsFinished || _settling) return;
        _settling = true;
        await CreatureCmd.Heal(EventOwner.Creature, WarmWaterHeal);
        SetEventFinished(L10NLookup("POTION_TASTING.pages.WATER.description"));
    }
}
