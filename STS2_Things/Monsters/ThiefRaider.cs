using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Vfx;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Powers;

namespace STS2_Things.Monsters;

/// <summary>
///     劫掠者窃贼 — 普通敌人
///     登场自带劫掠者Buff（死亡+50金）
///     状态机: 隐匿 → 准备 → 反击 → 逃离（生成1个随机劫掠者）
/// </summary>
public sealed class ThiefRaider : MonsterModel
{
    protected override string AttackSfx =>
        "event:/sfx/enemy/enemy_attacks/axe_ruby_raider/axe_ruby_raider_attack";
    protected override string CastSfx =>
        "event:/sfx/enemy/enemy_attacks/tracker_ruby_raider/tracker_ruby_raider_buff";
    public override string DeathSfx =>
        "event:/sfx/enemy/enemy_attacks/axe_ruby_raider/axe_ruby_raider_die";
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Armor;
    public override Vector2 ExtraDeathVfxPadding => new(1.5f, 1.8f);

    // 逃离动作可生成任一种劫掠者；预加载完整候选集，而不是依赖本次初始随机抽到的三只。
    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat(
    [
        .. ModelDb.Monster<AxeRubyRaider>().AssetPaths,
        .. ModelDb.Monster<AssassinRubyRaider>().AssetPaths,
        .. ModelDb.Monster<BruteRubyRaider>().AssetPaths,
        .. ModelDb.Monster<CrossbowRubyRaider>().AssetPaths,
        .. ModelDb.Monster<TrackerRubyRaider>().AssetPaths,
        ModelDb.Power<ThiefRaiderPower>().ResolvedBigIconPath,
        ModelDb.Power<WeakPower>().ResolvedBigIconPath
    ]).Distinct();

    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(
        AscensionLevel.ToughEnemies, 17, 15);

    public override int MaxInitialHp => MinInitialHp;

    private int RetaliateDamage => AscensionHelper.GetValueIfAscension(
        AscensionLevel.DeadlyEnemies, 5, 4);

    // ========== 入场 ==========
    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        await PowerCmd.Apply<ThiefRaiderPower>(new ThrowingPlayerChoiceContext(),
            Creature, 1m, Creature, null);

        // 开局给所有队友 1 层虚弱（掩护代价）
        foreach (var enemy in CombatState.Enemies)
        {
            if (enemy != Creature && enemy.IsAlive)
                await PowerCmd.Apply<WeakPower>(new ThrowingPlayerChoiceContext(),
                    new[] { enemy }, 1m, Creature, null);
        }
    }

    // ========== 状态机 ==========
    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var list = new List<MonsterState>();

        var stealthMove = new MoveState("STEALTH_MOVE", StealthMove, new DebuffIntent());
        var prepareMove = new MoveState("PREPARE_MOVE", PrepareMove, new DefendIntent());
        var retaliateMove = new MoveState("RETALIATE_MOVE", RetaliateMove, new SingleAttackIntent(RetaliateDamage),
            new DefendIntent());
        var escapeMove = new MoveState("ESCAPE_MOVE", EscapeMove, new EscapeIntent());

        stealthMove.FollowUpState = prepareMove;
        prepareMove.FollowUpState = retaliateMove;
        retaliateMove.FollowUpState = escapeMove;
        escapeMove.FollowUpState = escapeMove; // 逃离后不再行动

        list.Add(stealthMove);
        list.Add(prepareMove);
        list.Add(retaliateMove);
        list.Add(escapeMove);

        return new MonsterMoveStateMachine(list, stealthMove);
    }

    // ========== 招式 ==========

    private async Task StealthMove(IReadOnlyList<Creature> targets)
    {
        TalkCmd.Play(new LocString("monsters", "THIEF_RAIDER.moves.STEALTH_MOVE.speakLine"), Creature, VfxColor.Blue);
        await Cmd.Wait(0.5f);
        SfxCmd.Play(CastSfx);
        await CreatureCmd.TriggerAnim(Creature, "Cast", 0.5f);
        await PowerCmd.Apply<WeakPower>(new ThrowingPlayerChoiceContext(),
            targets, 1m, Creature, null);
    }

    private async Task PrepareMove(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await CreatureCmd.TriggerAnim(Creature, "Cast", 0.5f);
        await CreatureCmd.GainBlock(Creature, 8, ValueProp.Move, null);
    }

    private async Task RetaliateMove(IReadOnlyList<Creature> targets)
    {
        TalkCmd.Play(new LocString("monsters", "THIEF_RAIDER.moves.RETALIATE_MOVE.speakLine"), Creature, VfxColor.Blue);
        await Cmd.Wait(0.5f);
        await DamageCmd.Attack(RetaliateDamage)
            .FromMonster(this)
            .WithAttackerAnim("Attack", 0.5f)
            .WithAttackerFx(null, AttackSfx)
            .Execute(null);
        await CreatureCmd.GainBlock(Creature, 6, ValueProp.Move, null);
    }

    private async Task EscapeMove(IReadOnlyList<Creature> targets)
    {
        var combatState = CombatState;
        var encounter = combatState?.Encounter;
        var slotName = encounter?.Slots.FirstOrDefault(
            s => s != null && s.StartsWith("raider_", StringComparison.Ordinal) &&
                 combatState!.Enemies.All(c => !c.IsAlive || c.SlotName != s),
            null);
        if (slotName != null && combatState != null)
        {
            // 使用同步的怪物 AI RNG；旧实现的实例计数器每只怪都从 0 开始，
            // 实际上永远只会召唤 AxeRubyRaider。
            MonsterModel raider = RunRng.MonsterAi.NextInt(5) switch
            {
                0 => ModelDb.Monster<AxeRubyRaider>(),
                1 => ModelDb.Monster<AssassinRubyRaider>(),
                2 => ModelDb.Monster<BruteRubyRaider>(),
                3 => ModelDb.Monster<CrossbowRubyRaider>(),
                _ => ModelDb.Monster<TrackerRubyRaider>()
            };
            await CreatureCmd.Add(raider.ToMutable(), combatState, CombatSide.Enemy, slotName);
        }

        // 逃离
        NCombatRoom.Instance?.GetCreatureNode(Creature)?.ToggleIsInteractable(false);
        await CreatureCmd.TriggerAnim(Creature, "Cast", 0.5f);
        await CreatureCmd.Escape(Creature);
    }
}
