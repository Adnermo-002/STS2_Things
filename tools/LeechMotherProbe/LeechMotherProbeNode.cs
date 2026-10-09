using System.Reflection;
using System.Runtime.Loader;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Acts;
using STS2_Things.Cards;
using STS2_Things.Encounters;
using STS2_Things.Monsters;
using STS2_Things.Powers;

public partial class LeechMotherProbeNode : Node
{
    private static readonly ThrowingPlayerChoiceContext Choice = new();
    private static int _checks;
    public override void _Ready() { AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency; _ = Run(); }
    private async Task Run()
    {
        try
        {
            TestMode.TurnOnInternal();
            ProjectSettings.LoadResourcePack("D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck");
            string? pack = System.Environment.GetEnvironmentVariable("THINGS_PROBE_PCK");
            if (pack != null) Assert(ProjectSettings.LoadResourcePack(pack), "Shipping resource package mounts");
            SaveManager.Instance.InitSettingsDataForTest(); SaveManager.Instance.InitPrefsDataForTest();
            SaveManager.Instance.SettingsSave.Language = "zhs"; LocManager.Initialize(); InitializeModelDb();
            Assert(ModelDb.Act<Depths>().AllRegularEncounters.Any(e => e is LeechMotherEncounter), "Strong pool includes mother");
            Assert(!ModelDb.Act<Depths>().AllWeakEncounters.Any(e => e is LeechMotherEncounter), "Mother never enters weak pool");
            foreach (int players in new[] { 1, 2, 3, 4 })
            {
                await SleepingExit(players);
                await AwakenedCombat(players);
            }
            await LateWake();
            await KillSleeping();
            await FullHandAndStun();
            DeactivateSyntheticCombat();
            GD.Print($"Leech Mother probe: PASS ({_checks} assertions)"); GetTree().Quit();
        }
        catch (Exception e) { GD.PushError(e.ToString()); GetTree().Quit(1); }
    }
    private static async Task<Fixture> Scenario(int players = 1, int ascension = 0)
    {
        DeactivateSyntheticCombat();
        var party = Enumerable.Range(1, players).Select(i => Player.CreateForNewRun<Ironclad>(UnlockState.all, (ulong)i)).ToList();
        var run = RunState.CreateForNewRun(party, ActModel.GetDefaultList().Select(a => a.ToMutable()).ToList(), [], GameMode.Standard, ascension, "leech-mother-native");
        run.CurrentActIndex = 1;
        typeof(RunManager).GetProperty("State", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(RunManager.Instance, run);
        typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance, new AscensionManager(ascension));
        typeof(RunManager).GetProperty("NetService")!.SetValue(RunManager.Instance, new NetSingleplayerGameService());
        var encounter = (LeechMotherEncounter)ModelDb.Encounter<LeechMotherEncounter>().ToMutable();
        run.AppendToMapPointHistory(MapPointType.Monster, RoomType.Monster, encounter.Id);
        var room = new CombatRoom(encounter, run); run.PushRoom(room);
        foreach (var p in party) { p.ResetCombatState(); room.CombatState.AddPlayer(p); p.PopulateCombatState(run.Rng.Shuffle, room.CombatState); p.Creature.SetMaxHpInternal(10000); p.Creature.SetCurrentHpInternal(10000); }
        encounter.GenerateMonstersWithSlots(run);
        foreach (var (monster, slot) in encounter.MonstersWithSlots)
        {
            var creature = room.CombatState.CreateCreature(monster, CombatSide.Enemy, slot); room.CombatState.AddCreature(creature); monster.SetUpForCombat(); monster.RollMove(party.Select(p => p.Creature));
        }
        room.CombatState.CurrentSide = CombatSide.Player; ActivateSyntheticCombat(room.CombatState);
        var mother = (LeechMother)encounter.MonstersWithSlots.Single().Item1;
        await mother.AfterAddedToRoom(); await Hook.BeforeCombatStart(run, room.CombatState);
        return new(run, room, encounter, mother, party);
    }
    private static async Task EnemyEnd(Fixture f)
    {
        f.State.CurrentSide = CombatSide.Enemy;
        var hook = typeof(Hook).GetMethod("AfterSideTurnEnd", BindingFlags.Public | BindingFlags.Static)
            ?? typeof(Hook).GetMethod("AfterTurnEnd", BindingFlags.Public | BindingFlags.Static)!;
        await (Task)hook.Invoke(null, [f.State, CombatSide.Enemy, f.State.Enemies.ToArray()])!;
    }
    private static async Task SleepingExit(int players)
    {
        var f = await Scenario(players);
        Assert(!f.Mother.IsAwake && f.Mother.NextMove.Intents.Single().GetType().Name == "SleepIntent", "Starts asleep with native sleep intent");
        Assert(f.Encounter.ShouldGiveRewards && f.State.Enemies.Count() == 1, "Only one initial enemy, normal reward eligibility");
        Assert(f.Players.All(p => p.PlayerCombatState!.Hand.Cards.Count == 0), "Sleeping mother creates no opening parasites");
        for (int turn = 1; turn <= 3; turn++)
        {
            await EnemyEnd(f);
            if (turn < 3) Assert(f.State.Enemies.Contains(f.Mother.Creature) && f.Mother.Creature.GetPower<LeechMotherSlumberPower>()?.Amount == 3-turn, "Two full opportunities before departure");
        }
        Assert(!f.State.Enemies.Contains(f.Mother.Creature) && !f.Encounter.ShouldGiveRewards, "Third undisturbed round removes enemy and disables all rewards");
        Assert(f.State.EscapedCreatures.Contains(f.Mother.Creature), "Exit uses native escape accounting");
        var restored = (LeechMotherEncounter)ModelDb.Encounter<LeechMotherEncounter>().ToMutable(); restored.LoadCustomState(f.Encounter.SaveCustomState());
        Assert(!restored.ShouldGiveRewards && ModelDb.Encounter<LeechMotherEncounter>().ShouldGiveRewards, "No-reward state persists without canonical contamination");
    }
    private static async Task AwakenedCombat(int players)
    {
        var f = await Scenario(players, ascension:20);
        Assert(f.Mother.MinInitialHp == 89, "High ascension reference HP");
        await CreatureCmd.GainBlock(f.Mother.Creature, 1000, ValueProp.Unpowered, null);
        int hp = f.Mother.Creature.CurrentHp;
        var card = f.State.CreateCard<StrikeIronclad>(f.Players[0]);
#if STS2_V107_1
        await DamageCmd.Attack(1).FromCard(card).Targeting(f.Mother.Creature).Execute(Choice);
#else
        await DamageCmd.Attack(1).FromCard(card, null).Targeting(f.Mother.Creature).Execute(Choice);
#endif
        Assert(f.Mother.Creature.CurrentHp == hp && f.Mother.IsAwake, "Even a fully blocked player attack wakes her");
        Assert(!f.Mother.Creature.HasPower<LeechMotherSlumberPower>() && !f.Mother.Creature.HasPower<PlatingPower>(), "Wake clears sleep and plating through native commands");
        Assert(f.Mother.NextMove.Id == LeechMother.BroodMoveId, "First advertised awake action is brood");
        f.State.CurrentSide = CombatSide.Enemy;
        await f.Mother.PerformMove();
        var brood = f.State.Enemies.Select(c => c.Monster).OfType<SanguineLeech>().ToArray();
        Assert(brood.Length == 2 && brood.All(l => l.SpawnedThisTurn), "Exactly two native summons; neither acts immediately");
        Assert(brood.All(l => l.Creature.HasPower<LeechInfestationPower>()), "Summoned leeches retain delayed reinfestation hook");
        Assert(f.Players.All(p => p.PlayerCombatState!.Hand.Cards.OfType<LeechParasite>().Count() == 2), "Exactly two parasites in each player's hand");
        foreach (var p in f.Players) await Hook.BeforeHandDraw(f.State, p, Choice);
        Assert(f.Players.All(p => p.PlayerCombatState!.Hand.Cards.OfType<LeechParasite>().Count() == 2), "Summoned leeches do not add a second opening delivery");
        foreach (var p in f.Players)
            foreach (var status in p.PlayerCombatState!.Hand.Cards.ToArray()) await CardCmd.Discard(Choice, status);
        string[] cycle = ["SIP_MOVE", "CRUSH_MOVE", "REST_MOVE", "SIP_MOVE"];
        foreach (var id in cycle)
        {
            f.Mother.RollMove(f.Players.Select(p => p.Creature)); Assert(f.Mother.NextMove.Id == id, "Finite awake cycle without more summons");
            await f.Mother.PerformMove();
        }
        Assert(f.State.Enemies.Count(c => c.Monster is SanguineLeech) == 2 && f.Encounter.ShouldGiveRewards, "Awake fight remains normally rewarded and capped at two brood");
        Assert(f.Players.All(p => !p.Deck.Cards.OfType<LeechParasite>().Any()), "Parasites never enter permanent decks");
    }
    private static async Task LateWake()
    {
        var f = await Scenario(); await EnemyEnd(f); await EnemyEnd(f);
        await f.Mother.PerformMove();
        await f.Mother.Wake(); await EnemyEnd(f);
        Assert(f.Mother.IsAwake && f.State.Enemies.Contains(f.Mother.Creature) && f.Encounter.ShouldGiveRewards, "Attack in third player window prevents peaceful exit");
        f.Mother.RollMove(f.Players.Select(p=>p.Creature));
        Assert(f.Mother.NextMove.Id==LeechMother.BroodMoveId,"Waking during enemy-side damage does not skip the first summon");
    }
    private static async Task KillSleeping()
    {
        var f = await Scenario(); await CreatureCmd.Damage(Choice, f.Mother.Creature, 9999, ValueProp.Unpowered, f.Players[0].Creature);
        Assert(!f.Mother.Creature.IsAlive && f.Encounter.ShouldGiveRewards && f.State.Enemies.All(c => c.Monster is not SanguineLeech), "One-shot kill gives normal rewards without summoning");
    }
    private static async Task FullHandAndStun()
    {
        var f=await Scenario(players:2);
        var full=f.Players[0]; var free=f.Players[1];
        for(int i=0;i<CardPile.MaxCardsInHand;i++)
            await CardPileCmd.AddGeneratedCardToCombat(f.State.CreateCard<StrikeIronclad>(full),PileType.Hand,full);
        await f.Mother.Wake();
        await CreatureCmd.Stun(f.Mother.Creature);
        Assert(f.Mother.NextMove.Id=="STUNNED","Brood remains interruptible by native stun");
        await f.Mother.PerformMove();
        await EnemyEnd(f);
        f.Mother.RollMove(f.Players.Select(p=>p.Creature));
        Assert(f.Mother.NextMove.Id==LeechMother.BroodMoveId,"Stun postpones rather than skips the first brood action");
        f.State.CurrentSide=CombatSide.Enemy;
        await f.Mother.PerformMove();
        Assert(full.PlayerCombatState!.Hand.Cards.Count==CardPile.MaxCardsInHand &&
            full.PlayerCombatState.DiscardPile.Cards.OfType<LeechParasite>().Count()==2,"Brood statuses respect native full-hand overflow");
        Assert(free.PlayerCombatState!.Hand.Cards.OfType<LeechParasite>().Count()==2,"Free player's brood statuses remain in hand");
    }
    private static void Assert(bool value,string message) { if(!value)throw new Exception(message);_checks++; }
    private sealed record Fixture(RunState Run,CombatRoom Room,LeechMotherEncounter Encounter,LeechMother Mother,List<Player> Players)
    { public CombatState State => Room.CombatState; }
}
