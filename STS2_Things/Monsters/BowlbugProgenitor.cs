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
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Powers;

namespace STS2_Things.Monsters;

/// <summary>
/// 盛碗虫族母 — Hive Act Boss
/// 状态机循环：召唤 → 干扰/激励(交替) → 准备 → 休息 → 召唤...
/// 护巢本能：累计受到>=20%最大HP伤害时召唤盛碗虫（固定顺序：卵→蜜→岩→丝循环）
/// 视觉：原生 Spine 4.2 网格骨骼（animations/monsters/bowlbug_progenitor），产卵播放 summon，
/// 其余招式播放 cast / power_up。
/// </summary>
public sealed class BowlbugProgenitor : ThingsSpineMonster
{
    // The encounter lives in Hive, so it uses an act2 track that is already
    // loaded by the native Act music lifecycle.
    private const string _trackName = "kaiser_crab_progress";

    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 280, 260);
    public override int MaxInitialHp => MinInitialHp;

    // 战斗中按序召唤四种原版盛碗虫；在进入房间前预加载完整动态候选集。
    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat(
    [
        .. ModelDb.Monster<BowlbugEgg>().AssetPaths,
        .. ModelDb.Monster<BowlbugNectar>().AssetPaths,
        .. ModelDb.Monster<BowlbugRock>().AssetPaths,
        .. ModelDb.Monster<BowlbugSilk>().AssetPaths,
        ModelDb.Power<BowlbugProgenitorPower>().ResolvedBigIconPath,
        ModelDb.Power<ProtectTheMasterPower>().ResolvedBigIconPath,
        ModelDb.Power<MinionPower>().ResolvedBigIconPath,
        ModelDb.Power<WeakPower>().ResolvedBigIconPath,
        ModelDb.Power<StrengthPower>().ResolvedBigIconPath
    ]).Distinct();

    // 复用原版产卵母虫的有机攻击、产卵和死亡音效。
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/egg_layer/egg_layer_attack";
    protected override string CastSfx => "event:/sfx/enemy/enemy_attacks/egg_layer/egg_layer_lay";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/egg_layer/egg_layer_die";
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Insect;
    public override Vector2 ExtraDeathVfxPadding => new(1.35f, 1.8f);

    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        STS2_Things.Audio.ModMusicPolicy.UpdateParameter(_trackName, 1f);
        // 隐藏 Power 保存下一只召唤物索引，使序列进入多人 checksum/full-state。
        await PowerCmd.Apply<BowlbugSequencePower>(
            new ThrowingPlayerChoiceContext(), Creature, 1m, Creature, null);
        // 护巢本能：计数=20%最大HP，玩家造成伤害即计数减1，归零召唤2只并重置
        await PowerCmd.Apply<BowlbugProgenitorPower>(
            new ThrowingPlayerChoiceContext(), Creature, Creature.MaxHp * 0.2m, Creature, null);
        // 护主：场上有盛碗虫存活时，玩家对族母伤害减半
        await PowerCmd.Apply<ProtectTheMasterPower>(
            new ThrowingPlayerChoiceContext(), Creature, 1m, Creature, null);
    }

    public override Task AfterDeath(PlayerChoiceContext choiceContext, Creature creature,
        bool wasRemovalPrevented, float deathAnimLength)
    {
        if (creature == Creature)
        {
            STS2_Things.Audio.ModMusicPolicy.UpdateParameter(_trackName, 5f);
        }
        return Task.CompletedTask;
    }

    // ========== 状态机 ==========

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var states = new List<MonsterState>();

        // 1. 召唤：召唤1只盛碗虫 + 获得基础20格挡（ValueProp.Move 负责多人缩放）
        var summon = new MoveState("SUMMON_MOVE", SummonMove,
            new SummonIntent(), new DefendIntent());

        // 2a. 干扰：获得基础16格挡（ValueProp.Move 负责多人缩放）+ 给所有玩家2层虚弱
        var disrupt = new MoveState("DISRUPT_MOVE", DisruptMove,
            new DefendIntent(), new DebuffIntent());

        // 2b. 激励：召唤1只盛碗虫 + 全体怪物+3力量
        var rally = new MoveState("RALLY_MOVE", RallyMove,
            new SummonIntent(), new BuffIntent());

        // 3. 准备：全体怪物+3力量
        var prepare = new MoveState("PREPARE_MOVE", PrepareMove,
            new BuffIntent());

        // 4. 休息：回复(玩家数*10)生命
        var rest = new MoveState("REST_MOVE", RestMove,
            new HealIntent());

        // 固定循环：召唤 → 干扰 → 激励 → 准备 → 休息 → 召唤...
        summon.FollowUpState = disrupt;
        disrupt.FollowUpState = rally;
        rally.FollowUpState = prepare;
        prepare.FollowUpState = rest;
        rest.FollowUpState = summon;

        states.Add(summon);
        states.Add(disrupt);
        states.Add(rally);
        states.Add(prepare);
        states.Add(rest);

        return new MonsterMoveStateMachine(states, summon);
    }

    // ========== 招式实现 ==========

    private int PlayerCount => CombatState.Players.Count;

    private int LiveBowlbugCount => CombatState.Enemies.Count(e => e.IsAlive &&
        (e.Monster is BowlbugSilk || e.Monster is BowlbugRock ||
         e.Monster is BowlbugNectar || e.Monster is BowlbugEgg));

    private string NextAvailableSlot => CombatState.Encounter?.Slots.FirstOrDefault(
        candidate => CombatState.Enemies.All(
            enemy => !enemy.IsAlive || enemy.SlotName != candidate),
        string.Empty) ?? string.Empty;

    /// <summary>
    /// 受到伤害阈值触发的响应召唤：单次播放产卵动画，批量生成盛碗虫，并透传合法的 choiceContext。
    /// 杜绝重复等待1.5秒动画及 ThrowingPlayerChoiceContext 导致的联机选牌软锁。
    /// </summary>
    internal async Task SummonFromDamage(PlayerChoiceContext choiceContext, int count = 2)
    {
        if (!CombatState.IsLiveCombat()) return;

        SfxCmd.Play(CastSfx);
        // 产卵动画：卵囊蠕动挤压，0.70s 处“啵”地产出，随后召唤物登场。
        await CreatureCmd.TriggerAnim(Creature, "Summon", 0.75f);

        for (int i = 0; i < count; i++)
        {
            await SpawnSingleBowlbug(choiceContext, 0.5m);
        }

        var power = Creature.Powers.OfType<BowlbugProgenitorPower>().FirstOrDefault();
        if (power != null)
            power.RefreshDescription();
    }

    /// <summary>按固定顺序召唤1只盛碗虫（卵→蜜→岩→丝循环），场上盛碗虫达到16只时取消</summary>
    internal async Task<bool> SummonNextBowlbug(PlayerChoiceContext choiceContext, decimal maxHpMultiplier)
    {
        if (!CombatState.IsLiveCombat()) return false;
        if (LiveBowlbugCount >= 16) return false;

        string slot = NextAvailableSlot;
        if (string.IsNullOrEmpty(slot)) return false;

        SfxCmd.Play(CastSfx);
        await CreatureCmd.TriggerAnim(Creature, "Summon", 0.75f);

        bool spawned = await SpawnSingleBowlbug(choiceContext, maxHpMultiplier);

        var power = Creature.Powers.OfType<BowlbugProgenitorPower>().FirstOrDefault();
        if (power != null)
            power.RefreshDescription();

        return spawned;
    }

    /// <summary>生成单只盛碗虫底层实现，遵循原版 SpawnedThisTurn 规则，不强行注入 Stun 避免破坏状态机</summary>
    private async Task<bool> SpawnSingleBowlbug(PlayerChoiceContext choiceContext, decimal maxHpMultiplier)
    {
        if (!CombatState.IsLiveCombat()) return false;
        if (LiveBowlbugCount >= 16) return false;

        string slot = NextAvailableSlot;
        if (string.IsNullOrEmpty(slot)) return false;

        // 固定顺序：0=卵, 1=蜜, 2=岩, 3=丝
        var sequence = Creature.GetPower<BowlbugSequencePower>();
        int nextIndex = sequence?.NextIndex ?? 0;
        Creature creature = nextIndex switch
        {
            0 => await CreatureCmd.Add<BowlbugEgg>(CombatState, slot),
            1 => await CreatureCmd.Add<BowlbugNectar>(CombatState, slot),
            2 => await CreatureCmd.Add<BowlbugRock>(CombatState, slot),
            _ => await CreatureCmd.Add<BowlbugSilk>(CombatState, slot)
        };
        sequence?.Advance();

        // 爪牙属性：透传有效 choiceContext，不使用 ThrowingPlayerChoiceContext 避免联机深层 Hook 异常
        await PowerCmd.Apply<MinionPower>(choiceContext, creature, 1m, Creature, null);
        int newMaxHp = Math.Max(1, (int)(creature.MaxHp * maxHpMultiplier));
        await CreatureCmd.SetMaxAndCurrentHp(creature, newMaxHp);

        return true;
    }

    /// <summary>1. 召唤：召唤1只盛碗虫 + 获得基础20格挡，由 ValueProp.Move 负责多人缩放</summary>
    private async Task SummonMove(IReadOnlyList<Creature> targets)
    {
        bool summoned = await SummonNextBowlbug(new ThrowingPlayerChoiceContext(), 0.7m);
        if (!summoned)
            await CreatureCmd.TriggerAnim(Creature, "PowerUp", 0.45f);
        await CreatureCmd.GainBlock(Creature, 20, ValueProp.Move, null, fast: true);
    }

    /// <summary>2a. 干扰：获得基础16格挡，由 ValueProp.Move 负责多人缩放，并给所有玩家2层虚弱</summary>
    private async Task DisruptMove(IReadOnlyList<Creature> targets)
    {
        await CreatureCmd.TriggerAnim(Creature, "Cast", 0.5f);
        await CreatureCmd.GainBlock(Creature, 16, ValueProp.Move, null, fast: true);
        await PowerCmd.Apply<WeakPower>(new ThrowingPlayerChoiceContext(),
            CombatState.Players.Select(p => p.Creature).ToArray(), 2m, Creature, null);
    }

    /// <summary>2b. 激励：召唤1只盛碗虫 + 全体怪物+3力量</summary>
    private async Task RallyMove(IReadOnlyList<Creature> targets)
    {
        bool summoned = await SummonNextBowlbug(new ThrowingPlayerChoiceContext(), 0.7m);
        if (!summoned)
            await CreatureCmd.TriggerAnim(Creature, "PowerUp", 0.45f);
        // 全体怪物获得+3力量
        foreach (var enemy in CombatState.Enemies.Where(e => e.IsAlive))
        {
            await PowerCmd.Apply<StrengthPower>(new ThrowingPlayerChoiceContext(),
                enemy, 3m, Creature, null);
        }
    }

    /// <summary>3. 准备：全体怪物+3力量</summary>
    private async Task PrepareMove(IReadOnlyList<Creature> targets)
    {
        await CreatureCmd.TriggerAnim(Creature, "PowerUp", 0.5f);
        foreach (var enemy in CombatState.Enemies.Where(e => e.IsAlive))
        {
            await PowerCmd.Apply<StrengthPower>(new ThrowingPlayerChoiceContext(),
                enemy, 3m, Creature, null);
        }
    }

    /// <summary>4. 休息：回复(玩家数*10)生命</summary>
    private async Task RestMove(IReadOnlyList<Creature> targets)
    {
        await CreatureCmd.TriggerAnim(Creature, "PowerUp", 0.55f);
        await CreatureCmd.Heal(Creature, PlayerCount * 10);
    }
}
