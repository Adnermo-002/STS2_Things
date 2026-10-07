using System.Text.Json;
using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Afflictions;
using MegaCrit.Sts2.Core.Nodes.Cards;
using STS2_Things.Afflictions;
using STS2_Things.Visuals;

public partial class SilkMothProbeNode
{
    private async Task RenderCardVfxReview(Fixture scenario, string output)
    {
        var view=new SubViewport{Size=new Vector2I(1440,900),Disable3D=true,
            RenderTargetUpdateMode=SubViewport.UpdateMode.Always};AddChild(view);
        view.AddChild(new ColorRect{Size=new Vector2(1440,900),Color=new Color("18272a"),MouseFilter=Control.MouseFilterEnum.Ignore});
        string[] captions=["Queen · 原版束缚","垂丝蛾 · 先手 1","垂丝蛾 · 后手 2"];
        var cards=new List<NCard>();var effects=new List<Control>();
        for(int i=0;i<3;i++)
        {
            var model=scenario.Room.CombatState.CreateCard<StrikeIronclad>(scenario.Player);
            if(i==0)await CardCmd.Afflict<Bound>(model,3);
            else if(i==1)await CardCmd.Afflict<SilkLead>(model,1);
            else await CardCmd.Afflict<SilkBound>(model,1);
            var card=GD.Load<PackedScene>("res://scenes/cards/card.tscn").Instantiate<NCard>();
            card.Model=model;card.Position=new Vector2(240+i*480,465);card.Scale=Vector2.One*1.20f;
            view.AddChild(card);card.UpdateVisuals(PileType.Hand,CardPreviewMode.Normal);cards.Add(card);
            view.AddChild(new Label{Text=captions[i],Position=new Vector2(i*480,80),Size=new Vector2(480,70),
                HorizontalAlignment=HorizontalAlignment.Center,MouseFilter=Control.MouseFilterEnum.Ignore});
            var overlay=card.OverlayContainer.GetChildren().OfType<Control>().Single();
            var effect=i==0?overlay.GetChildren().OfType<Control>().Single():overlay.GetNode<Control>("SilkEffect");
            effects.Add(effect);
        }
        foreach(var effect in effects)
        {
            Assert(effect.GetNode<TextureRect>("card_mask").Get("clip_children").AsInt32()==1,"Queen's native card-shaped clip mask.");
            Assert(effect.GetNode<GpuParticles2D>("card_mask/vfx_common_specks").Emitting,"Native ambient particles emit.");
        }
        var firstMaterial=(ShaderMaterial)effects[1].GetNode<TextureRect>("vfx_container/main").Material;
        var secondMaterial=(ShaderMaterial)effects[2].GetNode<TextureRect>("vfx_container/main").Material;
        Assert(firstMaterial.GetInstanceId()!=secondMaterial.GetInstanceId(),"Separate card materials cannot share dissolve progress.");
        var players=effects.Skip(1).Select(e=>e.GetNode<AnimationPlayer>("AnimationPlayer")).ToArray();
        foreach(var player in players){player.Play("apply");player.Seek(.55,true);player.Pause();}
        Assert(firstMaterial.GetShaderParameter("effect_amount").AsSingle()>.99f,"Apply settles fully visible.");
        players[0].Play("release");players[0].Seek(.3,true);players[0].Pause();
        Assert(firstMaterial.GetShaderParameter("effect_amount").AsSingle()<.65f && secondMaterial.GetShaderParameter("effect_amount").AsSingle()>.99f,
            "One card's release leaves the other card unchanged.");
        string folder=Path.Combine(output,"card_vfx_motion");Directory.CreateDirectory(folder);
        const int fps=20;const int count=121;
        for(int frame=0;frame<count;frame++)
        {
            float t=frame/(float)fps;
            foreach(var player in players)
            {
                player.Play(t<4.5f?"apply":"release");
                player.Seek(t<4.5f?Math.Min(t,.55f):Math.Min(t-4.5f,.48f),true);player.Pause();
            }
            await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);RenderingServer.ForceDraw();
            using var pixels=view.GetTexture().GetImage();
            Assert(pixels.SaveJpg(Path.Combine(folder,$"frame_{frame:D4}.jpg"),.95f)==Error.Ok,"Captured native comparison frame.");
            if(frame is 2 or 7 or 20 or 60 or 94 or 105)
                Assert(pixels.SavePng(Path.Combine(output,$"queen_silk_{frame:D3}.png"))==Error.Ok,"Captured effect phase.");
        }
        File.WriteAllText(Path.Combine(folder,"report.json"),JsonSerializer.Serialize(new{fps,frames=count,seconds=count/(float)fps,
            source="Native Queen Bound effect and new silk Affliction overlays rendered by Godot"},new JsonSerializerOptions{WriteIndented=true}));
        view.QueueFree();await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);RenderingServer.ForceDraw();
        GD.Print("PASS native Queen comparison, masked particle card VFX, independent material progress and dissolve sequence.");
    }
}
