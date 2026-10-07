using System.Text.Json;
using Godot;
using Godot.Bridge;
using HarmonyLib;
using MegaCrit.Sts2.Core.Assets;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Saves;
using STS2_Things.Afflictions;
using STS2_Things.Monsters;
using STS2_Things.Powers;
using STS2_Things.Visuals;

public partial class SilkMothProbeNode
{
    private static readonly Dictionary<CardModel,NCard> ShownCards=[];
    private static bool FindRenderCard(CardModel card,ref NCard? __result)
    { if(!ShownCards.TryGetValue(card,out var shown))return true;__result=shown;return false; }
    private static bool SkipUiGuard()=>false;
    private static void Pose(Node2D sprite,string animation,float time)
    {
        sprite.Call("get_skeleton").AsGodotObject().Call("set_to_setup_pose");
        var state=sprite.Call("get_animation_state").AsGodotObject();state.Call("clear_tracks");
        var track=state.Call("set_animation",animation,false,0).AsGodotObject();
        track.Call("set_track_time",time);track.Call("set_mix_duration",0f);sprite.Call("update_skeleton",0f);
    }

    private async Task RenderProbe()
    {
        string output=Path.Combine(System.Environment.GetEnvironmentVariable("THINGS_PROBE_OUTPUT")??Path.Combine(_root,"build/silk_moth"),"visuals");Directory.CreateDirectory(output);
        var extension=GDExtensionManager.LoadExtension(Path.Combine(_root,"addons/spine/spine_godot_extension.gdextension"));
        Assert(extension is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded,"Native Spine extension.");
        var ui=new Harmony("SilkMothProbe.VisualHost");
        ui.Patch(AccessTools.Method(typeof(CombatStateTracker),"NotifyCombatStateChanged"),prefix:new HarmonyMethod(typeof(SilkMothProbeNode),nameof(SkipUiGuard)));
        ui.Patch(AccessTools.Method(typeof(NCard),nameof(NCard.FindOnTable)),prefix:new HarmonyMethod(typeof(SilkMothProbeNode),nameof(FindRenderCard)));
        ScriptManagerBridge.LookupScriptsInAssembly(typeof(NCard).Assembly);ScriptManagerBridge.LookupScriptsInAssembly(typeof(SilkMoth).Assembly);
        var loaderType=typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Assets.AtlasResourceLoader");
        var loader=loaderType==null?null:(ResourceFormatLoader)Activator.CreateInstance(loaderType)!;
        if(loader!=null)ResourceLoader.AddResourceFormatLoader(loader,true);
        SaveManager.Instance.SettingsSave.Language="zhs";LocManager.Initialize();
        GetTree().Root.Size=new Vector2I(1920,1080);
        var view=new SubViewport{Size=new Vector2I(1920,1080),Disable3D=true,RenderTargetUpdateMode=SubViewport.UpdateMode.Always};AddChild(view);
        async Task Capture(string name)
        {
            await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);RenderingServer.ForceDraw();
            using var image=view.GetTexture().GetImage();Assert(image.SavePng(Path.Combine(output,name+".png"))==Error.Ok,"Captured "+name);
        }
        NCreature AddCreature(Creature entity,string path,Vector2 position)
        {
            var node=GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
            typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(node,entity);
            typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(node,GD.Load<PackedScene>(path).Instantiate<NCreatureVisuals>());
            node.Position=position;view.AddChild(node);return node;
        }
        foreach(bool weak in new[]{true,false})
        {
            var s=await Scenario(weak);
            var bg=NCombatBackground.Create(new BackgroundAssets(s.Encounter.Id.Entry.ToLowerInvariant(),new Rng()));
            bg.Position=new Vector2(983,540);view.AddChild(bg);
            var slots=s.Encounter.CreateScene();view.AddChild(slots);
            var playerNode=AddCreature(s.Player.Creature,"res://scenes/creature_visuals/ironclad.tscn",new Vector2(480,746));
            NCreature? mothNode=null;
            foreach(var(monster,_) in s.Encounter.MonstersWithSlots)
            {
                string slug=monster is SilkMoth?"silk_moth":"sanguine_leech";
                var node=AddCreature(monster.Creature,$"res://scenes/creature_visuals/{slug}.tscn",slots.GetNode<Node2D>(monster.Creature.SlotName!).Position);
                await node.UpdateIntent(s.Players.Select(p=>p.Creature).ToArray());node.IntentContainer.Modulate=Colors.White;
                var sprite=node.Visuals.GetNode<Node2D>("Visuals");sprite.Call("set_update_mode",ClassDB.ClassGetIntegerConstant("SpineConstant","UpdateMode_Manual"));Pose(sprite,"idle_loop",0);
                if(monster is SilkMoth)mothNode=node;
            }
            for(int frame=0;frame<12;frame++)await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            await Capture(weak?"weak_pair":"strong_colony");
            var mothSprite=mothNode!.Visuals.GetNode<Node2D>("Visuals");
            Pose(mothSprite,"cast",.67f);await Capture(weak?"weak_cast":"strong_cast");
            Pose(mothSprite,"idle_loop",0);
            if(weak)
            {
                await BasicHand(s);
                int index=0;
                foreach(var model in s.Player.PlayerCombatState!.Hand.Cards)
                {
                    var card=GD.Load<PackedScene>("res://scenes/cards/card.tscn").Instantiate<NCard>();
                    card.Model=model;card.Position=new Vector2(435+index*245,922);card.Scale=Vector2.One*.60f;
                    view.AddChild(card);card.UpdateVisuals(PileType.Hand,CardPreviewMode.Normal);ShownCards[model]=card;index++;
                }
                var power=await Apply(s);await Capture("player_pending_buff");
                Assert(!ShownCards.Values.Any(c=>c.OverlayContainer.GetChildren().OfType<NSilkCardOverlay>().Any()),"Pending buff shows no card overlay.");
                await Begin(s);
                foreach(var card in ShownCards.Values)card.UpdateVisuals(PileType.Hand,CardPreviewMode.Normal);
                for(int frame=0;frame<8;frame++)await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
                Assert(power.HasLivePair,"Rendered bound pair exists.");
                Assert(ShownCards.Values.Sum(c=>c.OverlayContainer.GetChildren().OfType<NSilkCardOverlay>().Count())==2,"Two native affliction overlays.");
                Assert(power.HoverTips.OfType<HoverTip>().First().Description.Contains("1"),"Native formatted active hover tip.");
                Assert(playerNode.FindChildren("*","",true,false).OfType<NPower>().Any(n=>n.Model==power),"Player has original NPower HUD icon.");
                Assert(ModelDb.Power<SilkThreadPower>().BigIcon.GetSize()==new Vector2(256,256),"Generated icon resolves.");
                Assert(ModelDb.Affliction<SilkLead>().HasOverlay && ModelDb.Affliction<SilkBound>().HasOverlay,"Both native overlay scene paths resolve.");
                await Capture("cards_bound");
                if(OS.GetCmdlineUserArgs().Contains("--card-vfx")) await RenderCardVfxReview(s, output);
                var first=power.FirstCard!;
                await CardCmd.AutoPlay(Choice,first,first.TargetType==TargetType.AnyEnemy?s.Moth.Creature:null,skipCardPileVisuals:true);
                foreach(var card in ShownCards.Values)card.UpdateVisuals(PileType.Hand,CardPreviewMode.Normal);
                await Capture("cards_released");
                Assert(!ShownCards.Values.Any(c=>c.OverlayContainer.GetChildren().OfType<NSilkCardOverlay>().Any()),"Native overlays removed on unlock.");
                foreach(var card in ShownCards.Values){view.RemoveChild(card);card.QueueFree();}ShownCards.Clear();
                if(OS.GetCmdlineUserArgs().Contains("--motion"))
                {
                    const int fps=20;string framesDir=Path.Combine(output,"motion");Directory.CreateDirectory(framesDir);
                    var clips=new List<object>();int total=0;
                    foreach(var(name,length) in new(string,float)[]{("idle_loop",4f),("attack",1.2f),("cast",1.55f),("flutter",1.3f),("hurt",.58f),("power_up",1.2f),("die",1.55f),("revive",1.4f),("summon",1.4f)})
                    {
                        int count=(int)Math.Ceiling(length*fps)+1;
                        for(int frame=0;frame<count;frame++)
                        {
                            Pose(mothSprite,name,Math.Min(frame/(float)fps,length));
                            await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);RenderingServer.ForceDraw();
                            using var image=view.GetTexture().GetImage();image.Resize(1280,720,Image.Interpolation.Lanczos);
                            Assert(image.SaveJpg(Path.Combine(framesDir,$"moth_{name}_{frame:D4}.jpg"),.94f)==Error.Ok,"Native motion frame.");total++;
                        }
                        clips.Add(new{slug="moth_"+name,name,duration=length,frames=count});GD.Print("Captured moth motion "+name);
                    }
                    File.WriteAllText(Path.Combine(framesDir,"report.json"),JsonSerializer.Serialize(new{fps,frames=total,clips},new JsonSerializerOptions{WriteIndented=true}));
                }
            }
            foreach(var child in view.GetChildren()){view.RemoveChild(child);child.QueueFree();}
            await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);RenderingServer.ForceDraw();DeactivateSyntheticCombat();
        }
        view.QueueFree();await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);RenderingServer.ForceDraw();ui.UnpatchAll(ui.Id);
        if(loader!=null)ResourceLoader.RemoveResourceFormatLoader(loader);
        var cache=PreloadManager.Cache;cache.GetType().GetMethod("UnloadMissedCacheAssets")?.Invoke(cache,null);
        GC.Collect();GC.WaitForPendingFinalizers();await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);RenderingServer.ForceDraw();
        GD.Print("PASS original Power HUD, affliction overlays, linked hand, packaged creatures and native animations.");
    }
}
