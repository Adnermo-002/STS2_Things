using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Monsters;
using STS2_Things.Visuals;

namespace STS2_Things.Powers;

public readonly record struct RadioChannel(int Attacks, int Skills)
{
    public int Mask => (Attacks > 0 ? 1 : 0) | (Skills > 0 ? 2 : 0);
}

public readonly record struct RadioProgram(RadioChannel First, RadioChannel Second)
{
    public int Key => First.Mask | (Second.Mask << 2);
    public int AttackCount => 1 + (First.Attacks > 0 ? 1 : 0) + (Second.Attacks > 0 ? 1 : 0);
    public int SkillCount => First.Skills + Second.Skills;
    public RadioChannel Channel(int index) => index == 0 ? First : Second;
}

/// <summary>Per-player first-two records, merged by beat. All peers run native card hooks.</summary>
public sealed class RadioReceptionPower : PowerModel
{
    public const int BonusPerStack = 2;
    private sealed class Data
    {
        public readonly Dictionary<ulong, List<CardType>> Records = [];
        public readonly HashSet<ulong> ListeningPlayers = [];
        public int Revision;
    }
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public int ReplayBonus => Math.Max(0, Amount) * BonusPerStack;
    protected override object InitInternalData() => new Data();
    public int Revision => IsMutable ? GetInternalData<Data>().Revision : 0;
    private RadioProgram VisibleProgram => Owner.Monster is RadioJellyfish { ActiveProgram: { } active }
        ? active : GetProgram();
    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new IntVar("EchoDamage", RadioJellyfish.BaseEchoDamage + BonusPerStack),
         new IntVar("ShieldPerSkill", RadioJellyfish.BaseSkillBlock + BonusPerStack),
         new IntVar("BonusPerStack", BonusPerStack), new IntVar("ReplayBonus", BonusPerStack)];
    protected override IEnumerable<IHoverTip> ExtraHoverTips
    {
        get
        {
            var attack = new LocString("powers", "RADIO_RECEPTION_POWER.attackDescription");
            var skill = new LocString("powers", "RADIO_RECEPTION_POWER.skillDescription");
            DynamicVars.AddTo(attack);
            DynamicVars.AddTo(skill);
            return [new HoverTip(new LocString("powers", "RADIO_RECEPTION_POWER.attackTitle"), attack),
                new HoverTip(new LocString("powers", "RADIO_RECEPTION_POWER.skillTitle"), skill)];
        }
    }

    public RadioProgram GetProgram()
    {
        if (!IsMutable) return default;
        var data = GetInternalData<Data>();
        int a0 = 0, a1 = 0, s0 = 0, s1 = 0;
        // NetId identifies the actor; roster order and packet interleaving cannot
        // let the fastest player consume another player's two recording slots.
        foreach (var player in CombatState.Players.OrderBy(p => p.NetId))
        {
            if (!player.Creature.IsAlive || !data.Records.TryGetValue(player.NetId, out var records)) continue;
            if (records.Count > 0) { if (records[0] == CardType.Attack) a0++; else s0++; }
            if (records.Count > 1) { if (records[1] == CardType.Attack) a1++; else s1++; }
        }
        return new(new(a0, s0), new(a1, s1));
    }

    public override Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        Refresh(refreshIntents: true);
        return Task.CompletedTask;
    }

    public override Task AfterPowerAmountChanged(PlayerChoiceContext choiceContext, PowerModel power,
        decimal amount, Creature? applier, CardModel? cardSource)
    {
        if (ReferenceEquals(power, this)) Refresh(refreshIntents: true);
        return Task.CompletedTask;
    }

#if STS2_V107_1
    public override decimal ModifyDamageAdditive(Creature? target, decimal amount, ValueProp props,
        Creature? dealer, CardModel? cardSource)
#else
    public override decimal ModifyDamageAdditive(Creature? target, decimal amount, ValueProp props,
        Creature? dealer, CardModel? cardSource, CardPlay? cardPlay)
