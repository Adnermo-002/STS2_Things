using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Bestiary;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Cards;
using STS2_Things.Powers;
using STS2_Things.Visuals;

namespace STS2_Things.Monsters;

/// <summary>
/// 活体巨岩（Living Megalith）的核心：唯一的招式循环持有者。双臂只投射本模型的下一招；
/// 打断、苏醒与转阶段都不会推进三套独立时钟。
/// Crystal Vein (晶脉) is the encounter's visible countdown: every completed cycle move adds one,
/// four stacks replace the next move with Crystal Burst. Fissure (崩落裂痕) rewards burst damage
/// during an exposure window by cancelling that window's recovery growth.
/// </summary>
public sealed class ThingsCaveGodBody : MonsterModel
{
    public const string KaiserMusicTrack = "kaiser_crab_progress";
    // Move ids double as localization keys: THINGS_CAVE_GOD_BODY.moves.<id>.title.
    public const string JabsId = "ALTERNATING_JABS", SweepId = "P1_REST_SWEEP", SlamId = "CENTRAL_SLAM", GuardId = "MOUNTAIN_GUARD";
    public const string CrushId = "DOUBLE_FIST_CRUSH", GrabId = "P2_REST_GRAB", AirSlamId = "P2_REST_SLAM", AngrySlamId = "P2_CENTRAL_SLAM";
    public const string BurstId = "CRYSTAL_BURST";
    public const string Exposed1Id = "WEAK_PRONE_1", Exposed2Id = "WEAK_PRONE_2", RecoverId = "WEAK_UNKNOWN_3", FissureRecoverId = "FISSURE_RECOVER";
    public const string TransitionId = "STUNNED";
    public const int VeinThreshold = 4;
    public const int VeinLossOnArmBreak = 2;
    public const int ShardCount = 2;
    public const decimal FissureFraction = 0.25m;
    public int Phase { get; private set; } = 1;
    public bool IsWeakPhase { get; private set; }
    public bool IsLeftArmBroken { get; private set; }
    public bool IsPhaseTransitionPending { get; private set; }
    public bool IsDefeated { get; private set; }
    /// <summary>Authoritative Crystal Vein stacks. Arms mirror it because the core's power row hides while it is buried.</summary>
    public int CrystalVein { get; private set; }
    public bool IsFissureBroken { get; private set; }
    public int FissureThreshold => (int)Math.Ceiling(Creature.MaxHp * FissureFraction);
    private bool VeinReady => CrystalVein >= VeinThreshold;
    private Dictionary<string, string> _cycleNext = [];
    private string _resumeMove = JabsId;
    private bool _deferExposure;
    private bool _rightLeads;
    private bool _releasingCaptives;
    private bool _applyingGrowth;
    public ThingsCaveGodLeftHand? LeftHand => CombatState?.Enemies.Select(c => c.Monster).OfType<ThingsCaveGodLeftHand>().FirstOrDefault();
    public ThingsCaveGodRightHand? RightHand => CombatState?.Enemies.Select(c => c.Monster).OfType<ThingsCaveGodRightHand>().FirstOrDefault();
    private IEnumerable<ThingsCaveGodHand> Hands => CombatState?.Enemies.Select(c => c.Monster).OfType<ThingsCaveGodHand>() ?? [];
    // The left arm remains in combat even when down, so its native Power Amount
    // is the shared state. The other arm mirrors it; no private timer is needed.
    public int AgingCountdown =>
        LeftHand?.Creature.GetPower<ThingsCaveGodAgingPower>()?.Amount ??
        RightHand?.Creature.GetPower<ThingsCaveGodAgingPower>()?.Amount ?? ThingsCaveGodAgingPower.ResetAmount;
    public NCaveGodBossBackground? Background => (NCombatRoom.Instance?.Background ?? NBestiary.Instance?.Layout)?.GetNodeOrNull<NCaveGodBossBackground>("%CaveGod");
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_knockout";
    protected override string VisualsPath => "res://scenes/creature_visuals/things_cave_god.tscn";
    public override bool ShouldFadeAfterDeath => false;
    public override bool ShouldDisappearFromDoom => false;
    public override float DeathAnimLengthOverride => 7.20f;
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 140, 130);
    public override int MaxInitialHp => MinInitialHp;
    public override bool IsHealthBarVisible => IsWeakPhase;
    public override bool ShouldAllowHitting(Creature creature) => creature != Creature || _applyingGrowth || CoreIsExposed;
    public override bool ShouldAllowTargeting(Creature target) => target != Creature || CoreIsExposed;
    private bool CoreIsExposed => IsWeakPhase && !IsPhaseTransitionPending && !IsDefeated;

