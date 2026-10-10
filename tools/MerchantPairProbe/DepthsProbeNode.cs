using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
using Godot;
using Godot.Bridge;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Encounters;
using STS2_Things.Events;

public partial class DepthsProbeNode : Node
{
    private static int _checks;
    private string _root = null!;
    private static void Assert(bool okay, string message)
    {
        if (!okay) throw new InvalidOperationException(message);
        _checks++;
    }
    public override void _Ready()
    {
        AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency;
#if !STS2_V107_1
        EnsureRuntimeDependency("Sentry");EnsureRuntimeDependency("Sentry.Godot");
#endif
        _ = Run();
    }
    private async Task Run()
    {
        try
        {
            _root = Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "../.."));
            TestMode.TurnOnInternal();
            Assert(ProjectSettings.LoadResourcePack(System.Environment.GetEnvironmentVariable("THINGS_VANILLA_PCK")!), "Matching native resource pack");
            Assert(ProjectSettings.LoadResourcePack(System.Environment.GetEnvironmentVariable("THINGS_PROBE_PCK")!), "Final mod pack");
            InitializeModelDb();ScriptManagerBridge.LookupScriptsInAssembly(typeof(ModelDb).Assembly);
            SaveManager.Instance.InitSettingsDataForTest();SaveManager.Instance.InitPrefsDataForTest();
            var extension = GDExtensionManager.LoadExtension(Path.Combine(_root,"addons/spine/spine_godot_extension.gdextension"));
            Assert(extension is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded,"Native Spine extension");
            var atlasType=typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Assets.AtlasResourceLoader");
            var atlas=atlasType==null?null:(ResourceFormatLoader)Activator.CreateInstance(atlasType)!;
            if(atlas!=null)ResourceLoader.AddResourceFormatLoader(atlas,true);
            foreach (int players in new[] {1,2,3,4})
            foreach (int ascension in new[] {0,20})
            {
                var party = Enumerable.Range(1,players).Select(i => Player.CreateForNewRun<Ironclad>(UnlockState.all,(ulong)i)).ToList();
                var run = RunState.CreateForNewRun(party,ActModel.GetDefaultList().Select(a=>a.ToMutable()).ToList(),[],GameMode.Standard,ascension,"merchant-pair");
                typeof(RunManager).GetProperty("State",BindingFlags.Instance|BindingFlags.NonPublic)!.SetValue(RunManager.Instance,run);
                typeof(RunManager).GetProperty("NetService")!.SetValue(RunManager.Instance,new NetSingleplayerGameService());
                typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance,new AscensionManager(ascension));
                LocalContext.NetId = party[0].NetId;
                var old = ModelDb.Encounter<FakeMerchantEventEncounter>().ToMutable();old.GenerateMonstersWithSlots(run);
                Assert(old.MonstersWithSlots.Count == 1, "Native Fake Merchant event remains single");
                var pair = ModelDb.Encounter<RobberyFakeMerchantEncounter>().ToMutable();pair.GenerateMonstersWithSlots(run);
                Assert(pair.MonstersWithSlots.Count == 2 && pair.MonstersWithSlots.All(p=>p.Item1 is FakeMerchantMonster), "Two native merchants");
                Assert(!ReferenceEquals(pair.MonstersWithSlots[0].Item1,pair.MonstersWithSlots[1].Item1), "Separate mutable monsters");
                Assert(pair.Slots.SequenceEqual(new[]{"merchant_left","merchant_right"}), "Distinct slots");
                Assert(pair.MinGoldReward == 300 && pair.MaxGoldReward == 300, "Existing encounter reward retained once");
                var room = new CombatRoom(pair,run);
                foreach(var p in party){p.ResetCombatState();room.CombatState.AddPlayer(p);}
                foreach(var (model,slot) in pair.MonstersWithSlots)
                {
                    var creature = room.CombatState.CreateCreature(model,CombatSide.Enemy,slot);room.CombatState.AddCreature(creature);
                    model.SetUpForCombat();model.RollMove(party.Select(p=>p.Creature));
                }
                int[] original = room.CombatState.Enemies.Select(c=>c.MaxHp).ToArray();
                var prepare = typeof(RobberyFakeMerchantEncounter).GetMethod("PrepareForFight",BindingFlags.Instance|BindingFlags.NonPublic)!;
                for(int callback=0;callback<=players;callback++)await (Task)prepare.Invoke(pair,[room.CombatState])!;
                Assert(room.CombatState.Enemies.Select(c=>c.MaxHp).SequenceEqual(original.Select(h=>Math.Max(1,h/2))), "Health halved once despite all player callbacks");
                Assert(room.CombatState.Enemies.All(c=>c.CurrentHp==c.MaxHp && c.Monster!.NextMove.Intents.Any()), "Both have correct HP and native move intents");
                var scene = pair.CreateScene();
                Assert(pair.Slots.All(s=>scene.HasNode(s)), "Both encounter markers present");scene.Free();
                var bg = pair.CreateBackground(run.Act,run.Rng.UpFront);
                Assert(bg != null, "Native shop background factory loads new event alias");bg!.Free();
                foreach(string path in pair.GetAssetPaths(run))Assert(ResourceLoader.Exists(path), "Pair asset: "+path);
            }
            Assert(ModelDb.Event<RobberyFakeMerchant>().IsShared && ModelDb.Event<RobberyFakeMerchant>().LayoutType==EventLayoutType.Combat,
                "Native shared combat event layout retained");
            Assert(ModelDb.Event<RobberyFakeMerchant>().CanonicalEncounter is RobberyFakeMerchantEncounter, "Event points to pair encounter");
            foreach(string lang in new[]{"zhs","eng"})
            {
                SaveManager.Instance.SettingsSave.Language=lang;LocManager.Initialize();
                var model=ModelDb.Event<RobberyFakeMerchant>();
                Assert(model.InitialDescription.GetFormattedText().Contains(lang=="zhs"?"两名":"Two merchants"), "Pair introductory text");
                var desc=new LocString("events","ROBBERY_FAKE_MERCHANT.pages.INITIAL.options.BEGINFIGHT.description");
                model.DynamicVars.AddTo(desc);
                Assert(desc.GetFormattedText().Contains(lang=="zhs"?"两名":"2 Fake Merchants"), "Battle option advertises both enemies");
                var split=new LocString("events","CUTTING_IT_CLOSE.pages.IMPROVISE.selectionScreenPrompt").GetFormattedText();
                Assert(!split.Contains(lang=="zhs"?"技能":"Skill"), "Attack-only selection text");
            }
            var output=System.Environment.GetEnvironmentVariable("THINGS_PROBE_OUTPUT")!;
            File.WriteAllText(Path.Combine(output,"report.json"),JsonSerializer.Serialize(new
            {
                assertions=_checks,playerCounts=new[]{1,2,3,4},ascensions=new[]{0,20},
                scope="Native monster instances, unmodified original encounter, pair slots/assets/HP/intents, shared preparation idempotence, bilingual text",
                limitation="Single-process model probe; live event transition verified separately"
            },new JsonSerializerOptions{WriteIndented=true}));
            if(atlas!=null)ResourceLoader.RemoveResourceFormatLoader(atlas);
            GD.Print($"Merchant pair probe: PASS ({_checks} assertions)");GetTree().Quit(0);
        }
        catch(Exception e){GD.PushError(e.ToString());GetTree().Quit(1);}
    }
}
