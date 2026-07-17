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
using STS2_Things.Encounters;
using STS2_Things.Powers;

namespace STS2_Things.Monsters;

/// <summary>
///     灵魂鱼子精英 — 4回合循环 + 死亡爆6只小 SoulRoe
///     招式循环:
///     回合1: BeckonStrength         → 给玩家 2 张 Beckon + 自身 +1 力量
///     回合2: MultiAttack6           → 造成 1 点伤害 × 6 次
///     回合3: MultiAttack4Intangible → 造成 1 点伤害 × 4 次 + 自身 +1 无实体
///     回合4: SpawnSoulRoe           → 生成 2 只 SoulRoe（phase 1 beckon / phase 2 damage）
///     死亡机制:
///     AfterAddedToRoom 给自己挂 SoulRoesPower
///     SoulRoesPower.AfterDeath 生成 6 只 SoulRoe:
///     soulroe1、4 → phase 0 (Intangible)
///     soulroe2、5 → phase 1 (Beckon)
///     soulroe3、6 → phase 2 (Damage)
///     全部入场眩晕 1 回合
/// </summary>
public sealed class SoulRoes : MonsterModel
{
    protected override string AttackSfx =>
        "event:/sfx/enemy/enemy_attacks/soul_fysh/soul_fysh_attack";
    protected override string CastSfx =>
        "event:/sfx/enemy/enemy_attacks/soul_fysh/soul_fysh_beckon";
    public override string DeathSfx =>
        "event:/sfx/enemy/enemy_attacks/soul_fysh/soul_fysh_die";
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Magic;
    public override Vector2 ExtraDeathVfxPadding => new(1.6f, 3.0f);

    // 像原版 Queen 预加载动态随从一样，把 SoulRoe 的全部视觉/意图资源挂到召唤者。
    public override IEnumerable<string> AssetPaths =>
        base.AssetPaths
            .Concat(ModelDb.Monster<SoulRoe>().AssetPaths)
            .Append(ModelDb.Power<SoulRoesPower>().ResolvedBigIconPath)
            .Append(ModelDb.Power<IntangiblePower>().ResolvedBigIconPath)
            .Append(ModelDb.Power<StrengthPower>().ResolvedBigIconPath)
            .Distinct();

    // ========== 血量：低难度 33~42，高难度 36~45 ==========
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(
        AscensionLevel.ToughEnemies, 45, 40);

    public override int MaxInitialHp => AscensionHelper.GetValueIfAscension(
        AscensionLevel.ToughEnemies, 48, 44);

    // ========== 入场：给自己挂上死亡召唤 Power ==========
    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        // SoulRoesPower 的作用:
        //   1. ShouldStopCombatFromEnding() → true（死后不结算胜利）
        //   2. AfterDeath() → 等死亡动画 → 生成 6 只 SoulRoe
        await PowerCmd.Apply<SoulRoesPower>(new ThrowingPlayerChoiceContext(), Creature, 6m, Creature, null);
    }

    // ========== 4 回合招式循环 ==========
    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var list = new List<MonsterState>();

        // 回合1: 2 张 Beckon + 自身 +1 力量
        // Intent: StatusIntent(2) + BuffIntent → 状态牌×2 + 绿色buff
        var beckonStrMove = new MoveState(
            "BECKON_STR_MOVE", BeckonStrengthMove,
            new StatusIntent(2), new BuffIntent());

        // 回合2: 1 点伤害 × 6 次
        // Intent: MultiAttackIntent(1, 6) → 剑×6 + 伤害1
        var multi6Move = new MoveState(
            "MULTI6_MOVE", MultiAttack6Move,
            new MultiAttackIntent(1, 6));

        // 回合3: 1 点伤害 × 4 次 + 自身 +1 无实体
        // Intent: MultiAttackIntent(1, 4) + BuffIntent → 剑×4 + 绿色buff
        var multi4IntMove = new MoveState(
            "MULTI4_INT_MOVE", MultiAttack4IntangibleMove,
            new MultiAttackIntent(1, 4), new BuffIntent());

        // 回合4: 生成 2 只 SoulRoe
        // Intent: SummonIntent → 召唤图标
        var spawnMove = new MoveState(
            "SPAWN_MOVE", SpawnSoulRoeMove,
            new SummonIntent());

        // 固定循环: 1→2→3→4→1→...
        beckonStrMove.FollowUpState = multi6Move;
        multi6Move.FollowUpState = multi4IntMove;
        multi4IntMove.FollowUpState = spawnMove;
        spawnMove.FollowUpState = beckonStrMove;

        list.Add(beckonStrMove);
        list.Add(multi6Move);
        list.Add(multi4IntMove);
        list.Add(spawnMove);

        return new MonsterMoveStateMachine(list, beckonStrMove);
    }

    // ========== 回合1: 2 张 Beckon + 自身 +1 力量 ==========
    private async Task BeckonStrengthMove(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await CreatureCmd.TriggerAnim(Creature, "Cast", 0.5f);

        // 给所有目标弃牌堆各塞 2 张 Beckon
        await CardPileCmd.AddToCombatAndPreview<Beckon>(
            targets, PileType.Discard, 2, null);

        // 自身 +1 力量
        await PowerCmd.Apply<StrengthPower>(new ThrowingPlayerChoiceContext(),
            Creature, 1m, Creature, null);
    }

    // ========== 回合2: 1 点伤害 × 6 次 ==========
    private async Task MultiAttack6Move(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(1)
            .FromMonster(this)
            .WithHitCount(6) // 打 6 下
            .WithAttackerAnim("Attack", 0.5f)
            .WithAttackerFx(null, AttackSfx)
            .Execute(null);
    }

    // ========== 回合3: 1 点伤害 × 4 次 + 自身 +1 无实体 ==========
    private async Task MultiAttack4IntangibleMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(1)
            .FromMonster(this)
            .WithHitCount(4) // 打 4 下
            .WithAttackerAnim("Attack", 0.5f)
            .WithAttackerFx(null, AttackSfx)
            .Execute(null);

        // 自身 +1 无实体（2 层 = 跨回合生效，同 SoulFysh）
        await PowerCmd.Apply<IntangiblePower>(new ThrowingPlayerChoiceContext(),
            Creature, 2m, Creature, null);
    }

    // ========== 回合4: 生成 2 只 SoulRoe ==========
    // 生成的 SoulRoe 不眩晕，直接按指定 phase 进入战斗
    // 第1只 → phase 1 (Beckon)，第2只 → phase 2 (Damage)
    private async Task SpawnSoulRoeMove(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await CreatureCmd.TriggerAnim(Creature, "Summon", 0.75f);

        int[] phases = { 1, 2 }; // beckon, damage
        var spawned = 0;

        // 扫描 soulroe找空槽位
        for (var i = 0; i < SoulRoesEncounter.SoulRoeSlotCount && spawned < 2; i++)
        {
            var slotName = SoulRoesEncounter.GetSoulRoeSlotName(i);
            if (CombatState.Enemies.Any(c => c.IsAlive && c.SlotName == slotName))
                continue; // 槽位已被占用，跳过

            // ToMutable() 把模板转为可修改变量实例
            var soulRoe = (SoulRoe)ModelDb.Monster<SoulRoe>().ToMutable();
            soulRoe.StartMovePhase = phases[spawned];

            await CreatureCmd.Add(soulRoe, CombatState,
                Creature.Side, slotName);
            spawned++;
        }
    }
}
