using System.Reflection;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Multiplayer;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Map;
using STS2_Things.Modifiers;

public partial class CaveGodProbeNode
{
    private static NHotkeyManager? RoadHotkeys;
    private static bool RoadHotkeyGetter(ref NHotkeyManager? __result){__result=RoadHotkeys;return false;}
    private static bool RoadDrawingMode(ref DrawingMode __result){__result=DrawingMode.None;return false;}
    private static bool RoadPopupFactory(ref NGenericPopup? __result)
    {
        __result=GD.Load<PackedScene>("res://scenes/ui/generic_popup.tscn").Instantiate<NGenericPopup>();
        void HideHints(Node node)
        {
            if(node is NHotkeyIcon hint)hint.Visible=false;
            foreach(var child in node.GetChildren())HideHints(child);
        }
        HideHints(__result);return false;
    }
    private static bool RoadPreviewSetMap(NMapScreen __instance)
    {
        if(__instance is not CrossroadPreviewScreen screen)return true;
        screen.Populate();return false;
    }
    private static bool RoadPreviewInitialize(NMapScreen __instance) => __instance is not CrossroadPreviewScreen;

    private async Task VerifyCrossroadUi()
    {
        string root=Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"),"../.."));
        string output=Path.Combine(root,"build/crossroads-20261003");Directory.CreateDirectory(output);
        SaveManager.Instance.InitPrefsDataForTest();SaveManager.Instance.SettingsSave.Language="zhs";LocManager.Initialize();
        var harmony=new Harmony("Things.Crossroads.UiProbe");
        foreach(var name in new[]{"CrossroadMapOwnerPatch","CrossroadMapDisplayPatch"})
            harmony.CreateClassProcessor(ImplementationAssembly.GetType("STS2_Things.Map."+name,true)!).Patch();
        harmony.Patch(AccessTools.PropertyGetter(typeof(NHotkeyManager),nameof(NHotkeyManager.Instance)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(RoadHotkeyGetter)));
        harmony.Patch(AccessTools.Method(typeof(NMapDrawings),nameof(NMapDrawings.GetLocalDrawingMode)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(RoadDrawingMode)));
        harmony.Patch(AccessTools.Method(typeof(NGenericPopup),nameof(NGenericPopup.Create)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(RoadPopupFactory)));
        harmony.Patch(AccessTools.Method(typeof(NMapScreen),nameof(NMapScreen.SetMap)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(RoadPreviewSetMap)));
        harmony.Patch(AccessTools.Method(typeof(NMapScreen),nameof(NMapScreen.Initialize)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(RoadPreviewInitialize)));
        var player=Player.CreateForNewRun<Ironclad>(UnlockState.all,1);
        var ledger=ModelDb.Modifier<ThingsCrossroads>().ToMutable();
        var run=RunState.CreateForTest([player],modifiers:[ledger],seed:"crossroads-ui");
        var map=run.Act.CreateMap(run,false);run.Map=map;((ThingsCrossroads)ledger).Bind(run);
        var plan=((ThingsCrossroads)ledger).EnsurePlan(run,map,0)!;var road=plan.Roads[0];
        run.AddVisitedMapCoord(road.A);player.Gold=125;LocalContext.NetId=1;
        var net=new NetSingleplayerGameService();var queue=new ActionQueueSet(run.Players);
        var executor=new ActionExecutor(queue);executor.Unpause();queue.UnpauseAllPlayerQueues();
        var buffer=new RunLocationTargetedMessageBuffer(net);
        var sync=new ActionQueueSynchronizer(run,queue,buffer,net);
        typeof(RunManager).GetProperty(nameof(RunManager.ActionQueueSynchronizer))!.SetValue(RunManager.Instance,sync);

        var viewport=new SubViewport{Size=new Vector2I(1400,1000),Disable3D=true,RenderTargetUpdateMode=SubViewport.UpdateMode.Always};AddChild(viewport);
        viewport.AddChild(new ColorRect{Size=new Vector2(1400,1000),Color=run.Act.MapBgColor,MouseFilter=Control.MouseFilterEnum.Ignore});
        RoadHotkeys=new NHotkeyManager();viewport.AddChild(RoadHotkeys);
        var screen=new CrossroadPreviewScreen{Run=run,ActMap=map,Size=new Vector2(1400,1000)};viewport.AddChild(screen);
        screen.Initialize(run);screen.SetMap(map,run.Rng.Seed,false);
        var modal=new NModalContainer{Size=new Vector2(1400,1000),MouseFilter=Control.MouseFilterEnum.Ignore};
        modal.AddChild(new ColorRect{Name="Backstop",Size=new Vector2(1400,1000),Color=new Color(0,0,0,0),Visible=false});viewport.AddChild(modal);
        async Task Capture(string name)
        {
            for(int frame=0;frame<24;frame++)await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            RenderingServer.ForceDraw(false);using var image=viewport.GetTexture().GetImage();image.SavePng(Path.Combine(output,name+".png"));
        }
        NCrossroadButton Button(CrossroadRecord? selected=null)
        {
            selected??=road;
            return screen.GetNode<NCrossroadButton>($"TheMap/Points/ThingsCrossroads/Road_{selected.Row}_{selected.Left}_{selected.Right}");
        }
        async Task SetCurrent(MapCoord? coord)
        {
            run.ClearVisitedMapCoordsDebug();
            if(coord.HasValue)run.AddVisitedMapCoord(coord.Value);
            for(int frame=0;frame<2;frame++)await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        }
        async Task AssertUnavailable(string state)
        {
            Assert(!Button().IsEnabled&&Button().FocusMode==Control.FocusModeEnum.None&&Button().MouseFilter==Control.MouseFilterEnum.Ignore,
                $"Lock is interactive {state}");
            Task ignored=Button().Activate!();
            Assert(modal.OpenModal==null,$"Lock opens a popup {state}");
            await ignored;
        }
        void AssertAligned()
        {
            var nodes=screen.GetNode<Control>("TheMap/Points").GetChildren().OfType<NMapPoint>().ToDictionary(p=>p.Point.coord);
            var segments=plan.Roads.Select(r=>(Start:nodes[r.A].GetGlobalRect().GetCenter(),End:nodes[r.B].GetGlobalRect().GetCenter())).ToArray();
            foreach(var candidate in plan.Roads)
            {
                Vector2 expected=(nodes[candidate.A].GetGlobalRect().GetCenter()+nodes[candidate.B].GetGlobalRect().GetCenter())/2;
                Assert(Button(candidate).GetGlobalRect().GetCenter().DistanceTo(expected)<0.5f,"Lock misses node centers after map scaling/scrolling");
            }
            foreach(var dot in screen.GetNode<NCrossroadLayer>("TheMap/Points/ThingsCrossroads").GetChildren().OfType<TextureRect>().Where(dot=>dot.Visible))
            {
                Vector2 center=dot.GetGlobalTransform()*(dot.Size/2);
                float distance=segments.Min(s=>Geometry2D.GetClosestPointToSegment(center,s.Start,s.End).DistanceTo(center));
                Assert(distance<0.5f,"Path dots do not follow the line between node centers");
            }
        }
        try
        {
            await Capture("map-locked");
            for(int redraw=0;redraw<3;redraw++)
            {
                var retiring=screen.GetNode<Control>("TheMap/Points").GetChildren().OfType<NMapPoint>()
                    .Where(point=>!point.IsQueuedForDeletion()).ToArray();
                screen.SetMap(map,run.Rng.Seed,false);
                Assert(retiring.All(point=>point.IsQueuedForDeletion()),"Fixture must preserve native deferred map-point deletion");
                var layers=screen.GetNode<Control>("TheMap/Points").GetChildren().OfType<NCrossroadLayer>().ToArray();
                Assert(layers.Length==1&&!layers[0].IsQueuedForDeletion(),"Redrawing leaves a retired crossroad layer attached");
                var attached=(Dictionary<MapCoord,NMapPoint>)typeof(NCrossroadLayer).GetField("_points",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(layers[0])!;
                Assert(attached.Values.All(point=>!point.IsQueuedForDeletion()),"Crossroads retained a map point awaiting deletion");
            }
            await Capture("map-redrawn-same-frame");
            AssertAligned();
            // The real native map points can shift when their center anchors or
            // viewport layout settle after SetMap. Locks and dotted routes must
            // follow the live room positions, not their initial screen coords.
            var dynamicPoints = screen.GetNode<Control>("TheMap/Points")
                .GetChildren().OfType<NMapPoint>().ToArray();
            foreach (var point in dynamicPoints) point.Position += new Vector2(93, -67);
            for (int frame = 0; frame < 2; frame++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            AssertAligned();
            await Capture("map-layout-shifted");
            foreach (var point in dynamicPoints) point.Position -= new Vector2(93, -67);
            for (int frame = 0; frame < 2; frame++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            AssertAligned();
            var failures=new List<string>();
            var nodes=screen.GetNode<Control>("TheMap/Points").GetChildren().OfType<NMapPoint>().ToDictionary(p=>p.Point.coord);
            foreach(var candidate in plan.Roads)
            {
                Vector2 expected=(nodes[candidate.A].GetGlobalRect().GetCenter()+nodes[candidate.B].GetGlobalRect().GetCenter())/2;
                float offset=Button(candidate).GetGlobalRect().GetCenter().DistanceTo(expected);
                if(offset>0.5f)failures.Add($"Lock/path midpoint misses native node centers by {offset:F2} px");
            }
            var remote=plan.Roads.First(r=>!r.Touches(run.CurrentMapCoord!.Value));
            var remoteButton=Button(remote);
            Task remoteClick=remoteButton.Activate!();
            if(modal.OpenModal is NGenericPopup remotePopup)
            {
                failures.Add("A lock opened a popup before reaching either endpoint");
                var remoteControls=remotePopup.GetNode<NVerticalPopup>("VerticalPopup");
                remoteControls.NoButton.EmitSignal(NClickableControl.SignalName.Released,remoteControls.NoButton);
            }
            await remoteClick;
            if(remoteButton.IsEnabled||remoteButton.FocusMode!=Control.FocusModeEnum.None||remoteButton.MouseFilter!=Control.MouseFilterEnum.Ignore)
                failures.Add("A distant lock still accepts mouse/controller interaction");
            Assert(failures.Count==0,string.Join("; ",failures));
            AssertAligned();
            var mapControl=screen.GetNode<Control>("TheMap");
            mapControl.Position=new Vector2(75,-135);mapControl.Scale=new Vector2(.85f,.85f);
            AssertAligned();
            mapControl.Position=Vector2.Zero;mapControl.Scale=Vector2.One;
            await SetCurrent(null);await AssertUnavailable("before entering the map");
            await SetCurrent(road.B);
            Assert(Button().IsEnabled,"Arrival at the right endpoint did not enable the lock without rebuilding the map");
            Task fromRight=Button().Activate!();
            var rightControls=((NGenericPopup)modal.OpenModal!).GetNode<NVerticalPopup>("VerticalPopup");
            Assert(rightControls.YesButton.IsEnabled,"Right endpoint cannot unlock an affordable route");
            rightControls.NoButton.EmitSignal(NClickableControl.SignalName.Released,rightControls.NoButton);await fromRight;
            await SetCurrent(remote.A);await AssertUnavailable("after leaving its endpoint");
            await SetCurrent(road.A);
            typeof(NMapScreen).GetProperty(nameof(NMapScreen.IsTravelEnabled))!.SetValue(screen,false);
            for(int frame=0;frame<2;frame++)await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            await AssertUnavailable("before finishing the endpoint room");
            typeof(NMapScreen).GetProperty(nameof(NMapScreen.IsTravelEnabled))!.SetValue(screen,true);
            for(int frame=0;frame<2;frame++)await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            Assert(Button().IsEnabled,"Left endpoint did not become interactive after finishing its room");
            Task pending=Button().Activate!();await Capture("popup-confirm");
            var popup=(NGenericPopup)modal.OpenModal!;var controls=popup.GetNode<NVerticalPopup>("VerticalPopup");
            Assert(controls.YesButton.IsEnabled,"Affordable route cannot be confirmed");
            controls.NoButton.EmitSignal(NClickableControl.SignalName.Released,controls.NoButton);await pending;
            Assert(player.Gold==125&&!road.IsOpen,"Cancel changed money or route");
            player.Gold=49;pending=Button().Activate!();await Capture("popup-insufficient");
            controls=((NGenericPopup)modal.OpenModal!).GetNode<NVerticalPopup>("VerticalPopup");
            Assert(!controls.YesButton.IsEnabled,"Insufficient-gold confirm is enabled");
            controls.NoButton.EmitSignal(NClickableControl.SignalName.Released,controls.NoButton);await pending;
            player.Gold=125;pending=Button().Activate!();
            controls=((NGenericPopup)modal.OpenModal!).GetNode<NVerticalPopup>("VerticalPopup");
            controls.YesButton.EmitSignal(NClickableControl.SignalName.Released,controls.YesButton);await pending;
            await executor.FinishedExecutingActions();await Capture("map-unlocked");
            Assert(player.Gold==75&&road.IsOpen&&run.CurrentMapCoord==road.A,"Confirmation did not unlock exactly once without automatic travel");
            AssertAligned();
            run.AddVisitedMapCoord(road.B);
            for(int frame=0;frame<2;frame++)await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            await AssertUnavailable("at the visited destination of an open road");
            GD.Print("CROSSROADS_UI_PASS node alignment, scaled/scrolled map, endpoint-only mouse/controller interaction, both endpoints, room completion, native dialog, cancel, insufficient funds, gold spending, unlocked map");
        }
        finally
        {
            viewport.QueueFree();await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            sync.Dispose();executor.Cancel();RoadHotkeys=null;harmony.UnpatchAll(harmony.Id);
        }
    }
}
