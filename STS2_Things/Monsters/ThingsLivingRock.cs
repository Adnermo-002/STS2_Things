using System.Collections.Generic;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using STS2_Things.Visuals;

namespace STS2_Things.Monsters;

public sealed class ThingsLivingRock : MonsterModel
{
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(
        AscensionLevel.ToughEnemies, 230, 220);

    public override int MaxInitialHp => MinInitialHp;

    public override bool HasDeathSfx => false;

    public override Vector2 ExtraDeathVfxPadding => new(1.6f, 1.6f);

    protected override string VisualsPath => SceneHelper.GetScenePath("creature_visuals/living_rock");

    private int PunchDamage => AscensionHelper.GetValueIfAscension(
        AscensionLevel.DeadlyEnemies, 14, 12);

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var leftPunch = new MoveState(
            "LEFT_PUNCH_MOVE",
            LeftPunchMove,
            new SingleAttackIntent(PunchDamage));
        var rightPunch = new MoveState(
            "RIGHT_PUNCH_MOVE",
            RightPunchMove,
            new SingleAttackIntent(PunchDamage));
        leftPunch.FollowUpState = rightPunch;
        rightPunch.FollowUpState = leftPunch;
        return new MonsterMoveStateMachine([leftPunch, rightPunch], leftPunch);
    }

    public override CreatureAnimator GenerateAnimator(MegaSprite controller)
    {
        var idle = new AnimState(NCaveGodVisuals.LeftToRightAnimation);
        var dead = new AnimState("hide");
        var animator = new CreatureAnimator(idle, controller);
        animator.AddAnyState(CreatureAnimator.idleTrigger, idle);
        animator.AddAnyState(CreatureAnimator.deathTrigger, dead);
        return animator;
    }

    private Task LeftPunchMove(IReadOnlyList<Creature> _)
    {
        return DamageCmd.Attack(PunchDamage)
            .FromMonster(this)
            .WithAttackerAnim(NCaveGodVisuals.LeftPunchTrigger, 0.3f)
            .WithHitFx("vfx/vfx_attack_blunt")
            .Execute(null);
    }

    private Task RightPunchMove(IReadOnlyList<Creature> _)
    {
        return DamageCmd.Attack(PunchDamage)
            .FromMonster(this)
            .WithAttackerAnim(NCaveGodVisuals.RightPunchTrigger, 0.3f)
            .WithHitFx("vfx/vfx_attack_blunt")
            .Execute(null);
    }
}
