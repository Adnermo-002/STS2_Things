using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Powers;
using STS2_Things.Visuals;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Monsters;

/// <summary>
///     放缩巨甲虫 — Overgrowth Boss
///     开局: 重构化（玩家 ScaleDown×1 + 自身 ScaleUp×1）+ 常驻 ThingsScaleBeetlePower
///     循环: 撕咬 → 触角鞭打 → 蜕壳 → 循环
///     ThingsScaleBeetlePower: 对玩家造成未被抵挡的伤害时，该玩家获得5层缩小
/// </summary>
public sealed class ThingsScaleBeetle : ThingsSpineMonster
{
    // 对应CustomBgm "act1_boss_vantom" 的FMOD参数
    private const string _trackName = "vantom_progress";
    private const int MoltBlock = 14;
    public const float BiteContact = 0.68f;
    public const float ReconstructRelease = 0.76f;
    public const float MoltRelease = 0.80f;
    public static readonly float[] WhipContacts = [0.60f, 1.12f, 1.68f];

    // Match the creature's beetle body and scale-changing cast to its vanilla kin.
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/shrinker_beetle/shrinker_beetle_attack";
    protected override string CastSfx => "event:/sfx/enemy/enemy_attacks/shrinker_beetle/shrinker_beetle_cast";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/shrinker_beetle/shrinker_beetle_die";
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Insect;
    public override Vector2 ExtraDeathVfxPadding => new(2.3f, 2.1f);

    public override bool CanChangeScale => true;

    protected override void AddExtraAnimationStates(CreatureAnimator animator, AnimState idle)
    {
        animator.AddAnyState("Whip", new AnimState("whip") { NextState = idle });
        animator.AddAnyState("Molt", new AnimState("molt") { NextState = idle });
    }

