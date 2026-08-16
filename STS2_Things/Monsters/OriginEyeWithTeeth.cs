using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using HarmonyLib;
using STS2_Things.Powers;

namespace STS2_Things.Monsters;

public sealed class OriginEyeWithTeeth : MonsterModel
{
    private const int _distractAmount = 2;
    private const int HealAmountPerPlayer = 6;

    protected override string AttackSfx =>
        "event:/sfx/enemy/enemy_attacks/eye_with_teeth/eye_with_teeth_attack";
    // EyeWithTeeth has no death event in the V110 SFX bank. The Obscura
    // hologram event is the native illusion-disappearance equivalent.
    public override string DeathSfx =>
        "event:/sfx/enemy/enemy_attacks/obscura/obscura_hologram_die";

    protected override string VisualsPath => SceneHelper.GetScenePath("creature_visuals/eye_with_teeth");

    public override int MinInitialHp => 9;

    public override int MaxInitialHp => MinInitialHp;

    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Magic;

    public override bool ShouldDisappearFromDoom => false;

    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        await ApplyIllusionPower();
    }

    /// <summary>
    /// 施加IllusionPower并设置复活后跳转眩晕意图。
    /// CreatureCmd.Add 会调用 AfterAddedToRoom，因此动态召唤无需重复施加。
    /// </summary>
    private async Task ApplyIllusionPower()
    {
        await PowerCmd.Apply<IllusionPower>(new ThrowingPlayerChoiceContext(), Creature, 1m, Creature, null);
        var illusion = Creature.GetPower<IllusionPower>();
        if (illusion != null)
        {
            illusion.FollowUpStateId = "STUN_AFTER_REVIVE";
        }
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var list = new List<MonsterState>();
        var healBoss = new MoveState("HEAL_BOSS_MOVE", HealBossMove, new HealIntent());
        var giveCard = new MoveState("DISTRACT_MOVE", DistractMove, new StatusIntent(_distractAmount));
        // 复活后眩晕状态，执行完后回到正常循环
        var stunAfterRevive = new MoveState("STUN_AFTER_REVIVE", _ => Task.CompletedTask, new StunIntent())
        {
            FollowUpState = giveCard,
            MustPerformOnceBeforeTransitioning = true
        };
        giveCard.FollowUpState = healBoss;
        healBoss.FollowUpState = giveCard;
        list.Add(giveCard);
        list.Add(healBoss);
        list.Add(stunAfterRevive);
        return new MonsterMoveStateMachine(list, giveCard);
    }

    private async Task HealBossMove(IReadOnlyList<Creature> targets)
    {
        var combatState = Creature.CombatState;
        if (combatState == null) return;
        var boss = combatState.GetTeammatesOf(Creature)
            .FirstOrDefault(c => c.IsPrimaryEnemy);
        if (boss == null) return;

        await CreatureCmd.TriggerAnim(Creature, "Attack", 0.45f);
        // 多人游戏时回血按玩家数 scaling，与 OriginFogmog 的 HealMove 保持一致
        var healAmount = HealAmountPerPlayer * combatState.Players.Count;
        await CreatureCmd.Heal(boss, healAmount);
    }

    private async Task DistractMove(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(AttackSfx);
        await CreatureCmd.TriggerAnim(Creature, "Attack", 0.7f);
        VfxCmd.PlayOnCreatureCenters(targets, "vfx/vfx_attack_slash");
        await CardPileCmd.AddToCombatAndPreview<Dazed>(targets, PileType.Discard, _distractAmount, null);
    }

    public override void SetupSkins(MegaSprite spine, MegaSkeleton skeleton)
    {
        base.SetupSkins(spine, skeleton);
        if (spine.BoundObject is CanvasItem visuals)
            // Preserve the shipped hand-painted value range.  The old saturated
            // Preserve the shipped Eye atlas palette exactly.  Illusion identity
            // comes from its native powers/VFX rather than a destructive tint.
            visuals.Modulate = Colors.White;
    }

    public override CreatureAnimator GenerateAnimator(MegaSprite controller)
    {
        var animState = new AnimState("idle_loop", true);
        var animState2 = new AnimState("attack");
        var state = new AnimState("die");
        animState2.NextState = animState;
        var creatureAnimator = new CreatureAnimator(animState, controller);
        creatureAnimator.AddAnyState("Attack", animState2);
        creatureAnimator.AddAnyState("Dead", state,
            () => !CombatState.GetTeammatesOf(Creature).Any(t => t != null && t.IsPrimaryEnemy && t.IsAlive));
        return creatureAnimator;
    }
}

/// <summary>
/// 保证两个一次性强制状态不会被已有的 MustPerformOnce 状态静默吞掉。
/// </summary>
[HarmonyPatch(typeof(MonsterModel), nameof(MonsterModel.SetMoveImmediate))]
public static class RequiredMonsterMoveTransitionPatch
{
    private static void Prefix(MonsterModel __instance, MoveState state, ref bool forceTransition)
    {
        if (__instance is OriginEyeWithTeeth && state.StateId == "REVIVE_MOVE")
            forceTransition = true;

        // Fogmog 跨半血时 ThingsOriginPower 只触发一次；如果当前正被其他来源眩晕，
        // 普通 SetMoveImmediate 会拒绝新的 STUNNED 并永久跳过幻象阶段。
        if (__instance is OriginFogmog
            && state.StateId == MonsterModel.stunnedMoveId
            && state.FollowUpStateId == OriginFogmog.SwipeMoveId)
            forceTransition = true;
    }
}
