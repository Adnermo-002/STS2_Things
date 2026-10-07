using System.Reflection;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using STS2_Things.Acts;
using STS2_Things.Encounters;

public partial class DepthsProbeNode
{
    private static bool SkipTestUiGuard() => false;
    private async Task RenderDepths()
    {
        var host=new Harmony("DepthsProbe.VisualHost");
        host.Patch(AccessTools.Method(typeof(CombatStateTracker),"NotifyCombatStateChanged"),
            prefix:new HarmonyMethod(typeof(DepthsProbeNode),nameof(SkipTestUiGuard)));
        Type? atlasType=typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Assets.AtlasResourceLoader");
        ResourceFormatLoader? atlas=atlasType==null?null:(ResourceFormatLoader)Activator.CreateInstance(atlasType)!;
        if(atlas!=null)ResourceLoader.AddResourceFormatLoader(atlas,true);
        var view=new SubViewport{Size=new Vector2I(1920,1080),Disable3D=true,RenderTargetUpdateMode=SubViewport.UpdateMode.Always};
        AddChild(view);GetTree().Root.Size=view.Size;
        string output=Path.Combine(_root,"build/depths/visuals");Directory.CreateDirectory(output);
        async Task Clear()
        {
            foreach(var child in view.GetChildren()){view.RemoveChild(child);child.QueueFree();}
            await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        }
        async Task Capture(string name)
        {
            await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            await ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
            using var im=view.GetTexture().GetImage();Assert(im.SavePng(Path.Combine(output,name+".png"))==Error.Ok,"Captured "+name);
        }
        NCombatBackground Background(string? path=null)
        {
            var assets=ModelDb.Act<Depths>().GenerateBackgroundAssets(new Rng());
            if(path!=null)assets.BgLayers[0]=path;
            var bg=NCombatBackground.Create(assets);bg.Position=new Vector2(983,540);view.AddChild(bg);return bg;
        }
        foreach(bool weak in new[]{true,false})
        {
            var run=CreateRun(weak?"pair-preview":"shoal-preview");run.CurrentActIndex=1;
            typeof(RunManager).GetProperty("State",BindingFlags.NonPublic|BindingFlags.Instance)!.SetValue(RunManager.Instance,run);
            EncounterModel encounter=(weak?ModelDb.Encounter<LanternFishWeak>() as EncounterModel:ModelDb.Encounter<LanternFishEncounter>()).ToMutable();
            var habitat=NCombatBackground.Create(new BackgroundAssets(encounter.Id.Entry.ToLowerInvariant(),new Rng()));
            habitat.Position=new Vector2(983,540);view.AddChild(habitat);
            run.AppendToMapPointHistory(MapPointType.Monster,RoomType.Monster,encounter.Id);
            var room=new CombatRoom(encounter,run);run.PushRoom(room);
            var player=run.Players[0];player.ResetCombatState();room.CombatState.AddPlayer(player);
            encounter.GenerateMonstersWithSlots(run);
            var slots=encounter.CreateScene();view.AddChild(slots);
            ActivateSyntheticCombat(room.CombatState);
            foreach(var (monster,slot) in encounter.MonstersWithSlots)
            {
                var entity=room.CombatState.CreateCreature(monster,CombatSide.Enemy,slot);room.CombatState.AddCreature(entity);
                monster.SetUpForCombat();monster.RollMove([player.Creature]);
                var creature=GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
                typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(creature,entity);
                var visuals=GD.Load<PackedScene>("res://scenes/creature_visuals/lantern_fish.tscn").Instantiate<NCreatureVisuals>();
                typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(creature,visuals);
                creature.Position=slots.GetNode<Node2D>(slot!).Position;view.AddChild(creature);
                await creature.UpdateIntent([player.Creature]);creature.IntentContainer.Modulate=Colors.White;
            }
            var hero=GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
            typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(hero,player.Creature);
            typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(hero,
                GD.Load<PackedScene>("res://scenes/creature_visuals/ironclad.tscn").Instantiate<NCreatureVisuals>());
            hero.Position=new Vector2(480,746);view.AddChild(hero);
            await ToSignal(GetTree().CreateTimer(1.0),SceneTreeTimer.SignalName.Timeout);
            await Capture(weak?"weak_pair":"strong_shoal");
            if(!weak)
            {
                var banner=GD.Load<PackedScene>("res://scenes/ui/act_banner.tscn").Instantiate<NActBanner>();
                typeof(NActBanner).GetField("_act",BindingFlags.NonPublic|BindingFlags.Instance)!.SetValue(banner,run.Act);
                typeof(NActBanner).GetField("_actIndex",BindingFlags.NonPublic|BindingFlags.Instance)!.SetValue(banner,1);
                view.AddChild(banner);
                await ToSignal(GetTree().CreateTimer(1.7),SceneTreeTimer.SignalName.Timeout);
                await Capture("chapter_banner");
                await ToSignal(GetTree().CreateTimer(2.2),SceneTreeTimer.SignalName.Timeout);
            }
            await Clear();DeactivateSyntheticCombat();
        }
        using(var directory=DirAccess.Open("res://scenes/backgrounds/depths/layers"))
        foreach(string file in directory.GetFiles().Where(file=>file.Contains("_bg_00_")).Order())
        {
            Background("res://scenes/backgrounds/depths/layers/"+file);
            await ToSignal(GetTree().CreateTimer(.3),SceneTreeTimer.SignalName.Timeout);
            await Capture(Path.GetFileNameWithoutExtension(file));await Clear();
        }
        var rest=ModelDb.Act<Depths>().CreateRestSiteBackground();rest.Position=new Vector2(26,74);view.AddChild(rest);
        var camperRun=CreateRun("depths-camp-layout");camperRun.CurrentActIndex=1;
        var camper=MegaCrit.Sts2.Core.Nodes.RestSite.NRestSiteCharacter.Create(camperRun.Players[0],0);
        camper.Position=new Vector2(650.8f,715.8f);camper.Scale=Vector2.One*.5f;view.AddChild(camper);
        await ToSignal(GetTree().CreateTimer(1.0),SceneTreeTimer.SignalName.Timeout);
        await Capture("rest_site");
        rest.GetNode<Control>("%RestSiteLighting").Visible=false;
        await Capture("rest_site_extinguished");await Clear();

        // Review sheet uses the real generated map's nodes/edges and the actual new
        // texture; it is explicitly a route overview rather than a mocked game UI.
        var mapRun=CreateRun("depths-map-review");mapRun.CurrentActIndex=1;
        mapRun.Act.GenerateRooms(mapRun.Rng.UpFront,MegaCrit.Sts2.Core.Unlocks.UnlockState.all);
        var map=mapRun.Act.CreateMap(mapRun,false);
        var paper=new TextureRect{Texture=mapRun.Act.MapMidBg,Size=new Vector2(1920,1080),ExpandMode=TextureRect.ExpandModeEnum.IgnoreSize};view.AddChild(paper);
        var font=new SystemFont{FontNames=["Microsoft YaHei"]};
        Vector2 Pos(MapPoint point)=>new(510+point.coord.col*150,970-point.coord.row*53);
        foreach(var point in map.GetAllMapPoints().Append(map.StartingMapPoint))
        foreach(var child in point.Children)
            view.AddChild(new Line2D{Points=[Pos(point),Pos(child)],Width=3,DefaultColor=new Color("557780"),Antialiased=true});
        foreach(var point in map.GetAllMapPoints().Append(map.BossMapPoint).Distinct())
        {
            var label=new Label{Text=point.PointType switch{MapPointType.Monster=>"●",MapPointType.Elite=>"◆",MapPointType.RestSite=>"营",MapPointType.Treasure=>"箱",MapPointType.Shop=>"商",MapPointType.Boss=>"★",MapPointType.Ancient=>"古",_=>"?"},
                Position=Pos(point)-new Vector2(13,17),Size=new Vector2(32,32),HorizontalAlignment=HorizontalAlignment.Center};
            label.AddThemeFontOverride("font",font);label.AddThemeFontSizeOverride("font_size",25);label.AddThemeColorOverride("font_color",new Color("203D47"));view.AddChild(label);
        }
        var title=new Label{Text="第二章 · 深处\n原生生成路线预览",Position=new Vector2(80,66)};
        title.AddThemeFontOverride("font",font);title.AddThemeFontSizeOverride("font_size",38);title.AddThemeColorOverride("font_color",new Color("233F4A"));view.AddChild(title);
        await Capture("map_overview");await Clear();
        view.QueueFree();host.UnpatchAll(host.Id);
        if(atlas!=null)ResourceLoader.RemoveResourceFormatLoader(atlas);
        GD.Print("PASS native weak/strong encounters, act banner, eight backgrounds, camp and generated route renders.");
    }
}
