using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Saves.Runs;

namespace STS2_Things.Relics;

/// <summary>Saved two-combat debt; opening draw uses the native Bag of Preparation hook.</summary>
public sealed class AnestheticChart : RelicModel
{
    public const int Duration = 2;
    public const int DrawPenalty = 2;
    private int _remainingCombats = Duration;
    private bool _appliedThisCombat;

    public override RelicRarity Rarity => RelicRarity.Event;
    public override bool ShowCounter => true;
    public override int DisplayAmount => RemainingCombats;
    public override bool IsUsedUp => RemainingCombats <= 0;
    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new IntVar("Combats", Duration), new CardsVar(DrawPenalty)];

    [SavedProperty]
    public int RemainingCombats
    {
        get => _remainingCombats;
        private set { AssertMutable(); _remainingCombats = Math.Max(0, value); Refresh(); }
    }

    [SavedProperty]
    public bool AppliedThisCombat
    {
        get => _appliedThisCombat;
        private set { AssertMutable(); _appliedThisCombat = value; Refresh(); }
    }

    private void Refresh()
    {
        DynamicVars["Combats"].BaseValue = RemainingCombats;
        Status = IsUsedUp ? RelicStatus.Disabled : AppliedThisCombat ? RelicStatus.Active : RelicStatus.Normal;
        InvokeDisplayAmountChanged();
    }

    internal void Extend() => RemainingCombats += Duration;

    public override decimal ModifyHandDraw(Player player, decimal count)
    {
        if (player != Owner || IsUsedUp || AppliedThisCombat || player.PlayerCombatState?.TurnNumber != 1)
            return count;
        return Math.Max(0m, count - DrawPenalty);
    }

    public override Task AfterModifyingHandDraw()
    {
        AppliedThisCombat = true;
        Flash();
        return Task.CompletedTask;
    }

    public override Task AfterCombatEnd(CombatRoom room)
    {
        if (AppliedThisCombat)
        {
            RemainingCombats--;
            AppliedThisCombat = false;
        }
        return Task.CompletedTask;
    }
}
