using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using STS2_Things.Powers;

namespace STS2_Things.Monsters;

/// <summary>A five-action survival encounter: attacking lends the attacker its shadow as Block.</summary>
public sealed class FleetingEcho : ThingsSpineMonster
{
    public const int Lifetime = 5;
    public override int MinInitialHp => 999;
    public override int MaxInitialHp => 999;
    public override float HpBarSizeReduction => 80f;
    private int OpeningDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 26, 22);
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Magic;
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/soul_fysh/soul_fysh_wave";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/soul_fysh/soul_fysh_intangible";
    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat([
        ModelDb.Power<BorrowedShadowPower>().ResolvedBigIconPath,
        ModelDb.Power<FleetingFadePower>().ResolvedBigIconPath,
        "res://images/vfx/fleeting_shadow.png"]);

    public override async Task BeforeCombatStart()
    {
        var choice = new ThrowingPlayerChoiceContext();
        await PowerCmd.Apply<BorrowedShadowPower>(choice, Creature, 1, Creature, null);
        await PowerCmd.Apply<FleetingFadePower>(choice, Creature, Lifetime, Creature, null);
    }

    protected override void AddExtraAnimationStates(CreatureAnimator animator, AnimState idle)
    {
        foreach (string clip in new[] { "sweep", "grasp", "pulse", "scatter" })
            animator.AddAnyState(clip, new AnimState(clip) { NextState = idle });
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        string[] ids = ["REACH_MOVE", "SWEEP_MOVE", "GRASP_MOVE", "PULSE_MOVE", "SCATTER_MOVE"];
        string[] clips = ["attack", "sweep", "grasp", "pulse", "scatter"];
        float[] contacts = [.52f, .58f, .62f, .64f, .70f];
        float[] durations = [1.25f, 1.4f, 1.5f, 1.55f, 1.65f];
        var moves = new MoveState[Lifetime];
        for (int i = 0; i < moves.Length; i++)
        {
            int phase = i;
            int damage = OpeningDamage + phase * 4;
            moves[i] = new MoveState(ids[i], _ => Strike(damage, clips[phase], contacts[phase], durations[phase]),
                new SingleAttackIntent(damage));
        }
        for (int i = 0; i < moves.Length - 1; i++) moves[i].FollowUpState = moves[i + 1];
        // A forced stun consumes neither a real attack nor the disappearance timer.
        // The final move has a follow-up for native state-machine invariants; it
        // cannot occur in a normal battle because the timer ends the encounter.
        moves[^1].FollowUpState = moves[^1];
        return new MonsterMoveStateMachine(moves, moves[0]);
    }

    private async Task Strike(int damage, string clip, float contact, float duration)
    {
        await DamageCmd.Attack(damage).FromMonster(this)
            .WithAttackerAnim(clip == "attack" ? CreatureAnimator.attackTrigger : clip, contact)
            .WithAttackerFx(null, AttackSfx).WithHitFx("vfx/vfx_attack_blunt").Execute(null);
        await Cmd.Wait(duration - contact);
        if (!Creature.IsAlive || CombatManager.Instance.IsOverOrEnding) return;
        if (Creature.GetPower<FleetingFadePower>() is not { } timer) return;
        await PowerCmd.Decrement(timer);
        if (Creature.GetPower<FleetingFadePower>() == null)
        {
            // Native death handles the dissolve clip, removal, battle outcome,
            // rewards and all clients. Do not leave an escaped visual behind.
            await CreatureCmd.Kill(Creature);
        }
    }
}
