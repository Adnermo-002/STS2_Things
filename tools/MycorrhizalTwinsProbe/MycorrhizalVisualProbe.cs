using System.Text.Json;
using Godot;
using Godot.Bridge;
using HarmonyLib;
using MegaCrit.Sts2.Core.Assets;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Monsters;
using STS2_Things.Hooks;
using STS2_Things.Powers;
using STS2_Things.Visuals;

public partial class MycorrhizalTwinsProbeNode
{
    private static bool SkipUiGuard()=>false;
    private static void Pose(Node2D sprite,string name,float time)
    {
        sprite.Call("get_skeleton").AsGodotObject().Call("set_to_setup_pose");
        var state=sprite.Call("get_animation_state").AsGodotObject();state.Call("clear_track",0);
        var track=state.Call("set_animation",name,false,0).AsGodotObject();track.Call("set_track_time",time);track.Call("set_mix_duration",0f);sprite.Call("update_skeleton",0f);
    }
    private async Task RenderProbe()
    {
        string output=Path.Combine(System.Environment.GetEnvironmentVariable("THINGS_PROBE_OUTPUT")??Path.Combine(_root,"build/mycorrhizal_twins"),"visuals");Directory.CreateDirectory(output);
        var ext=GDExtensionManager.LoadExtension(Path.Combine(_root,"addons/spine/spine_godot_extension.gdextension"));
        Assert(ext is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded,"Native Spine extension.");
        var ui=new Harmony("MycorrhizalTwinsProbe.VisualHost");ui.Patch(AccessTools.Method(typeof(CombatStateTracker),"NotifyCombatStateChanged"),prefix:new HarmonyMethod(typeof(MycorrhizalTwinsProbeNode),nameof(SkipUiGuard)));
        ui.CreateClassProcessor(typeof(MycorrhizalPlayerLayoutPatch)).Patch();
        ScriptManagerBridge.LookupScriptsInAssembly(typeof(NCreature).Assembly);ScriptManagerBridge.LookupScriptsInAssembly(typeof(MycorrhizalTwin).Assembly);
        var loaderType=typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Assets.AtlasResourceLoader");var loader=loaderType==null?null:(ResourceFormatLoader)Activator.CreateInstance(loaderType)!;
        if(loader!=null)ResourceLoader.AddResourceFormatLoader(loader,true);
        SaveManager.Instance.SettingsSave.Language="zhs";LocManager.Initialize();GetTree().Root.Size=new Vector2I(1920,1080);
        var view=new SubViewport{Size=new Vector2I(1920,1080),Disable3D=true,RenderTargetUpdateMode=SubViewport.UpdateMode.Always};AddChild(view);
        async Task Frames(int n){for(int i=0;i<n;i++)await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);RenderingServer.ForceDraw();}
        async Task Settle(float seconds){await ToSignal(GetTree().CreateTimer(seconds),SceneTreeTimer.SignalName.Timeout);await Frames(3);}
        async Task Capture(string name)
        {
            // The fixture suppresses the global UI tracker; refresh its real
            // health bars explicitly after native HP commands.
            foreach(var bar in view.FindChildren("*","",true,false).OfType<NHealthBar>())bar.RefreshValues();
            await Frames(3);using var im=view.GetTexture().GetImage();Assert(im.SavePng(Path.Combine(output,name+".png"))==Error.Ok,"Capture "+name);
        }
        NCreature Add(Creature e,string slug,Vector2 pos,Node? parent=null)
        {
            var node=GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
            typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(node,e);
            typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(node,GD.Load<PackedScene>($"res://scenes/creature_visuals/{slug}.tscn").Instantiate<NCreatureVisuals>());
            node.Position=pos;(parent??view).AddChild(node);return node;
        }
        var s=await Scenario();
        var bg=NCombatBackground.Create(new BackgroundAssets(s.Encounter.Id.Entry.ToLowerInvariant(),new Rng()));bg.Position=new Vector2(983,540);view.AddChild(bg);
        var slots=s.Encounter.CreateScene();view.AddChild(slots);
        var allyContainer=new Node2D{Position=new Vector2(960,540)};view.AddChild(allyContainer);
        var hero=Add(s.Player.Creature,"ironclad",Vector2.Zero,allyContainer);
        NCombatRoom.PositionPlayersAndPets([hero],1,false);
        var tall=Add(s.Tall.Creature,"mycorrhizal_vanguard",slots.GetNode<Node2D>("vanguard").Position);
        var small=Add(s.Short.Creature,"mycorrhizal_bulwark",slots.GetNode<Node2D>("bulwark").Position);
        var sprites=new[]{tall.Visuals.GetNode<Node2D>("Visuals"),small.Visuals.GetNode<Node2D>("Visuals")};
        foreach(var n in new[]{tall,small}){await n.UpdateIntent(s.Players.Select(p=>p.Creature).ToArray());n.IntentContainer.Modulate=Colors.White;}
        foreach(var sprite in sprites){sprite.Call("set_update_mode",ClassDB.ClassGetIntegerConstant("SpineConstant","UpdateMode_Manual"));Pose(sprite,"idle_loop",0);}
        await Settle(1.1f);await Capture("01_elite_robust_elder");
        if(System.Environment.GetEnvironmentVariable("THINGS_GROUNDING_REVIEW")=="1") CheckGrounding(view,hero,tall,small,output);
        Assert(tall.Visuals.GetNode<NMycorrhizalLink>("RootLink").HasPartner,"Visible root follows actual partner node.");
        Assert(s.Tall.Creature.GetPower<MycorrhizalBondPower>()!.HoverTips.OfType<HoverTip>().First().Description.Contains("25"),"Formatted native robust description.");
        Assert(ModelDb.Power<MycorrhizalBondPower>().BigIcon.GetSize()==new Vector2(256,256),"Native large icon.");
        var scaleBefore=sprites[0].Scale;
        await CreatureCmd.SetCurrentHp(s.Short.Creature,28);await EndRound(s);await Settle(1.2f);
        foreach(var n in new[]{tall,small}){await n.UpdateIntent(s.Players.Select(p=>p.Creature).ToArray());n.IntentContainer.Modulate=Colors.White;}
        foreach(var sprite in sprites)Pose(sprite,"idle_loop",0);
        await Capture("02_exchanged_robust_younger");Assert(sprites[0].Scale.X<scaleBefore.X*.85f,"Exchange visibly changes stature.");
        if(System.Environment.GetEnvironmentVariable("THINGS_GROUNDING_REVIEW")=="1") CheckGrounding(view,hero,tall,small,output,"grounding-swapped");
        Assert(s.Tall.Creature.CurrentHp==28&&s.Short.Creature.CurrentHp==102,"Rendered HP follows transfer.");
        NMycorrhizalLink.Pulse(s.Tall.Creature,s.Short.Creature);await Settle(.4f);await Capture("03_root_transfer");
        if(OS.GetCmdlineUserArgs().Contains("--motion"))
        {
            const int fps=20;string frames=Path.Combine(output,"motion");Directory.CreateDirectory(frames);var clips=new List<object>();int total=0;
            foreach(var(name,length) in new(string,float)[]{("idle_loop",3.6f),("attack",1.28f),("double_attack",1.52f),("cast",1.5f),("guard",1.5f),("exchange",1.55f),("enrage",1.6f),("hurt",.62f),("power_up",1.35f),("die",1.9f),("revive",1.7f),("summon",1.4f)})
            {
                int count=(int)Math.Ceiling(length*fps)+1;
                for(int frame=0;frame<count;frame++)
                {
                    foreach(var sprite in sprites)Pose(sprite,name,Math.Min(frame/(float)fps,length));await Frames(2);
                    using var im=view.GetTexture().GetImage();im.Resize(1280,720,Image.Interpolation.Lanczos);
                    Assert(im.SaveJpg(Path.Combine(frames,$"twins_{name}_{frame:D4}.jpg"),.94f)==Error.Ok,"Native paired motion frame");total++;
                }
                clips.Add(new{slug="twins_"+name,name,duration=length,frames=count});GD.Print("Captured twins "+name);
            }
            File.WriteAllText(Path.Combine(frames,"report.json"),JsonSerializer.Serialize(new{fps,frames=total,clips},new JsonSerializerOptions{WriteIndented=true}));
        }
        foreach(var sprite in sprites)Pose(sprite,"idle_loop",0);
        await CreatureCmd.Damage(Choice,s.Short.Creature,9999,ValueProp.Unpowered,s.Player.Creature);await Settle(1.2f);Pose(sprites[0],"enrage",.7f);
        Pose(sprites[1],"die",1.9f);small.IntentContainer.Modulate=Colors.Transparent;
        await tall.UpdateIntent(s.Players.Select(p=>p.Creature).ToArray());tall.IntentContainer.Modulate=Colors.White;
        await Capture("04_surviving_elder_fury");Assert(s.Tall.IsFurious&&s.Tall.Creature.GetPower<MycorrhizalBondPower>()==null,"Rendered severed fury.");
        foreach(var child in view.GetChildren()){view.RemoveChild(child);child.QueueFree();}await Frames(3);
        if(System.Environment.GetEnvironmentVariable("THINGS_PLAYER_LAYOUT_REVIEW")=="1")
        {
            foreach(int count in new[]{2,4})
            {
                var party=await Scenario(players:count);
                var background=NCombatBackground.Create(new BackgroundAssets(party.Encounter.Id.Entry.ToLowerInvariant(),new Rng()));
                background.Position=new Vector2(983,540);view.AddChild(background);
                var allies=new Node2D{Position=new Vector2(960,540)};view.AddChild(allies);
                var players=party.Players.Select(p=>Add(p.Creature,"ironclad",Vector2.Zero,allies)).ToList();
                NCombatRoom.PositionPlayersAndPets(players,1,false);
                Add(party.Tall.Creature,"mycorrhizal_vanguard",new Vector2(1235,800));
                Add(party.Short.Creature,"mycorrhizal_bulwark",new Vector2(1635,790));
                await Settle(.9f);await Capture("players_"+count);
                File.WriteAllText(Path.Combine(output,$"players_{count}.json"),JsonSerializer.Serialize(players.Select(p=>new{x=p.GlobalPosition.X,y=p.GlobalPosition.Y})));
                foreach(var child in view.GetChildren()){view.RemoveChild(child);child.QueueFree();}await Frames(3);
            }
        }
        view.QueueFree();
        DeactivateSyntheticCombat();ui.UnpatchAll(ui.Id);if(loader!=null)ResourceLoader.RemoveResourceFormatLoader(loader);
        PreloadManager.Cache.GetType().GetMethod("UnloadMissedCacheAssets")?.Invoke(PreloadManager.Cache,null);
        GC.Collect();GC.WaitForPendingFinalizers();await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);RenderingServer.ForceDraw();
    }
}
