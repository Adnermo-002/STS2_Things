using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Logging;
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

    private ThingsCaveGodRightHand? SiblingHand =>
        CombatState?.Enemies.Select(c => c.Monster).OfType<ThingsCaveGodRightHand>().FirstOrDefault();

    private bool IsSiblingDead => SiblingHand?.Creature == null || !SiblingHand.Creature.IsAlive;
    private bool IsAngry => (Background?.IsAngry ?? false) || _enteredAngry;

    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 219, 209);
    public override int MaxInitialHp => MinInitialHp;

    private int JabDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 5, 4);
    private int JabTimes => 3;
    private int FrontSweepDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 11, 10);
    private int MountainGuardDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 14, 12);
    private int MountainGuardBlock => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 16, 14);

    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        Background?.AlignStageAndPlayers();
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

        MoveState alternatingJabs = new("ALTERNATING_JABS", AlternatingJabsMove, new MultiAttackIntent(JabDamage, JabTimes));
        MoveState rest1 = new("REST_1", RestMove);
        MoveState frontSweep = new("FRONT_SWEEP", FrontSweepMove, new SingleAttackIntent(FrontSweepDamage), new DebuffIntent());
        MoveState rest2 = new("REST_2", RestMove);
        MoveState mountainGuard = new("MOUNTAIN_GUARD", MountainGuardMove, new SingleAttackIntent(MountainGuardDamage), new DefendIntent());
        MoveState rest3 = new("REST_3", RestMove);

        ConditionalBranchState branchAfterJabs = new("BRANCH_AFTER_JABS");
        branchAfterJabs.AddState(frontSweep, () => IsSiblingDead);
        branchAfterJabs.AddState(rest1, () => true);

        ConditionalBranchState branchAfterSweep = new("BRANCH_AFTER_SWEEP");
        branchAfterSweep.AddState(mountainGuard, () => IsSiblingDead);
        branchAfterSweep.AddState(rest2, () => true);

        ConditionalBranchState branchAfterGuard = new("BRANCH_AFTER_GUARD");
        branchAfterGuard.AddState(alternatingJabs, () => IsSiblingDead);
        branchAfterGuard.AddState(rest3, () => true);

        alternatingJabs.FollowUpState = branchAfterJabs;
        rest1.FollowUpState = frontSweep;

        frontSweep.FollowUpState = branchAfterSweep;
        rest2.FollowUpState = mountainGuard;

        mountainGuard.FollowUpState = branchAfterGuard;
        rest3.FollowUpState = alternatingJabs;

        states.Add(alternatingJabs);
        states.Add(branchAfterJabs);
        states.Add(rest1);
        states.Add(frontSweep);
        states.Add(branchAfterSweep);
        states.Add(rest2);
        states.Add(mountainGuard);
        states.Add(branchAfterGuard);
        states.Add(rest3);

        return new MonsterMoveStateMachine(states, alternatingJabs);
    }

    private static Task RestMove(IReadOnlyList<Creature> _) => Task.CompletedTask;


    private async Task AlternatingJabsMove(IReadOnlyList<Creature> targets)
    {
        try
        {
            Background?.StartAttackAnim("alternating_jabs");

            // Hit 1: Left jab impacts at t = 0.72s (calibrated from Spine bone sampling)
            await Cmd.Wait(0.72f);
            await DamageCmd.Attack(JabDamage)
                .FromMonster(this)
                .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_left_attack_slam")
                .Execute(null);

            // Hit 2: Right jab impacts at t = 1.40s (dt = 0.68s)
            await Cmd.Wait(0.68f);
            await DamageCmd.Attack(JabDamage)
                .FromMonster(this)
                .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_right_attack_slam")
                .Execute(null);

            // Hit 3: Finisher double slam impacts at t = 2.42s (dt = 1.02s)
            await Cmd.Wait(1.02f);
            await DamageCmd.Attack(JabDamage)
                .FromMonster(this)
                .WithHitFx("vfx/vfx_heavy_blunt", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_left_attack_slam")
                .Execute(null);
        }
        catch (Exception ex)
        {
            Log.Error($"[ThingsCaveGodLeftHand] AlternatingJabsMove error: {ex}");
        }
    }

    private async Task FrontSweepMove(IReadOnlyList<Creature> targets)
    {
        try
        {
            Background?.StartAttackAnim("front_sweep");

            // Windup: sweeping arm strikes center at t = 1.35s
            await Cmd.Wait(1.35f);
            await DamageCmd.Attack(FrontSweepDamage)
                .FromMonster(this)
                .WithHitFx("vfx/vfx_giant_horizontal_slash", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_left_attack_scoop")
                .Execute(null);

            if (targets != null && targets.Count > 0)
            {
                await PowerCmd.Apply<WeakPower>(new ThrowingPlayerChoiceContext(), targets, 2m, Creature, null);
            }
        }
        catch (Exception ex)
        {
            Log.Error($"[ThingsCaveGodLeftHand] FrontSweepMove error: {ex}");
        }
    }

    private async Task MountainGuardMove(IReadOnlyList<Creature> targets)
    {
        try
        {
            Background?.StartAttackAnim("double_fist_crush");

            // Windup: both fists crush inward meeting at t = 1.35s (calibrated from Spine bone sampling)
            await Cmd.Wait(1.35f);
            await DamageCmd.Attack(MountainGuardDamage)
                .FromMonster(this)
                .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_left_attack_slam")
                .Execute(null);

            await CreatureCmd.GainBlock(Creature, (decimal)MountainGuardBlock, ValueProp.Move, null);
        }
        catch (Exception ex)
        {
            Log.Error($"[ThingsCaveGodLeftHand] MountainGuardMove error: {ex}");
        }
    }
}