    private async Task WaitForPose(string animation, float moment, float fallback)
    {
        var sprite = Creature.GetCreatureNode()?.Visuals?.SpineBody;
        float wait = fallback;
        using (TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? track))
            if (track != null && track.GetAnimationName() == animation)
                wait = Math.Max(0, moment - track.GetTrackTime());
        await Cmd.Wait(wait);
        // Instant mode still commits the authored contact before damage or powers.
        using var scope = TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? current);
        if (current != null && current.GetAnimationName() == animation && current.GetTrackTime() < moment)
        {
            current.SetMixDuration(0);
            current.SetTrackTime(moment);
            sprite!.BoundObject.Call("update_skeleton", 0f);
        }
    }

    private async Task BeginMotion(string trigger, string animation, float contact)
    {
        await CreatureCmd.TriggerAnim(Creature, trigger, 0f);
        await WaitForPose(animation, contact, contact);
    }

    private async Task FinishMotion(string animation)
    {
        var sprite = Creature.GetCreatureNode()?.Visuals?.SpineBody;
        float end;
        using (TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? track))
        {
            if (track == null || track.GetAnimationName() != animation) return;
            end = track.GetAnimationEnd();
        }
        await WaitForPose(animation, end, 0f);
    }

    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat(
    [
        ModelDb.Power<ThingsScaleBeetlePower>().ResolvedBigIconPath,
        ModelDb.Power<ThingsScaleUpPower>().ResolvedBigIconPath,
        ModelDb.Power<ThingsScaleDownPower>().ResolvedBigIconPath
    ]).Distinct();

    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        // 初始化专属音乐参数（CustomBgm = act1_boss_vantom）
        STS2_Things.Audio.ModMusicPolicy.UpdateParameter(_trackName, 1f);
        // 常驻buff：对玩家造成未被抵挡伤害时施加缩小
        await PowerCmd.Apply<ThingsScaleBeetlePower>(new ThrowingPlayerChoiceContext(), Creature, 1m, Creature, null);
    }

    public override Task AfterDeath(PlayerChoiceContext choiceContext, Creature creature,
        bool wasRemovalPrevented, float deathAnimLength)
    {
        if (creature == Creature)
        {
            // 死亡升调（vantom_progress=5 触发FMOD升调自动化）
            STS2_Things.Audio.ModMusicPolicy.UpdateParameter(_trackName, 5f);
        }
        return Task.CompletedTask;
    }

    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(
        AscensionLevel.ToughEnemies, 210, 200);

    public override int MaxInitialHp => MinInitialHp;

    private int BiteDamage => AscensionHelper.GetValueIfAscension(
        AscensionLevel.DeadlyEnemies, 14, 12);

    private int WhipDamage => AscensionHelper.GetValueIfAscension(
        AscensionLevel.DeadlyEnemies, 5, 4);

    // ========== 状态机 ==========

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        List<MonsterState> list = new();

        // 重构化: 开局仅一次
        var reconstructMove = new MoveState("RECONSTRUCT_MOVE", ReconstructMove,
            new DebuffIntent(), new BuffIntent());

        // 撕咬
        var biteMove = new MoveState("BITE_MOVE", BiteMove,
            new SingleAttackIntent(BiteDamage));

        // 触角鞭打 ×3
        var whipMove = new MoveState("WHIP_MOVE", WhipMove,
            new MultiAttackIntent(WhipDamage, 3));

        // 蜕壳: 14 防御 + ScaleUp 再叠 15 层
        var moltMove = new MoveState("MOLT_MOVE", MoltMove,
            new DefendIntent(), new BuffIntent());

        // 连线: 重构化(仅一次) → 撕咬 → 鞭打 → 蜕壳 → 撕咬...
        reconstructMove.FollowUpState = biteMove;
        biteMove.FollowUpState = whipMove;
        whipMove.FollowUpState = moltMove;
        moltMove.FollowUpState = biteMove;

        list.Add(reconstructMove);
        list.Add(biteMove);
        list.Add(whipMove);
        list.Add(moltMove);

        return new MonsterMoveStateMachine(list, reconstructMove);
    }

    // ========== 招式 ==========

    private async Task ReconstructMove(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await BeginMotion("Cast", "cast", ReconstructRelease);

        await PowerCmd.Apply<ThingsScaleDownPower>(new ThrowingPlayerChoiceContext(),
            targets, 15m, Creature, null);
        await PowerCmd.Apply<ThingsScaleUpPower>(new ThrowingPlayerChoiceContext(),
            Creature, 15m, Creature, null);
        await FinishMotion("cast");
    }

    private async Task BiteMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(BiteDamage)
            .FromMonster(this)
            .WithNoAttackerAnim()
            .AfterAttackerAnim(() => BeginMotion("Attack", "attack", BiteContact))
            .WithAttackerFx(null, AttackSfx)
            .Execute(null);
        await FinishMotion("attack");
    }

    private async Task WhipMove(IReadOnlyList<Creature> targets)
    {
        int strike = 0;
        var motion = Creature.GetCreatureNode()?.Visuals?.GetNodeOrNull<NThingsScaleBeetleMotion>("Visuals/MotionTiming");
        try
        {
            await DamageCmd.Attack(WhipDamage)
                .FromMonster(this)
                .WithHitCount(3)
                .WithNoAttackerAnim()
                .AfterAttackerAnim(async () =>
                {
                    int beat = strike++ % WhipContacts.Length;
                    if (beat == 0)
                    {
                        if (strike > 1)
                        {
                            motion?.FinishCombo();
                            await FinishMotion("whip");
                        }
                        await CreatureCmd.TriggerAnim(Creature, "Whip", 0f);
                    }
                    motion?.AllowBeat(beat + 1);
                    float previous = beat == 0 ? 0 : WhipContacts[beat - 1];
                    await WaitForPose("whip", WhipContacts[beat], WhipContacts[beat] - previous);
                })
                .WithAttackerFx(null, AttackSfx)
                .Execute(null);
        }
        finally
        {
            motion?.FinishCombo();
        }
        await FinishMotion("whip");
    }

    private async Task MoltMove(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await BeginMotion("Molt", "molt", MoltRelease);

        await CreatureCmd.GainBlock(Creature, MoltBlock, ValueProp.Move, null);
        await PowerCmd.Apply<ThingsScaleUpPower>(new ThrowingPlayerChoiceContext(),
            Creature, 15m, Creature, null);
        await FinishMotion("molt");
    }
}
