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
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Powers;

namespace STS2_Things.Monsters;

public sealed class OriginFogmog : MonsterModel
{
    public const string IllusionMoveId = "ILLUSION_MOVE";
    public const string SwipeMoveId = "SWIPE_MOVE";

    // 对应CustomBgm "act1_boss_the_kin" 的FMOD参数
    private const string _trackName = "the_kin_progress";
    private bool _hasTransformed; // 仅控制本地音乐/音效，不承载玩法状态。
    // 复用Fogmog（同源生物）的原版音效
    protected override string AttackSfx =>
        "event:/sfx/enemy/enemy_attacks/origin_fogmog/origin_fogmog_attack";
    protected override string CastSfx =>
        "event:/sfx/enemy/enemy_attacks/origin_fogmog/origin_fogmog_summon";
    public override string DeathSfx =>
        "event:/sfx/enemy/enemy_attacks/origin_fogmog/origin_fogmog_die";
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Plant;
    public override Vector2 ExtraDeathVfxPadding => new(1.45f, 1.75f);

    // 动态召唤的幻象不会出现在初始 MonstersWithSlots 中，按原版 Queen 的做法
    // 从召唤者的 AssetPaths 显式预加载随从视觉和意图资源。
    public override IEnumerable<string> AssetPaths =>
        base.AssetPaths
            .Concat(ModelDb.Monster<OriginEyeWithTeeth>().AssetPaths)
            .Append(ModelDb.Power<OriginPower>().ResolvedBigIconPath)
            .Append(ModelDb.Power<OriginGainEnergyPower>().ResolvedBigIconPath)
            .Append(ModelDb.Power<IllusionPower>().ResolvedBigIconPath)
            .Append(ModelDb.Power<MinionPower>().ResolvedBigIconPath)
            .Append(ModelDb.Power<StrengthPower>().ResolvedBigIconPath)
            .Distinct();

    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(
        AscensionLevel.ToughEnemies, 240, 235);

    public override int MaxInitialHp => MinInitialHp;

    //高低进阶血量伤害
    private int SwipeDamage => AscensionHelper.GetValueIfAscension(
        AscensionLevel.DeadlyEnemies, 12, 10);

    private int HeadbuttDamage => AscensionHelper.GetValueIfAscension(
        AscensionLevel.DeadlyEnemies, 15, 13);

    private int BlockAmount => AscensionHelper.GetValueIfAscension(
        AscensionLevel.DeadlyEnemies, 15, 10);

    private decimal HealAmount => AscensionHelper.GetValueIfAscension(
        AscensionLevel.DeadlyEnemies, 7m, 5m);

