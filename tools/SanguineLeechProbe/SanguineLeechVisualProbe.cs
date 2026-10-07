using Godot;
using Godot.Bridge;
using HarmonyLib;
using MegaCrit.Sts2.Core.Assets;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Saves;
using STS2_Things.Monsters;

public partial class SanguineLeechProbeNode
{
    private async Task RenderProbe()
    {
        string output=Path.Combine(System.Environment.GetEnvironmentVariable("THINGS_PROBE_OUTPUT")
            ?? Path.Combine(_root,"build/sanguine_leech"),"visuals");Directory.CreateDirectory(output);
        var extension=GDExtensionManager.LoadExtension(Path.Combine(_root,"addons/spine/spine_godot_extension.gdextension"));
        Assert(extension is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded,"Native Spine extension loaded.");
        var ui=new Harmony("SanguineLeechProbe.VisualHost");
        ui.Patch(AccessTools.Method(typeof(CombatStateTracker),"NotifyCombatStateChanged"),prefix:new HarmonyMethod(typeof(SanguineLeechProbeNode),nameof(SkipUiGuard)));
        ScriptManagerBridge.LookupScriptsInAssembly(typeof(NCard).Assembly);
        ScriptManagerBridge.LookupScriptsInAssembly(typeof(SanguineLeech).Assembly);
        var loaderType=typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Assets.AtlasResourceLoader");
        var loader=loaderType==null?null:(ResourceFormatLoader)Activator.CreateInstance(loaderType)!;
        if(loader!=null)ResourceLoader.AddResourceFormatLoader(loader,true);
        SaveManager.Instance.SettingsSave.Language="zhs";LocManager.Initialize();
        GetTree().Root.Size=new Vector2I(1920,1080);
        var view=new SubViewport{Size=new Vector2I(1920,1080),Disable3D=true,RenderTargetUpdateMode=SubViewport.UpdateMode.Always};
        AddChild(view);
        async Task Capture(string name)
        {
            // Spine queues CanvasItem redraws; allow the scene-tree frame to flush
            // those callbacks before forcing a capture of a hidden test viewport.
            await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            RenderingServer.ForceDraw();
            using var image=view.GetTexture().GetImage();
            Assert(image.SavePng(Path.Combine(output,name+".png"))==Error.Ok,"Captured "+name);
        }
        async Task Clear()
        {
            foreach(var child in view.GetChildren()){view.RemoveChild(child);child.QueueFree();}
            await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        }
        static void Pose(Node2D sprite,string animation,float time)
        {
            var skeleton=sprite.Call("get_skeleton").AsGodotObject();skeleton.Call("set_to_setup_pose");
            var state=sprite.Call("get_animation_state").AsGodotObject();state.Call("clear_tracks");
            var track=state.Call("set_animation",animation,false,0).AsGodotObject();
            track.Call("set_track_time",time);track.Call("set_mix_duration",0f);sprite.Call("update_skeleton",0f);
        }
        NCreature AddCreature(Creature entity,string visualsPath,Vector2 position)
        {
            var creature=GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
            typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(creature,entity);
            typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(creature,GD.Load<PackedScene>(visualsPath).Instantiate<NCreatureVisuals>());
            creature.Position=position;view.AddChild(creature);return creature;
        }
        NCard AddCard(CardModel model,Vector2 position,float scale)
        {
            var card=GD.Load<PackedScene>("res://scenes/cards/card.tscn").Instantiate<NCard>();
            card.Model=model;card.Position=position;card.Scale=Vector2.One*scale;
            view.AddChild(card);card.UpdateVisuals(PileType.Hand,CardPreviewMode.Normal);return card;
        }
        foreach(bool weak in new[]{true,false})
        {
            var s=Scenario(weak);
            var bg=NCombatBackground.Create(new BackgroundAssets(s.Encounter.Id.Entry.ToLowerInvariant(),new Rng()));
            bg.Position=new Vector2(983,540);view.AddChild(bg);
            var slots=s.Encounter.CreateScene();view.AddChild(slots);
            AddCreature(s.Player.Creature,"res://scenes/creature_visuals/ironclad.tscn",new Vector2(480,746));
            var sprites=new List<Node2D>();
            foreach(var leech in s.Leeches)
            {
                leech.RollMove([s.Player.Creature]);
                var creature=AddCreature(leech.Creature,"res://scenes/creature_visuals/sanguine_leech.tscn",slots.GetNode<Node2D>(leech.Creature.SlotName!).Position);
                await creature.UpdateIntent([s.Player.Creature]);creature.IntentContainer.Modulate=Colors.White;
                var sprite=creature.Visuals.GetNode<Node2D>("Visuals");sprites.Add(sprite);
                sprite.Call("set_update_mode",ClassDB.ClassGetIntegerConstant("SpineConstant","UpdateMode_Manual"));
                foreach(var (trigger,clip) in new[]{("Attack","attack"),("Cast","cast"),("Curl","curl"),("Feed","feed")})
                {
                    creature.SetAnimationTrigger(trigger);
                    var state=sprite.Call("get_animation_state").AsGodotObject();
                    var track=state.Call("get_current",0).AsGodotObject();
                    Assert(track.Call("get_animation").AsGodotObject().Call("get_name").AsString()==clip,"Native animation trigger "+trigger);
                }
            }
            for(int i=0;i<12;i++)await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            for(int i=0;i<sprites.Count;i++)Pose(sprites[i],"idle_loop",i*.9f);
            await Capture(weak?"weak_pair":"strong_colony");
            if(!weak)
            {
                var parasite=Parasite(s);await EndHand(s);
                AddCard(parasite,new Vector2(375,919),.58f);
                // The fixture deliberately bypasses the backend-only UI notification guard;
                // refresh intentions explicitly so the preview shows native Strength scaling.
                foreach(var creature in view.GetChildren().OfType<NCreature>().Where(n=>n.Entity.Monster is SanguineLeech))
                {
                    await creature.UpdateIntent([s.Player.Creature]);
                    creature.IntentContainer.Modulate=Colors.White;
                }
                Pose(sprites[0],"feed",.3f);Pose(sprites[1],"cast",.62f);
                await Capture("parasite_feeding");
                foreach(var (name,duration) in new[]{("idle_loop",4f),("attack",1.12f),("cast",1.45f),("curl",1.1f),("feed",.85f),("hurt",.6f),("die",1.5f),("revive",1.4f),("summon",1.2f),("power_up",1.3f)})
                {
                    var resource=sprites[0].Get("skeleton_data_res").AsGodotObject();
                    Assert(resource.Call("find_animation",name).AsGodotObject()!=null,"Packaged clip "+name);
                    for(int i=0;i<4;i++)
                    {
                        for(int j=0;j<sprites.Count;j++)Pose(sprites[j],name,duration*i/3);
                        await Capture($"pose_{name}_{i}");
                    }
                }
                for(int i=0;i<36;i++)
                {
                    Pose(sprites[0],"idle_loop",i/9f);
                    Pose(sprites[1],"attack",(i%14)/12f);
                    Pose(sprites[2],"cast",(i%18)/12f);
                    await Capture($"sequence_{i:000}");
                }
            }
            await Clear();DeactivateSyntheticCombat();
        }
        {
            var s=Scenario();
            view.AddChild(new ColorRect{Color=new Color("172735"),Size=new Vector2(1920,1080),MouseFilter=Control.MouseFilterEnum.Ignore});
            var parasite=Parasite(s);
            AddCard(parasite,new Vector2(450,525),1.05f);
            Assert(parasite.Title=="寄生","Localized card title resolves.");
            Assert(parasite.GetDescriptionForPile(PileType.Hand,null).Contains("吸血血蛭"),"Native card description resolves.");
            AddCreature(s.Leeches[0].Creature,"res://scenes/creature_visuals/sanguine_leech.tscn",new Vector2(1320,730));
            await Capture("parasite_card_native");
            await Clear();DeactivateSyntheticCombat();
        }
        view.QueueFree();await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        ui.UnpatchAll(ui.Id);
        if(loader!=null)ResourceLoader.RemoveResourceFormatLoader(loader);
        var cache=PreloadManager.Cache;cache.GetType().GetMethod("UnloadMissedCacheAssets")?.Invoke(cache,null);
        GC.Collect();GC.WaitForPendingFinalizers();
        GD.Print("PASS packaged native creature/card rendering and ten animation clips.");
    }
    private static bool SkipUiGuard()=>false;
}
