using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Audio;
using STS2_Things.Audio;
using STS2_Things.Powers;

namespace STS2_Things.Monsters;

/// <summary>
///     腐化之遗 — Underdocks Boss
///     开局: LegacyBeatOfDeathPower (玩家出牌扣2血) + HardenedShellPower (HP/3 层)
///     意图循环:
///     衰竭 → 回音 → 血弹 → 强化 → 循环
///     强化阶段:
///     第1次: 1层人工制品
///     第2次: 1层死亡律动 + 硬化外壳改成HP/4
///     第3次: 眩晕戳刺(ThingsDazedPower)
///     第4次: 2点力量 + 1层死亡律动
///     之后循环: n+1层人工制品 + 外壳HP/(n+1) + 2点力量 + 1层死亡律动
/// </summary>
public sealed class ThingsTheLegacy : MonsterModel
{
    // The encounter lives in Underdocks, so it uses an act1_b track that is
    // already loaded by the native Act music lifecycle.
    private const string _trackName = "waterfall_giant_progress";
    private const int BloodDamage = 3;

    private const int BloodCount = 4;

    // 复用Vantom（暗黑Boss）的原版音效
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/vantom/vantom_inky_lance";
    protected override string CastSfx => "event:/sfx/enemy/enemy_attacks/vantom/vantom_buff";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/vantom/vantom_die";
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Magic;
    public override Vector2 ExtraDeathVfxPadding => new(1.4f, 1.7f);

    private CancellationTokenSource? _heartbeatCts;

    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat(
    [
        ModelDb.Power<LegacyBeatOfDeathPower>().ResolvedBigIconPath,
        ModelDb.Power<ThingsDazedPower>().ResolvedBigIconPath,
        ModelDb.Power<HardenedShellPower>().ResolvedBigIconPath,
        ModelDb.Power<ArtifactPower>().ResolvedBigIconPath,
        ModelDb.Power<StrengthPower>().ResolvedBigIconPath
    ]).Distinct();

    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(
        AscensionLevel.ToughEnemies, 298, 285);

    public override int MaxInitialHp => MinInitialHp;

    private int EchoDamage => AscensionHelper.GetValueIfAscension(
        AscensionLevel.DeadlyEnemies, 13, 12);

