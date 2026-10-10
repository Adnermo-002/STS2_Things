using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Runs;
using STS2_Things.Relics;

namespace STS2_Things.Events;

public sealed class CrowdedWard : EventModel
{
    public const int LocalHeal = 25;
    public const int BandageHeal = 6;
    private bool _settling;

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new HealVar("LocalHeal", LocalHeal), new HealVar("BandageHeal", BandageHeal),
        new IntVar("Combats", AnestheticChart.Duration), new IntVar("Cards", AnestheticChart.DrawPenalty),
        new StringVar("Curse", new LocString("cards", "INJURY.title").GetFormattedText()),
    ];

    public override bool IsAllowed(IRunState runState) => runState.Players.Any(p => !p.Creature.IsDead);
    public override IEnumerable<LocString> GameInfoOptions =>
        DepthsEventDefaults.DescribeOptions(this, "TREAT", "ANESTHETIZE", "BANDAGES");

    protected override IReadOnlyList<EventOption> GenerateInitialOptions() =>
    [
        new EventOption(this, Treat, InitialOptionKey("TREAT"), HoverTipFactory.FromCardWithCardHoverTips<Injury>()),
        new EventOption(this, Anesthetize, InitialOptionKey("ANESTHETIZE"),
            HoverTipFactory.FromRelic(ModelDb.Relic<AnestheticChart>())),
        new EventOption(this, TakeBandages, InitialOptionKey("BANDAGES")),
    ];

    private bool BeginSettlement()
    {
        if (IsFinished || _settling || Owner!.Creature.IsDead) return false;
        _settling = true;
        return true;
    }

    private async Task Treat()
    {
        if (!BeginSettlement()) return;
        await CreatureCmd.Heal(Owner!.Creature, Owner.Creature.MaxHp - Owner.Creature.CurrentHp);
        await CardPileCmd.AddCurseToDeck<Injury>(Owner);
        SetEventFinished(L10NLookup("CROWDED_WARD.pages.TREATED.description"));
    }

    private async Task Anesthetize()
    {
        if (!BeginSettlement()) return;
        // Obtain the saved native relic before healing; no hidden, unsaved debt.
        var existing = Owner!.Relics.OfType<AnestheticChart>().FirstOrDefault();
        if (existing == null) await RelicCmd.Obtain(ModelDb.Relic<AnestheticChart>().ToMutable(), Owner);
        else existing.Extend();
        await CreatureCmd.Heal(Owner.Creature, LocalHeal);
        SetEventFinished(L10NLookup("CROWDED_WARD.pages.ANESTHETIZED.description"));
    }

    private async Task TakeBandages()
    {
        if (!BeginSettlement()) return;
        await CreatureCmd.Heal(Owner!.Creature, BandageHeal);
        SetEventFinished(L10NLookup("CROWDED_WARD.pages.BANDAGES.description"));
    }
}
