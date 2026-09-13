using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Bestiary;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Cards;
using STS2_Things.Encounters;
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
    private bool _handBroken;

    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Stone;
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_knockout";
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
    private int AirSlamDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 24, 21);
    private int EarthquakeDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 15, 13);
    private int EarthquakeStrengthGain => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 3, 2);

    public void OnHandBroken()
    {
        _handBroken = true;
        Log.Info("[ThingsCaveGodRightHand] Claw shattered! Next AirSlam will miss/stun.");
    }

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
        MoveState airSlam = new("AIR_SLAM", AirSlamMove, new SingleAttackIntent(AirSlamDamage));
        MoveState rest4 = new("REST_4", RestMove);

        MoveState earthquake = new("EARTHQUAKE", EarthquakeMove, new SingleAttackIntent(EarthquakeDamage), new BuffIntent());
        MoveState centralSlam2 = new("CENTRAL_SLAM_2", CentralSlamMove, new SingleAttackIntent(CentralSlamDamage));

        ConditionalBranchState angryBranch = new("ANGRY_BRANCH");
        angryBranch.AddState(earthquake, () => IsAngry);
        angryBranch.AddState(centralSlam2, () => true);

        ConditionalBranchState branchAfterSlam = new("BRANCH_AFTER_SLAM");
        branchAfterSlam.AddState(grabPlayer, () => IsSiblingDead);
        branchAfterSlam.AddState(rest2, () => true);

        ConditionalBranchState branchAfterGrab = new("BRANCH_AFTER_GRAB");
        branchAfterGrab.AddState(airSlam, () => IsSiblingDead);
        branchAfterGrab.AddState(rest3, () => true);

        ConditionalBranchState branchAfterAirSlam = new("BRANCH_AFTER_AIR_SLAM");
        branchAfterAirSlam.AddState(angryBranch, () => IsSiblingDead);
        branchAfterAirSlam.AddState(rest4, () => true);

        ConditionalBranchState branchAfterSlot3 = new("BRANCH_AFTER_SLOT3");
        branchAfterSlot3.AddState(centralSlam, () => IsSiblingDead);
        branchAfterSlot3.AddState(rest1, () => true);

        rest1.FollowUpState = centralSlam;
        centralSlam.FollowUpState = branchAfterSlam;

        rest2.FollowUpState = grabPlayer;
        grabPlayer.FollowUpState = branchAfterGrab;

        rest3.FollowUpState = airSlam;
        airSlam.FollowUpState = branchAfterAirSlam;

        rest4.FollowUpState = angryBranch;
        earthquake.FollowUpState = branchAfterSlot3;
        centralSlam2.FollowUpState = branchAfterSlot3;

        states.Add(rest1);
        states.Add(centralSlam);
        states.Add(branchAfterSlam);
        states.Add(rest2);
        states.Add(grabPlayer);
        states.Add(branchAfterGrab);
        states.Add(rest3);
        states.Add(airSlam);
        states.Add(branchAfterAirSlam);
        states.Add(rest4);
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

            // Windup: giant stone fists rise to apex and smash down onto center at t = 1.98s
            await Cmd.Wait(1.98f);
            await DamageCmd.Attack(CentralSlamDamage)
                .FromMonster(this)
                .WithHitFx("vfx/vfx_heavy_blunt", "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_stomp")
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
            _handBroken = false;
            Background?.StartAttackAnim("grab_player");

            // 1. Hand reaches forward and grasps at t = 1.15s
            await Cmd.Wait(1.15f);
            await DamageCmd.Attack(GrabDamage)
                .FromMonster(this)
                .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_kick")
                .Execute(null);

            if (targets != null && targets.Count > 0)
            {
                await PowerCmd.Apply<VulnerablePower>(new ThrowingPlayerChoiceContext(), targets, 2m, Creature, null);
            }

            // 2. Hand lifts players up into the air (0.70s lift tween to apex)
            if (Background != null && targets != null)
            {
                await Background.LiftPlayersToAir(targets, 0.70f);
                Background.HoldGrabAnim();
            }

            // 3. Spawn 30 HP Captive Claw at captive_hand slot
            if (CombatState != null && CombatState.IsLiveCombat())
            {
                await CreatureCmd.Add<ThingsCaveGodCaptiveClaw>(CombatState, CaveGodBossEncounter.CaptiveHandSlot);
            }

            // 4. Knowledge Demon two-card choice screen for all player targets
            if (targets != null)
            {
                List<Task> choiceTasks = new();
                foreach (Creature target in targets)
                {
                    if (target.Player != null && target.IsAlive)
                    {
                        choiceTasks.Add(ChooseTrial(target));
                    }
                }
                if (choiceTasks.Count > 0)
                {
                    await Task.WhenAll(choiceTasks);
                }
            }
        }
        catch (Exception ex)
        {
            Log.Error($"[ThingsCaveGodRightHand] GrabPlayerMove error: {ex}");
            Background?.RestoreCapturedPlayersInstantly();
        }
    }

    private async Task ChooseTrial(Creature target)
    {
        if (target.IsDead || target.Player == null || CombatState == null) return;

        List<CardModel> cards =
        [
            CombatState.CreateCard(ModelDb.Card<CaveGodMartialTrial>(), target.Player),
            CombatState.CreateCard(ModelDb.Card<CaveGodArcaneTrial>(), target.Player)
        ];

        CardModel? chosen = await CardSelectCmd.FromChooseACardScreen(new BlockingPlayerChoiceContext(), cards, target.Player);
        if (chosen is KnowledgeDemon.IChoosable choosable)
        {
            await choosable.OnChosen();
        }
    }

    private async Task AirSlamMove(IReadOnlyList<Creature> targets)
    {
        try
        {
            // Check if captive claw is still alive
            Creature? captiveCreature = CombatState?.Enemies.FirstOrDefault(c => c.Monster is ThingsCaveGodCaptiveClaw);

            if (_handBroken || captiveCreature == null || !captiveCreature.IsAlive)
            {
                // Broken claw branch: slam is aborted! Boss is stunned/recoiling!
                Log.Info("[ThingsCaveGodRightHand] AirSlam aborted because claw was broken!");
                Background?.PlayHurtAnim();
                await Cmd.Wait(0.8f);

                if (captiveCreature != null && captiveCreature.IsAlive)
                {
                    await CreatureCmd.Kill(captiveCreature, force: true);
                }
                Background?.RestoreCapturedPlayersInstantly();
                return;
            }

            // Unbroken claw branch: giant hand resumes downward slam from apex (dt = 0.80s)
            Background?.ResumeSlamAnim();
            await Cmd.Wait(0.80f);

            // At impact: slam players down to stage with violent expo ease
            if (Background != null)
            {
                await Background.DropPlayersToGround(isSlam: true);
            }

            NAudioManager.Instance?.PlayOneShot("event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_stomp");
            await DamageCmd.Attack(AirSlamDamage)
                .FromMonster(this)
                .WithHitFx("vfx/vfx_heavy_blunt", "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_stomp")
                .Execute(null);

            // Remove captive claw
            if (captiveCreature != null && captiveCreature.IsAlive)
            {
                await CreatureCmd.Kill(captiveCreature, force: true);
            }
        }
        catch (Exception ex)
        {
            Log.Error($"[ThingsCaveGodRightHand] AirSlamMove error: {ex}");
            Background?.RestoreCapturedPlayersInstantly();
        }
    }

    private async Task EarthquakeMove(IReadOnlyList<Creature> targets)
    {
        try
        {
            Background?.StartAttackAnim("earthquake");

            // Windup: first seismic shockwave erupts at t = 0.90s
            await Cmd.Wait(0.90f);
            await DamageCmd.Attack(EarthquakeDamage)
                .FromMonster(this)
                .WithHitFx("vfx/vfx_heavy_blunt", "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_eruption")
                .Execute(null);

            await PowerCmd.Apply<StrengthPower>(new ThrowingPlayerChoiceContext(), Creature, EarthquakeStrengthGain, Creature, null);
        }
        catch (Exception ex)
        {
            Log.Error($"[ThingsCaveGodRightHand] EarthquakeMove error: {ex}");
        }
    }
}
