using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Gold;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Vfx;
using MegaCrit.Sts2.Core.Runs;
using STS2_Things.Relics;

namespace STS2_Things.Events;

public sealed class UnlitFire : EventModel
{
    private const int DescriptionMinimumHeight = 220;
    public const int FuelCost = 25;
    private List<RestSiteOption> _options = [];
    private Player EventOwner => Owner ?? throw new InvalidOperationException("Unlit Fire has no owner.");
    private bool CanMakePlan => !EventOwner.Creature.IsDead && EventOwner.GetRelic<BorrowedEmber>() == null &&
        BorrowedEmber.FindNextRestSites(EventOwner.RunState).Count > 0;

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [new HealVar(0m), new GoldVar(FuelCost), new IntVar("BonusHeal", BorrowedEmber.KindledHeal), DepthsEventDefaults.SmallGoldVar()];

    public override bool IsAllowed(IRunState runState) => BorrowedEmber.FindNextRestSites(runState).Count > 0 &&
        runState.Players.Any(player => !player.Creature.IsDead && player.GetRelic<BorrowedEmber>() == null);

    public override void OnRoomEnter()
    {
        if (Node?.GetNodeOrNull<Control>("%EventDescription") is { } description)
            description.CustomMinimumSize = new Vector2(description.CustomMinimumSize.X, DescriptionMinimumHeight);
    }

    protected override Task BeforeEventStarted(bool isPreFinished)
    {
        // Generate once so native relic restrictions and modified smith counts
        // are honored without repeatedly consuming option-generation RNG.
        if (!isPreFinished) _options = RestSiteOption.Generate(EventOwner);
        return Task.CompletedTask;
    }

    public override void CalculateVars() => DynamicVars.Heal.BaseValue = HealRestSiteOption.GetHealAmount(EventOwner);

    public override IEnumerable<string> GetAssetPaths(IRunState runState) => base.GetAssetPaths(runState)
        .Concat(NCardSmithVfx.AssetPaths).Distinct();

    private IEnumerable<IHoverTip> PlanTips(bool kindled)
    {
        var preview = (BorrowedEmber)ModelDb.Relic<BorrowedEmber>().ToMutable();
        preview.Configure(kindled);
        return preview.HoverTips;
    }

    protected override IReadOnlyList<EventOption> GenerateInitialOptions()
    {
        bool heal = CanMakePlan && _options.OfType<HealRestSiteOption>().Any(option => option.IsEnabled);
        bool smith = CanMakePlan && _options.OfType<SmithRestSiteOption>().Any(option => option.IsEnabled);
        bool fuel = CanMakePlan && EventOwner.Gold >= FuelCost;
        return
        [
            new EventOption(this, heal ? BorrowRest : null, InitialOptionKey(heal ? "REST" : "REST_LOCKED"), PlanTips(false)),
            new EventOption(this, smith ? BorrowSmith : null, InitialOptionKey(smith ? "SMITH" : "SMITH_LOCKED"), PlanTips(false)),
            new EventOption(this, fuel ? AddFuel : null, InitialOptionKey(fuel ? "FUEL" : "FUEL_LOCKED"), PlanTips(true)),
            new EventOption(this, TakeCharcoal, InitialOptionKey("CHARCOAL")),
        ];
    }

    private async Task MakePlan(bool kindled)
    {
        var ember = (BorrowedEmber)ModelDb.Relic<BorrowedEmber>().ToMutable();
        ember.Configure(kindled);
        await RelicCmd.Obtain(ember, EventOwner);
    }

    private async Task BorrowRest()
    {
        if (IsFinished || !CanMakePlan) return;
        await MakePlan(false);
        await PlayerCmd.MimicRestSiteHeal(EventOwner);
        Finish("REST");
    }

    private async Task BorrowSmith()
    {
        if (IsFinished || !CanMakePlan) return;
        var smith = _options.OfType<SmithRestSiteOption>().FirstOrDefault(option => option.IsEnabled);
        if (smith == null || !await smith.OnSelect())
        {
            SetEventState(InitialDescription, GenerateInitialOptions());
            return;
        }
        await MakePlan(false);
        if (LocalContext.IsMe(EventOwner)) await smith.DoLocalPostSelectVfx();
        Finish("SMITH");
    }

    private async Task AddFuel()
    {
        if (IsFinished || !CanMakePlan || EventOwner.Gold < FuelCost) return;
        await PlayerCmd.LoseGold(FuelCost, EventOwner, GoldLossType.Spent);
        await MakePlan(true);
        Finish("FUEL");
    }

    private async Task TakeCharcoal()
    {
        if (IsFinished) return;
        await DepthsEventDefaults.TakeSmallReward(EventOwner);
        Finish("CHARCOAL");
    }

    private void Finish(string page) => SetEventFinished(L10NLookup($"UNLIT_FIRE.pages.{page}.description"));
}
