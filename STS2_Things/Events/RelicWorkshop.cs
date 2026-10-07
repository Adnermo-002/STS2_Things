using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Gold;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Factories;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;

namespace STS2_Things.Events;

/// <summary>A personal, previewed exchange using the native tradability rules.</summary>
public sealed class RelicWorkshop : EventModel
{
    private const int TradeCost = 30;
    private const int SaleGold = 200;
    private const int PageSize = 3;
    private RelicModel? _offer;
    private bool _settling;
    private Player EventOwner => Owner ?? throw new InvalidOperationException("Relic Workshop has no owner.");
    private RelicModel[] TradableRelics => EventOwner.Relics.Where(relic => relic.IsTradable).ToArray();
    private bool CanTrade => _offer != null && TradableRelics.Length > 0 && EventOwner.Gold >= TradeCost;

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new GoldVar(TradeCost), new IntVar("SaleGold", SaleGold), DepthsEventDefaults.SmallGoldVar(),
        new StringVar("Offer", L10NLookup("RELIC_WORKSHOP.commonRelic").GetFormattedText()),
    ];

    public override bool IsAllowed(IRunState runState) => runState.Players.Any(player => !player.Creature.IsDead);
    public override IEnumerable<LocString> GameInfoOptions =>
        DepthsEventDefaults.DescribeOptions(this, "TRADE", "SELL", "COINS");

    public override void OnRoomEnter()
    {
        base.OnRoomEnter();
        // At most three relics plus More and Back, using native event buttons.
        if (Node?.GetNodeOrNull<Control>("%EventDescription") is { } description)
            description.CustomMinimumSize = new Vector2(description.CustomMinimumSize.X, 144);
    }

    protected override Task BeforeEventStarted(bool isPreFinished)
    {
        if (!isPreFinished && _offer == null && TradableRelics.Length > 0)
        {
            var relic = RelicFactory.PullNextRelicFromFront(EventOwner, RelicRarity.Common,
                candidate => EventOwner.Relics.All(owned => owned.Id != candidate.Id));
            // An exhausted grab bag returns Circlet. Do not advertise it as Common.
            if (relic.Rarity == RelicRarity.Common && EventOwner.Relics.All(owned => owned.Id != relic.Id))
            {
                _offer = relic.ToMutable();
                _offer.Owner = EventOwner;
                ((StringVar)DynamicVars["Offer"]).StringValue = _offer.Title.GetFormattedText();
            }
        }
        return Task.CompletedTask;
    }

    protected override IReadOnlyList<EventOption> GenerateInitialOptions()
    {
        string trade = TradableRelics.Length == 0 ? "NO_RELIC" : _offer == null ? "NO_OFFER" :
            EventOwner.Gold < TradeCost ? "NO_GOLD" : "TRADE";
        return
        [
            new EventOption(this, trade == "TRADE" ? () => ShowRelics(false, 0) : null,
                InitialOptionKey(trade), _offer?.HoverTips ?? Array.Empty<IHoverTip>()),
            new EventOption(this, TradableRelics.Length > 0 ? () => ShowRelics(true, 0) : null,
                InitialOptionKey(TradableRelics.Length > 0 ? "SELL" : "SELL_LOCKED")),
            new EventOption(this, TakeCoins, InitialOptionKey("COINS")),
        ];
    }

    private Task ShowRelics(bool selling, int page)
    {
        if (IsFinished || _settling) return Task.CompletedTask;
        var relics = TradableRelics;
        if (relics.Length == 0 || (!selling && !CanTrade)) return Back();
        int pages = (relics.Length + PageSize - 1) / PageSize;
        page %= pages;
        var options = new List<EventOption>();
        string key = $"RELIC_WORKSHOP.pages.SELECT.options.{(selling ? "SELL" : "TRADE")}";
        foreach (var relic in relics.Skip(page * PageSize).Take(PageSize))
        {
            var title = L10NLookup(key + ".title");
            title.Add("Relic", relic.Title.GetFormattedText());
            var description = L10NLookup(key + ".description");
            description.Add("Relic", relic.Title.GetFormattedText());
            var tips = selling ? relic.HoverTips : relic.HoverTips.Concat(_offer!.HoverTips);
            options.Add(new EventOption(this, () => Settle(relic, selling), title, description, key, tips)
                .ThatHasDynamicTitle());
        }
        if (pages > 1)
        {
            int nextPage = (page + 1) % pages;
            const string moreKey = "RELIC_WORKSHOP.pages.SELECT.options.MORE";
            var description = L10NLookup(moreKey + ".description");
            description.Add("Page", page + 1);
            description.Add("Pages", pages);
            options.Add(new EventOption(this, () => ShowRelics(selling, nextPage),
                L10NLookup(moreKey + ".title"), description, moreKey, Array.Empty<IHoverTip>()));
        }
        options.Add(new EventOption(this, Back, "RELIC_WORKSHOP.pages.SELECT.options.BACK"));
        SetEventState(L10NLookup($"RELIC_WORKSHOP.pages.SELECT_{(selling ? "SELL" : "TRADE")}.description"), options);
        return Task.CompletedTask;
    }

    private async Task Settle(RelicModel relic, bool selling)
    {
        if (IsFinished || _settling) return;
        if (EventOwner.Creature.IsDead || !EventOwner.Relics.Contains(relic) || !relic.IsTradable ||
            (!selling && !CanTrade)) { await Back(); return; }
        _settling = true;
        await RelicCmd.Remove(relic);
        if (selling) await PlayerCmd.GainGold(SaleGold, EventOwner);
        else
        {
            await PlayerCmd.LoseGold(TradeCost, EventOwner, GoldLossType.Spent);
            await RelicCmd.Obtain(_offer!, EventOwner);
        }
        SetEventFinished(L10NLookup($"RELIC_WORKSHOP.pages.{(selling ? "SOLD" : "TRADED")}.description"));
    }

    private Task Back()
    {
        if (!IsFinished && !_settling) SetEventState(InitialDescription, GenerateInitialOptions());
        return Task.CompletedTask;
    }

    private async Task TakeCoins()
    {
        if (IsFinished || _settling) return;
        _settling = true;
        await DepthsEventDefaults.TakeSmallReward(EventOwner);
        SetEventFinished(L10NLookup("RELIC_WORKSHOP.pages.COINS.description"));
    }
}
