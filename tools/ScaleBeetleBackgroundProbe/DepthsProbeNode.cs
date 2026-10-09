using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
using Godot;
using Godot.Bridge;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Encounters;
using STS2_Things.Monsters;

public partial class DepthsProbeNode : Node
{
    private static int _checks;
    private string _root=null!;
    private static void Assert(bool ok,string text){if(!ok)throw new InvalidOperationException(text);_checks++;}
    private static bool SkipUiGuard()=>false;
    public override void _Ready()
    {
        AssemblyLoadContext.Default.Resolving+=ResolveRuntimeDependency;
#if !STS2_V107_1
        EnsureRuntimeDependency("Sentry");EnsureRuntimeDependency("Sentry.Godot");
#endif
        _=Run();
    }
    private async Task Run()
    {
        try
        {
            _root=Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"),"../.."));
            TestMode.TurnOnInternal();
            Assert(ProjectSettings.LoadResourcePack("D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck"),"Vanilla pack");
            Assert(ProjectSettings.LoadResourcePack(System.Environment.GetEnvironmentVariable("THINGS_PROBE_PCK")!),"Final background pack");
            InitializeModelDb();ScriptManagerBridge.LookupScriptsInAssembly(typeof(ModelDb).Assembly);
            ScriptManagerBridge.LookupScriptsInAssembly(typeof(ThingsScaleBeetle).Assembly);
            SaveManager.Instance.InitSettingsDataForTest();SaveManager.Instance.InitPrefsDataForTest();
            SaveManager.Instance.SettingsSave.Language="zhs";LocManager.Initialize();
            var ext=GDExtensionManager.LoadExtension(Path.Combine(_root,"addons/spine/spine_godot_extension.gdextension"));
            Assert(ext is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded,"Spine");
            var loaderType=typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Assets.AtlasResourceLoader");
            var loader=loaderType==null?null:(ResourceFormatLoader)Activator.CreateInstance(loaderType)!;
            if(loader!=null)ResourceLoader.AddResourceFormatLoader(loader,true);
            var host=new Harmony("ScaleBeetleBackgroundProbe.UiHost");
            host.Patch(AccessTools.Method(typeof(CombatStateTracker),"NotifyCombatStateChanged"),
                prefix:new HarmonyMethod(typeof(DepthsProbeNode),nameof(SkipUiGuard)));
            string output=System.Environment.GetEnvironmentVariable("THINGS_PROBE_OUTPUT")!;
            Directory.CreateDirectory(output);
            var view=new SubViewport{Size=new Vector2I(1920,1080),Disable3D=true,RenderTargetUpdateMode=SubViewport.UpdateMode.Always};
            AddChild(view);GetTree().Root.Size=view.Size;
            foreach(int count in new[]{1,4})
            {
                DeactivateSyntheticCombat();
                var players=Enumerable.Range(1,count).Select(i=>Player.CreateForNewRun<Ironclad>(UnlockState.all,(ulong)i)).ToList();
                var run=RunState.CreateForNewRun(players,ActModel.GetDefaultList().Select(a=>a.ToMutable()).ToList(),[],GameMode.Standard,0,"beetle-background");
                typeof(RunManager).GetProperty("State",BindingFlags.NonPublic|BindingFlags.Instance)!.SetValue(RunManager.Instance,run);
                typeof(RunManager).GetProperty("NetService")!.SetValue(RunManager.Instance,new NetSingleplayerGameService());
                typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance,new AscensionManager(0));
                var encounter=ModelDb.Encounter<ScaleBeetleBossEncounter>().ToMutable();
                var room=new CombatRoom(encounter,run);run.PushRoom(room);
                foreach(var p in players){p.ResetCombatState();room.CombatState.AddPlayer(p);}
                encounter.GenerateMonstersWithSlots(run);
                var model=encounter.MonstersWithSlots.Single().Item1;
                var entity=room.CombatState.CreateCreature(model,CombatSide.Enemy,"scale_beetle");
                room.CombatState.AddCreature(entity);model.SetUpForCombat();model.RollMove(players.Select(p=>p.Creature));
                ActivateSyntheticCombat(room.CombatState);
                var assets=new BackgroundAssets("scale_beetle_boss_encounter",new Rng(139UL));
                Assert(assets.BgLayers.Count==2 && assets.FgLayer!=null,"Native discovery sees backdrop/floor/foreground");
                var world=new Control{Size=view.Size};
                view.AddChild(world);
                var bg=NCombatBackground.Create(assets);bg.Position=new Vector2(983,540);bg.Scale=Vector2.One*.9f;
                world.AddChild(bg);
                Assert(bg.GetNode("Layer_00").GetChildCount()==1 && bg.GetNode("Layer_01").GetChildCount()==1 &&
                    bg.GetNode("Foreground").GetChildCount()==1,"All layers mounted through original factory");
                var creatures=new List<NCreature>();
                NCreature Add(Creature creature)
                {
                    var node=GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
                    typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(node,creature);
                    typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(node,
                        creature.Monster?.CreateVisuals() ?? creature.Player!.Character.CreateVisuals());
                    return node;
                }
                var team=new Node2D{Position=new Vector2(960,540)};world.AddChild(team);
                foreach(var p in players){var hero=Add(p.Creature);team.AddChild(hero);creatures.Add(hero);}
                NCombatRoom.PositionPlayersAndPets(creatures,encounter.GetCameraScaling(),encounter.FullyCenterPlayers);
                var slots=encounter.CreateScene();world.AddChild(slots);
                var beetle=Add(entity);beetle.Position=slots.GetNode<Node2D>("scale_beetle").Position;world.AddChild(beetle);
                await beetle.UpdateIntent(players.Select(p=>p.Creature));beetle.IntentContainer.Modulate=Colors.White;
                await ToSignal(GetTree().CreateTimer(.35),SceneTreeTimer.SignalName.Timeout);
                await ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
                using(var image=view.GetTexture().GetImage())Assert(image.SavePng(Path.Combine(output,"party-"+count+".png"))==Error.Ok,"Combat composite");
                bg.GetNode<Control>("Foreground").Visible=false;
                await ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
                using(var image=view.GetTexture().GetImage())Assert(image.SavePng(Path.Combine(output,"party-"+count+"-no-foreground.png"))==Error.Ok,"Clean plate proof");
                foreach(var child in view.GetChildren()){view.RemoveChild(child);child.QueueFree();}
                await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            }
            view.QueueFree();await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            DeactivateSyntheticCombat();host.UnpatchAll(host.Id);
            if(loader!=null)ResourceLoader.RemoveResourceFormatLoader(loader);
            File.WriteAllText(Path.Combine(output,"report.json"),JsonSerializer.Serialize(new{assertions=_checks,
                cases=new[]{1,4},render="native game background factory and creature components; not a live client"}));
            GD.Print("Scale Beetle background probe: PASS ("+_checks+" assertions)");
            GetTree().Quit(0);
        }
        catch(Exception e){GD.PushError(e.ToString());GetTree().Quit(1);}
    }
}