    private int TripleDamage => AscensionHelper.GetValueIfAscension(
        AscensionLevel.DeadlyEnemies, 4, 4);

    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        // 初始化专属音乐参数（CustomBgm = act1_boss_the_kin）
        NRunMusicController.Instance?.UpdateMusicParameter(_trackName, 1f);
        // OriginPower 的 Amount 是半血阈值，ShouldScaleInMultiplayer=true 会自动按玩家数缩放。
        // 必须用缩放前的原始 HP 计算，避免双重缩放导致阈值错误。
        var baseHp = Creature.MonsterMaxHpBeforeModification ?? Creature.MaxHp;
        await PowerCmd.Apply<OriginPower>(new ThrowingPlayerChoiceContext(), Creature, baseHp / 2m, Creature,
            null);
    }

    public override Task AfterDeath(PlayerChoiceContext choiceContext, Creature creature,
        bool wasRemovalPrevented, float deathAnimLength)
    {
        if (creature == Creature)
        {
            // 死亡升调（the_kin_progress=5 触发 FMOD 自动化）
            NRunMusicController.Instance?.UpdateMusicParameter(_trackName, 5f);
        }
        return Task.CompletedTask;
    }

    /// <summary>
    /// 触发二阶段转场（音乐+音效），幂等。
    /// 仅在 OriginPower 已成功安装带召唤回调的强制 STUNNED→SWIPE_MOVE 链后调用。
    /// </summary>
    public void OnPhaseTransition()
    {
        if (_hasTransformed) return;
        _hasTransformed = true;
        Log.Info("[OriginFogmog] Phase2 transition triggered!");
        SfxCmd.Play(CastSfx);
        NRunMusicController.Instance?.UpdateMusicParameter(_trackName, 2f);
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var list = new List<MonsterState>();

        // 第一招：召唤（开局只召唤一次）
        var illusionMove = new MoveState(IllusionMoveId, PerformIllusionMove,
            new SummonIntent());
        // 第二招：挥击 + 给自己加力量
        var swipeMove = new MoveState("SWIPE_MOVE", SwipeMove,
            new SingleAttackIntent(SwipeDamage), new BuffIntent());
        // 分支 A：挥击
        var swipeBlockMove = new MoveState("SWIPE_RANDOM_MOVE", SwipeBlockMove,
            new SingleAttackIntent(SwipeDamage), new DefendIntent());
        // 分支 B：头槌
        var headbuttMove = new MoveState("HEADBUTT_MOVE", HeadbuttMove,
            new SingleAttackIntent(HeadbuttDamage));
        var tripleMove = new MoveState("TRIPLE_MOVE", TripleMove,
            new MultiAttackIntent(TripleDamage, 3));
        var healMove = new MoveState("HEAL_MOVE", HealMove,
            new HealIntent());
        // 随机分支
        var branch = new RandomBranchState("BRANCH");
        branch.AddBranch(tripleMove, MoveRepeatType.CannotRepeat, () => 0.4f);
        branch.AddBranch(headbuttMove, MoveRepeatType.CannotRepeat, () => 0.6f);

        illusionMove.FollowUpState = swipeMove; //召唤完先力量
        healMove.FollowUpState = swipeMove;
        swipeMove.FollowUpState = branch;
        tripleMove.FollowUpState = swipeBlockMove;
        headbuttMove.FollowUpState = swipeBlockMove;
        swipeBlockMove.FollowUpState = healMove;


        list.Add(illusionMove);
        list.Add(swipeMove);
        list.Add(swipeBlockMove);
        list.Add(branch);
        list.Add(headbuttMove);
        list.Add(healMove);
        list.Add(tripleMove);
        return new MonsterMoveStateMachine(list, illusionMove);
    }


    // OriginPower passes one of these native move delegates to CreatureCmd.Stun so
    // the phase-two summon is performed during the stunned turn, rather than one
    // full enemy turn after the stun has already ended.
    public Task PerformIllusionMove(IReadOnlyList<Creature> targets)
    {
        return SummonIllusions(1);
    }

    // If the half-health transition replaces the still-pending opening summon,
    // that interrupted summon and the phase-two summon must both be preserved.
    // Filling both encounter slots in the forced stunned move keeps the outcome
    // identical to the normal sequence: opening Eye, then phase-two Eye.
    public Task PerformInterruptedOpeningIllusionMove(IReadOnlyList<Creature> targets)
    {
        return SummonIllusions(2);
    }

    private async Task SummonIllusions(int maxCount)
    {
        var combatState = CombatState;
        var encounter = combatState?.Encounter;
        if (combatState == null || encounter == null) return;
        var hasFreeSlot = encounter.Slots.Any(
            s => s.StartsWith("illusion", StringComparison.Ordinal)
                 && combatState.Enemies.All(c => c.SlotName != s));
        if (!hasFreeSlot) return;

        SfxCmd.Play(CastSfx);
        await CreatureCmd.TriggerAnim(Creature, "Summon", 0.75f);
        for (var i = 0; i < maxCount; i++)
        {
            // Re-evaluate after every add because CreatureCmd.Add can run hooks.
            // A dead Origin Eye still owns its slot while IllusionPower queues its
            // revive, so only a completely absent creature makes the slot free.
            var slotName = encounter.Slots.FirstOrDefault(
                s => s.StartsWith("illusion", StringComparison.Ordinal)
                     && combatState.Enemies.All(c => c.SlotName != s),
                string.Empty);
            if (string.IsNullOrEmpty(slotName))
                break;

            var eye = await CreatureCmd.Add<OriginEyeWithTeeth>(combatState, slotName);
            await PowerCmd.Apply<OriginGainEnergyPower>(new ThrowingPlayerChoiceContext(), eye, 1m, Creature, null);
        }
    }


    private async Task SwipeMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(SwipeDamage)
            .FromMonster(this)
            .WithAttackerAnim("Attack", 0.5f)
            .WithAttackerFx(null, AttackSfx)
            .WithHitFx("vfx/vfx_attack_slash")
            .Execute(null);
        await PowerCmd.Apply<StrengthPower>(new ThrowingPlayerChoiceContext(), Creature, 2m, Creature, null);
    }

    private async Task SwipeBlockMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(SwipeDamage)
            .FromMonster(this)
            .WithAttackerAnim("Attack", 0.5f)
            .WithAttackerFx(null, AttackSfx)
            .WithHitFx("vfx/vfx_attack_slash")
            .Execute(null);
        // Enemy move block is scaled exactly once by V109 MultiplayerScalingModel.
        await CreatureCmd.GainBlock(Creature, BlockAmount, ValueProp.Move, null);
    }

    private async Task HeadbuttMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(HeadbuttDamage)
            .FromMonster(this)
            .WithAttackerAnim("Attack", 0.5f)
            .WithAttackerFx(null, AttackSfx)
            .WithHitFx("vfx/vfx_attack_slash")
            .Execute(null);
    }

    private async Task TripleMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(TripleDamage)
            .FromMonster(this)
            .WithHitCount(3)
            .WithAttackerAnim("Attack", 0.5f)
            .WithAttackerFx(null, AttackSfx)
            .WithHitFx("vfx/vfx_attack_slash")
            .Execute(null);
    }

    private async Task HealMove(IReadOnlyList<Creature> targets)
    {
        await CreatureCmd.TriggerAnim(Creature, "PowerUp", 0.55f);
        await CreatureCmd.Heal(Creature, HealAmount * CombatState.Players.Count);
    }
}
