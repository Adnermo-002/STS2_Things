using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;

namespace STS2_Things.Monsters;

/// <summary>
///     灵魂鱼子 — 固定3回合循环的脆皮小怪
///     支持从任意招式开始循环（由调用方设置 StartMovePhase）
///     支持入场眩晕（StartStunned = true）
///     招式循环: Intangible → Beckon → Damage → Intangible → ...
///     Phase 0 = Intangible: 给自己一层无实体
///     Phase 1 = Beckon:     给玩家弃牌堆塞一张 Beckon
///     Phase 2 = Damage:     造成 6 点伤害
/// </summary>
public sealed class SoulRoe : MonsterModel
{
    private const int _damage = 6;
    protected override string AttackSfx =>
        "event:/sfx/enemy/enemy_attacks/soul_fysh/soul_fysh_attack";
    protected override string CastSfx =>
        "event:/sfx/enemy/enemy_attacks/soul_fysh/soul_fysh_beckon";
    public override string DeathSfx =>
        "event:/sfx/enemy/enemy_attacks/soul_fysh/soul_fysh_die";
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Magic;
    public override Vector2 ExtraDeathVfxPadding => new(2.2f, 5.0f);

    private static readonly string[] _visualVariants =
    [
        SceneHelper.GetScenePath("creature_visuals/soul_roe"),
        SceneHelper.GetScenePath("creature_visuals/soul_roe_2"),
        SceneHelper.GetScenePath("creature_visuals/soul_roe_3")
    ];
    private int _startMovePhase;

    // ========== 可配置属性（必须在 ToMutable() 后设置） ==========

    private bool _startStunned;

    // 变体选择只依赖同步的起始阶段；所有变体都进入 AssetPaths，避免动态召唤时临时加载。
    protected override string VisualsPath =>
        _visualVariants[Math.Abs(_startMovePhase % _visualVariants.Length)];

    public override IEnumerable<string> AssetPaths =>
        base.AssetPaths.Concat(_visualVariants).Distinct();

    // ========== 血量 ==========
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(
        AscensionLevel.ToughEnemies, 6, 4);

    public override int MaxInitialHp => AscensionHelper.GetValueIfAscension(
        AscensionLevel.ToughEnemies, 8, 6);

    /// <summary>入场第一回合是否眩晕（死亡生成时设为 true）</summary>
    public bool StartStunned
    {
        get => _startStunned;
        set
        {
            AssertMutable(); // 防止在不可变模板上设置 → 编译期/运行时保护
            _startStunned = value;
        }
    }

    /// <summary>
    ///     起始招式阶段:
    ///     0 = IntangibleMove（给自己无实体）
    ///     1 = BeckonMove（给玩家 Beckon）
    ///     2 = DamageMove（造成 6 伤害）
    /// </summary>
    public int StartMovePhase
    {
        get => _startMovePhase;
        set
        {
            AssertMutable();
            _startMovePhase = value;
        }
    }

    // ========== 状态机 ==========
    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var list = new List<MonsterState>();

        // --- 三招招式 ---
        var intangibleMove = new MoveState(
            "INTANGIBLE_MOVE", IntangibleMove, new BuffIntent());
        var beckonMove = new MoveState(
            "BECKON_MOVE", BeckonMove, new StatusIntent(1));
        var damageMove = new MoveState(
            "DAMAGE_MOVE", DamageMove, new SingleAttackIntent(_damage));

        // --- 眩晕招式（入场第一回合什么都不做） ---
        var stunnedMove = new MoveState(
            "STUNNED_MOVE", StunnedMove, new StunIntent());

        // --- 三招固定循环 ---
        intangibleMove.FollowUpState = beckonMove;
        beckonMove.FollowUpState = damageMove;
        damageMove.FollowUpState = intangibleMove;

        // --- 条件分支：根据 StartMovePhase 选择起始招式 ---
        // ConditionalBranchState 在状态机启动时惰性求值 lambda，
        // 此时 _startMovePhase 已被调用方设置好
        var initBranch = new ConditionalBranchState("INIT_BRANCH");
        initBranch.AddState(intangibleMove, () => _startMovePhase == 0);
        initBranch.AddState(beckonMove, () => _startMovePhase == 1);
        initBranch.AddState(damageMove, () => _startMovePhase == 2);

        // 眩晕后进入条件分支
        stunnedMove.FollowUpState = initBranch;

        list.Add(intangibleMove);
        list.Add(beckonMove);
        list.Add(damageMove);
        list.Add(stunnedMove);
        list.Add(initBranch);

        // 选择初始状态：眩晕 还是 直接按 phase 进入
        var initialState = _startStunned
            ? stunnedMove
            : (MonsterState)initBranch;

        return new MonsterMoveStateMachine(list, initialState);
    }

    // ========== Stunned: 空操作 ==========
    private Task StunnedMove(IReadOnlyList<Creature> targets)
    {
        return Task.CompletedTask;
    }

    // ========== Intangible: 自身 +1 无实体 ==========
    private async Task IntangibleMove(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await CreatureCmd.TriggerAnim(Creature, "Cast", 0.5f);
        await PowerCmd.Apply<IntangiblePower>(new ThrowingPlayerChoiceContext(),
            Creature, 2m, Creature, null);
    }

    // ========== Beckon: 给玩家弃牌堆 +1 Beckon ==========
    private async Task BeckonMove(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await CreatureCmd.TriggerAnim(Creature, "Cast", 0.5f);
        await CardPileCmd.AddToCombatAndPreview<Beckon>(
            targets, PileType.Discard, 1, null);
    }

    // ========== Damage: 造成 6 点伤害 ==========
    private async Task DamageMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(_damage)
            .FromMonster(this)
            .WithAttackerAnim("Attack", 0.5f)
            .WithAttackerFx(null, AttackSfx)
            .Execute(null);
    }
}
