using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json.Nodes;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Cards;

public partial class BugReportProbeNode : Node
{
    private static int _checks;
    private static readonly Type Recorder = typeof(LeechParasite).Assembly.GetType("STS2_Things.Diagnostics.BugRunRecorder")!;
    private static string DirectoryPath => Path.Combine(OS.GetUserDataDir(),"mod_data/STS2_Things/bug_reports");
    public override void _Ready() { AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency; _ = Run(); }
    private static object? Invoke(string method, params object?[] args) => Recorder.GetMethod(method,BindingFlags.NonPublic|BindingFlags.Static)!.Invoke(null,args);
    private static JsonObject Current() => JsonNode.Parse(File.ReadAllText(Path.Combine(DirectoryPath,"current-run.json")))!.AsObject();
    private static void Check(bool test,string name) { if(!test)throw new Exception(name);_checks++; }
    private async Task Run()
    {
        try
        {
            TestMode.TurnOnInternal();
            Check(OS.GetUserDataDir().Contains("ReportTest"),"probe uses independent user directory");
            ProjectSettings.LoadResourcePack("D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck");
            InitializeModelDb();
            SaveManager.Instance.InitSettingsDataForTest();SaveManager.Instance.InitPrefsDataForTest();
            var first=await Scenario("report-first");
            Invoke("Initialize");
            var initial=Current();
            string firstId=initial["client_run_id"]!.GetValue<string>();
            Check(initial["schema"]!.GetValue<int>()==2,"new diagnostic schema");
            var hand=initial["state"]!["players"]![0]!["combat"]!["hand"]!.AsArray();
            Check(hand.Count==2,"actual model hand captured");
            Check(hand[0]!["instance_id"]!.GetValue<string>()!=hand[1]!["instance_id"]!.GetValue<string>(),"same-name cards have distinct IDs");
            Check(hand[0]!["energy"]!.GetValue<int>()==3,"native temporary cost recorded");
            Check(initial["state"]!["players"]![0]!["powers"]![0]!["amount"]!.GetValue<int>()==3,"Power amounts recorded");
            var oldExecutor=RunManager.Instance.ActionExecutor;
            var action=new PlayCardAction(first.Player.PlayerCombatState!.Hand.Cards[0],null);
            Invoke("BeforeAction",action);
            Check(Current()["events"]!.AsArray().Any(e=>e?["kind"]?.GetValue<string>()=="action_started"),"unfinished actions have a starting event");
            Invoke("BeforeChoice",action);
            Check(Current()["events"]!.AsArray().Any(e=>e?["kind"]?.GetValue<string>()=="action_waiting_for_choice"),"waiting choice is retained before completion");
            var second=await Scenario("report-second");
            Invoke("OnStarted",second.Run);
            var current=Current();
            Check(current["client_run_id"]!.GetValue<string>()!=firstId,"second run gets a distinct ID without recursive serialization");
            var previous=JsonNode.Parse(File.ReadAllText(Path.Combine(DirectoryPath,"last-run.json")))!;
            Check(previous["client_run_id"]!.GetValue<string>()==firstId,"previous run is archived correctly");
            var handler=typeof(ActionExecutor).GetField("BeforeActionExecuted",BindingFlags.NonPublic|BindingFlags.Instance)?.GetValue(oldExecutor) as Delegate;
            Check(handler?.GetInvocationList().All(d=>d.Method.DeclaringType!=Recorder)!=false,"old executor is detached");
            Check(current["initial_state"]!["seed"]!.GetValue<string>()=="report-second","new initial snapshot belongs to second run");
            foreach(string name in new[]{"ThingsFeedbackCategoryPatch","ThingsFeedbackSendPatch","ThingsFeedbackReceiptPatch","ThingsFeedbackFailurePatch"})
                Check(typeof(LeechParasite).Assembly.GetType("STS2_Things.Diagnostics."+name) is not null,"shipping F2 patch exists: "+name);
            Check(typeof(MegaCrit.Sts2.Core.Nodes.Screens.FeedbackScreen.NSendFeedbackScreen).GetMethod("SendFeedback",BindingFlags.NonPublic|BindingFlags.Static)!.GetParameters().Length==3,"current native F2 signature includes both owned streams");
            Invoke("DetachExecutor");DeactivateSyntheticCombat();
            GD.Print($"BugReport native probe: PASS ({_checks} assertions)");GetTree().Quit();
        }
        catch(Exception ex){GD.PushError(ex.ToString());GetTree().Quit(1);}
    }
    private static async Task<(RunState Run,Player Player)> Scenario(string seed)
    {
        DeactivateSyntheticCombat();
        var player=Player.CreateForNewRun<Ironclad>(UnlockState.all,1);
        var run=RunState.CreateForNewRun([player],ActModel.GetDefaultList().Select(a=>a.ToMutable()).ToList(),[],GameMode.Standard,0,seed);
        typeof(RunManager).GetProperty("State",BindingFlags.NonPublic|BindingFlags.Instance)!.SetValue(RunManager.Instance,run);
        typeof(RunManager).GetProperty("NetService")!.SetValue(RunManager.Instance,new NetSingleplayerGameService());
        typeof(RunManager).GetProperty("ActionExecutor")!.SetValue(RunManager.Instance,new ActionExecutor(new ActionQueueSet([player])));
        typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance,new AscensionManager(0));
        var encounter=ModelDb.AllEncounters.First(e=>e.Id.Entry=="SLIMES_WEAK").ToMutable();
        var room=new CombatRoom(encounter,run);run.PushRoom(room);room.CombatState.AddPlayer(player);player.ResetCombatState();
        player.Creature.SetMaxHpInternal(70);player.Creature.SetCurrentHpInternal(70);
        encounter.GenerateMonstersWithSlots(run);
        foreach(var (monster,slot) in encounter.MonstersWithSlots)
        {
            var creature=room.CombatState.CreateCreature(monster,CombatSide.Enemy,slot);room.CombatState.AddCreature(creature);
            monster.SetUpForCombat();monster.RollMove([player.Creature]);
        }
        room.CombatState.CurrentSide=CombatSide.Player;ActivateSyntheticCombat(room.CombatState);
        var card=room.CombatState.CreateCard<LeechParasite>(player);card.EnergyCost.SetUntilPlayed(3);
        player.PlayerCombatState!.Hand.AddInternal(card,silent:true);
        player.PlayerCombatState.Hand.AddInternal(room.CombatState.CreateCard<LeechParasite>(player),silent:true);
        player.PlayerCombatState.Energy=3;player.PlayerCombatState.Phase=PlayerTurnPhase.Play;
        NetCombatCardDb.Instance.StartCombat([player]);
        await PowerCmd.Apply<StrengthPower>(new ThrowingPlayerChoiceContext(),player.Creature,3,player.Creature,null,silent:true);
        return (run,player);
    }
}