#if STS2_V107_1
    public override decimal ModifyDamageMultiplicative(Creature? target, decimal amount, ValueProp props,
        Creature? dealer, CardModel? cardSource)
#else
    public override decimal ModifyDamageMultiplicative(Creature? target, decimal amount, ValueProp props,
        Creature? dealer, CardModel? cardSource, MegaCrit.Sts2.Core.Entities.Cards.CardPlay? cardPlay)
#endif
        => target == Creature && !CoreIsExposed ? 0m : 1m;
    private int JabDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 5, 4);
    private int SlamDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 18, 16);
    private int GuardDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 10, 9);
    private int GuardBlock => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 14, 12);
    private int CrushDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 10, 9);
    private int AngrySlamDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 22, 19);
    private int BurstDamage => Phase == 1
        ? AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 14, 12)
        : AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 17, 15);
    private int StrengthGain => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 3, 2);
    private bool CanAttack => !IsWeakPhase && !IsPhaseTransitionPending && !IsDefeated && Creature.IsAlive;

    // ToMutable() is a MemberwiseClone; give each combat instance its own lookup table.
    protected override void DeepCloneFields()
    {
        base.DeepCloneFields();
        _cycleNext = [];
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        MoveState[] normal =
        [
            new(JabsId, Cycle(JabsId, JabsMove), new MultiAttackIntent(JabDamage, 3)),
            new(SweepId, Cycle(SweepId, RestMove)),
            new(SlamId, Cycle(SlamId, SlamMove), new SingleAttackIntent(SlamDamage)),
            new(GuardId, Cycle(GuardId, GuardMove), new SingleAttackIntent(GuardDamage), new DefendIntent()),
            new(CrushId, Cycle(CrushId, CrushMove), new MultiAttackIntent(CrushDamage, 2), new DebuffIntent()),
            new(GrabId, Cycle(GrabId, RestMove)),
            new(AirSlamId, Cycle(AirSlamId, RestMove)),
            new(AngrySlamId, Cycle(AngrySlamId, AngrySlamMove), new SingleAttackIntent(AngrySlamDamage))
        ];
        MoveState burst = new(BurstId, BurstMove, new SingleAttackIntent(() => BurstDamage), new StatusIntent(ShardCount), new BuffIntent());
        ConditionalBranchState resume = new("RESUME_CYCLE");
        foreach (MoveState state in normal) resume.AddState(state, () => _resumeMove == state.Id);
        burst.FollowUpState = resume;
        List<MonsterState> states = [.. normal, burst, resume];
        for (int i = 0; i < normal.Length; i++)
        {
            // Same fixed four-move loop as before; a full vein inserts Crystal Burst in front of the next slot.
            MoveState next = normal[i / 4 * 4 + (i + 1) % 4];
            _cycleNext[normal[i].Id] = next.Id;
            ConditionalBranchState veinCheck = new($"VEIN_AFTER_{normal[i].Id}");
            veinCheck.AddState(burst, () => VeinReady);
            veinCheck.AddState(next, () => true);
            normal[i].FollowUpState = veinCheck;
            states.Add(veinCheck);
        }
        MoveState weak1 = new(Exposed1Id, RestMove), weak2 = new(Exposed2Id, RestMove);
        MoveState recover = new(RecoverId, RecoverMove, new HealIntent(), new BuffIntent());
        MoveState fissureRecover = new(FissureRecoverId, FissureRecoverMove, new HealIntent());
        MoveState transition = new(TransitionId, TransitionMove, new StunIntent(), new HealIntent());
        ConditionalBranchState recoverCheck = new("RECOVER_BRANCH");
        recoverCheck.AddState(fissureRecover, () => IsFissureBroken);
        recoverCheck.AddState(recover, () => true);
        weak1.FollowUpState = weak2;
        weak2.FollowUpState = recoverCheck;
        recover.FollowUpState = resume;
        fissureRecover.FollowUpState = resume;
        transition.FollowUpState = normal[4];
        states.AddRange([weak1, weak2, recover, fissureRecover, transition, recoverCheck]);
        foreach (MoveState state in new[] { weak1, weak2, recover, fissureRecover, transition }) state.MustPerformOnceBeforeTransitioning = true;
        return new MonsterMoveStateMachine(states, normal[0]);
    }

    /// <summary>Wraps a cycle move: a move that resolves outside exposure/transition feeds the vein.</summary>
    private Func<IReadOnlyList<Creature>, Task> Cycle(string id, Func<IReadOnlyList<Creature>, Task> perform) => async targets =>
    {
        await perform(targets);
        if (!CanAttack) return;
        await SetCrystalVein(CrystalVein + 1);
        if (VeinReady) _resumeMove = _cycleNext[id];
    };

    private async Task SetCrystalVein(int value)
    {
        CrystalVein = Math.Clamp(value, 0, VeinThreshold);
        foreach (ThingsCaveGodHand hand in Hands.Where(h => h.Creature.IsAlive).ToList())
            await hand.MirrorCrystalVein(CrystalVein, Creature);
    }

    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        Background?.AlignStageAndPlayers();
        STS2_Things.Audio.ModMusicPolicy.UpdateParameter(KaiserMusicTrack, 1f);
        NCombatRoom.Instance?.GetCreatureNode(Creature)?.ToggleIsInteractable(false);
    }

    public override async Task BeforeSideTurnStart(PlayerChoiceContext choiceContext, CombatSide side, IReadOnlyList<Creature> participants, ICombatState combatState)
    {
        if (side == CombatSide.Enemy && Hands.Any(h => h.IsGrabbing && h.NextMove.Intents.Any(i => i is StunIntent)))
            await ReleaseCaptives(stun: false);
        if (side == CombatSide.Player && !IsDefeated)
        {
            // Retaliation may expose the core during the enemy turn; still grant three player windows.
            if (_deferExposure && IsWeakPhase && !IsPhaseTransitionPending)
            {
                _deferExposure = false;
                SetMoveImmediate(Move(Exposed1Id), forceTransition: true);
                ProjectHandIntents();
            }
        }
    }

    public override Task AfterSideTurnStart(CombatSide side, IReadOnlyList<Creature> participants, ICombatState combatState)
    {
        if (side == CombatSide.Player && !IsDefeated)
        {
            ProjectHandIntents();
        }
        return Task.CompletedTask;
    }


    private MoveState Move(string id) => (MoveState)MoveStateMachine!.States[id];

    internal async Task AdvanceAgingCountdown(ThingsCaveGodAgingPower source)
    {
        if (IsDefeated || IsPhaseTransitionPending) return;
        var hands = Hands.ToArray();
        foreach (var hand in hands) await hand.EnsureAgingPower();
        int remaining = Math.Max(1, AgingCountdown) - 1;
        int next = remaining == 0 ? ThingsCaveGodAgingPower.ResetAmount : remaining;
        // Commit both counters before yielding to card-generation hooks. A second
        // arm knocked down by the same AoE must advance this one shared sequence.
        foreach (var hand in hands)
            if (hand.Creature.GetPower<ThingsCaveGodAgingPower>() is { } aging)
                aging.SetCountdown(next);
        if (remaining == 0) await source.GiveStoneArmor();
    }

    private void ProjectHandIntents()
    {
        ThingsCaveGodHand? lead = _rightLeads ? RightHand : LeftHand;
        lead ??= Hands.FirstOrDefault(h => !h.IsDown && h.Creature.IsAlive);
        foreach (ThingsCaveGodHand hand in Hands)
        {
            ThingsCaveGodHand.Action action = ThingsCaveGodHand.Action.Rest;
            if (IsPhaseTransitionPending || IsDefeated) action = ThingsCaveGodHand.Action.Down;
            else if (IsWeakPhase) action = NextMove.Id == Exposed1Id ? ThingsCaveGodHand.Action.WeakStun : ThingsCaveGodHand.Action.WeakAttack;
            else if (NextMove.Id == SweepId && hand == lead) action = ThingsCaveGodHand.Action.Sweep;
            else if (NextMove.Id == GrabId && hand == lead) action = ThingsCaveGodHand.Action.Grab;
            else if (NextMove.Id == AirSlamId && hand.IsGrabbing) action = ThingsCaveGodHand.Action.Slam;
            hand.Plan(action);
        }
    }

    internal async Task ExposeCore(ThingsCaveGodHand broken)
    {
        if (IsWeakPhase || IsPhaseTransitionPending || IsDefeated) return;
        // A pending Crystal Burst already stored the slot after it; breaking an arm cancels the burst.
        if (NextMove.Id != BurstId)
            _resumeMove = NextMove.Id == TransitionId ? NextMove.FollowUpStateId ?? (Phase == 1 ? JabsId : CrushId) : NextMove.Id;
        // Cancelled capture cannot resume at AIR_SLAM without captives.
        if (_resumeMove == AirSlamId) _resumeMove = AngrySlamId;
        IsWeakPhase = true;
        IsFissureBroken = false;
        IsLeftArmBroken = broken.IsLeft;
        _deferExposure = CombatState?.CurrentSide == CombatSide.Enemy;
        SetMoveImmediate(Move(Exposed1Id), forceTransition: true);
        ProjectHandIntents();
        await ReleaseCaptives(stun: false);
        await SetCrystalVein(CrystalVein - VeinLossOnArmBreak);
        if (Phase == 1 && !Creature.HasPower<ThingsCaveGodAncientCorePower>())
            await PowerCmd.Apply<ThingsCaveGodAncientCorePower>(new ThrowingPlayerChoiceContext(), Creature, 1m, Creature, null);
        if (!Creature.HasPower<ThingsCaveGodFissurePower>())
            await PowerCmd.Apply<ThingsCaveGodFissurePower>(new ThrowingPlayerChoiceContext(), Creature, FissureThreshold, Creature, null);
        NCombatRoom.Instance?.GetCreatureNode(Creature)?.ToggleIsInteractable(true);
        if (Background != null) await Background.PlayWeakEnterAnim(IsLeftArmBroken);
    }

    private Task RecoverMove(IReadOnlyList<Creature> _) => Awaken(fractured: false);
    private Task FissureRecoverMove(IReadOnlyList<Creature> _) => Awaken(fractured: true);

    private async Task Awaken(bool fractured)
    {
        if (!IsWeakPhase || IsPhaseTransitionPending || IsDefeated) return;
        // Core is last in slot order: finish both arm actions before restoring either arm.
        IsWeakPhase = false;
        IsFissureBroken = false;
        NCombatRoom.Instance?.GetCreatureNode(Creature)?.ToggleIsInteractable(false);
        await PowerCmd.Remove<ThingsCaveGodAncientCorePower>(Creature);
        await PowerCmd.Remove<ThingsCaveGodFissurePower>(Creature);
        if (Background != null) await Background.PlayWeakRecoverAnim(IsLeftArmBroken);
        foreach (ThingsCaveGodHand hand in Hands.ToList()) await hand.Restore();
        if (fractured)
        {
            // Fissure paid off: the shattered core wakes without growth and its vein drains.
            await SetCrystalVein(0);
            return;
        }
        // Repeated arm breaks must not freeze the boss at its initial strength forever.
        await Grow();
    }

    /// <summary>
    /// Fissure (崩落裂痕): damage dealt to the exposed core counts down the power; reaching zero
    /// swaps the advertised recovery for a growth-free one immediately, so the reward is visible.
    /// </summary>
    private async Task TrackFissure(decimal delta)
    {
        if (!CoreIsExposed || IsFissureBroken || Creature.GetPower<ThingsCaveGodFissurePower>() is not { } fissure) return;
        int dealt = (int)Math.Ceiling(-delta);
        if (dealt < fissure.Amount)
        {
            await PowerCmd.ModifyAmount(new ThrowingPlayerChoiceContext(), fissure, -dealt, Creature, null);
            return;
        }
        IsFissureBroken = true;
        await PowerCmd.Remove(fissure);
        Background?.PlayFissureBreak();
        if (NextMove.Id == RecoverId) SetMoveImmediate(Move(FissureRecoverId), forceTransition: true);
    }

    public override bool ShouldStopCombatFromEnding() => !IsDefeated && (Phase == 1 || IsPhaseTransitionPending);
    public override bool ShouldDie(Creature creature) => creature != Creature || Phase != 1 || IsDefeated;
    public override async Task AfterPreventingDeath(Creature creature)
    {
        if (creature != Creature || Phase != 1 || IsPhaseTransitionPending) return;
        IsPhaseTransitionPending = true;
        _deferExposure = false;
        foreach (ThingsCaveGodHand hand in Hands)
        {
            hand.Disable();
            if (hand.Creature.GetPower<StrengthPower>() is { } strength && strength.Amount != 0)
                await PowerCmd.Remove(strength);
        }
        SetMoveImmediate(Move(TransitionId), forceTransition: true);
        IsFissureBroken = false;
        await PowerCmd.Remove<ThingsCaveGodFissurePower>(Creature);
        await SetCrystalVein(0);
        await CreatureCmd.Heal(Creature, 1m, playAnim: false);
        await ThingsCaveGodHand.ClearDebuffs(Creature);
        await ReleaseCaptives(stun: false);
        NCombatRoom.Instance?.GetCreatureNode(Creature)?.ToggleIsInteractable(false);
    }

    private async Task TransitionMove(IReadOnlyList<Creature> _)
    {
        if (!IsPhaseTransitionPending || IsDefeated || CombatState == null) return;
        await ReleaseCaptives(stun: false);
        if (Background != null)
        {
            await Background.PlayWeakRecoverAnim(IsLeftArmBroken);
            await Background.PlayPhaseTransitionAnim();
        }
        Phase = 2;
        IsWeakPhase = false;
        _resumeMove = CrushId;
        int coreHp = AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 215, 200);
        int armHp = AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 90, 80);
        decimal Scale(int hp) => Creature.ScaleHpForMultiplayer(hp, CombatState.Encounter, CombatState.Players.Count, CombatState.RunState.CurrentActIndex);
        await CreatureCmd.SetMaxAndCurrentHp(Creature, Scale(coreHp));
        await PowerCmd.Remove<ThingsCaveGodAncientCorePower>(Creature);
        foreach (ThingsCaveGodHand hand in Hands.ToList())
        {
            await ThingsCaveGodHand.ClearDebuffs(hand.Creature);
            if (hand.Creature.GetPower<StrengthPower>() is { } strength && strength.Amount != 0)
                await PowerCmd.Remove(strength);
            await CreatureCmd.SetMaxAndCurrentHp(hand.Creature, Scale(armHp));
            await hand.Restore();
        }
        IsPhaseTransitionPending = false;
        STS2_Things.Audio.ModMusicPolicy.UpdateParameter(KaiserMusicTrack, 3f);
    }

    internal async Task ReleaseCaptives(bool stun, bool slam = false)
    {
        if (_releasingCaptives) return;
        _releasingCaptives = true;
        try
        {
            foreach (ThingsCaveGodHand hand in Hands) if (hand.IsGrabbing) hand.CancelGrab(stun);
            if (CombatState != null)
            {
                foreach (Creature captive in CombatState.Enemies.Where(c => c.Monster is ThingsCaveGodCaptiveClaw && c.IsAlive).ToList())
                {
                    ((ThingsCaveGodCaptiveClaw)captive.Monster!).IsSlamResolved = true;
                    await CreatureCmd.Kill(captive, force: true);
                }
                foreach (Creature player in CombatState.PlayerCreatures)
                {
                    await PowerCmd.Remove<CaveGodPendingTrialPower>(player);
                    await PowerCmd.Remove<CaveGodBrokenBladePower>(player);
                    await PowerCmd.Remove<CaveGodShatteredShieldPower>(player);
                    await PowerCmd.Remove<CaveGodMartialPower>(player);
                    await PowerCmd.Remove<CaveGodArcanePower>(player);
                }
            }
            if (Background != null && Background.HasCapturedPlayers) await Background.DropPlayersToGround(isSlam: slam);
        }
        finally { _releasingCaptives = false; }
    }

    public override async Task AfterDeath(PlayerChoiceContext choiceContext, Creature creature, bool wasRemovalPrevented, float deathAnimLength)
    {
        if (creature != Creature || wasRemovalPrevented || IsDefeated) return;
        IsDefeated = true;
        foreach (ThingsCaveGodHand hand in Hands) hand.Disable();
        await ReleaseCaptives(stun: false);
        foreach (ThingsCaveGodHand hand in Hands) await hand.ReleaseStolenCards();
        Background?.PlayBodyDeathAnim();
        STS2_Things.Audio.ModMusicPolicy.UpdateParameter(KaiserMusicTrack, 5f);
        foreach (ThingsCaveGodHand hand in Hands.ToList()) if (hand.Creature.IsAlive) await CreatureCmd.Kill(hand.Creature, force: true);
    }

    public override async Task AfterCurrentHpChanged(Creature creature, decimal delta)
    {
        if (creature != Creature || delta >= 0 || IsDefeated) return;
        Background?.PlayHurtAnim(forceGroan: true, hitPos: creature.GetCreatureNode()?.VfxSpawnPosition);
        await TrackFissure(delta);
    }
    public override async Task AfterCombatEnd(CombatRoom room)
    {
        Background?.RestoreCapturedPlayersInstantly();
        Background?.ClearAllStolenCards();
        foreach (ThingsCaveGodHand hand in Hands) await hand.ReleaseStolenCards();
    }
    public override void BeforeRemovedFromRoom()
    {
        Background?.RestoreCapturedPlayersInstantly();
        Background?.ClearAllStolenCards();
    }
    private static Task RestMove(IReadOnlyList<Creature> _) => Task.CompletedTask;

    private async Task JabsMove(IReadOnlyList<Creature> _)
    {
        if (!CanAttack) return;
        Background?.StartAttackAnim("alternating_jabs");
        float previous = 0f;
        foreach (float hit in new[] { CaveGodAnimTiming.JabsHit1, CaveGodAnimTiming.JabsHit2, CaveGodAnimTiming.JabsHit3 })
        {
            if (Background is { } background)
                await background.WaitForAttackFrame("alternating_jabs", hit, hit - previous);
            else
                await Cmd.Wait(hit - previous);
            previous = hit;
            if (!CanAttack) return;
            await DamageCmd.Attack(JabDamage).FromMonster(this).WithNoAttackerAnim().WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_kick").Execute(null);
        }
        await Cmd.Wait(CaveGodAnimTiming.ImpactSettle);
    }
    private Task SlamMove(IReadOnlyList<Creature> _) => CentralSlam(SlamDamage);
    private async Task CentralSlam(int damage)
    {
        if (!CanAttack) return;
        Background?.StartAttackAnim("central_slam");
        if (Background is { } background)
            await background.WaitForAttackFrame("central_slam", CaveGodAnimTiming.CentralSlamHit, CaveGodAnimTiming.CentralSlamHit);
        else await Cmd.Wait(CaveGodAnimTiming.CentralSlamHit);
        if (!CanAttack) return;
        await DamageCmd.Attack(damage).FromMonster(this).WithHitFx("vfx/vfx_heavy_blunt", "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_stomp").Execute(null);
        await Cmd.Wait(CaveGodAnimTiming.ImpactSettle);
    }
    private async Task GuardMove(IReadOnlyList<Creature> _)
    {
        if (!CanAttack) return;
        Background?.StartAttackAnim("double_fist_crush");
        if (Background is { } background)
            await background.WaitForAttackFrame("double_fist_crush", CaveGodAnimTiming.DoubleFistCrushHit, CaveGodAnimTiming.DoubleFistCrushHit);
        else await Cmd.Wait(CaveGodAnimTiming.DoubleFistCrushHit);
        if (!CanAttack) return;
        await DamageCmd.Attack(GuardDamage).FromMonster(this).WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_stomp").Execute(null);
        if (!CanAttack) return;
        foreach (ThingsCaveGodHand hand in Hands.Where(h => !h.IsDown && h.Creature.IsAlive))
            await CreatureCmd.GainBlock(hand.Creature, GuardBlock, ValueProp.Move, null);
        // Growth moved to Crystal Burst; the cycle end still hands the lead to the other arm.
        _rightLeads = !_rightLeads;
        await Cmd.Wait(CaveGodAnimTiming.ImpactSettle);
    }
    private async Task CrushMove(IReadOnlyList<Creature> targets)
    {
        if (!CanAttack) return;
        Background?.StartAttackAnim("double_fist_crush");
        if (Background is { } background)
            await background.WaitForAttackFrame("double_fist_crush", CaveGodAnimTiming.DoubleFistCrushHit, CaveGodAnimTiming.DoubleFistCrushHit);
        else await Cmd.Wait(CaveGodAnimTiming.DoubleFistCrushHit);
        for (int i = 0; i < 2; i++)
        {
            if (!CanAttack) return;
            await DamageCmd.Attack(CrushDamage).FromMonster(this).WithHitFx("vfx/vfx_heavy_blunt", "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_stomp").Execute(null);
            if (i == 0) await Cmd.Wait(0.20f);
        }
        if (CanAttack) await PowerCmd.Apply<WeakPower>(new ThrowingPlayerChoiceContext(), targets.Where(c => c.IsAlive), 2m, Creature, null);
        await Cmd.Wait(1.85f);
    }
    private async Task AngrySlamMove(IReadOnlyList<Creature> _)
    {
        await CentralSlam(AngrySlamDamage);
        if (CanAttack) _rightLeads = !_rightLeads;
    }

    /// <summary>
    /// 晶簇崩发：the vein discharges through the arena. Hits everyone, seeds Crystal Shards,
    /// then the megalith grows. Reuses central_slam timing until a dedicated clip exists.
    /// </summary>
    private async Task BurstMove(IReadOnlyList<Creature> targets)
    {
        if (!CanAttack) return;
        Background?.StartCrystalBurstAnim();
        if (Background is { } background)
            await background.WaitForAttackFrame("central_slam", CaveGodAnimTiming.CentralSlamHit, CaveGodAnimTiming.CentralSlamHit);
        else await Cmd.Wait(CaveGodAnimTiming.CentralSlamHit);
        if (!CanAttack) return;
        Background?.PlayCrystalBurstImpact();
        await DamageCmd.Attack(BurstDamage).FromMonster(this).WithHitFx("vfx/vfx_heavy_blunt", "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_eruption").Execute(null);
        if (!CanAttack) return;
        await CardPileCmd.AddToCombatAndPreview<ThingsCaveGodCrystalShard>(targets.Where(c => c.IsAlive && c.Player != null), PileType.Discard, ShardCount, null);
        await SetCrystalVein(0);
        await Grow();
        await Cmd.Wait(CaveGodAnimTiming.ImpactSettle);
    }

    private async Task Grow()
    {
        // Knowledge Demon / Kaiser Crab tier: +2 (DeadlyEnemies +3) per Crystal Burst or full recovery.
        // Native CanReceivePowers uses ShouldAllowHitting. Open only the self-buff scope;
        // targeting and damage protection remain in force throughout the command/hooks.
        _applyingGrowth = true;
        try
        {
            await PowerCmd.Apply<StrengthPower>(new ThrowingPlayerChoiceContext(), Creature, StrengthGain, Creature, null);
        }
        finally { _applyingGrowth = false; }
        foreach (ThingsCaveGodHand hand in Hands.Where(h => h.Creature.IsAlive))
            await hand.GainStrength(StrengthGain, Creature);
    }
}
