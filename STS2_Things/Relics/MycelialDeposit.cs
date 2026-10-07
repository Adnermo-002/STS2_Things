using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Saves.Runs;

namespace STS2_Things.Relics;

public sealed class MycelialDeposit : RelicModel
{
    public const int ShortPrincipal = 12, ShortRepayment = 6, ShortPayments = 3;
    public const int LongPrincipal = 6, LongRepayment = 12;
    private bool _longTerm;
    private int _payments = ShortPayments;
    private CombatRoom? _lastPaidCombat;

    public override RelicRarity Rarity => RelicRarity.Event;
    public override bool IsUsedUp => PaymentsRemaining == 0;
    public override bool ShowCounter => true;
    public override int DisplayAmount => PaymentsRemaining;
    protected override IEnumerable<DynamicVar> CanonicalVars => [new StringVar("Terms", ShortTerms(ShortPayments))];

    [SavedProperty]
    public bool LongTerm
    {
        get => _longTerm;
        private set { AssertMutable(); _longTerm = value; Refresh(); }
    }
    [SavedProperty]
    public int DepositActIndex { get; private set; }
    [SavedProperty]
    public int PaymentsRemaining
    {
        get => _payments;
        private set { AssertMutable(); _payments = Math.Max(0, value); Refresh(); }
    }

    internal void Open(bool longTerm, int act)
    {
        AssertMutable();
        LongTerm = longTerm;
        DepositActIndex = act;
        PaymentsRemaining = longTerm ? 1 : ShortPayments;
    }

    private static string ShortTerms(int remaining)
    {
        var text = new LocString("relics", "MYCELIAL_DEPOSIT.shortTerms");
        text.Add("Payments", remaining);
        text.Add("Heal", ShortRepayment);
        return text.GetFormattedText();
    }

    private void Refresh()
    {
        var longTerms = new LocString("relics", "MYCELIAL_DEPOSIT.longTerms");
        longTerms.Add("MaxHp", LongRepayment);
        ((StringVar)DynamicVars["Terms"]).StringValue = LongTerm ? longTerms.GetFormattedText() : ShortTerms(PaymentsRemaining);
        Status = IsUsedUp ? RelicStatus.Disabled : RelicStatus.Normal;
        InvokeDisplayAmountChanged();
    }

    protected override void AfterCloned() { base.AfterCloned(); _lastPaidCombat = null; }
    public override Task BeforeCombatStart() { _lastPaidCombat = null; return Task.CompletedTask; }

    public override async Task AfterCombatEnd(CombatRoom room)
    {
        if (LongTerm || IsUsedUp || Owner.Creature.IsDead || ReferenceEquals(room, _lastPaidCombat)) return;
        _lastPaidCombat = room;
        PaymentsRemaining--;
        Flash();
        await CreatureCmd.Heal(Owner.Creature, ShortRepayment);
    }

    public override Task AfterCombatVictory(CombatRoom room) => LongTerm &&
        room.RoomType == RoomType.Boss && Owner.RunState.CurrentActIndex == DepositActIndex
        ? PayLongTerm() : Task.CompletedTask;

    // A surviving teammate may finish the Boss while this owner is dead.
    // The principal remains saved until its owner is alive in the next act.
    public override Task AfterActEntered() => PayOverdue();
    public override Task AfterRoomEntered(AbstractRoom room) => PayOverdue();
    private Task PayOverdue() => LongTerm && Owner.RunState.CurrentActIndex > DepositActIndex
        ? PayLongTerm() : Task.CompletedTask;

    private async Task PayLongTerm()
    {
        if (IsUsedUp || Owner.Creature.IsDead) return;
        PaymentsRemaining = 0;
        Flash();
        await CreatureCmd.GainMaxHp(Owner.Creature, LongRepayment);
    }
}