#endif
    {
        // Native damage hooks apply the same stack bonus to the intent and hit.
        return Owner == dealer && Owner.Monster is RadioJellyfish && props.IsPoweredAttack()
            ? ReplayBonus : 0m;
    }

    public override Task BeforeSideTurnStart(PlayerChoiceContext choiceContext, CombatSide side,
        IReadOnlyList<Creature> participants, ICombatState combatState)
    {
        if (side != CombatSide.Player || !Owner.IsAlive) return Task.CompletedTask;
        var data = GetInternalData<Data>();
        data.ListeningPlayers.Clear();
        if (Owner.Monster is RadioJellyfish { IsTuningTurn: true })
        {
            data.Records.Clear();
            data.Revision++;
            Refresh();
            return Task.CompletedTask;
        }
        // Extra turns reset only participating players, before opening draws
        // and automatic plays. Other players keep their own current records.
        foreach (var creature in participants)
            if (creature.Player is { } player)
            {
                data.Records.Remove(player.NetId);
                data.ListeningPlayers.Add(player.NetId);
            }
        data.Revision++;
        Refresh();
        return Task.CompletedTask;
    }

    public override Task BeforeCardPlayed(CardPlay play)
    {
        var data = GetInternalData<Data>();
        if (!Owner.IsAlive || CombatManager.Instance.IsOverOrEnding ||
            Owner.Monster is RadioJellyfish { IsTuningTurn: true } ||
            play.Card.Type is not (CardType.Attack or CardType.Skill) ||
            !play.IsFirstInSeries || play.Card.IsDupe) return Task.CompletedTask;
#if STS2_V107_1
        // Capture before OnPlay, so native cards that transfer ownership later
        // are still credited to the player who started playing them.
        Player actor = play.Card.Owner;
#else
        Player actor = play.Player;
#endif
        if (!data.ListeningPlayers.Contains(actor.NetId) || !actor.Creature.IsAlive ||
            actor.Creature.CombatState != CombatState) return Task.CompletedTask;
        if (!data.Records.TryGetValue(actor.NetId, out var records))
            data.Records[actor.NetId] = records = [];
        if (records.Count >= 2) return Task.CompletedTask;
        int beat = records.Count;
        records.Add(play.Card.Type);
        data.Revision++;
        Flash();
        Refresh();
        NRadioCaptureVfx.Play(play.Card, actor.Creature, Owner, beat);
        return Task.CompletedTask;
    }

    public override Task AfterSideTurnEnd(PlayerChoiceContext choiceContext, CombatSide side,
        IEnumerable<Creature> participants)
    {
        if (side == CombatSide.Player)
        {
            GetInternalData<Data>().ListeningPlayers.Clear();
            if (Owner.IsAlive) Refresh();
        }
        return Task.CompletedTask;
    }

    public override Task AfterDeath(PlayerChoiceContext choiceContext, Creature creature,
        bool wasRemovalPrevented, float deathAnimLength)
    {
        if (!wasRemovalPrevented && !creature.IsAlive && creature.Player is { } player)
        {
            GetInternalData<Data>().Records.Remove(player.NetId);
            GetInternalData<Data>().ListeningPlayers.Remove(player.NetId);
            GetInternalData<Data>().Revision++;
            if (Owner.IsAlive) Refresh();
        }
        return Task.CompletedTask;
    }

    public override Task AfterRemoved(Creature oldOwner)
    {
        GetInternalData<Data>().Records.Clear();
        GetInternalData<Data>().ListeningPlayers.Clear();
        oldOwner.GetPower<RadioReceptionStatePower>()?.Clear();
        if (oldOwner.Monster is RadioJellyfish jelly) jelly.RefreshReplayState(default, refreshIntents: true);
        return Task.CompletedTask;
    }

    public override Task AfterCombatEnd(CombatRoom room)
    {
        GetInternalData<Data>().Records.Clear();
        GetInternalData<Data>().ListeningPlayers.Clear();
        return Task.CompletedTask;
    }

    public void ShowReplay() { Flash(); Refresh(); }
    public void PlaybackFinished()
    {
        if (Owner.IsAlive && !CombatManager.Instance.IsOverOrEnding) Refresh();
    }

    private void Refresh(bool refreshIntents = false)
    {
        DynamicVars["ReplayBonus"].BaseValue = ReplayBonus;
        if (Owner.Monster is RadioJellyfish owner)
        {
            DynamicVars["EchoDamage"].BaseValue = owner.EchoDamage + ReplayBonus;
            DynamicVars["ShieldPerSkill"].BaseValue = owner.ShieldPerSkill;
        }
        var program = VisibleProgram;
        var data = GetInternalData<Data>();
        IEnumerable<int> Codes()
        {
            foreach (var player in CombatState.Players)
            {
                int code = data.ListeningPlayers.Contains(player.NetId) ? 16 : 0;
                if (!player.Creature.IsAlive) code |= 32;
                if (data.Records.TryGetValue(player.NetId, out var records))
                {
                    if (records.Count > 0) code |= records[0] == CardType.Attack ? 1 : 2;
                    if (records.Count > 1) code |= (records[1] == CardType.Attack ? 1 : 2) << 2;
                }
                yield return code;
            }
        }
        Owner.GetPower<RadioReceptionStatePower>()?.Synchronize(Codes(), program);
        // The native intent and physical chambers display the current programme.
        InvokeDisplayAmountChanged();
        if (Owner.Monster is RadioJellyfish jelly) jelly.RefreshReplayState(program, refreshIntents);
    }
}
