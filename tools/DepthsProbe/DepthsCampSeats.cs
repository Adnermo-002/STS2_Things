using Godot;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Acts;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Nodes.RestSite;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Acts;

public partial class DepthsProbeNode
{
    private async Task RenderCampSeats()
    {
        Type? atlasType=typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Assets.AtlasResourceLoader");
        ResourceFormatLoader? atlas=atlasType==null?null:(ResourceFormatLoader)Activator.CreateInstance(atlasType)!;
        if(atlas!=null)ResourceLoader.AddResourceFormatLoader(atlas,true);
        string output=Path.Combine(_root,"build/depths/camp_review");Directory.CreateDirectory(output);
        var view=new SubViewport{Size=new Vector2I(1920,1080),Disable3D=true,RenderTargetUpdateMode=SubViewport.UpdateMode.Always,TransparentBg=true};AddChild(view);
        GetTree().Root.Size=view.Size;
        var camp=ModelDb.Act<Depths>().CreateRestSiteBackground();camp.Position=new Vector2(26,74);view.AddChild(camp);
        Vector2[] seats=[new(650.8f,715.8f),new(1264.8f,722.8f),new(775.8f,658.8f),new(1117.8f,656.8f)];
        var party=new List<Player>{Player.CreateForNewRun<Ironclad>(UnlockState.all,1),Player.CreateForNewRun<Silent>(UnlockState.all,2),
            Player.CreateForNewRun<Defect>(UnlockState.all,3),Player.CreateForNewRun<Necrobinder>(UnlockState.all,4)};
        var run=RunState.CreateForNewRun(party,[ModelDb.Act<Overgrowth>().ToMutable(),ModelDb.Act<Depths>().ToMutable(),ModelDb.Act<Glory>().ToMutable()],[],GameMode.Standard,0,"native-camp-seating");
        run.CurrentActIndex=1;
        var actors=new List<NRestSiteCharacter>();
        foreach(int i in new[]{2,3,0,1})
        {
            var actor=NRestSiteCharacter.Create(party[i],i);actor.Position=seats[i];actor.Scale=Vector2.One*.5f;view.AddChild(actor);
            if(i%2==1)actor.FlipX();actors.Add(actor);
        }
        async Task Capture(string name)
        {
            await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            await ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
            using var frame=view.GetTexture().GetImage();Assert(frame.SavePng(Path.Combine(output,name+".png"))==Error.Ok,"Capture "+name);
        }
        await ToSignal(GetTree().CreateTimer(1.5),SceneTreeTimer.SignalName.Timeout);
        await Capture("four_seats");
        camp.GetNode<Control>("%RestSiteLighting").Visible=false;
        await Capture("four_seats_fire_out");
        camp.Visible=false;await Capture("native_actors_transparent");camp.Visible=true;
        foreach(var actor in actors)actor.Visible=actor.Player==party[0];
        camp.GetNode<Control>("%RestSiteLighting").Visible=true;
        await Capture("single_seat");
        foreach(var actor in actors)actor.Visible=false;
        await Capture("camp_lit");camp.GetNode<Control>("%RestSiteLighting").Visible=false;
        await Capture("camp_fire_out");
        view.QueueFree();if(atlas!=null)ResourceLoader.RemoveResourceFormatLoader(atlas);
    }
}
