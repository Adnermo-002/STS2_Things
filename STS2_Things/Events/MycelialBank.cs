using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Relics;

namespace STS2_Things.Events;

public sealed class MycelialBank : EventModel
{
    private Player EventOwner => Owner ?? throw new InvalidOperationException("Mycelial Bank has no owner.");
    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new HpLossVar(MycelialDeposit.ShortPrincipal), new HealVar(MycelialDeposit.ShortRepayment),
        new IntVar("Payments", MycelialDeposit.ShortPayments), new IntVar("MaxHpCost", MycelialDeposit.LongPrincipal),
        new IntVar("MaxHpReturn", MycelialDeposit.LongRepayment), DepthsEventDefaults.SmallGoldVar(),
    ];

    public override bool IsAllowed(IRunState runState) => runState.Players.Any(player => !player.Creature.IsDead);
    private bool HasAccount => EventOwner.GetRelic<MycelialDeposit>() != null;
    private bool CanShort => !HasAccount && !EventOwner.Creature.IsDead && EventOwner.Creature.CurrentHp > MycelialDeposit.ShortPrincipal;
    private bool CanLong => !HasAccount && !EventOwner.Creature.IsDead && EventOwner.Creature.MaxHp > MycelialDeposit.LongPrincipal;

    private IEnumerable<IHoverTip> Terms(bool longTerm)
    {
        var preview = (MycelialDeposit)ModelDb.Relic<MycelialDeposit>().ToMutable();
        preview.Open(longTerm, EventOwner.RunState.CurrentActIndex);
        return preview.HoverTips;
    }

    protected override IReadOnlyList<EventOption> GenerateInitialOptions() =>
    [
        new EventOption(this, CanShort ? DepositShort : null, InitialOptionKey(CanShort ? "SHORT" : "SHORT_LOCKED"), Terms(false)),
        new EventOption(this, CanLong ? DepositLong : null, InitialOptionKey(CanLong ? "LONG" : "LONG_LOCKED"), Terms(true)),
        new EventOption(this, TakeGift, InitialOptionKey("GIFT")),
    ];

    private async Task DepositShort()
    {
        if (IsFinished || !CanShort) return;
        await OpenAccount(false);
        await CreatureCmd.Damage(new ThrowingPlayerChoiceContext(), EventOwner.Creature,
            MycelialDeposit.ShortPrincipal, ValueProp.Unblockable | ValueProp.Unpowered, null, null);
        Finish(EventOwner.Creature.IsDead ? "DEATH" : "SHORT");
    }

    private async Task DepositLong()
    {
        if (IsFinished || !CanLong) return;
        await OpenAccount(true);
        await CreatureCmd.LoseMaxHp(new ThrowingPlayerChoiceContext(), EventOwner.Creature,
            MycelialDeposit.LongPrincipal, false);
        Finish(EventOwner.Creature.IsDead ? "DEATH" : "LONG");
    }

    private async Task OpenAccount(bool longTerm)
    {
        var receipt = (MycelialDeposit)ModelDb.Relic<MycelialDeposit>().ToMutable();
        receipt.Open(longTerm, EventOwner.RunState.CurrentActIndex);
        await RelicCmd.Obtain(receipt, EventOwner);
    }

    private async Task TakeGift()
    {
        if (IsFinished) return;
        await DepthsEventDefaults.TakeSmallReward(EventOwner);
        Finish("GIFT");
    }

    private void Finish(string page) => SetEventFinished(L10NLookup($"MYCELIAL_BANK.pages.{page}.description"));
}
