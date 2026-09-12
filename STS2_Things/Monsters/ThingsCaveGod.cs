using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Visuals;

namespace STS2_Things.Monsters;

/// <summary>
/// Cave God (山神) - Colossal subterranean stone deity.
/// Acts as the central master entity in CaveGodBossEncounter, driving
/// full-screen Spine animations via NCaveGodBossBackground in the scene.
/// </summary>
public sealed class ThingsCaveGod : MonsterModel
{
    private const string KaiserMusicTrack = "kaiser_crab_progress";

    private NCaveGodBossBackground? _background;
    private bool _enteredAngry;

    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_left_die";

    private NCaveGodBossBackground? Background
    {
        get
        {
            AssertMutable();
            if (_background == null)
            {
                _background = (NCombatRoom.Instance?.Background)?.GetNodeOrNull<NCaveGodBossBackground>("%CaveGod");
            }
            return _background;
        }
    }

    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 450, 420);
    public override int MaxInitialHp => MinInitialHp;

    private int CentralSlamDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 21, 18);
    private int FrontSweepDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 12, 10);
    private int JabDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 5, 4);
    private int JabTimes => 3;
    private int DoubleCrushDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 14, 12);
    private int DoubleCrushBlock => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 18, 15);
    private int GrabDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 9, 8);

    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        NRunMusicController.Instance?.UpdateMusicParameter(KaiserMusicTrack, 1f);
        Log.Info("[ThingsCaveGod] Cave God entered combat chamber.");
    }

    public override Task AfterCurrentHpChanged(Creature creature, decimal delta)
    {
        if (creature == Creature && delta < 0)
        {
            // 受击向后仰反馈
            Background?.PlayHitRecoil();

            // 半血狂暴形态切换
            if (Creature.CurrentHp <= Creature.MaxHp / 2m && !_enteredAngry)
            {
                _enteredAngry = true;
                Background?.SetAngry(true);
                NRunMusicController.Instance?.UpdateMusicParameter(KaiserMusicTrack, 3f);
                Log.Info("[ThingsCaveGod] Cave God entered ANGRY magma phase!");
            }
        }
        return Task.CompletedTask;
    }

    public override Task AfterDeath(PlayerChoiceContext choiceContext, Creature creature, bool wasRemovalPrevented, float deathAnimLength)
    {
        if (creature == Creature)
        {
            Background?.PlayDie();
            NRunMusicController.Instance?.UpdateMusicParameter(KaiserMusicTrack, 5f);
            Log.Info("[ThingsCaveGod] Cave God collapsed in victory.");
        }
        return Task.CompletedTask;
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        List<MonsterState> states = new();

        // 1. Central Slam (泰山压顶) - 单体强力震地
        MoveState centralSlam = new(
            "CENTRAL_SLAM",
            CentralSlamMove,
            new SingleAttackIntent(CentralSlamDamage)
        );

        // 2. Front Sweep (向心横扫) - 横扫贴地冲击
        MoveState frontSweep = new(
            "FRONT_SWEEP",
            FrontSweepMove,
            new SingleAttackIntent(FrontSweepDamage)
        );

        // 3. Alternating Jabs (交替重拳) - 3段连击
        MoveState alternatingJabs = new(
            "ALTERNATING_JABS",
            AlternatingJabsMove,
            new MultiAttackIntent(JabDamage, JabTimes)
        );

        // 4. Double Fist Crush (巨岩合击) - 攻击 + 格挡
        MoveState doubleCrush = new(
            "DOUBLE_FIST_CRUSH",
            DoubleCrushMove,
            new SingleAttackIntent(DoubleCrushDamage),
            new DefendIntent()
        );

        // 5. Grab Player (山神擒拿) - 攻击 + 易伤
        MoveState grabPlayer = new(
            "GRAB_PLAYER",
            GrabPlayerMove,
            new SingleAttackIntent(GrabDamage),
            new DebuffIntent()
        );

        // 循环链条
        centralSlam.FollowUpState = frontSweep;
        frontSweep.FollowUpState = alternatingJabs;
        alternatingJabs.FollowUpState = doubleCrush;
        doubleCrush.FollowUpState = grabPlayer;
        grabPlayer.FollowUpState = centralSlam;

        states.Add(centralSlam);
        states.Add(frontSweep);
        states.Add(alternatingJabs);
        states.Add(doubleCrush);
        states.Add(grabPlayer);

        return new MonsterMoveStateMachine(states, centralSlam);
    }

    private async Task CentralSlamMove(IReadOnlyList<Creature> targets)
    {
        Background?.PlayCentralSlam();
        await DamageCmd.Attack(CentralSlamDamage)
            .FromMonster(this)
            .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_attack_slam")
            .Execute(null);
    }

    private async Task FrontSweepMove(IReadOnlyList<Creature> targets)
    {
        Background?.PlayFrontSweep();
        await DamageCmd.Attack(FrontSweepDamage)
            .FromMonster(this)
            .WithHitFx("vfx/vfx_attack_cleave", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_left_attack_scoop")
            .Execute(null);
    }

    private async Task AlternatingJabsMove(IReadOnlyList<Creature> targets)
    {
        Background?.PlayAlternatingJabs();
        await DamageCmd.Attack(JabDamage)
            .WithHitCount(JabTimes)
            .FromMonster(this)
            .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_left_attack_slam")
            .Execute(null);
    }

    private async Task DoubleCrushMove(IReadOnlyList<Creature> targets)
    {
        Background?.PlayDoubleFistCrush();
        await DamageCmd.Attack(DoubleCrushDamage)
            .FromMonster(this)
            .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_attack_slam")
            .Execute(null);
        await CreatureCmd.GainBlock(Creature, (decimal)DoubleCrushBlock, ValueProp.Move, null);
    }

    private async Task GrabPlayerMove(IReadOnlyList<Creature> targets)
    {
        Background?.PlayGrabPlayer();
        await DamageCmd.Attack(GrabDamage)
            .FromMonster(this)
            .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_left_attack_scissor")
            .Execute(null);

        if (targets.Count > 0)
        {
            await PowerCmd.Apply<VulnerablePower>(new ThrowingPlayerChoiceContext(), targets, 2m, Creature, null);
        }
    }
}
