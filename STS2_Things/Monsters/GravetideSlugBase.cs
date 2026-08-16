using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;

namespace STS2_Things.Monsters;

/// <summary>
/// Shared native Corpse Slug move and animation contract used by the boss and
/// its attendant variants.
/// </summary>
public abstract class GravetideSlugBase : MonsterModel
{
    private const string HeavyAttackTrigger = "HeavyAttackTrigger";
    private const string DoubleAttackTrigger = "DoubleAttackTrigger";

    internal const string DevourStartTrigger = "DevourStartTrigger";
    internal const string DevourEndTrigger = "DevourEndkTrigger";

    protected virtual string LightAttackSfx =>
        "event:/sfx/enemy/enemy_attacks/corpse_slugs/corpse_slugs_attack_light";
    internal const string DevourSfx =
        "event:/sfx/enemy/enemy_attacks/corpse_slugs/corpse_slugs_ravenous";
    internal const string DevourEndSfx =
        "event:/sfx/enemy/enemy_attacks/corpse_slugs/corpse_slugs_ravenous_up_double";

    private bool _isDevouring;
    private int _starterMoveIndex;

    protected abstract int WhipSlapDamage { get; }
    protected virtual int WhipSlapRepeat => 2;
    protected abstract int GlompDamage { get; }
    protected virtual int GoopFrailAmount => 2;

    protected override string VisualsPath =>
        SceneHelper.GetScenePath("creature_visuals/corpse_slug");

    protected override string AttackSfx =>
        "event:/sfx/enemy/enemy_attacks/corpse_slugs/corpse_slugs_attack";

    public override string DeathSfx =>
        "event:/sfx/enemy/enemy_attacks/corpse_slugs/corpse_slugs_die";

    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Slime;

    internal bool IsDevouring
    {
        get => _isDevouring;
        set
        {
            AssertMutable();
            _isDevouring = value;
        }
    }

    public int StarterMoveIndex
    {
        get => _starterMoveIndex;
        set
        {
            AssertMutable();
            _starterMoveIndex = value;
        }
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var whipSlap = new MoveState(
            "WHIP_SLAP_MOVE",
            WhipSlapMove,
            new MultiAttackIntent(WhipSlapDamage, WhipSlapRepeat));
        var glomp = new MoveState(
            "GLOMP_MOVE",
            GlompMove,
            new SingleAttackIntent(GlompDamage));
        var goop = new MoveState(
            "GOOP_MOVE",
            GoopMove,
            new DebuffIntent());

        whipSlap.FollowUpState = glomp;
        glomp.FollowUpState = goop;
        goop.FollowUpState = whipSlap;

        return new MonsterMoveStateMachine(
            [whipSlap, glomp, goop],
            ((StarterMoveIndex % 3 + 3) % 3) switch
            {
                0 => whipSlap,
                1 => glomp,
                _ => goop,
            });
    }

    protected async Task WhipSlapMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(WhipSlapDamage)
            .WithHitCount(WhipSlapRepeat)
            .FromMonster(this)
            .WithAttackerAnim(DoubleAttackTrigger, 0.3f)
            .OnlyPlayAnimOnce()
            .WithAttackerFx(null, LightAttackSfx)
            .WithHitFx("vfx/vfx_attack_slash")
            .Execute(null);
    }

    protected async Task GlompMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(GlompDamage)
            .FromMonster(this)
            .WithAttackerAnim(HeavyAttackTrigger, 0.3f)
            .WithAttackerFx(null, AttackSfx)
            .WithHitFx("vfx/vfx_attack_slash")
            .Execute(null);
    }

    protected async Task GoopMove(IReadOnlyList<Creature> targets)
    {
        await CreatureCmd.TriggerAnim(Creature, "Attack", 0.2f);
        await PowerCmd.Apply<FrailPower>(
            new ThrowingPlayerChoiceContext(), targets, GoopFrailAmount, Creature, null);
    }

    public override CreatureAnimator GenerateAnimator(MegaSprite controller)
    {
        var idle = new AnimState("idle_loop", isLooping: true);
        var attack = ReturnToIdle("attack", idle);
        var heavyAttack = ReturnToIdle("attack_heavy", idle);
        var doubleAttack = ReturnToIdle("attack_double", idle);
        var hurt = ReturnToIdle("hurt", idle);
        var death = new AnimState("die");
        var devourLoop = new AnimState("devour_loop", isLooping: true);
        var devourStart = new AnimState("devour_start") { NextState = devourLoop };
        var devourEnd = ReturnToIdle("devour_end", idle);
        var devouringHurt = new AnimState("hurt_devouring") { NextState = devourLoop };
        var devouringDeath = new AnimState("die_devouring");

        var animator = new CreatureAnimator(idle, controller);
        animator.AddAnyState(HeavyAttackTrigger, heavyAttack);
        animator.AddAnyState(DoubleAttackTrigger, doubleAttack);
        animator.AddAnyState(DevourStartTrigger, devourStart, () => !IsDevouring);
        animator.AddAnyState(DevourEndTrigger, devourEnd);
        animator.AddAnyState("Attack", attack);
        animator.AddAnyState("Dead", death, () => !IsDevouring);
        animator.AddAnyState("Hit", hurt, () => !IsDevouring);
        animator.AddAnyState("Dead", devouringDeath, () => IsDevouring);
        animator.AddAnyState("Hit", devouringHurt, () => IsDevouring);
        return animator;
    }

    private static AnimState ReturnToIdle(string animationName, AnimState idle)
    {
        return new AnimState(animationName) { NextState = idle };
    }
}
