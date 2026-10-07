using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using STS2_Things.Monsters;
using STS2_Things.Visuals;
using MegaCrit.Sts2.Core.ValueProps;

namespace STS2_Things.Powers;

public sealed class MycorrhizalBondPower : PowerModel
{
    private sealed class Data { public int LastExchangeRound = -1; public bool Robust; }
    protected override object InitInternalData() => new Data();
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.None;
    public bool IsRobust => GetInternalData<Data>().Robust;
    protected override string SmartDescriptionLocKey => IsMutable
        ? IsRobust ? "MYCORRHIZAL_BOND_POWER.robustDescription" : "MYCORRHIZAL_BOND_POWER.witheredDescription"
        : base.SmartDescriptionLocKey;
    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        [HoverTipFactory.FromPower<StrengthPower>(), HoverTipFactory.FromPower<PlatingPower>(), HoverTipFactory.FromPower<MycorrhizalFuryPower>()];

    public override Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        GetInternalData<Data>().Robust = Owner.Monster is MycorrhizalVanguard;
        return Task.CompletedTask;
    }
#if STS2_V107_1
    public override decimal ModifyDamageMultiplicative(Creature? target, decimal amount, ValueProp props,
        Creature? dealer, CardModel? cardSource) =>
#else
    public override decimal ModifyDamageMultiplicative(Creature? target, decimal amount, ValueProp props,
        Creature? dealer, CardModel? cardSource, CardPlay? cardPlay) =>
#endif
        dealer == Owner && props.IsPoweredAttack() ? IsRobust ? 1.25m : .75m : 1m;

    public override async Task AfterSideTurnEnd(PlayerChoiceContext choiceContext, CombatSide side, IEnumerable<Creature> participants)
    {
        if (side != CombatSide.Enemy || !Owner.IsAlive || Owner.Monster is not MycorrhizalVanguard twin ||
            twin.Partner is not { } partner || partner.Creature.GetPower<MycorrhizalBondPower>() == null ||
            !participants.Contains(Owner)) return;
        var data = GetInternalData<Data>();
        if (data.LastExchangeRound == CombatState.RoundNumber) return;
        data.LastExchangeRound = CombatState.RoundNumber;
        int first = Owner.CurrentHp, second = partner.Creature.CurrentHp;
        Flash(); partner.Creature.GetPower<MycorrhizalBondPower>()!.Flash();
        NMycorrhizalLink.Pulse(Owner, partner.Creature);
        await CreatureCmd.TriggerAnim(Owner, "Exchange", 0);
        await CreatureCmd.TriggerAnim(partner.Creature, "Exchange", .62f);
        // Transfer actual HP through native commands, never damage, healing, or revival.
        if (!Owner.IsAlive || !partner.Creature.IsAlive) return;
        await CreatureCmd.SetCurrentHp(Owner, Math.Min(second, Owner.MaxHp));
        if (partner.Creature.IsAlive && Owner.IsAlive)
            await CreatureCmd.SetCurrentHp(partner.Creature, Math.Min(first, partner.Creature.MaxHp));
        if (partner.Creature.IsAlive && Owner.IsAlive)
        {
            // Equal HP still trades the two forms. Form is fixed for the round,
            // so multihit attacks never change damage halfway through execution.
            bool robust = Owner.CurrentHp == partner.Creature.CurrentHp ? !IsRobust : Owner.CurrentHp > partner.Creature.CurrentHp;
            data.Robust = robust;
            var other = partner.Creature.GetPower<MycorrhizalBondPower>();
            if (other != null) { other.GetInternalData<Data>().Robust = !robust; other.InvokeDisplayAmountChanged(); }
            InvokeDisplayAmountChanged();
        }
        await twin.FinishPose("exchange",1.55f,.9f);
    }

    public override async Task AfterDeath(PlayerChoiceContext choiceContext, Creature creature, bool wasRemovalPrevented, float deathAnimLength)
    {
        if (wasRemovalPrevented || creature.IsAlive || creature == Owner || !Owner.IsAlive ||
            Owner.Monster is not MycorrhizalTwin twin || creature.Monster is not MycorrhizalTwin dead ||
            dead.IsVanguard == twin.IsVanguard || twin.IsFurious) return;
        await PowerCmd.Apply<MycorrhizalFuryPower>(choiceContext, Owner, 1, Owner, null);
        await PowerCmd.Apply<StrengthPower>(choiceContext, Owner, 4, Owner, null);
        await PowerCmd.Remove(this);
        await CreatureCmd.TriggerAnim(Owner, "Enrage", .7f);
        // Keep the already announced action (and native stun). The next normal
        // transition selects the survivor's own frenzy cycle.
    }
}
