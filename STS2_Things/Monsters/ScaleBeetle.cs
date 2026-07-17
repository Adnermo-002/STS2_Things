using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Audio;
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

namespace STS2_Things.Monsters;

/// <summary>
///     放缩巨甲虫 — Overgrowth Boss
///     开局: 重构化（玩家 ScaleDown×1 + 自身 ScaleUp×1）+ 常驻 ScaleBeetlePower
///     循环: 撕咬 → 触角鞭打 → 蜕壳 → 循环
///     ScaleBeetlePower: 对玩家造成未被抵挡的伤害时，该玩家获得5层缩小
/// </summary>
public sealed class ScaleBeetle : MonsterModel
{
    // 对应CustomBgm "act1_boss_vantom" 的FMOD参数
    private const string _trackName = "vantom_progress";
    private const int MoltBlock = 14;

    // Match the creature's beetle body and scale-changing cast to its vanilla kin.
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/shrinker_beetle/shrinker_beetle_attack";
    protected override string CastSfx => "event:/sfx/enemy/enemy_attacks/shrinker_beetle/shrinker_beetle_cast";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/shrinker_beetle/shrinker_beetle_die";
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Insect;
    public override Vector2 ExtraDeathVfxPadding => new(2.3f, 2.1f);

    public override bool CanChangeScale => true;

    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat(
    [
        ModelDb.Power<ScaleBeetlePower>().ResolvedBigIconPath,
        ModelDb.Power<ScaleUpPower>().ResolvedBigIconPath,
        ModelDb.Power<ScaleDownPower>().ResolvedBigIconPath
    ]).Distinct();

    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        // 初始化专属音乐参数（CustomBgm = act1_boss_vantom）
        NRunMusicController.Instance?.UpdateMusicParameter(_trackName, 1f);
        // 常驻buff：对玩家造成未被抵挡伤害时施加缩小
        await PowerCmd.Apply<ScaleBeetlePower>(new ThrowingPlayerChoiceContext(), Creature, 1m, Creature, null);
    }

    public override Task AfterDeath(PlayerChoiceContext choiceContext, Creature creature,
        bool wasRemovalPrevented, float deathAnimLength)
    {
        if (creature == Creature)
        {
            // 死亡升调（vantom_progress=5 触发FMOD升调自动化）
            NRunMusicController.Instance?.UpdateMusicParameter(_trackName, 5f);
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
        await CreatureCmd.TriggerAnim(Creature, "Cast", 0.5f);

        await PowerCmd.Apply<ScaleDownPower>(new ThrowingPlayerChoiceContext(),
            targets, 15m, Creature, null);
        await PowerCmd.Apply<ScaleUpPower>(new ThrowingPlayerChoiceContext(),
            Creature, 15m, Creature, null);
    }

    private async Task BiteMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(BiteDamage)
            .FromMonster(this)
            .WithAttackerAnim("Attack", 0.5f)
            .WithAttackerFx(null, AttackSfx)
            .Execute(null);
    }

    private async Task WhipMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(WhipDamage)
            .FromMonster(this)
            .WithHitCount(3)
            .WithAttackerAnim("Attack", 0.5f)
            .WithAttackerFx(null, AttackSfx)
            .Execute(null);
    }

    private async Task MoltMove(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await CreatureCmd.TriggerAnim(Creature, "Cast", 0.5f);

        await CreatureCmd.GainBlock(Creature, MoltBlock, ValueProp.Move, null);
        await PowerCmd.Apply<ScaleUpPower>(new ThrowingPlayerChoiceContext(),
            Creature, 15m, Creature, null);
    }
}
