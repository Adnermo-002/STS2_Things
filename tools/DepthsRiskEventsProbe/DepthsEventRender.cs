using Godot;
using System.Reflection;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using STS2_Things.Events;

public partial class DepthsProbeNode
{
    private async Task RenderEventLayouts()
    {
        var output = System.Environment.GetEnvironmentVariable("THINGS_PROBE_OUTPUT")!;
        var view = new SubViewport {Size = new Vector2I(1920,1080),Disable3D = true,
            RenderTargetUpdateMode = SubViewport.UpdateMode.Always};
        AddChild(view);GetTree().Root.Size = view.Size;
        foreach (string lang in new[] {"zhs","eng"})
        foreach (bool ward in new[] {false,true})
        {
            var run = NewRun("native-event-layout");
            typeof(RunManager).GetProperty("State",BindingFlags.NonPublic|BindingFlags.Instance)!.SetValue(RunManager.Instance,null);
            RunManager.Instance.SetUpTest(run,new NetSingleplayerGameService(),shouldSave:false);
            SaveManager.Instance.SettingsSave.Language = lang;LocManager.Initialize();
            EventModel model = ward ? await Begin<CrowdedWard>(run.Players[0]) : await Begin<BitingChest>(run.Players[0]);
            var world = new Control {Size = view.Size};view.AddChild(world);
            world.AddChild(new ColorRect {Size = view.Size,Color = Colors.Black});
            var layout = GD.Load<PackedScene>(NEventLayout.defaultScenePath).Instantiate<NEventLayout>();
            world.AddChild(layout);
            layout.SetEvent(model);layout.SetTitle(model.Title.GetFormattedText());
            layout.SetDescription(model.Description!.GetFormattedText());layout.AddOptions(model.CurrentOptions);
            layout.OnSetupComplete();
            await ToSignal(GetTree().CreateTimer(2.0),SceneTreeTimer.SignalName.Timeout);
            await ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
            var portrait = layout.GetNode<TextureRect>("%Portrait");
            GD.Print($"Layout geometry: world={world.Size}/{world.Position} layout={layout.Size}/{layout.Position} portrait={portrait.GetGlobalRect()}");
            Assert(layout.OptionButtons.Count() == 3,"Native layout has three event options");
            using (var image = view.GetTexture().GetImage())
                Assert(image.SavePng(Path.Combine(output,"event-"+(ward?"crowded_ward":"biting_chest")+"-"+lang+".png")) == Error.Ok,"Native event layout capture");
            world.QueueFree();await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        }
        view.QueueFree();await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
    }
}
