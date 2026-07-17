using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Things.Monsters;

/// <summary>
/// Shared animation-state contract for the mod's native Spine 4.2 monsters.
/// The visual assets expose semantic one-shot animations in addition to the
/// five states supplied by <see cref="MonsterModel"/>.
/// </summary>
public abstract class ThingsSpineMonster : MonsterModel
{
    public override CreatureAnimator GenerateAnimator(MegaSprite controller)
    {
        var idle = new AnimState("idle_loop", isLooping: true);
        var attack = ReturnToIdle("attack", idle);
        var cast = ReturnToIdle("cast", idle);
        var hurt = ReturnToIdle("hurt", idle);
        var summon = ReturnToIdle("summon", idle);
        var powerUp = ReturnToIdle("power_up", idle);
        var revive = ReturnToIdle("revive", idle);
        var die = new AnimState("die");

        var animator = new CreatureAnimator(idle, controller);
        animator.AddAnyState(CreatureAnimator.idleTrigger, idle);
        animator.AddAnyState(CreatureAnimator.attackTrigger, attack);
        animator.AddAnyState(CreatureAnimator.castTrigger, cast);
        animator.AddAnyState(CreatureAnimator.hitTrigger, hurt);
        animator.AddAnyState(CreatureAnimator.deathTrigger, die);
        animator.AddAnyState(CreatureAnimator.powerUpTrigger, powerUp);
        animator.AddAnyState(CreatureAnimator.reviveTrigger, revive);
        animator.AddAnyState("Summon", summon);
        return animator;
    }

    private static AnimState ReturnToIdle(string animationName, AnimState idle)
    {
        return new AnimState(animationName)
        {
            NextState = idle,
        };
    }
}
