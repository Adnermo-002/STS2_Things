using System.Collections.Generic;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Bestiary;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Visuals;

namespace STS2_Things.Monsters;

/// <summary>
/// Left Hand / Left Arm entity of Cave God (山神·左臂).
/// Manages the left side HP bar, intents, and strikes in coordination with NCaveGodBossBackground.
/// </summary>
public sealed class ThingsCaveGodLeftHand : MonsterModel
{
    private const string KaiserMusicTrack = "kaiser_crab_progress";
    private NCaveGodBossBackground? _background;
    private bool _enteredAngry;

    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_left_die";
    public override bool ShouldFadeAfterDeath => false;
    public override bool ShouldDisappearFromDoom => false;
    public override float DeathAnimLengthOverride => 2.5f;

    private NCaveGodBossBackground? Background
    {
        get
        {
            AssertMutable();
            if (_background == null)
            {
                _background = (NCombatRoom.Instance?.Background ?? NBestiary.Instance?.Layout)?.GetNodeOrNull<NCaveGodBossBackground>("%CaveGod");
            }
            return _background;
        }
    }

    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 219, 209);
    public override int MaxInitialHp => MinInitialHp;

    private int LeftPunchDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 14, 12);
    private int JabDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 5, 4);
    private int JabTimes => 3;
    private int FrontSweepDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 11, 10);
    private int MountainGuardDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 14, 12);
    private int MountainGuardBlock => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 16, 14);

    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        NRunMusicController.Instance?.UpdateMusicParameter(KaiserMusicTrack, 1f);
    }

    public override Task AfterCurrentHpChanged(Creature creature, decimal delta)
    {
        if (creature == Creature && delta < 0m)
        {
            Background?.PlayHurtAnim();

            if (Creature.CurrentHp <= Creature.MaxHp / 2m && !_enteredAngry)
            {
                _enteredAngry = true;
                Background?.SetAngry(true);
                NRunMusicController.Instance?.UpdateMusicParameter(KaiserMusicTrack, 3f);
            }
        }
        return Task.CompletedTask;
    }

    public override Task BeforeDeath(Creature creature)
    {
        if (creature != Creature)
            return Task.CompletedTask;

        NAudioManager.Instance?.PlayOneShot(DeathSfx);

        if (CombatManager.Instance.IsOverOrEnding)
        {
            Background?.PlayBodyDeathAnim();
            NRunMusicController.Instance?.UpdateMusicParameter(KaiserMusicTrack, 5f);
        }
        else
        {
            NRunMusicController.Instance?.UpdateMusicParameter(KaiserMusicTrack, 2f);
        }
        return Task.CompletedTask;
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        List<MonsterState> states = new();

        MoveState leftPunch = new("LEFT_PUNCH", LeftPunchMove, new SingleAttackIntent(LeftPunchDamage));
        MoveState alternatingJabs = new("ALTERNATING_JABS", AlternatingJabsMove, new MultiAttackIntent(JabDamage, JabTimes));
        MoveState frontSweep = new("FRONT_SWEEP", FrontSweepMove, new SingleAttackIntent(FrontSweepDamage), new DebuffIntent());
        MoveState mountainGuard = new("MOUNTAIN_GUARD", MountainGuardMove, new SingleAttackIntent(MountainGuardDamage), new DefendIntent());

        leftPunch.FollowUpState = alternatingJabs;
        alternatingJabs.FollowUpState = frontSweep;
        frontSweep.FollowUpState = mountainGuard;
        mountainGuard.FollowUpState = leftPunch;

        states.Add(leftPunch);
        states.Add(alternatingJabs);
        states.Add(frontSweep);
        states.Add(mountainGuard);

        return new MonsterMoveStateMachine(states, leftPunch);
    }

    private async Task LeftPunchMove(IReadOnlyList<Creature> targets)
    {
        await (Background?.PlayAttackAnim("leftpunch", 1.0f) ?? Task.CompletedTask);
        await DamageCmd.Attack(LeftPunchDamage)
            .FromMonster(this)
            .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_left_attack_slam")
            .Execute(null);
    }

    private async Task AlternatingJabsMove(IReadOnlyList<Creature> targets)
    {
        await (Background?.PlayAttackAnim("alternating_jabs", 0.8f) ?? Task.CompletedTask);
        await DamageCmd.Attack(JabDamage)
            .WithHitCount(JabTimes)
            .FromMonster(this)
            .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_left_attack_slam")
            .Execute(null);
    }

    private async Task FrontSweepMove(IReadOnlyList<Creature> targets)
    {
        await (Background?.PlayAttackAnim("front_sweep", 0.8f) ?? Task.CompletedTask);
        await DamageCmd.Attack(FrontSweepDamage)
            .FromMonster(this)
            .WithHitFx("vfx/vfx_attack_cleave", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_left_attack_scoop")
            .Execute(null);
        if (targets.Count > 0)
        {
            await PowerCmd.Apply<WeakPower>(new ThrowingPlayerChoiceContext(), targets, 2m, Creature, null);
        }
    }

    private async Task MountainGuardMove(IReadOnlyList<Creature> targets)
    {
        await (Background?.PlayAttackAnim("double_fist_crush", 0.8f) ?? Task.CompletedTask);
        await DamageCmd.Attack(MountainGuardDamage)
            .FromMonster(this)
            .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_left_attack_slam")
            .Execute(null);
        await CreatureCmd.GainBlock(Creature, (decimal)MountainGuardBlock, ValueProp.Move, null);
    }
}
