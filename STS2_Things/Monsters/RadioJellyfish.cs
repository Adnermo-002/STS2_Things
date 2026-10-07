using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Powers;
using STS2_Things.Visuals;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Monsters;

public sealed class RadioJellyfish : ThingsSpineMonster
{
    public const int BaseEchoDamage = 6;
    public const int BaseSkillBlock = 8;
    public const string TuneMoveId = "TUNE_MOVE";
    private Dictionary<(int Phase, int Program), MoveState>? _replays;
    private ConditionalBranchState[]? _selectors;
    public RadioProgram? ActiveProgram { get; private set; }
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 180, 160);
    public override int MaxInitialHp => MinInitialHp;
    public override float HpBarSizeReduction => 35f;
    // Reception adds 2 per stack to both the native intent and actual hit.
    // One opening stack gives 7/8 damage and 9/11 Block per Skill.
    public int EchoDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 7, BaseEchoDamage);
    public int ShieldPerSkill => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 10, BaseSkillBlock)
        + (Creature.GetPower<RadioReceptionPower>()?.ReplayBonus ?? 0);
    private int TuningBlock => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 16, 12);
    public bool IsTuningTurn => NextMove.StateId == TuneMoveId ||
        (NextMove.StateId == MonsterModel.stunnedMoveId &&
         (NextMove.FollowUpState?.Id ?? NextMove.FollowUpStateId) == TuneMoveId);
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Slime;
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/soul_fysh/soul_fysh_wave";
    protected override string CastSfx => "event:/sfx/enemy/enemy_attacks/soul_fysh/soul_fysh_intangible";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/obscura/obscura_die";
    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat([
        ModelDb.Power<RadioReceptionPower>().ResolvedBigIconPath,
        "res://images/vfx/radio_channel_0.png", "res://images/vfx/radio_channel_1.png"]);

    public override async Task BeforeCombatStart()
    {
        await PowerCmd.Apply<RadioReceptionStatePower>(new ThrowingPlayerChoiceContext(), Creature, 1, Creature, null);
        await PowerCmd.Apply<RadioReceptionPower>(new ThrowingPlayerChoiceContext(), Creature, 1, Creature, null);
    }

    protected override void AddExtraAnimationStates(CreatureAnimator animator, AnimState idle)
    {
        for (int first = 0; first < 4; first++)
            for (int second = 0; second < 4; second++)
                animator.AddAnyState($"Replay{first}{second}",
                    new AnimState($"playback_{first}_{second}") { NextState = idle });
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        // Allocate per instance: mutable monsters must never share a dictionary
        // copied from the canonical model during asset discovery.
        // Encode the two replay phases in native state IDs, so the cycle is
        // included in the game's multiplayer combat state without a local counter.
        var replays = new Dictionary<(int Phase, int Program), MoveState>();
        var selectors = new[] { new ConditionalBranchState("CHOOSE_REPLAY"),
            new ConditionalBranchState("CHOOSE_SECOND_REPLAY") };
        var tune = new MoveState(TuneMoveId, Tune, new BuffIntent(), new DefendIntent())
        {
            FollowUpState = selectors[0],
        };
        for (int phase = 0; phase < 2; phase++)
            for (int a = 0; a < 4; a++)
                for (int b = 0; b < 4; b++)
                {
                    int key = a | (b << 2);
                    int hits = 1 + ((a & 1) != 0 ? 1 : 0) + ((b & 1) != 0 ? 1 : 0);
                    var intents = new List<AbstractIntent>
                    {
                        hits == 1 ? new SingleAttackIntent(EchoDamage) : new MultiAttackIntent(EchoDamage, hits),
                    };
                    if (((a | b) & 2) != 0) intents.Add(new DefendIntent());
                    string id = phase == 0 ? $"REPLAY_{a}_{b}_MOVE" : $"REPLAY_SECOND_{a}_{b}_MOVE";
                    var move = new MoveState(id, Playback, intents.ToArray())
                    {
                        FollowUpState = phase == 0 ? selectors[1] : tune,
                    };
                    replays.Add((phase, key), move);
                    selectors[phase].AddState(move, () => CurrentProgram.Key == key);
                }
        _replays = replays;
        _selectors = selectors;
        ActiveProgram = null;
        return new MonsterMoveStateMachine([.. replays.Values, .. selectors, tune], replays[(0, 0)]);
    }

    public RadioProgram CurrentProgram => ActiveProgram ?? Creature.GetPower<RadioReceptionPower>()?.GetProgram() ?? default;

    private static int ReplayPhase(string? stateId) => stateId switch
    {
        "CHOOSE_REPLAY" or "UNSET_MOVE" => 0,
        "CHOOSE_SECOND_REPLAY" => 1,
        { } id when id.StartsWith("REPLAY_SECOND_", StringComparison.Ordinal) => 1,
        { } id when id.StartsWith("REPLAY_", StringComparison.Ordinal) => 0,
        _ => -1,
    };

    public void RefreshReplayState(RadioProgram program, bool refreshIntents = false)
    {
        if (_replays == null || _selectors == null || MoveStateMachine == null || !Creature.IsAlive || IsPerformingMove) return;
        if (NextMove.StateId == MonsterModel.stunnedMoveId)
        {
            // Preserve both the stun and its cycle phase, including a pending Tune.
            int resumePhase = ReplayPhase(NextMove.FollowUpState?.Id ?? NextMove.FollowUpStateId);
            if (resumePhase >= 0) NextMove.FollowUpState = _selectors[resumePhase];
            return;
        }
        int phase = ReplayPhase(NextMove.StateId);
        if (phase < 0) return;
        var desired = _replays[(phase, program.Key)];
        if (refreshIntents || !ReferenceEquals(NextMove, desired)) SetMoveImmediate(desired);
    }

    private async Task Tune(IReadOnlyList<Creature> targets)
    {
        await CreatureCmd.TriggerAnim(Creature, CreatureAnimator.powerUpTrigger, 0);
        await WaitForPose("power_up", .50f, .50f);
        if (!CanContinue) return;
        SfxCmd.Play(CastSfx);
        NRadioWaveVfx.Shield(Creature);
        await CreatureCmd.GainBlock(Creature, TuningBlock, ValueProp.Move, null);
        if (!CanContinue) return;
        await PowerCmd.Apply<RadioReceptionPower>(new ThrowingPlayerChoiceContext(), Creature, 1, Creature, null);
        await WaitForPose("power_up", 1.35f, .85f);
    }

    private async Task Playback(IReadOnlyList<Creature> targets)
    {
        var program = Creature.GetPower<RadioReceptionPower>()?.GetProgram() ?? default;
        ActiveProgram = program;
        string animation = $"playback_{program.First.Mask}_{program.Second.Mask}";
        try
        {
            Creature.GetPower<RadioReceptionPower>()?.ShowReplay();
            await CreatureCmd.TriggerAnim(Creature, $"Replay{program.First.Mask}{program.Second.Mask}", 0);
            for (int beat = 0; beat < 2; beat++)
            {
                await WaitForPose(animation, .50f + beat * .50f, .50f);
                if (!CanContinue) return;
                var channel = program.Channel(beat);
                if (channel.Skills > 0)
                {
                    SfxCmd.Play(CastSfx);
                    NRadioWaveVfx.Shield(Creature);
                    await CreatureCmd.GainBlock(Creature, ShieldPerSkill * channel.Skills, ValueProp.Move, null);
                }
                if (!CanContinue) return;
                if (channel.Attacks > 0) await Echo(false);
            }
            await WaitForPose(animation, 1.55f, .55f);
            if (!CanContinue) return;
            // A final pulse prevents two Skill openers from cancelling all damage.
            await Echo(true);
            if (!CanContinue) return;
            await WaitForPose(animation, 2.3f, 0);
        }
        finally
        {
            ActiveProgram = null;
            Creature.GetPower<RadioReceptionPower>()?.PlaybackFinished();
        }
    }

    private bool CanContinue => Creature.IsAlive && !CombatManager.Instance.IsOverOrEnding;

    private async Task Echo(bool finale)
    {
        NRadioWaveVfx.Attack(Creature, finale);
        await DamageCmd.Attack(EchoDamage).FromMonster(this).WithNoAttackerAnim()
            .WithAttackerFx(null, AttackSfx).WithHitFx("vfx/vfx_attack_blunt").Execute(null);
    }

    private async Task WaitForPose(string animation, float moment, float fallback)
    {
        var sprite = Creature.GetCreatureNode()?.Visuals?.SpineBody;
        float wait = fallback;
        using (TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? entry))
            if (entry != null && entry.GetAnimationName() == animation) wait = Math.Max(0, moment - entry.GetTrackTime());
        await Cmd.Wait(wait);
        using var scope = TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? current);
        if (current != null && current.GetAnimationName() == animation && current.GetTrackTime() < moment)
        {
            current.SetMixDuration(0);
            current.SetTrackTime(moment);
            sprite!.BoundObject.Call("update_skeleton", 0f);
        }
    }
}
