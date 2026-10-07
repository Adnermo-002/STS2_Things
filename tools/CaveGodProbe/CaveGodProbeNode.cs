using System;
using System.Collections;
using System.Reflection;
using System.Runtime.Loader;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Monsters;
using STS2_Things.Encounters;
using STS2_Things.Powers;
using STS2_Things.Cards;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Visuals;

public partial class CaveGodProbeNode : Node
{
    private static readonly Assembly ImplementationAssembly = typeof(STS2_ThingsInit).Assembly;
    public override void _Ready() => _ = Run();
    private async Task Run()
    {
        try
        {
            TestMode.TurnOnInternal();
            string root = Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "../.."));
            ProjectSettings.LoadResourcePack("D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck");
            ProjectSettings.LoadResourcePack(System.Environment.GetEnvironmentVariable("THINGS_PROBE_PCK")
                ?? Path.Combine(root, "build/v111/STS2_Things.pck"));
            string? overlay=System.Environment.GetEnvironmentVariable("THINGS_PROBE_OVERLAY_PCK");
            if(!string.IsNullOrWhiteSpace(overlay))Assert(ProjectSettings.LoadResourcePack(overlay),"Recovery overlay mounted.");
            try
            {
                SaveManager.Instance.InitSettingsDataForTest();
                SaveManager.Instance.SettingsSave.Language = "eng";
                LocManager.Initialize();
            }
            catch (Exception ex)
            {
                GD.PrintErr($"LocManager.Initialize failed: {ex}");
            }
            InitializeModelDb();
            EnsureScriptsLookedUp();
            if (OS.GetCmdlineUserArgs().Contains("--ui-art-review"))
            {
                await RenderCaveGodUiArt();
                GetTree().Quit(0);
                return;
            }
            if (OS.GetCmdlineUserArgs().Contains("--crossroads-ui"))
            {
                await VerifyCrossroadUi();
                GetTree().Quit(0);
                return;
            }
            if (OS.GetCmdlineUserArgs().Contains("--crossroads"))
            {
                await VerifyCrossroads();
                GetTree().Quit(0);
                return;
            }
            if (OS.GetCmdlineUserArgs().Contains("--scale-beetle-actions"))
            {
                await VerifyBeetleActions();
                GetTree().Quit(0);
                return;
            }
            if (OS.GetCmdlineUserArgs().Contains("--fogmog-preview"))
            {
                await RenderFogmogPreview();
                GetTree().Quit(0);
                return;
            }
            if (OS.GetCmdlineUserArgs().Contains("--fogmog-actions"))
            {
                await VerifyFogmogActions();
                GetTree().Quit(0);
                return;
            }
            if (OS.GetCmdlineUserArgs().Contains("--action-regression"))
            {
                await VerifyActionRegression();
                GetTree().Quit(0);
                return;
            }
            if (OS.GetCmdlineUserArgs().Contains("--ui-regression"))
            {
                await VerifyUiRegression();
                GetTree().Quit(0);
                return;
            }
            if (OS.GetCmdlineUserArgs().Contains("--visual"))
            {
                await VerifyRenderedResources();
                GetTree().Quit(0);
                return;
            }
            if (OS.GetCmdlineUserArgs().Contains("--render-official-rooms"))
            {
                await RenderOfficialRooms();
                GetTree().Quit(0);
                return;
            }
            await VerifyDefeatCleanse();
            await VerifyCleanseAndRecovery();
            await VerifyCyclesAndIntents();
            await VerifyPhaseScaling();
            await VerifyCapture(escape: true);
            await VerifyCapture(escape: false);
            await VerifyCaptureInterrupted();
            await VerifyEnemyTurnBreak();
            await VerifyFinalDefeat();
            await VerifyPoisonAndThorns();
            await VerifyNativeStunAndForcedDeath();
            await VerifyTransitionPoisonAndGrowth();
            await VerifyRepeatedBreakGrowth();
            await VerifyStunnedArmGrowth();
            await VerifyWeakPhaseSurvivingArmFlow();
            await VerifyAgingPowerAndStoneArmor();
            await VerifyPhaseTransitionClearsArmStrength();
            await VerifyCrystalVeinAndBurst();
            await VerifyArmBreakDrainsVein();
            await VerifyFissure(breakBeforeRecoverRoll: false);
            await VerifyFissure(breakBeforeRecoverRoll: true);
            await VerifySweepCardTheft();
            await VerifyHandLayoutAndZIndex();
            GD.Print("CaveGod behavior probe: PASS");
            GetTree().Quit(0);
        }
        catch (Exception ex) { GD.PushError(ex.ToString()); GetTree().Quit(1); }
        finally { DeactivateSyntheticCombat(); }
    }
    private sealed record Fixture(CombatState State, ThingsCaveGodBody Body, ThingsCaveGodLeftHand Left, ThingsCaveGodRightHand Right);
    private static Fixture Scenario(int count = 1, int ascension = 0, bool mixedCharacters = false)
    {
        var players = Enumerable.Range(1, count).Select(i => !mixedCharacters ? Player.CreateForNewRun<Ironclad>(UnlockState.all, (ulong)i) : i switch
        {
            2 => Player.CreateForNewRun<Silent>(UnlockState.all, (ulong)i),
            3 => Player.CreateForNewRun<Regent>(UnlockState.all, (ulong)i),
            4 => Player.CreateForNewRun<Defect>(UnlockState.all, (ulong)i),
            _ => Player.CreateForNewRun<Ironclad>(UnlockState.all, (ulong)i),
        }).ToArray();
        var run = RunState.CreateForTest(players, seed: "cavegod-regression", ascensionLevel: ascension);
        typeof(RunManager).GetProperty("State", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(RunManager.Instance, run);
        typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance, new AscensionManager(ascension));
        var room = new CombatRoom(ModelDb.Encounter<CaveGodBossEncounter>().ToMutable(), run);
        run.PushRoom(room);
        foreach (var player in players)
        {
            player.ResetCombatState(); room.CombatState.AddPlayer(player);
            player.Creature.SetMaxHpInternal(10000); player.Creature.SetCurrentHpInternal(10000);
        }
        var left = Add<ThingsCaveGodLeftHand>(room.CombatState, CaveGodBossEncounter.LeftHandSlot);
        var right = Add<ThingsCaveGodRightHand>(room.CombatState, CaveGodBossEncounter.RightHandSlot);
        var body = Add<ThingsCaveGodBody>(room.CombatState, CaveGodBossEncounter.BodySlot);
        ActivateSyntheticCombat(room.CombatState);
        left.EnsureAgingPower().GetAwaiter().GetResult();
        right.EnsureAgingPower().GetAwaiter().GetResult();
        return new Fixture(room.CombatState, body, left, right);
    }
    private static T Add<T>(CombatState state, string slot) where T : MonsterModel
    {
        var monster = (T)ModelDb.Monster<T>().ToMutable();
        var creature = state.CreateCreature(monster, CombatSide.Enemy, slot);
        state.AddCreature(creature);
        monster.SetUpForCombat();
        monster.RollMove(state.PlayerCreatures);
        return monster;
    }
    private static async Task VerifyDefeatCleanse()
    {
        var s = Scenario();
        var choice = new ThrowingPlayerChoiceContext();
        await PowerCmd.Apply<PoisonPower>(choice, s.Left.Creature, 9m, s.State.Players[0].Creature, null);
        await CreatureCmd.Damage(choice, s.Left.Creature, 10000m, MegaCrit.Sts2.Core.ValueProps.ValueProp.Unpowered | MegaCrit.Sts2.Core.ValueProps.ValueProp.Unblockable, s.State.Players[0].Creature);
        Assert(!s.Left.Creature.HasPower<PoisonPower>(), "Defeated arm retains Poison (regression).");
        Assert(s.Body.IsWeakPhase, "Breaking an arm must expose the core.");
        GD.Print("PASS defeated arm clears poison");
    }
    private static readonly ThrowingPlayerChoiceContext Choice = new();
    private static Task Hit(Fixture s, Creature target, decimal amount = 10000m) =>
        CreatureCmd.Damage(Choice, target, amount, ValueProp.Unpowered | ValueProp.Unblockable, s.State.Players[0].Creature);
    private static async Task Act(Fixture s)
    {
        s.State.CurrentSide = CombatSide.Enemy;
        await Hook.BeforeSideTurnStart(s.State, CombatSide.Enemy, s.State.Enemies.ToArray());
        foreach (var enemy in s.State.Enemies.ToList())
            if (enemy.IsAlive && enemy.Monster != null) await enemy.Monster.PerformMove();
        await Hook.AfterSideTurnEnd(s.State, CombatSide.Enemy, s.State.Enemies.ToArray());
        s.State.CurrentSide = CombatSide.Player;
        await Hook.BeforeSideTurnStart(s.State, CombatSide.Player, s.State.PlayerCreatures);
        foreach (var enemy in s.State.Enemies.ToList())
            if (enemy.IsAlive) enemy.Monster!.RollMove(s.State.PlayerCreatures);
        await Hook.AfterSideTurnStart(s.State, CombatSide.Player, s.State.PlayerCreatures);
    }
    private static async Task Phase2(Fixture s)
    {
        await Hit(s, s.Left.Creature);
        await Hit(s, s.Body.Creature);
        Assert(s.Body.IsPhaseTransitionPending, "Lethal core hit must schedule rebirth.");
        await Act(s);
        Assert(s.Body.Phase == 2 && s.Body.NextMove.Id == "DOUBLE_FIST_CRUSH", "Phase two must start with crush, not skip a turn.");
    }
    private static async Task VerifyCleanseAndRecovery()
    {
        foreach (bool breakLeft in new[] { true, false })
        {
            var s = Scenario();
            ThingsCaveGodHand broken = breakLeft ? s.Left : s.Right;
            ThingsCaveGodHand survivor = breakLeft ? s.Right : s.Left;
            await PowerCmd.Apply<StrengthPower>(Choice, broken.Creature, 4m, broken.Creature, null);
            await PowerCmd.Apply<WeakPower>(Choice, broken.Creature, 3m, s.State.Players[0].Creature, null);
            await PowerCmd.Apply<VulnerablePower>(Choice, broken.Creature, 3m, s.State.Players[0].Creature, null);
            await PowerCmd.Apply<PoisonPower>(Choice, broken.Creature, 9m, s.State.Players[0].Creature, null);
            await Hit(s, broken.Creature);
            Assert(!broken.Creature.Powers.Any(p => p.TypeForCurrentAmount == MegaCrit.Sts2.Core.Entities.Powers.PowerType.Debuff), "Defeat leaves a debuff.");
            Assert(broken.Creature.GetPowerAmount<StrengthPower>() == 4, "Defeat must preserve positive strength.");
            Assert(!broken.ShouldAllowTargeting(broken.Creature) && s.Body.ShouldAllowTargeting(s.Body.Creature), "Exposure targeting mismatch.");
            await Act(s);
            Assert(s.Body.NextMove.Id == "WEAK_PRONE_2", "Exposure turn 2 skipped.");
            Assert(survivor.NextMove.Id == ThingsCaveGodHand.MoveId(ThingsCaveGodHand.Action.WeakAttack), "Surviving arm must advertise weak attack on exposure turn 2.");
            Assert(!survivor.NextMove.Intents.OfType<StunIntent>().Any(), "Surviving arm must NOT be stunned on exposure turn 2 (no consecutive stun).");
            Assert(survivor.NextMove.Intents.OfType<AttackIntent>().Any(), "Surviving arm must have attack intent on exposure turn 2.");
            await PowerCmd.Apply<StrengthPower>(Choice, survivor.Creature, -4m, s.State.Players[0].Creature, null);
            await PowerCmd.Apply<DoomPower>(Choice, survivor.Creature, 2m, s.State.Players[0].Creature, null);
            await Hit(s, survivor.Creature);
            Assert(!survivor.Creature.HasPower<StrengthPower>() && !survivor.Creature.HasPower<DoomPower>(), "Negative strength/Doom not cleansed.");
            Assert(survivor.NextMove.Intents.Any(i => i is StunIntent) && survivor.NextMove.Intents.Any(i => i is HealIntent), "Stun+heal intent missing.");
            int before = s.State.Players[0].Creature.CurrentHp;
            await Act(s);
            Assert(survivor.Creature.CurrentHp == survivor.Creature.MaxHp, "Stunned arm did not heal to full.");
            Assert(s.State.Players[0].Creature.CurrentHp == before, "Stunned arm unexpectedly attacks.");
            Assert(s.Body.NextMove.Id == "WEAK_UNKNOWN_3" && survivor.NextMove.Intents.OfType<AttackIntent>().Any(), "Exposure turn 3 must advertise surviving arm attack.");
            await Act(s);
            Assert(!s.Body.IsWeakPhase && s.Body.NextMove.Id == "ALTERNATING_JABS", "Three turns must restore the interrupted move.");
            Assert(s.Left.Creature.CurrentHp == s.Left.Creature.MaxHp && s.Right.Creature.CurrentHp == s.Right.Creature.MaxHp, "Recovery failed.");
            Assert(s.Left.ShouldAllowTargeting(s.Left.Creature) && s.Right.ShouldAllowTargeting(s.Right.Creature), "Arms remain untargetable after recovery.");
            DeactivateSyntheticCombat();
        }
        GD.Print("PASS both arms: cleanse, retain buffs, negative Strength/Doom, stun/heal, three-window recovery");
    }
    private static async Task VerifyCyclesAndIntents()
    {
        foreach (int ascension in new[] { 0, 10 })
        {
            var s = Scenario(ascension: ascension);
            // Four cycle moves fill the Crystal Vein; Crystal Burst then takes the fifth slot.
            string[] sequence = ["ALTERNATING_JABS", "P1_REST_SWEEP", "CENTRAL_SLAM", "MOUNTAIN_GUARD", ThingsCaveGodBody.BurstId];
            for (int turn = 0; turn < 15; turn++)
            {
                Assert(s.Body.NextMove.Id == sequence[turn % 5], $"Normal loop drift at turn {turn}: {s.Body.NextMove.Id}.");
                var attackers = s.State.Enemies.Where(c => c.Monster!.NextMove.Intents.OfType<AttackIntent>().Any()).ToArray();
                Assert(attackers.Length == 1, "Expected exactly one advertised attacker.");
                var attacker = attackers[0];
                int expected = attacker.Monster!.NextMove.Intents.OfType<AttackIntent>().Sum(i => i.GetTotalDamage(s.State.PlayerCreatures, attacker));
                int hp = s.State.Players[0].Creature.CurrentHp;
                await Act(s);
                Assert(hp - s.State.Players[0].Creature.CurrentHp == expected, "Actual damage differs from visible intent.");
                int strength = (turn + 1) / 5 * (ascension == 0 ? 2 : 3);
                foreach (var owner in new[] { s.Body.Creature, s.Left.Creature, s.Right.Creature })
                    Assert(owner.GetPowerAmount<StrengthPower>() == strength, "Strength growth must occur once per Crystal Burst.");
                int vein = (turn + 1) % 5;
                Assert(s.Body.CrystalVein == vein, $"Crystal Vein expected {vein}, got {s.Body.CrystalVein}.");
                foreach (var arm in new[] { s.Left.Creature, s.Right.Creature })
                    Assert(arm.GetPowerAmount<ThingsCaveGodCrystalVeinPower>() == vein, "Arm must mirror the body's Crystal Vein.");
            }
            DeactivateSyntheticCombat();
        }
        // Give body and arm different modifiers to catch the old proxy-damage mismatch.
        var mismatch = Scenario();
        for (int turn = 0; turn < 4; turn++) await Act(mismatch);
        await PowerCmd.Apply<WeakPower>(Choice, mismatch.Left.Creature, 4m, mismatch.State.Players[0].Creature, null);
        var intent = mismatch.Body.NextMove.Intents.OfType<AttackIntent>().Single();
        int advertised = intent.GetTotalDamage(mismatch.State.PlayerCreatures, mismatch.Body.Creature);
        int health = mismatch.State.Players[0].Creature.CurrentHp;
        await Act(mismatch);
        Assert(health - mismatch.State.Players[0].Creature.CurrentHp == advertised, "Body attacks use arm modifiers.");
        GD.Print("PASS 30 normal turns at A0/A10, burst every 5th slot, exact intent damage, +2/+3 growth per burst, vein mirrored");
    }
    private static async Task VerifyPhaseScaling()
    {
        foreach (int count in new[] { 1, 2, 4 })
        foreach (int ascension in new[] { 0, 10 })
        {
            var s = Scenario(count, ascension);
            await Phase2(s);
            int Scale(int hp) => (int)Creature.ScaleHpForMultiplayer(hp, s.State.Encounter, count, s.State.RunState.CurrentActIndex);
            Assert(s.Body.Creature.MaxHp == Scale(ascension == 0 ? 200 : 215), "P2 core loses multiplayer scaling.");
            Assert(s.Left.Creature.MaxHp == Scale(ascension == 0 ? 80 : 90) && s.Right.Creature.MaxHp == s.Left.Creature.MaxHp, "P2 arms lose scaling.");
            DeactivateSyntheticCombat();
        }
        GD.Print("PASS P2 HP and opening move at 1/2/4 players and A0/A10");
    }
    private static async Task StartCapture(Fixture s)
    {
        await Act(s); // crush -> grab
        var selector = new TestCardSelector();
        for (int i = 0; i < s.State.Players.Count; i++) selector.PrepareToSelect(new[] { i % 2 });
        using (CardSelectCmd.UseSelector(selector))
        {
            await Act(s);
            Assert(s.State.PlayerCreatures.All(c => c.HasPower<CaveGodPendingTrialPower>()),
                "Capture must defer each player's trial until their opening draw has completed.");
            foreach (var player in s.State.Players)
                await Hook.AfterPlayerTurnStart(s.State, new BlockingPlayerChoiceContext(), player);
        }
        Assert(s.State.Enemies.Count(c => c.Monster is ThingsCaveGodCaptiveClaw) == 1, "Capture must create exactly one claw.");
        for (int i = 0; i < s.State.Players.Count; i++)
            Assert(i % 2 == 0 ? s.State.Players[i].Creature.HasPower<CaveGodBrokenBladePower>() : s.State.Players[i].Creature.HasPower<CaveGodShatteredShieldPower>(), "Trial assigned to wrong player.");
    }
    private static async Task VerifyCapture(bool escape)
    {
        var s = Scenario(2);
        await Phase2(s);
        for (int cycle = 0; cycle < 2; cycle++)
        {
            await StartCapture(s);
            ThingsCaveGodHand grabber = s.Left.IsGrabbing ? s.Left : s.Right;
            Assert(grabber.IsLeft == (cycle == 0), "Lead hand should alternate after each completed cycle.");
            if (escape)
            {
                await Hit(s, s.State.Enemies.Single(c => c.Monster is ThingsCaveGodCaptiveClaw));
                Assert(grabber.NextMove.Intents.Any(i => i is StunIntent), "Breaking claw must stun grabber.");
            }
            int hp = s.State.Players[0].Creature.CurrentHp;
            await Act(s);
            Assert(escape ? s.State.Players[0].Creature.CurrentHp == hp : s.State.Players[0].Creature.CurrentHp < hp, "Broken claw causes hidden hit or intact claw fails to slam.");
            Assert(!s.State.Enemies.Any(c => c.Monster is ThingsCaveGodCaptiveClaw), "Claw survived resolution.");
            Assert(!s.Left.IsGrabbing && !s.Right.IsGrabbing, "Capture flag survived resolution.");
            Assert(s.State.PlayerCreatures.All(c => !c.HasPower<CaveGodPendingTrialPower>() &&
                !c.HasPower<CaveGodBrokenBladePower>() && !c.HasPower<CaveGodShatteredShieldPower>()), "Trial powers survived resolution.");
            Assert(s.Body.NextMove.Id == "P2_CENTRAL_SLAM", "Escape/throw skips next move.");
            await Act(s); // angry slam fills the vein -> crystal burst
            Assert(s.Body.NextMove.Id == ThingsCaveGodBody.BurstId, "P2 cycle must end in Crystal Burst.");
            await Act(s); // burst + growth -> crush
        }
        GD.Print($"PASS both-hand capture, owner-specific choices, escape={escape}, cleanup and next move");
    }
    private static async Task VerifyCaptureInterrupted()
    {
        var s = Scenario();
        await Phase2(s);
        await StartCapture(s);
        await Hit(s, s.Right.Creature);
        Assert(s.Body.IsWeakPhase && !s.Left.IsGrabbing, "Breaking support arm must interrupt grab.");
        Assert(!s.State.Enemies.Any(c => c.Monster is ThingsCaveGodCaptiveClaw), "Orphan claw after exposure.");
        await Act(s); await Act(s); await Act(s);
        Assert(s.Body.NextMove.Id == "P2_CENTRAL_SLAM", "Recovery resumes a slam with no captives.");
        GD.Print("PASS mid-capture support break cleans up and skips obsolete throw");
    }
    private static async Task VerifyEnemyTurnBreak()
    {
        var s = Scenario();
        s.State.CurrentSide = CombatSide.Enemy;
        await Hit(s, s.Left.Creature);
        await Act(s);
        Assert(s.Body.NextMove.Id == "WEAK_PRONE_1", "Enemy-turn defeat consumes a player exposure window.");
        await Act(s); await Act(s); await Act(s);
        Assert(!s.Body.IsWeakPhase, "Deferred exposure never ends.");
        GD.Print("PASS enemy-turn defeat grants three complete player windows");
    }
    private static async Task VerifyFinalDefeat()
    {
        var s = Scenario();
        await Phase2(s); await StartCapture(s);
        await Hit(s, s.Right.Creature);
        await Hit(s, s.Body.Creature);
        Assert(s.Body.IsDefeated && !s.Body.ShouldStopCombatFromEnding(), "Final core defeat must allow victory.");
        Assert(!s.State.Enemies.Any(c => c.IsAlive), "Living boss part remains after victory.");
        GD.Print("PASS final defeat kills parts and clears capture");
    }

    private static async Task VerifyPoisonAndThorns()
    {
        foreach (bool left in new[] { true, false })
        {
            var s = Scenario();
            var hand = left ? s.Left.Creature : s.Right.Creature;
            await PowerCmd.Apply<PoisonPower>(Choice, hand, 100m, s.State.Players[0].Creature, null);
            s.State.CurrentSide = CombatSide.Enemy;
            await hand.GetPower<PoisonPower>()!.Trigger();
            Assert(!hand.HasPower<PoisonPower>() && s.Body.IsWeakPhase, "Lethal poison tick fails to cleanse itself.");
            DeactivateSyntheticCombat();
        }
        var thorns = Scenario();
        await Act(thorns); // sweep next
        await PowerCmd.Apply<ThornsPower>(Choice, thorns.State.Players[0].Creature, 100m, thorns.State.Players[0].Creature, null);
        await Act(thorns);
        Assert(thorns.Body.IsWeakPhase && thorns.Body.NextMove.Id == "WEAK_PRONE_1", "Real thorns break did not defer exposure window.");
        GD.Print("PASS real lethal Poison hook and retaliatory Thorns defeat");
    }
    private static async Task VerifyNativeStunAndForcedDeath()
    {
        var s = Scenario(); await Phase2(s); await StartCapture(s);
        await CreatureCmd.Stun(s.Left.Creature);
        Assert(s.Left.NextMove.Intents.Any(i => i is StunIntent), "Native stun was blocked by arm move flags.");
        int hp = s.State.Players[0].Creature.CurrentHp;
        await Act(s);
        Assert(s.State.Players[0].Creature.CurrentHp == hp && !s.Left.IsGrabbing, "Native stun leaves an active capture or unseen attack.");
        Assert(!s.State.Enemies.Any(c => c.Monster is ThingsCaveGodCaptiveClaw), "Native stun leaves a claw.");
        var forced = Scenario();
        await CreatureCmd.Kill(forced.Body.Creature, force: true);
        Assert(forced.Body.IsDefeated && !forced.Body.ShouldStopCombatFromEnding() && forced.State.Enemies.All(c => c.IsDead), "Forced P1 removal leaves immortal parts.");
        GD.Print("PASS native stun cancels capture; forced death cannot softlock encounter");
    }

    private static async Task VerifyTransitionPoisonAndGrowth()
    {
        var s = Scenario();
        for (int i = 0; i < 5; i++) await Act(s); // four moves + Crystal Burst growth
        await PowerCmd.Apply<PoisonPower>(Choice, s.Right.Creature, 999m, s.State.Players[0].Creature, null);
        await Hit(s, s.Left.Creature);
        await Hit(s, s.Body.Creature);
        int hp = s.Right.Creature.CurrentHp;
        await s.Right.Creature.GetPower<PoisonPower>()!.Trigger();
        Assert(s.Right.Creature.CurrentHp == hp && s.State.Enemies.Contains(s.Right.Creature), "Poison kills a disabled arm during rebirth.");
        await Act(s);
        Assert(s.Body.Creature.GetPowerAmount<StrengthPower>() == 2, "Body retains growth across phases.");
        Assert(s.Body.CrystalVein == 0 && !s.Right.Creature.HasPower<ThingsCaveGodCrystalVeinPower>(), "Phase transition must drain the Crystal Vein.");
        Assert(!s.Left.Creature.HasPower<StrengthPower>(), "Phase transition must clear left arm Strength.");
        Assert(!s.Right.Creature.HasPower<StrengthPower>(), "Phase transition must clear right arm Strength.");
        Assert(!s.Right.Creature.HasPower<PoisonPower>(), "P2 recovery retains arm poison.");
        int coreHp = s.Body.Creature.CurrentHp;
        await Hit(s, s.Body.Creature);
        Assert(s.Body.Creature.CurrentHp == coreHp, "Armored core takes direct damage.");
        GD.Print("PASS poison during rebirth, armored damage guard, permanent growth across phases");
    }

    private static async Task VerifyRepeatedBreakGrowth()
    {
        foreach (int ascension in new[] { 0, 10 })
        {
            var s = Scenario(ascension: ascension);
            for (int cycle = 1; cycle <= 3; cycle++)
            {
                await Hit(s, s.Left.Creature);
                await Act(s); await Act(s);
                Assert(s.Body.NextMove.Intents.Any(i => i is HealIntent) && s.Body.NextMove.Intents.Any(i => i is BuffIntent), "Recovery growth must be telegraphed.");
                await Act(s);
                foreach (var c in new[] { s.Body.Creature, s.Left.Creature, s.Right.Creature })
                    Assert(c.GetPowerAmount<StrengthPower>() == cycle * (ascension == 0 ? 2 : 3), "Repeated breaks freeze or duplicate growth.");
                Assert(s.Body.CrystalVein == 0, "Exposure turns must not feed the Crystal Vein.");
            }
        }
        GD.Print("PASS repeated arm breaks cannot freeze growth (A0/A10)");
    }

    private static async Task VerifyStunnedArmGrowth()
    {
        var s = Scenario();
        for (int i = 0; i < 4; i++) await Act(s); // next: Crystal Burst (the growth turn)
        await CreatureCmd.Stun(s.Left.Creature);
        await Hook.AfterSideTurnStart(s.State, CombatSide.Player, s.State.PlayerCreatures);
        Assert(s.Left.IsStunned && !s.Left.ShouldAllowTargeting(s.Left.Creature), "Native stun projection failed.");
        await Act(s);
        Assert(s.Left.Creature.GetPowerAmount<StrengthPower>() == 2, "Stunned arm silently misses encounter growth.");
        GD.Print("PASS stunned arm receives cycle growth without losing its protection");
    }

    private static async Task VerifyWeakPhaseSurvivingArmFlow()
    {
        foreach (bool breakLeft in new[] { true, false })
        {
            var s = Scenario();
            ThingsCaveGodHand broken = breakLeft ? s.Left : s.Right;
            ThingsCaveGodHand survivor = breakLeft ? s.Right : s.Left;

            // Turn 1: Player breaks one arm
            await Hit(s, broken.Creature);
            Assert(s.Body.IsWeakPhase, "Core must be exposed after arm break.");
            Assert(s.Body.NextMove.Id == "WEAK_PRONE_1", "Body must enter WEAK_PRONE_1.");
            Assert(broken.NextMove.Id == ThingsCaveGodHand.MoveId(ThingsCaveGodHand.Action.Down), "Broken arm must be Down.");
            Assert(survivor.NextMove.Id == ThingsCaveGodHand.MoveId(ThingsCaveGodHand.Action.WeakStun), "Surviving arm must be WeakStun on turn 1.");
            Assert(survivor.NextMove.Intents.OfType<StunIntent>().Any(), "Surviving arm must have StunIntent on turn 1.");
            Assert(!survivor.NextMove.Intents.OfType<AttackIntent>().Any(), "Surviving arm must not attack on turn 1.");

            // Turn 2: Player turn 2 starts (surviving arm must NOT stun again)
            await Act(s);
            Assert(s.Body.IsWeakPhase, "Core must remain exposed on turn 2.");
            Assert(s.Body.NextMove.Id == "WEAK_PRONE_2", "Body must advance to WEAK_PRONE_2.");
            Assert(broken.NextMove.Id == ThingsCaveGodHand.MoveId(ThingsCaveGodHand.Action.Down), "Broken arm must remain Down.");
            Assert(survivor.NextMove.Id == ThingsCaveGodHand.MoveId(ThingsCaveGodHand.Action.WeakAttack), "Surviving arm must be WeakAttack on turn 2 (NO consecutive stun).");
            Assert(!survivor.NextMove.Intents.OfType<StunIntent>().Any(), "Surviving arm must NOT have StunIntent on turn 2.");
            Assert(survivor.NextMove.Intents.OfType<AttackIntent>().Any(), "Surviving arm must advertise attack on turn 2.");

            // Turn 3: Player turn 3 starts (surviving arm attacked on enemy turn 2, now Body prepares recover)
            int playerHpBefore = s.State.Players[0].Creature.CurrentHp;
            await Act(s);
            int damageTaken = playerHpBefore - s.State.Players[0].Creature.CurrentHp;
            Assert(damageTaken > 0, "Surviving arm must have attacked and dealt damage on turn 2.");
            Assert(s.Body.IsWeakPhase, "Body must remain in weak phase on turn 3 before recover executes.");
            Assert(s.Body.NextMove.Id == "WEAK_UNKNOWN_3", "Body must advance to WEAK_UNKNOWN_3 (recovery).");
            Assert(survivor.NextMove.Id == ThingsCaveGodHand.MoveId(ThingsCaveGodHand.Action.WeakAttack), "Surviving arm must continue to attack on turn 3.");
            Assert(!survivor.NextMove.Intents.OfType<StunIntent>().Any(), "Surviving arm must NOT have StunIntent on turn 3.");

            // Turn 4: Recovery executes, boss restores arms and leaves weak phase
            await Act(s);
            Assert(!s.Body.IsWeakPhase, "Weak phase must end after turn 3.");
            Assert(s.Left.Creature.CurrentHp == s.Left.Creature.MaxHp && s.Right.Creature.CurrentHp == s.Right.Creature.MaxHp, "Both arms must be healed to full.");
            Assert(s.Left.ShouldAllowTargeting(s.Left.Creature) && s.Right.ShouldAllowTargeting(s.Right.Creature), "Arms must be targetable after recovery.");
            DeactivateSyntheticCombat();
        }
        GD.Print("PASS weak phase surviving arm: exactly 1 turn stun, turn 2 attack (no consecutive stun), turn 3 attack, turn 4 recovery");
    }

    private static CardModel AddTestCard<T>(Fixture s, Player player) where T : CardModel
    {
        CardModel card = s.State.CreateCard(ModelDb.Card<T>(), player);
        card.DeckVersion = card;
        player.PlayerCombatState!.DrawPile!.AddInternal(card);
        return card;
    }

    private static async Task VerifySweepCardTheft()
    {
        // 1. Priority 0 (Uncommon) over Rare, Basic, Ancient for Left Hand
        {
            var s = Scenario();
            var p = s.State.Players[0];
            var uncommon = AddTestCard<Inflame>(s, p);
            var rare = AddTestCard<DemonForm>(s, p);
            var basic = AddTestCard<Bash>(s, p);
            var ancient = AddTestCard<Apotheosis>(s, p);

            s.Left.Plan(ThingsCaveGodHand.Action.Sweep);
            await s.Left.PerformMove();

            Assert(s.Left.StolenCards.Count == 1, "Left arm must steal exactly 1 card.");
            Assert(s.Left.StolenCards[0] == uncommon, "Theft priority 0 failed: Uncommon must be stolen first.");
            Assert(uncommon.Pile == null, "Stolen card must be removed from combat piles.");
            Assert(s.Right.StolenCards.Count == 0, "Right arm must not hold Left arm's stolen card.");

            // Downing Left Hand returns the card to player Hand
            await Hit(s, s.Left.Creature);
            Assert(s.Left.StolenCards.Count == 0, "Downed arm must release all stolen cards.");
            Assert(p.PlayerCombatState!.Hand!.Cards.Contains(uncommon), "Released card must be placed back into player Hand.");
            DeactivateSyntheticCombat();
        }

        // 2. Priority 1 (Rare) over Basic and Ancient for Right Hand
        {
            var s = Scenario();
            var p = s.State.Players[0];
            var rare = AddTestCard<DemonForm>(s, p);
            var basic = AddTestCard<Bash>(s, p);
            var ancient = AddTestCard<Apotheosis>(s, p);

            s.Right.Plan(ThingsCaveGodHand.Action.Sweep);
            await s.Right.PerformMove();

            Assert(s.Right.StolenCards.Count == 1, "Right arm must steal exactly 1 card.");
            Assert(s.Right.StolenCards[0] == rare, "Theft priority 1 failed: Rare must be stolen over Basic/Ancient.");
            Assert(rare.Pile == null, "Stolen card must be removed from combat piles.");
            Assert(s.Left.StolenCards.Count == 0, "Left arm must not hold Right arm's stolen card.");

            // Downing Right Hand returns the card to player Hand
            await Hit(s, s.Right.Creature);
            Assert(s.Right.StolenCards.Count == 0, "Downed right arm must release stolen cards.");
            Assert(p.PlayerCombatState!.Hand!.Cards.Contains(rare), "Released rare card must be placed into player Hand.");
            DeactivateSyntheticCombat();
        }

        // 3. Priority 2 (Basic) over Ancient
        {
            var s = Scenario();
            var p = s.State.Players[0];
            var basic = AddTestCard<Bash>(s, p);
            var ancient = AddTestCard<Apotheosis>(s, p);

            s.Left.Plan(ThingsCaveGodHand.Action.Sweep);
            await s.Left.PerformMove();

            Assert(s.Left.StolenCards.Count == 1 && s.Left.StolenCards[0] == basic, "Theft priority 2 failed: Basic must be stolen before Ancient.");
            await Hit(s, s.Left.Creature);
            Assert(p.PlayerCombatState!.Hand!.Cards.Contains(basic), "Basic card must return to Hand upon arm downed.");
            DeactivateSyntheticCombat();
        }

        // 4. Priority 3 (Ancient stolen when only Ancient remains)
        {
            var s = Scenario();
            var p = s.State.Players[0];
            var ancient = AddTestCard<Apotheosis>(s, p);

            s.Right.Plan(ThingsCaveGodHand.Action.Sweep);
            await s.Right.PerformMove();

            Assert(s.Right.StolenCards.Count == 1 && s.Right.StolenCards[0] == ancient, "Theft priority 3 failed: Ancient card must be stolen when only option.");
            await Hit(s, s.Right.Creature);
            Assert(p.PlayerCombatState!.Hand!.Cards.Contains(ancient), "Ancient card must return to Hand upon arm downed.");
            DeactivateSyntheticCombat();
        }

        // 5. Multiplayer 2-player theft and return
        {
            var s = Scenario(count: 2);
            var p0 = s.State.Players[0];
            var p1 = s.State.Players[1];
            var card0 = AddTestCard<Inflame>(s, p0);
            var card1 = AddTestCard<DemonForm>(s, p1);

            s.Left.Plan(ThingsCaveGodHand.Action.Sweep);
            await s.Left.PerformMove();

            Assert(s.Left.StolenCards.Count == 2, "Left arm must steal 1 card per living player in multiplayer.");
            Assert(s.Left.StolenCards.Contains(card0) && s.Left.StolenCards.Contains(card1), "Left arm must hold cards from both players.");

            // Downing Left arm returns each card to its respective owner's hand
            await Hit(s, s.Left.Creature);
            Assert(s.Left.StolenCards.Count == 0, "Downed arm must release all cards.");
            Assert(p0.PlayerCombatState!.Hand!.Cards.Contains(card0), "Player 0's card must return to Player 0's Hand.");
            Assert(p1.PlayerCombatState!.Hand!.Cards.Contains(card1), "Player 1's card must return to Player 1's Hand.");
            DeactivateSyntheticCombat();
        }

        // 6. Boss defeat releases any held cards
        {
            var s = Scenario();
            var p = s.State.Players[0];
            var card = AddTestCard<Inflame>(s, p);

            s.Left.Plan(ThingsCaveGodHand.Action.Sweep);
            await s.Left.PerformMove();
            Assert(s.Left.StolenCards.Count == 1, "Left arm holds card before boss defeat.");

            // Defeat boss body directly
            await s.Body.AfterDeath(Choice, s.Body.Creature, false, 0f);
            Assert(s.Left.StolenCards.Count == 0, "Boss body defeat must release all held cards.");
            Assert(p.PlayerCombatState!.Hand!.Cards.Contains(card), "Card must be returned to Hand upon boss defeat.");
            DeactivateSyntheticCombat();
        }

        // 7. Hand full (10 cards) overflow routing to Discard upon arm downed
        {
            var s = Scenario();
            var p = s.State.Players[0];
            var stolenCard = AddTestCard<Inflame>(s, p);

            s.Left.Plan(ThingsCaveGodHand.Action.Sweep);
            await s.Left.PerformMove();
            Assert(s.Left.StolenCards.Count == 1, "Left arm must steal card.");

            // Fill hand to 10 cards
            for (int i = 0; i < CardPile.MaxCardsInHand; i++)
            {
                var dummy = s.State.CreateCard(ModelDb.Card<StrikeIronclad>(), p);
                dummy.DeckVersion = dummy;
                p.PlayerCombatState!.Hand!.AddInternal(dummy, 0);
            }
            Assert(p.PlayerCombatState!.Hand!.Cards.Count == CardPile.MaxCardsInHand, "Hand must have 10 cards.");

            // Downing Left Hand when hand is full routes to Discard pile
            await Hit(s, s.Left.Creature);
            Assert(s.Left.StolenCards.Count == 0, "Downed arm must release card even when hand is full.");
            Assert(p.PlayerCombatState!.DiscardPile!.Cards.Contains(stolenCard), "Stolen card must be routed to Discard pile when hand is full.");
            DeactivateSyntheticCombat();
        }

        // 8. Hand fallback theft (Draw and Discard are empty)
        {
            var s = Scenario();
            var p = s.State.Players[0];
            var handCard = s.State.CreateCard(ModelDb.Card<Inflame>(), p);
            handCard.DeckVersion = handCard;
            p.PlayerCombatState!.Hand!.AddInternal(handCard, 0);

            s.Right.Plan(ThingsCaveGodHand.Action.Sweep);
            await s.Right.PerformMove();

            Assert(s.Right.StolenCards.Count == 1, "Right arm must steal card from Hand when Draw/Discard empty.");
            Assert(s.Right.StolenCards[0] == handCard, "Stolen card must match the Hand card.");
            Assert(!p.PlayerCombatState!.Hand!.Cards.Contains(handCard), "Card must be removed from Hand.");

            await Hit(s, s.Right.Creature);
            Assert(p.PlayerCombatState!.Hand!.Cards.Contains(handCard), "Card must return to Hand upon arm downed.");
            DeactivateSyntheticCombat();
        }

        // 9. Stolen card preserved into Phase 2 until arm is downed in Phase 2
        {
            var s = Scenario();
            var p = s.State.Players[0];
            var card = AddTestCard<Inflame>(s, p);

            s.Right.Plan(ThingsCaveGodHand.Action.Sweep);
            await s.Right.PerformMove();
            Assert(s.Right.StolenCards.Count == 1, "Right arm holds stolen card.");

            // Down Left arm to expose core
            await Hit(s, s.Left.Creature);
            Assert(s.Body.IsWeakPhase, "Core exposed.");

            // Lethal hit to core triggers phase transition pending
            await Hit(s, s.Body.Creature);
            Assert(s.Body.IsPhaseTransitionPending, "Phase transition pending.");

            // Right arm still holds the card during transition
            Assert(s.Right.StolenCards.Count == 1, "Right arm preserves held card into Phase 2.");

            // Complete phase transition
            await Act(s);
            Assert(s.Body.Phase == 2, "Transitioned to Phase 2.");
            Assert(s.Right.StolenCards.Count == 1, "Right arm continues holding card in Phase 2.");

            // Downing Right arm in Phase 2 releases the card to Hand
            await Hit(s, s.Right.Creature);
            Assert(s.Right.StolenCards.Count == 0, "Right arm must release card upon defeat in Phase 2.");
            Assert(p.PlayerCombatState!.Hand!.Cards.Contains(card), "Card must return to Hand in Phase 2.");
            DeactivateSyntheticCombat();
        }

        // 10. Empty deck safety (0 cards anywhere)
        {
            var s = Scenario();
            s.Left.Plan(ThingsCaveGodHand.Action.Sweep);
            await s.Left.PerformMove();
            Assert(s.Left.StolenCards.Count == 0, "Sweep with 0 cards must complete cleanly with 0 stolen cards.");
            DeactivateSyntheticCombat();
        }

        GD.Print("PASS sweep card theft: priority hierarchy, left/right separation, hand return on arm downed, multiplayer, full-hand overflow, hand fallback, transition pending release & empty deck safety");
    }

    private async Task VerifyHandLayoutAndZIndex()
    {
        // 1. Encounter slot markers
        var encounterScene = GD.Load<PackedScene>("res://scenes/encounters/cave_god_boss_encounter.tscn");
        Assert(encounterScene != null, "Could not load cave_god_boss_encounter.tscn");
        var encounter = encounterScene!.Instantiate<Control>();
        var leftMarker = encounter.GetNode<Marker2D>("left_hand");
        var rightMarker = encounter.GetNode<Marker2D>("right_hand");
        Assert(leftMarker.Position == new Vector2(540, 490), $"left_hand expected (540, 490) but got {leftMarker.Position}");
        Assert(rightMarker.Position == new Vector2(1380, 490), $"right_hand expected (1380, 490) but got {rightMarker.Position}");
        encounter.QueueFree();

        // 2. Left and Right Hand visual scenes and UI elevation
        foreach (string scenePath in new[] { "res://scenes/creature_visuals/things_cave_god_left_hand.tscn", "res://scenes/creature_visuals/things_cave_god_right_hand.tscn" })
        {
            var visualScene = GD.Load<PackedScene>(scenePath);
            Assert(visualScene != null, $"Could not load {scenePath}");

            var dummyParent = new Control();
            var dummyHealthBar = new Control { Name = "HealthBar" };
            var dummyIntents = new Control { Name = "Intents" };
            dummyParent.AddChild(dummyHealthBar);
            dummyParent.AddChild(dummyIntents);

            var visuals = visualScene!.Instantiate<Node2D>();
            dummyParent.AddChild(visuals);
            AddChild(dummyParent);

            // Wait frame for Ready and deferred elevation
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);

            Assert(dummyParent.ZIndex == 0, $"Creature node ZIndex expected 0, got {dummyParent.ZIndex}");
            Assert(!dummyParent.ZAsRelative, "Creature node ZAsRelative must be false");
            Assert(dummyHealthBar.ZIndex == 0, $"HealthBar ZIndex expected 0, got {dummyHealthBar.ZIndex}");
            Assert(!dummyHealthBar.ZAsRelative, "HealthBar ZAsRelative must be false");
            Assert(dummyIntents.ZIndex == 0, $"Intents ZIndex expected 0, got {dummyIntents.ZIndex}");
            Assert(!dummyIntents.ZAsRelative, "Intents ZAsRelative must be false");

            var bounds = visuals.GetNode<Control>("Bounds");
            Assert(bounds.OffsetLeft == -130f && bounds.OffsetRight == 130f, $"Bounds X expected (-130, 130) but got ({bounds.OffsetLeft}, {bounds.OffsetRight})");
            Assert(bounds.OffsetTop == -180f && bounds.OffsetBottom == 10f, $"Bounds Y expected (-180, 10) but got ({bounds.OffsetTop}, {bounds.OffsetBottom})");

            var centerPos = visuals.GetNode<Marker2D>("CenterPos");
            Assert(centerPos.Position == new Vector2(0, -90), $"CenterPos expected (0, -90) but got {centerPos.Position}");

            var intentPos = visuals.GetNode<Marker2D>("IntentPos");
            Assert(intentPos.Position == new Vector2(0, -210), $"IntentPos expected (0, -210) but got {intentPos.Position}");

            dummyParent.QueueFree();
        }

        // 3. Verify ElevateHandsUi and ResetHandsUi behavior on combat room creatures
        var dummyRoom = new NCombatRoom();
        var enemyCreature = new Creature(ModelDb.Monster<ThingsCaveGodLeftHand>().ToMutable(), CombatSide.Enemy, "left_hand");
        var leftCreatureNode = new NCreature();
        typeof(NCreature).GetProperty("Entity", BindingFlags.Public | BindingFlags.Instance)!.SetValue(leftCreatureNode, enemyCreature);
        var nodesList = (List<NCreature>)typeof(NCombatRoom).GetField("_creatureNodes", BindingFlags.NonPublic | BindingFlags.Instance)!.GetValue(dummyRoom)!;
        nodesList.Add(leftCreatureNode);

        NCaveGodBossBackground.ElevateHandsUi(dummyRoom);
        Assert(leftCreatureNode.ZIndex == 0, $"ElevateHandsUi expected ZIndex 0, got {leftCreatureNode.ZIndex}");
        Assert(!leftCreatureNode.ZAsRelative, "ElevateHandsUi expected ZAsRelative false");

        NCaveGodBossBackground.ResetHandsUi(dummyRoom);
        Assert(leftCreatureNode.ZIndex == 0, $"ResetHandsUi expected ZIndex 0, got {leftCreatureNode.ZIndex}");
        Assert(!leftCreatureNode.ZAsRelative, "ResetHandsUi expected ZAsRelative false");

        leftCreatureNode.Free();
        dummyRoom.Free();

        GD.Print("PASS hand layout and ZIndex: slot markers, bounds, center/intent offsets, native UI plane Z=0, and ResetHandsUi robustness");
    }

    private async Task VerifyRenderedResources()
    {
        TestMode.TurnOnInternal(); // Render normally while suppressing unavailable FMOD/game services.
        string root = Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "../.."));
        // PCKs are already mounted in Run(); only load if not yet mounted.
        // Calling LoadResourcePack twice on the same PCK corrupts Godot's pack filesystem table.
        var extension = GDExtensionManager.LoadExtension(Path.Combine(root, "addons/spine/spine_godot_extension.gdextension"));
        Assert(extension is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded, $"Spine load failed: {extension}");
        EnsureScriptsLookedUp();
        try
        {
            SaveManager.Instance.InitSettingsDataForTest();
            SaveManager.Instance.SettingsSave.Language = "eng";
            LocManager.Initialize();
        }
        catch (Exception ex)
        {
            GD.PrintErr($"LocManager.Initialize failed: {ex}");
        }
        try { NCard.InitPool(); } catch { }
        GetTree().Root.Size = new Vector2I(1920, 1080);
        var scene = GD.Load<PackedScene>("res://scenes/backgrounds/cave_god_boss_encounter/cave_god_boss_encounter_background.tscn");
        var bg = scene.Instantiate<Control>();
        bg.Position = new Vector2(983, 540);
        bg.Scale = Vector2.One * 0.75f; // Encounter's native camera scale.
        bg.GetNode("Layer_00").AddChild(GD.Load<PackedScene>("res://scenes/backgrounds/cave_god_boss_encounter/layers/cave_god_boss_encounter_bg_00_a.tscn").Instantiate());
        bg.GetNode("Foreground").AddChild(GD.Load<PackedScene>("res://scenes/backgrounds/cave_god_boss_encounter/layers/cave_god_boss_encounter_fg_a.tscn").Instantiate());
        AddChild(bg);
        var controller = bg.GetNode<STS2_Things.Visuals.NCaveGodBossBackground>("CaveGod");
        var body = bg.GetNode<Node2D>("CaveGod/CaveGodBody");
        var arms = bg.GetNode<Node2D>("CaveGodArms");
        for (int i = 0; i < 30; i++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
        string output = Path.Combine(root, "build/cavegod-refactor-20260919/visuals");
        Directory.CreateDirectory(output);
        async Task Capture(string name)
        {
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            await ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
            using var frame = GetViewport().GetTexture().GetImage();
            Assert(frame.SavePng(Path.Combine(output, name + ".png")) == Error.Ok, "Could not save rendered frame.");
        }
        void Freeze(string animation, float time)
        {
            foreach (var node in new[] { body, arms })
            {
                var state = node.Call("get_animation_state").AsGodotObject();
                state.Call("clear_track", 0);
                var track = state.Call("set_animation", animation, false, 0).AsGodotObject();
                track.Call("set_track_time", time);
                track.Call("set_time_scale", 0f);
                track.Call("set_mix_duration", 0f);
            }
        }
        foreach (string animation in new[] { "idle_front", "idle_front_angry", "weak_idle", "weak_idle_angry", "grab_slam", "grab_slam_angry" })
        {
            var data = body.Get("skeleton_data_res").AsGodotObject();
            Assert(data.Call("find_animation", animation).AsGodotObject() != null, $"Missing packaged animation: {animation}");
        }
        controller.SetAngry(false);
        Freeze("idle_front", 0.5f); await Capture("01-blue-idle");
        var redBgNode = bg.GetNodeOrNull<TextureRect>("Layer_00/A/RedBg");
        if (redBgNode != null) redBgNode.Modulate = new Color(1f, 1f, 1f, 0.5f);
        await Capture("01b-phase-transition-half");
        controller.SetAngry(true);
        Freeze("idle_front_angry", 0.5f); await Capture("02-red-idle");

        var testCardLeft = (CardModel)ModelDb.Card<Inflame>().ToMutable();
        var testCardRight = (CardModel)ModelDb.Card<DemonForm>().ToMutable();
        controller.AttachStolenCard(true, testCardLeft);
        await Capture("idle-left-holding-card");
        controller.ClearStolenCard(true);

        controller.AttachStolenCard(false, testCardRight);
        await Capture("idle-right-holding-card");
        controller.ClearStolenCard(false);

        controller.AttachStolenCard(true, testCardLeft);
        controller.AttachStolenCard(false, testCardRight);
        await Capture("idle-both-holding-cards");
        controller.ClearAllStolenCards();
        controller.StartAttackAnim("front_sweep", isFlipped: false);
        Freeze("front_sweep_angry", 0.70f); await Capture("sweep-left-070");
        Freeze("front_sweep_angry", 1.00f); await Capture("sweep-left-100");
        Freeze("front_sweep_angry", 1.30f);
        testCardLeft = (CardModel)ModelDb.Card<Inflame>().ToMutable();
        controller.AttachStolenCard(true, testCardLeft);
        await Capture("sweep-left-130-holding-card");
        controller.ClearStolenCard(true);
        await Capture("sweep-left-130");

        // Verify that passing isFlipped: true routes cleanly to front_sweep_right_angry without negative scaling
        controller.StartAttackAnim("front_sweep", isFlipped: true);
        Assert(arms.Scale.X > 0, "Arm rig must never use negative X scale.");
        Freeze("front_sweep_right_angry", 0.70f); await Capture("sweep-right-070");
        Freeze("front_sweep_right_angry", 1.00f); await Capture("sweep-right-100");
        Freeze("front_sweep_right_angry", 1.30f); await Capture("sweep-right-130");

        controller.StartAttackAnim("front_sweep_right", isFlipped: false);
        Freeze("front_sweep_right_angry", 0.70f); await Capture("sweep-right-new-070");
        Freeze("front_sweep_right_angry", 1.00f); await Capture("sweep-right-new-100");
        Freeze("front_sweep_right_angry", 1.30f);
        testCardRight = (CardModel)ModelDb.Card<DemonForm>().ToMutable();
        controller.AttachStolenCard(false, testCardRight);
        await Capture("sweep-right-new-130-holding-card");
        controller.ClearStolenCard(false);
        await Capture("sweep-right-new-130");

        controller.StartAttackAnim("grab_player_right", isFlipped: false);
        controller.StartGrabTracking(Array.Empty<Creature>());
        Assert(arms.Scale.X > 0, "Arm rig must never use negative X scale during grab tracking.");
        controller.HoldGrabAnim();
        Freeze("grab_player_right_angry", 2.60f); await Capture("grab-right-new-hold");

        controller.ResumeSlamAnim();
        var animState = arms.Call("get_animation_state").AsGodotObject();
        var curTrack = animState.Call("get_current", 0).AsGodotObject();
        var anim = curTrack.Call("get_animation").AsGodotObject();
        string slamAnimName = anim.Call("get_name").AsString();
        Assert(slamAnimName == "grab_slam_right_angry", $"Expected grab_slam_right_angry after grab_player_right, but got {slamAnimName}");

        Freeze("grab_slam_right_angry", 0.45f); await Capture("slam-right-new-windup");
        Freeze("grab_slam_right_angry", 0.75f); await Capture("slam-right-new-impact");

        controller.ResetArmScale();
        Freeze("rightpunch", 1.20f); await Capture("rightpunch-120");
        Freeze("weak_attack_right_angry", 1.00f); await Capture("weak-attack-right-100");
        Freeze("weak_idle_right_angry", 0.50f); await Capture("weak-idle-right-050");
        Freeze("weak_enter_right_angry", 0.85f); await Capture("weak-enter-right-085");
        Freeze("weak_recover_right_angry", 1.00f); await Capture("weak-recover-right-100");

        controller.StartAttackAnim("grab_player", isFlipped: true);
        controller.StartGrabTracking(Array.Empty<Creature>(), isFlipped: true);
        Assert(arms.Scale.X > 0, "Arm rig must never use negative X scale during grab tracking.");
        controller.HoldGrabAnim();
        await Capture("grab-right-hold");
        controller.ResumeSlamAnim();
        Freeze("grab_slam_right_angry", 0.45f); await Capture("slam-right-windup");
        Freeze("grab_slam_right_angry", 0.75f); await Capture("slam-right-impact");

        controller.StartAttackAnim("grab_player", isFlipped: false);
        controller.HoldGrabAnim();
        await Capture("03-grab-hold");
        controller.ResumeSlamAnim();
        Freeze("grab_slam_angry", 0.45f); await Capture("04-slam-windup");
        Freeze("grab_slam_angry", 0.75f); await Capture("05-slam-impact");
        Assert(arms.GetIndex() > bg.GetNode("Foreground").GetIndex(), "Arms must draw in front of the platform during attacks.");
        controller.PlayBodyDeathAnim();
        Freeze("hide_angry", 3.0f);
        Assert(arms.GetIndex() < bg.GetNode("Foreground").GetIndex(), "Retreating arms must be behind the platform.");
        await Capture("06-death");
        GD.Print("CaveGod packaged background/render probe: PASS");
    }

    private static void InitializeModelDb()
    {
        AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency;
        EnsureRuntimeDependency("System.IO.Hashing");

        Type[] modTypes = ImplementationAssembly.GetTypes();
        Type[] modelTypes = AbstractModelSubtypes.All
            .Concat(modTypes.Where(type =>
                !type.IsAbstract && typeof(AbstractModel).IsAssignableFrom(type)))
            .Distinct()
            .ToArray();
        typeof(ReflectionHelper).GetField(
                "_modTypes", BindingFlags.NonPublic | BindingFlags.Static)!
            .SetValue(null, modTypes);
        RegisterSyntheticMod(ImplementationAssembly);

        PropertyInfo? managerState = typeof(ModManager).GetProperty(
            "State", BindingFlags.Public | BindingFlags.Static);
        if (managerState != null)
        {
            managerState.SetValue(null, Enum.Parse(managerState.PropertyType, "Initialized"));
        }

        Type? assemblyInfo = typeof(ModelDb).Assembly.GetType(
            "MegaCrit.Sts2.Core.Modding.AssemblyInfo");
        assemblyInfo?.GetMethod("Init", BindingFlags.Public | BindingFlags.Static)?
            .Invoke(null, null);
        typeof(ModelDb).GetMethod("ResetForTest", BindingFlags.Public | BindingFlags.Static)?
            .Invoke(null, null);

        MethodInfo init = typeof(ModelDb).GetMethods(BindingFlags.Public | BindingFlags.Static)
            .Single(method => method.Name == "Init");
        init.Invoke(null, init.GetParameters().Length == 0 ? null : [modelTypes]);

        Type serializationCache = typeof(ModelDb).Assembly.GetType(
            "MegaCrit.Sts2.Core.Multiplayer.Serialization.ModelIdSerializationCache",
            throwOnError: true)!;
        serializationCache.GetMethod("Init", BindingFlags.Public | BindingFlags.Static)!
            .Invoke(null, null);
        typeof(ModelDb).GetMethod("InitIds", BindingFlags.Public | BindingFlags.Static)!
            .Invoke(null, null);

        // The normal loader calls STS2_ThingsInit before ModelDb setup. The
        // isolated probe intentionally builds its own model database, so apply
        // the narrowly scoped Ravenous adapter here as well.
        // CaveGod uses native model hooks; unrelated registration patches are not needed here.
    }


    private static void RegisterSyntheticMod(Assembly implementationAssembly)
    {
        Assembly gameAssembly = typeof(ModManager).Assembly;
        Type modType = gameAssembly.GetType(
            "MegaCrit.Sts2.Core.Modding.Mod", throwOnError: true)!;
        Type manifestType = gameAssembly.GetType(
            "MegaCrit.Sts2.Core.Modding.ModManifest", throwOnError: true)!;
        object mod = Activator.CreateInstance(modType)!;
        object manifest = Activator.CreateInstance(manifestType)!;
        manifestType.GetField("id")!.SetValue(manifest, "STS2_Things");
        manifestType.GetField("name")?.SetValue(manifest, "STS2_Things Gravetide Probe");
        manifestType.GetField("affectsGameplay")?.SetValue(manifest, true);
        modType.GetField("path")!.SetValue(mod, "probe://STS2_Things");
        modType.GetField("manifest")!.SetValue(mod, manifest);
        FieldInfo stateField = modType.GetField("state")!;
        stateField.SetValue(mod, Enum.Parse(stateField.FieldType, "Loaded"));

        if (modType.GetField("assemblies")?.GetValue(mod) is IList assemblies)
        {
            assemblies.Add(implementationAssembly);
        }
        else
        {
            modType.GetField("assembly")!.SetValue(mod, implementationAssembly);
        }

        IList mods = (IList)typeof(ModManager)
            .GetField("_mods", BindingFlags.NonPublic | BindingFlags.Static)!
            .GetValue(null)!;
        mods.Clear();
        mods.Add(mod);
    }


    private static void ActivateSyntheticCombat(CombatState state)
    {
        LocalContext.NetId = state.Players[0].NetId;
        CombatManager manager = CombatManager.Instance;
        FieldInfo? legacyStateField = typeof(CombatManager).GetField(
            "_state", BindingFlags.NonPublic | BindingFlags.Instance);
        if (legacyStateField != null)
        {
            legacyStateField.SetValue(manager, state);
            typeof(CombatManager).GetField(
                    "<IsInProgress>k__BackingField",
                    BindingFlags.NonPublic | BindingFlags.Instance)!
                .SetValue(manager, true);
        }
        else
        {
            FieldInfo turnStateField = typeof(CombatManager).GetField(
                    "_turnState", BindingFlags.NonPublic | BindingFlags.Instance)
                ?? throw new MissingFieldException(typeof(CombatManager).FullName, "_turnState");
            object turnState = Activator.CreateInstance(
                    turnStateField.FieldType,
                    BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic,
                    binder: null,
                    args: [state],
                    culture: null)
                ?? throw new InvalidOperationException("Could not create the V111 combat turn state.");
            turnState.GetType().GetProperty("IsInProgress")!.SetValue(turnState, true);
            turnState.GetType().GetProperty("IsStarting")!.SetValue(turnState, false);
            turnStateField.SetValue(manager, turnState);
        }
        state.MultiplayerScalingModel?.OnCombatEntered(state);
        manager.StateTracker.SetState(state);
    }


    private static void DeactivateSyntheticCombat()
    {
        LocalContext.NetId = null;
        CombatManager manager = CombatManager.Instance;
        FieldInfo? legacyStateField = typeof(CombatManager).GetField(
            "_state", BindingFlags.NonPublic | BindingFlags.Instance);
        if (legacyStateField != null)
        {
            typeof(CombatManager).GetField(
                    "<IsInProgress>k__BackingField",
                    BindingFlags.NonPublic | BindingFlags.Instance)?
                .SetValue(manager, false);
            legacyStateField.SetValue(manager, null);
            return;
        }

        FieldInfo turnStateField = typeof(CombatManager).GetField(
                "_turnState", BindingFlags.NonPublic | BindingFlags.Instance)
            ?? throw new MissingFieldException(typeof(CombatManager).FullName, "_turnState");
        object? turnState = turnStateField.GetValue(manager);
        turnState?.GetType().GetMethod("Cancel", BindingFlags.Public | BindingFlags.Instance)?
            .Invoke(turnState, null);
        turnStateField.SetValue(manager, null);
    }


    private static void EnsureRuntimeDependency(string assemblyName)
    {
        if (AppDomain.CurrentDomain.GetAssemblies().Any(assembly =>
                string.Equals(assembly.GetName().Name, assemblyName, StringComparison.Ordinal)))
        {
            return;
        }

        string path = FindRuntimeDependencyPath(assemblyName)
            ?? throw new FileNotFoundException(
                $"Could not locate probe runtime dependency {assemblyName}.dll.");
        AssemblyLoadContext.Default.LoadFromAssemblyPath(path);
    }


    private static Assembly? ResolveRuntimeDependency(
        AssemblyLoadContext context,
        AssemblyName assemblyName)
    {
        if (string.IsNullOrWhiteSpace(assemblyName.Name))
        {
            return null;
        }
        string? path = FindRuntimeDependencyPath(assemblyName.Name);
        return path == null ? null : context.LoadFromAssemblyPath(path);
    }


    private static string? FindRuntimeDependencyPath(string assemblyName)
    {
        string configuration =
#if DEBUG
            "Debug";
#else
            "Release";
#endif
        string projectRoot = ProjectSettings.GlobalizePath("res://");
        string? assemblyDirectory = Path.GetDirectoryName(
            typeof(CaveGodProbeNode).Assembly.Location);
        string[] candidates =
        [
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", configuration,
                $"{assemblyName}.dll"),
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", "Debug",
                $"{assemblyName}.dll"),
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", "Release",
                $"{assemblyName}.dll"),
            Path.Combine(assemblyDirectory ?? string.Empty, $"{assemblyName}.dll")
        ];
        return candidates.FirstOrDefault(File.Exists);
    }


    private static bool _scriptsLookedUp;
    private static void EnsureScriptsLookedUp()
    {
        if (_scriptsLookedUp) return;
        _scriptsLookedUp = true;
        try { Godot.Bridge.ScriptManagerBridge.LookupScriptsInAssembly(typeof(ModelDb).Assembly); } catch { }
        try { Godot.Bridge.ScriptManagerBridge.LookupScriptsInAssembly(ImplementationAssembly); } catch { }
    }

    private static void Assert(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }

    private async Task RenderOfficialRooms()
    {
        TestMode.TurnOnInternal();
        string root = Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "../.."));
        Assert(ProjectSettings.LoadResourcePack("D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck"), "Game PCK mount failed.");
        EnsureScriptsLookedUp();
        
        GetTree().Root.Size = new Vector2I(1920, 1080);
        string output = @"d:\Things\CaveGod_STS2_Style_ARCHIVE_20260808\official_rendered_rooms";
        Directory.CreateDirectory(output);

        async Task Capture(string filename)
        {
            for (int i = 0; i < 10; i++)
                await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            await ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
            using var frame = GetViewport().GetTexture().GetImage();
            Assert(frame.SavePng(Path.Combine(output, filename)) == Error.Ok, $"Could not save {filename}");
            GD.Print($"Rendered and saved: {filename}");
        }

        // 1. Waterfall Giant Boss Room
        try
        {
            var sc = GD.Load<PackedScene>("res://scenes/backgrounds/waterfall_giant_boss/waterfall_giant_boss_background.tscn");
            if (sc != null)
            {
                var bg = sc.Instantiate<Control>();
                bg.Position = new Vector2(983, 540);
                bg.Scale = Vector2.One * 0.75f;
                var bgLayerSc = GD.Load<PackedScene>("res://scenes/backgrounds/waterfall_giant_boss/layers/waterfall_giant_boss_bg_00_a.tscn");
                if (bgLayerSc != null) bg.GetNodeOrNull("Layer_00")?.AddChild(bgLayerSc.Instantiate());
                var fgLayerSc = GD.Load<PackedScene>("res://scenes/backgrounds/waterfall_giant_boss/layers/waterfall_giant_boss_fg_a.tscn");
                if (fgLayerSc != null) bg.GetNodeOrNull("Foreground")?.AddChild(fgLayerSc.Instantiate());
                AddChild(bg);
                for (int i = 0; i < 30; i++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
                await Capture("01-waterfall_giant_boss_room.png");
                RemoveChild(bg);
                bg.QueueFree();
            }
        }
        catch (Exception ex) { GD.PrintErr($"Failed waterfall giant: {ex.Message}"); }

        // 2. Queen Boss Room
        try
        {
            var sc = GD.Load<PackedScene>("res://scenes/backgrounds/queen_boss/queen_boss_background.tscn");
            if (sc != null)
            {
                var bg = sc.Instantiate<Control>();
                bg.Position = new Vector2(983, 540);
                bg.Scale = Vector2.One * 0.75f;
                for (int l = 0; l <= 3; l++)
                {
                    var lSc = GD.Load<PackedScene>($"res://scenes/backgrounds/queen_boss/layers/queen_boss_bg_{l:D2}_a.tscn");
                    if (lSc != null) bg.GetNodeOrNull($"Layer_{l:D2}")?.AddChild(lSc.Instantiate());
                }
                var fgSc = GD.Load<PackedScene>("res://scenes/backgrounds/queen_boss/layers/queen_fg_a.tscn");
                if (fgSc != null) bg.GetNodeOrNull("Foreground")?.AddChild(fgSc.Instantiate());
                AddChild(bg);
                for (int i = 0; i < 30; i++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
                await Capture("02-queen_boss_room.png");
                RemoveChild(bg);
                bg.QueueFree();
            }
        }
        catch (Exception ex) { GD.PrintErr($"Failed queen: {ex.Message}"); }

        // 3. Ceremonial Beast Boss Room
        try
        {
            var sc = GD.Load<PackedScene>("res://scenes/backgrounds/ceremonial_beast_boss/ceremonial_beast_boss_background.tscn");
            if (sc != null)
            {
                var bg = sc.Instantiate<Control>();
                bg.Position = new Vector2(983, 540);
                bg.Scale = Vector2.One * 0.75f;
                for (int l = 0; l <= 4; l++)
                {
                    string suffix = l == 4 ? "c" : "a";
                    var lSc = GD.Load<PackedScene>($"res://scenes/backgrounds/ceremonial_beast_boss/layers/ceremonial_beast_boss_bg_{l:D2}_{suffix}.tscn");
                    if (lSc != null) bg.GetNodeOrNull($"Layer_{l:D2}")?.AddChild(lSc.Instantiate());
                }
                var fgSc = GD.Load<PackedScene>("res://scenes/backgrounds/ceremonial_beast_boss/layers/ceremonial_beast_boss_fg_a.tscn");
                if (fgSc != null) bg.GetNodeOrNull("Foreground")?.AddChild(fgSc.Instantiate());
                AddChild(bg);
                for (int i = 0; i < 30; i++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
                await Capture("03-ceremonial_beast_boss_room.png");
                RemoveChild(bg);
                bg.QueueFree();
            }
        }
        catch (Exception ex) { GD.PrintErr($"Failed ceremonial beast: {ex.Message}"); }

        // 4. Kaiser Crab Boss Room
        try
        {
            var sc = GD.Load<PackedScene>("res://scenes/backgrounds/kaiser_crab_boss/kaiser_crab_boss_background.tscn");
            if (sc != null)
            {
                var bg = sc.Instantiate<Control>();
                bg.Position = new Vector2(983, 540);
                bg.Scale = Vector2.One * 0.75f;
                for (int l = 0; l <= 3; l++)
                {
                    var lSc = GD.Load<PackedScene>($"res://scenes/backgrounds/kaiser_crab_boss/layers/kaiser_crab_boss_bg_{l:D2}_a.tscn");
                    if (lSc != null) bg.GetNodeOrNull($"Layer_{l:D2}")?.AddChild(lSc.Instantiate());
                }
                var fgSc = GD.Load<PackedScene>("res://scenes/backgrounds/kaiser_crab_boss/layers/kaiser_crab_boss_fg_a.tscn");
                if (fgSc != null) bg.GetNodeOrNull("Foreground")?.AddChild(fgSc.Instantiate());
                AddChild(bg);
                for (int i = 0; i < 30; i++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
                await Capture("04-kaiser_crab_boss_room.png");
                RemoveChild(bg);
                bg.QueueFree();
            }
        }
        catch (Exception ex) { GD.PrintErr($"Failed kaiser crab: {ex.Message}"); }

        // 5. The Insatiable Boss Room
        try
        {
            var sc = GD.Load<PackedScene>("res://scenes/backgrounds/the_insatiable_boss/the_insatiable_boss_background.tscn");
            if (sc != null)
            {
                var bg = sc.Instantiate<Control>();
                bg.Position = new Vector2(983, 540);
                bg.Scale = Vector2.One * 0.75f;
                for (int l = 0; l <= 4; l++)
                {
                    var lSc = GD.Load<PackedScene>($"res://scenes/backgrounds/the_insatiable_boss/layers/the_insatiable_boss_bg_{l:D2}_a.tscn");
                    if (lSc != null) bg.GetNodeOrNull($"Layer_{l:D2}")?.AddChild(lSc.Instantiate());
                }
                var fgSc = GD.Load<PackedScene>("res://scenes/backgrounds/the_insatiable_boss/layers/the_insatiable_boss_fg_a.tscn");
                if (fgSc != null) bg.GetNodeOrNull("Foreground")?.AddChild(fgSc.Instantiate());
                AddChild(bg);
                for (int i = 0; i < 30; i++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
                await Capture("05-the_insatiable_boss_room.png");
                RemoveChild(bg);
                bg.QueueFree();
            }
        }
        catch (Exception ex) { GD.PrintErr($"Failed the insatiable: {ex.Message}"); }
    }

    private static async Task VerifyAgingPowerAndStoneArmor()
    {
        var s = Scenario(count: 2);
        Assert(s.Left.Creature.HasPower<ThingsCaveGodAgingPower>(), "Left arm must have Aging power.");
        Assert(s.Right.Creature.HasPower<ThingsCaveGodAgingPower>(), "Right arm must have Aging power.");

        var p1 = s.State.Players[0];
        var p2 = s.State.Players[1];
        int p1CardsBefore = p1.PlayerCombatState!.Hand.Cards.Count;
        int p2CardsBefore = p2.PlayerCombatState!.Hand.Cards.Count;

        await Hit(s, s.Left.Creature, 10000m);
        Assert(s.Left.IsDown || s.Body.IsWeakPhase, "Left arm must be defeated/downed.");

        Assert(s.Body.AgingCountdown == 1 && s.Left.Creature.GetPower<ThingsCaveGodAgingPower>()!.Amount == 1 &&
            s.Right.Creature.GetPower<ThingsCaveGodAgingPower>()!.Amount == 1, "First knockdown decrements both views of the shared counter.");
        Assert(p1.PlayerCombatState.Hand.Cards.Count == p1CardsBefore &&
            p2.PlayerCombatState.Hand.Cards.Count == p2CardsBefore, "First knockdown must not award Stone Armor.");
        await Act(s); // the surviving arm becomes targetable after its exposure stun
        await Hit(s, s.Right.Creature, 10000m);
        Assert(s.Body.AgingCountdown == 2 && s.Right.Creature.GetPower<ThingsCaveGodAgingPower>()!.Amount == 2,
            "Second knockdown awards one set of cards and resets the shared countdown.");
        Assert(p1.PlayerCombatState.Hand.Cards.Count == p1CardsBefore + 1, "Player 1 must receive Stone Armor in hand.");
        Assert(p2.PlayerCombatState.Hand.Cards.Count == p2CardsBefore + 1, "Player 2 must receive Stone Armor in hand.");

        var card1 = p1.PlayerCombatState.Hand.Cards.Last();
        var card2 = p2.PlayerCombatState.Hand.Cards.Last();

        Assert(card1.Id == ModelDb.Card<StoneArmor>().Id, "Added card must be Stone Armor.");
        Assert(card2.Id == ModelDb.Card<StoneArmor>().Id, "Added card must be Stone Armor.");

        Assert(card1.EnergyCost.GetResolved() == 0, "Stone Armor cost must be 0 for player 1.");
        Assert(card2.EnergyCost.GetResolved() == 0, "Stone Armor cost must be 0 for player 2.");

        GD.Print("PASS shared aging countdown gives 0-cost Stone Armor every two arm knockdowns");
    }

    private static async Task VerifyPhaseTransitionClearsArmStrength()
    {
        var s = Scenario();
        var choice = new ThrowingPlayerChoiceContext();

        await PowerCmd.Apply<StrengthPower>(choice, s.Left.Creature, 6m, s.Left.Creature, null);
        await PowerCmd.Apply<StrengthPower>(choice, s.Right.Creature, 6m, s.Right.Creature, null);

        Assert(s.Left.Creature.GetPower<StrengthPower>()?.Amount == 6m, "Left arm must have 6 Strength before transition.");
        Assert(s.Right.Creature.GetPower<StrengthPower>()?.Amount == 6m, "Right arm must have 6 Strength before transition.");

        await Hit(s, s.Left.Creature, 10000m);
        Assert(s.Body.IsWeakPhase, "Core must be exposed after arm breaks.");

        await Hit(s, s.Body.Creature, 10000m);
        Assert(s.Body.IsPhaseTransitionPending, "Body must enter phase transition.");

        await Act(s);

        Assert(s.Body.Phase == 2, "Body must be in Phase 2.");
        Assert(s.Body.AgingCountdown == 1 && s.Right.Creature.GetPower<ThingsCaveGodAgingPower>()!.Amount == 1,
            "Phase transition preserves the shared aging countdown.");
        Assert(!s.Left.Creature.HasPower<StrengthPower>(), "Left arm Strength must be cleared on transition to Phase 2.");
        Assert(!s.Right.Creature.HasPower<StrengthPower>(), "Right arm Strength must be cleared on transition to Phase 2.");

        GD.Print("PASS phase transition clears arm strength");
    }

    private static async Task VerifyCrystalVeinAndBurst()
    {
        foreach (int ascension in new[] { 0, 10 })
        {
            var s = Scenario(count: 2, ascension: ascension);
            for (int i = 0; i < 4; i++) await Act(s);
            Assert(s.Body.CrystalVein == ThingsCaveGodBody.VeinThreshold, "Four cycle moves must fill the vein.");
            var burst = s.Body.NextMove;
            Assert(burst.Id == ThingsCaveGodBody.BurstId, "Full vein must replace the next move with Crystal Burst.");
            Assert(burst.Intents.OfType<AttackIntent>().Any() && burst.Intents.OfType<StatusIntent>().Any() && burst.Intents.OfType<BuffIntent>().Any(),
                "Crystal Burst must telegraph attack + status + buff.");
            Assert(s.Left.NextMove.Id == ThingsCaveGodHand.MoveId(ThingsCaveGodHand.Action.Rest), "Arms rest while the core bursts.");
            int[] shardsBefore = s.State.Players.Select(ShardCount).ToArray();
            int advertised = burst.Intents.OfType<AttackIntent>().Sum(i => i.GetTotalDamage(s.State.PlayerCreatures, s.Body.Creature));
            Assert(advertised == (ascension == 0 ? 12 : 14), $"P1 burst damage expected {(ascension == 0 ? 12 : 14)}, got {advertised}.");
            int[] hpBefore = s.State.PlayerCreatures.Select(c => c.CurrentHp).ToArray();
            await Act(s);
            for (int i = 0; i < s.State.Players.Count; i++)
            {
                Assert(hpBefore[i] - s.State.PlayerCreatures[i].CurrentHp == advertised, "Crystal Burst must hit every player for the advertised damage.");
                Assert(ShardCount(s.State.Players[i]) - shardsBefore[i] == ThingsCaveGodBody.ShardCount, "Each player must receive two Crystal Shards in discard.");
            }
            int gain = ascension == 0 ? 2 : 3;
            foreach (var c in new[] { s.Body.Creature, s.Left.Creature, s.Right.Creature })
                Assert(c.GetPowerAmount<StrengthPower>() == gain, "Crystal Burst must grant the cycle growth.");
            Assert(s.Body.CrystalVein == 0 && !s.Left.Creature.HasPower<ThingsCaveGodCrystalVeinPower>() && !s.Right.Creature.HasPower<ThingsCaveGodCrystalVeinPower>(),
                "Crystal Burst must drain the vein and its mirrors.");
            Assert(s.Body.NextMove.Id == "ALTERNATING_JABS", "Cycle must resume after Crystal Burst.");
            DeactivateSyntheticCombat();
        }
        var shard = (ThingsCaveGodCrystalShard)ModelDb.Card<ThingsCaveGodCrystalShard>().ToMutable();
        Assert(shard.HasTurnEndInHandEffect && shard.Type == CardType.Status, "Crystal Shard must be a status with an end-of-turn hand effect.");
        GD.Print("PASS Crystal Vein fills in 4 moves, burst telegraph/damage/shards/growth at A0/A10, vein drains and cycle resumes");
    }

    private static int ShardCount(Player player) =>
        player.PlayerCombatState!.DiscardPile!.Cards.Count(c => c is ThingsCaveGodCrystalShard);

    private static async Task VerifyArmBreakDrainsVein()
    {
        var s = Scenario();
        for (int i = 0; i < 4; i++) await Act(s);
        Assert(s.Body.NextMove.Id == ThingsCaveGodBody.BurstId, "Setup: burst must be pending.");
        await Hit(s, s.Left.Creature);
        Assert(s.Body.NextMove.Id == "WEAK_PRONE_1", "Arm break must cancel the pending burst.");
        Assert(s.Body.CrystalVein == ThingsCaveGodBody.VeinThreshold - ThingsCaveGodBody.VeinLossOnArmBreak, "Arm break must remove two vein stacks.");
        Assert(s.Right.Creature.GetPowerAmount<ThingsCaveGodCrystalVeinPower>() == s.Body.CrystalVein, "Surviving arm must mirror the drained vein.");
        await Act(s); await Act(s); await Act(s);
        Assert(!s.Body.IsWeakPhase && s.Body.NextMove.Id == "ALTERNATING_JABS", "Recovery must resume the slot after the cancelled burst.");
        Assert(s.Body.CrystalVein == 2, "Exposure must not feed or reset the remaining vein.");
        await Act(s); await Act(s);
        Assert(s.Body.NextMove.Id == ThingsCaveGodBody.BurstId, "Two more moves must refill the vein.");
        GD.Print("PASS arm break cancels pending burst, drains 2 vein, recovery resumes correct slot and vein refills");
    }

    private static async Task VerifyFissure(bool breakBeforeRecoverRoll)
    {
        var s = Scenario();
        for (int i = 0; i < 3; i++) await Act(s); // vein 3 -> 1 after the break
        await Hit(s, s.Left.Creature);
        Assert(s.Body.CrystalVein == 1, "Setup: arm break leaves one vein stack.");
        var fissure = s.Body.Creature.GetPower<ThingsCaveGodFissurePower>();
        int threshold = (int)Math.Ceiling(s.Body.Creature.MaxHp * 0.25m);
        Assert(fissure != null && fissure.Amount == threshold && s.Body.FissureThreshold == threshold, $"Exposure must open a {threshold}-damage fissure.");
        if (breakBeforeRecoverRoll)
        {
            await Hit(s, s.Body.Creature, threshold + 5);
            Assert(s.Body.IsFissureBroken && !s.Body.Creature.HasPower<ThingsCaveGodFissurePower>(), "Enough damage must crack the fissure.");
            await Act(s); await Act(s);
        }
        else
        {
            await Hit(s, s.Body.Creature, threshold - 10);
            Assert(s.Body.Creature.GetPowerAmount<ThingsCaveGodFissurePower>() == 10, "Fissure must count down remaining damage.");
            await Act(s); await Act(s);
            Assert(s.Body.NextMove.Id == "WEAK_UNKNOWN_3" && s.Body.NextMove.Intents.OfType<BuffIntent>().Any(), "Intact fissure keeps the growth telegraph.");
            await Hit(s, s.Body.Creature, 10);
            Assert(s.Body.IsFissureBroken, "Cracking on the recovery turn must register.");
        }
        Assert(s.Body.NextMove.Id == ThingsCaveGodBody.FissureRecoverId && !s.Body.NextMove.Intents.OfType<BuffIntent>().Any(),
            "Cracked fissure must advertise a growth-free recovery.");
        await Act(s);
        Assert(!s.Body.IsWeakPhase && !s.Body.IsFissureBroken, "Fractured recovery must end exposure and reset the flag.");
        foreach (var c in new[] { s.Body.Creature, s.Left.Creature, s.Right.Creature })
            Assert(c.GetPowerAmount<StrengthPower>() == 0, "Cracked fissure must cancel recovery growth.");
        Assert(s.Body.CrystalVein == 0 && !s.Body.Creature.HasPower<ThingsCaveGodFissurePower>(), "Cracked fissure must drain the vein and remove itself.");
        Assert(s.Body.NextMove.Id == "MOUNTAIN_GUARD", "Fractured recovery must resume the interrupted slot.");
        GD.Print($"PASS fissure countdown, crack (before recover roll={breakBeforeRecoverRoll}) swaps to growth-free recovery and drains vein");
    }
}