    // ========== 入场 ==========
    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        // 初始化专属音乐参数（CustomBgm = act1_b_boss_waterfall_giant）
        NRunMusicController.Instance?.UpdateMusicParameter(_trackName, 1f);
        // 心跳循环：血量越低跳得越快
        _heartbeatCts = new CancellationTokenSource();
        _ = HeartbeatLoop(_heartbeatCts.Token);
        // 隐藏 Power 保存下一次强化阶段，使进度进入多人 checksum/full-state。
        await PowerCmd.Apply<LegacyProgressPower>(new ThrowingPlayerChoiceContext(), Creature, 1m, Creature, null);
        // 死亡律动: 玩家每出一张牌扣 2 血
        await PowerCmd.Apply<LegacyBeatOfDeathPower>(new ThrowingPlayerChoiceContext(), Creature, 2m, Creature, null);
        // 硬化外壳: 层数 = 最大 HP / 3
        // 注意：HardenedShellPower 的 ShouldScaleInMultiplayer=true，PowerCmd.Apply 会自动缩放。
        // 必须用缩放前的原始 HP（MonsterMaxHpBeforeModification）计算，否则会双重缩放导致层数超过 MaxHp。
        var baseHp = Creature.MonsterMaxHpBeforeModification ?? Creature.MaxHp;
        await PowerCmd.Apply<HardenedShellPower>(new ThrowingPlayerChoiceContext(), Creature,
            baseHp / 3m, Creature, null);
    }

    // ========== 状态机 ==========
    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        List<MonsterState> list = new();

        // 衰竭: 给玩家 Burn + Dazed + Slimed 各一张
        var exhaustMove = new MoveState("EXHAUST_MOVE", ExhaustMove,
            new StatusIntent(6));

        // 回音: 12/14 伤害
        var echoMove = new MoveState("ECHO_MOVE", EchoMove,
            new SingleAttackIntent(EchoDamage));

        // 血弹: 3×4
        var bloodMove = new MoveState("BLOOD_MOVE", BloodMove,
            new MultiAttackIntent(BloodDamage, BloodCount));

        // 强化: 根据次数递增
        var strengthenMove = new MoveState("STRENGTHEN_MOVE", StrengthenMove,
            new BuffIntent());

        // 固定循环: 衰竭(仅开局) → 回音 → 血弹 → 强化 → 回音 → 血弹 → 强化 → ...
        exhaustMove.FollowUpState = echoMove;
        echoMove.FollowUpState = bloodMove;
        bloodMove.FollowUpState = strengthenMove;
        strengthenMove.FollowUpState = echoMove;

        list.Add(exhaustMove);
        list.Add(echoMove);
        list.Add(bloodMove);
        list.Add(strengthenMove);

        return new MonsterMoveStateMachine(list, exhaustMove);
    }

    // ========== 招式 ==========

    private async Task ExhaustMove(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await CreatureCmd.TriggerAnim(Creature, "Cast", 0.5f);

        await CardPileCmd.AddToCombatAndPreview<Burn>(targets, PileType.Discard, 2, null);
        await CardPileCmd.AddToCombatAndPreview<Dazed>(targets, PileType.Discard, 2, null);
        await CardPileCmd.AddToCombatAndPreview<Slimed>(targets, PileType.Discard, 2, null);
    }

    private async Task EchoMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(EchoDamage)
            .FromMonster(this)
            .WithAttackerAnim("Attack", 0.5f)
            .WithAttackerFx(null, AttackSfx)
            .Execute(null);
    }

    private async Task BloodMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(BloodDamage)
            .FromMonster(this)
            .WithHitCount(BloodCount)
            .WithAttackerAnim("Attack", 0.5f)
            .WithAttackerFx(null, AttackSfx)
            .Execute(null);
    }

    private async Task StrengthenMove(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await CreatureCmd.TriggerAnim(Creature, "Cast", 0.5f);

        var progress = Creature.GetPower<LegacyProgressPower>()
            ?? throw new InvalidOperationException("Legacy progress power is missing.");
        int strengthenStage = progress.NextStage;

        switch (strengthenStage)
        {
            case 1:
                // 第1次强化：1层人工制品
                await PowerCmd.Apply<ArtifactPower>(new ThrowingPlayerChoiceContext(), Creature, 1m, Creature, null);
                break;
            case 2:
                // 第2次强化：1层死亡律动 + 硬化外壳改成HP/4
                await PowerCmd.Apply<LegacyBeatOfDeathPower>(new ThrowingPlayerChoiceContext(), Creature, 1m, Creature, null);
                await SetShellDivisor(4);
                break;
            case 3:
                // 第3次强化：眩晕戳刺(ThingsDazedPower)
                await PowerCmd.Apply<ThingsDazedPower>(new ThrowingPlayerChoiceContext(), Creature, 1m, Creature, null);
                break;
            case 4:
                // 第4次强化：2点力量 + 1层死亡律动
                await PowerCmd.Apply<StrengthPower>(new ThrowingPlayerChoiceContext(), Creature, 2m, Creature, null);
                await PowerCmd.Apply<LegacyBeatOfDeathPower>(new ThrowingPlayerChoiceContext(), Creature, 1m, Creature, null);
                break;
            default:
                // 之后循环：第1次循环=2层人工制品+HP/5, 第2次=3层+HP/6, ...
                var n = strengthenStage - 4;
                // 先施死亡律动再施人工制品，避免人工制品抵消死亡律动
                await PowerCmd.Apply<LegacyBeatOfDeathPower>(new ThrowingPlayerChoiceContext(), Creature, 1m, Creature, null);
                await PowerCmd.Apply<ArtifactPower>(new ThrowingPlayerChoiceContext(), Creature, n + 1m, Creature, null);
                await SetShellDivisor(n + 4);
                await PowerCmd.Apply<StrengthPower>(new ThrowingPlayerChoiceContext(), Creature, 2m, Creature, null);
                break;
        }

        progress.Advance();
    }

    private async Task SetShellDivisor(int divisor)
    {
        var shell = Creature.Powers.OfType<HardenedShellPower>().FirstOrDefault();
        if (shell != null)
        {
            // PowerCmd.ModifyAmount truncates decimal offsets. Compute the desired
            // shell as an integer first so every divisor reaches the exact floor.
            var target = Creature.MaxHp / divisor;
            await PowerCmd.ModifyAmount(new ThrowingPlayerChoiceContext(), shell,
                target - shell.Amount, Creature, null);
        }
    }

    // ========== 死亡升调 ==========
    public override Task AfterDeath(PlayerChoiceContext choiceContext, Creature creature,
        bool wasRemovalPrevented, float deathAnimLength)
    {
        if (creature == Creature)
        {
            StopHeartbeat();
            // 死亡升调（vantom_progress=5 触发FMOD升调自动化）
            NRunMusicController.Instance?.UpdateMusicParameter(_trackName, 5f);
        }
        return Task.CompletedTask;
    }

    public override void BeforeRemovedFromRoom()
    {
        StopHeartbeat();
    }

    private void StopHeartbeat()
    {
        _heartbeatCts?.Cancel();
        _heartbeatCts?.Dispose();
        _heartbeatCts = null;
    }

    // ========== 心跳循环（半血后加速） ==========

    private async Task HeartbeatLoop(CancellationToken ct)
    {
        var files = new[]
        {
            "res://sfx/the_legacy/HeartBeat_1.ogg",
            "res://sfx/the_legacy/HeartBeat_2.ogg"
        };
        var index = 0;

        try
        {
            while (!ct.IsCancellationRequested)
            {
                if (!Creature.IsAlive)
                    break;

                NativeSfxPlayer.Play(files[index], volumeDb: -10f);
                index = (index + 1) % files.Length;
                // 半血后心跳加速: 0.75s vs 正常 1.5s
                float delay = Creature.CurrentHp <= Creature.MaxHp / 2 ? 0.75f : 1.5f;
                await Task.Delay(TimeSpan.FromSeconds(delay), ct);
            }
        }
        catch (OperationCanceledException)
        {
            // 正常取消，忽略
        }
        catch (Exception e)
        {
            Log.Error($"[ThingsTheLegacy] HeartbeatLoop 异常: {e}");
        }
    }
}
