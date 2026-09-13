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
/// Right Hand / Right Arm entity of Cave God (山神·右臂).
/// Manages the right side HP bar, intents, and strikes in coordination with NCaveGodBossBackground.
/// </summary>
public sealed class ThingsCaveGodRightHand : MonsterModel
{
    private const string KaiserMusicTrack = "kaiser_crab_progress";
    private NCaveGodBossBackground? _background;
    private bool _enteredAngry;

    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_right_die";
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

    private ThingsCaveGodLeftHand? SiblingHand =>
        CombatState?.Enemies.Select(c => c.Monster).OfType<ThingsCaveGodLeftHand>().FirstOrDefault();

    private bool IsSiblingDead => SiblingHand?.Creature == null || !SiblingHand.Creature.IsAlive;
    private bool IsAngry => (Background?.IsAngry ?? false) || _enteredAngry;

    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 219, 209);
    public override int MaxInitialHp => MinInitialHp;

    private int CentralSlamDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 22, 19);
    private int GrabDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 8, 7);
    private int EarthquakeDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 15, 13);
    private int EarthquakeStrengthGain => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 3, 2);

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

        MoveState rest1 = new("REST_1", RestMove);
        MoveState centralSlam = new("CENTRAL_SLAM", CentralSlamMove, new SingleAttackIntent(CentralSlamDamage));
        MoveState rest2 = new("REST_2", RestMove);
        MoveState grabPlayer = new("GRAB_PLAYER", GrabPlayerMove, new SingleAttackIntent(GrabDamage), new DebuffIntent());
        MoveState rest3 = new("REST_3", RestMove);

        MoveState earthquake = new("EARTHQUAKE", EarthquakeMove, new SingleAttackIntent(EarthquakeDamage), new BuffIntent());
        MoveState centralSlam2 = new("CENTRAL_SLAM_2", CentralSlamMove, new SingleAttackIntent(CentralSlamDamage));

        ConditionalBranchState angryBranch = new("ANGRY_BRANCH");
        angryBranch.AddState(earthquake, () => IsAngry);
        angryBranch.AddState(centralSlam2, () => true);

        ConditionalBranchState branchAfterSlam = new("BRANCH_AFTER_SLAM");
        branchAfterSlam.AddState(grabPlayer, () => IsSiblingDead);
        branchAfterSlam.AddState(rest2, () => true);

        ConditionalBranchState branchAfterGrab = new("BRANCH_AFTER_GRAB");
        branchAfterGrab.AddState(angryBranch, () => IsSiblingDead);
        branchAfterGrab.AddState(rest3, () => true);

        ConditionalBranchState branchAfterSlot3 = new("BRANCH_AFTER_SLOT3");
        branchAfterSlot3.AddState(centralSlam, () => IsSiblingDead);
        branchAfterSlot3.AddState(rest1, () => true);

        rest1.FollowUpState = centralSlam;
        centralSlam.FollowUpState = branchAfterSlam;

        rest2.FollowUpState = grabPlayer;
        grabPlayer.FollowUpState = branchAfterGrab;

        rest3.FollowUpState = angryBranch;
        earthquake.FollowUpState = branchAfterSlot3;
        centralSlam2.FollowUpState = branchAfterSlot3;

        states.Add(rest1);
        states.Add(centralSlam);
        states.Add(branchAfterSlam);
        states.Add(rest2);
        states.Add(grabPlayer);
        states.Add(branchAfterGrab);
        states.Add(rest3);
        states.Add(angryBranch);
        states.Add(earthquake);
        states.Add(centralSlam2);
        states.Add(branchAfterSlot3);

        return new MonsterMoveStateMachine(states, rest1);
    }

    private static Task RestMove(IReadOnlyList<Creature> _) => Task.CompletedTask;


    private async Task CentralSlamMove(IReadOnlyList<Creature> targets)
    {
        try
        {
            Background?.StartAttackAnim("central_slam");

            // Windup: giant stone fists rise to apex and smash down onto center at t = 1.88s
            await Cmd.Wait(1.88f);
            await DamageCmd.Attack(CentralSlamDamage)
                .FromMonster(this)
                .WithHitFx("vfx/vfx_heavy_blunt", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_right_attack_slam")
                .Execute(null);
        }
        catch (Exception ex)
        {
            Log.Error($"[ThingsCaveGodRightHand] CentralSlamMove error: {ex}");
        }
    }

    private async Task GrabPlayerMove(IReadOnlyList<Creature> targets)
    {
        try
        {
            Background?.StartAttackAnim("grab_player");

            // Windup: stone hand reaches forward and clenches at t = 1.10s
            await Cmd.Wait(1.10f);
            await DamageCmd.Attack(GrabDamage)
                .FromMonster(this)
                .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_right_attack_snap")
                .Execute(null);

            if (targets != null && targets.Count > 0)
            {
                await PowerCmd.Apply<VulnerablePower>(new ThrowingPlayerChoiceContext(), targets, 2m, Creature, null);
            }
        }
        catch (Exception ex)
        {
            Log.Error($"[ThingsCaveGodRightHand] GrabPlayerMove error: {ex}");
        }
    }

    private async Task EarthquakeMove(IReadOnlyList<Creature> targets)
    {
        try
        {
            Background?.StartAttackAnim("earthquake");

            // Windup: first seismic shockwave erupts at t = 0.87s
            await Cmd.Wait(0.87f);
            await DamageCmd.Attack(EarthquakeDamage)
                .FromMonster(this)
                .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_right_attack_slam")
                .Execute(null);

            await PowerCmd.Apply<StrengthPower>(new ThrowingPlayerChoiceContext(), Creature, EarthquakeStrengthGain, Creature, null);
        }
        catch (Exception ex)
        {
            Log.Error($"[ThingsCaveGodRightHand] EarthquakeMove error: {ex}");
        }
    }
}
