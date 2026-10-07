using System.Reflection;
using System.Text.Json;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using STS2_Things.Visuals;

public partial class CaveGodProbeNode
{
    private async Task VerifyContactReview(string output, NCaveGodBossBackground controller, MegaSprite rig,
        CaveGodProbeRoom room, NCombatBackground background)
    {
        string root=Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"),"../.."));
        using var source=JsonDocument.Parse(File.ReadAllText(Path.Combine(root,"source_assets/monsters/cave_god_motion/contact_profiles.json")));
        var profiles=source.RootElement.EnumerateArray().Select(p=>p.Clone()).ToArray();
        var harmony=new Harmony("CaveGodProbe.Contact");
        ActionRoom=room;
        harmony.Patch(AccessTools.PropertyGetter(typeof(NCombatRoom),nameof(NCombatRoom.Instance)),
            prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(ActionRoomGetter)));
        // Reproduce the native centered camera transform, rather than the older
        // action probe's hand-positioned single-player silhouette.
        background.Position=new Vector2(977.25f,575);
        var stage=new Control{Position=new Vector2(240,170),Scale=Vector2.One*.75f};room.AddChild(stage);
        var allies=new Control{Name="AllyContainer",Position=new Vector2(960,540)};stage.AddChild(allies);
        allies.Owner=room;allies.UniqueNameInOwner=true;
        var nodes=(List<NCreature>)typeof(NCombatRoom).GetField("_creatureNodes",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(room)!;
        var results=new List<object>();var failures=new List<string>();
        int motionFrame=0;
        string motionDirectory=Path.Combine(output,"motion");Directory.CreateDirectory(motionDirectory);
        try
        {
            foreach(int count in new[]{1,2,3,4})
            {
                var fixture=Scenario(count, mixedCharacters:true);
                nodes.Clear();
                foreach(var player in fixture.State.Players)
                {
                    var node=new CaveGodProbeCaptive();
                    typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(node,player.Creature);
                    var visuals=player.Character.CreateVisuals();node.AddChild(visuals);
                    typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(node,visuals);
                    allies.AddChild(node);nodes.Add(node);
                }
                await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
                NCombatRoom.PositionPlayersAndPets(nodes,.75f,true);
                Vector2 before=allies.Position;controller.AlignStageAndPlayers();Vector2 after=allies.Position;
                controller.AlignStageAndPlayers();
                if(allies.Position!=after)failures.Add("Repeated alignment moved the formation again.");
                if(count==1 && Math.Abs(after.Y-before.Y-120)>.001f)failures.Add("Wrong shared stage offset.");
                foreach(var node in nodes)
                {
                    node.Visuals.Body.Call("set_update_mode",ClassDB.ClassGetIntegerConstant("SpineConstant","UpdateMode_Manual"));
                    node.Visuals.SpineBody?.GetAnimationState()?.SetAnimation("idle_loop",true);
                    node.Visuals.Body.Call("update_skeleton",0f);
                }
                foreach(bool angry in new[]{false,true})
                foreach(var clipGroup in profiles.Where(p=>p.GetProperty("clip").GetString()!.EndsWith("_angry")==angry)
                    .GroupBy(p=>p.GetProperty("clip").GetString()!))
                {
                    controller.SetAngry(angry);AdvanceAction(.15);
                    controller.StartAttackAnim(clipGroup.Key);
                    float previous=0;
                    foreach(var phase in clipGroup.GroupBy(p=>p.GetProperty("hit").GetSingle()).OrderBy(g=>g.Key))
                    {
                        AdvanceAction(phase.Key-previous);previous=phase.Key;
                        var boxes=new List<Rect2>();
                        foreach(var p in phase)
                        {
                            string bone=p.GetProperty("hand").GetString()!;
                            var b=rig.GetGlobalBoneTransform(bone)!.Value;
                            // Calibrated mesh support in Spine world coordinates.
                            var offset=p.GetProperty("offset").EnumerateArray().Select(x=>x.GetSingle()).ToArray();
                            var size=p.GetProperty("size").EnumerateArray().Select(x=>x.GetSingle()).ToArray();
                            var plans=typeof(NCaveGodBossBackground).GetField("_contactPlans",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(controller) as Array;
                            float scale=1;
                            if(plans!=null)foreach(var plan in plans)
                            {
                                var type=plan!.GetType();var profile=type.GetProperty("Profile")!.GetValue(plan)!;
                                var pt=profile.GetType();
                                if((float)pt.GetProperty("Hit")!.GetValue(profile)! == phase.Key &&
                                    (bool)pt.GetProperty("Left")!.GetValue(profile)! == (bone=="arm1_3"))
                                    scale=(float)type.GetProperty("Scale")!.GetValue(plan)!;
                            }
                            Vector2 center=b.Origin+ActionSprites[1].GlobalTransform.BasisXform(new Vector2(offset[0],-offset[1])*scale);
                            Vector2 extent=new Vector2(size[0],size[1])*ActionSprites[1].GlobalScale.Abs()*scale;
                            boxes.Add(new Rect2(center-extent/2,extent));
                        }
                        int reached=nodes.Count(n=>boxes.Any(box=>box.Grow(10).HasPoint(n.VfxSpawnPosition)));
                        results.Add(new{count,clip=clipGroup.Key,time=phase.Key,reached,
                            targets=nodes.Select(n=>new[]{n.VfxSpawnPosition.X,n.VfxSpawnPosition.Y}).ToArray(),
                            boxes=boxes.Select(b=>new[]{b.Position.X,b.Position.Y,b.Size.X,b.Size.Y}).ToArray()});
                        if(reached!=count)failures.Add($"{clipGroup.Key} @{phase.Key}: {reached}/{count} player centers inside hand contact area");
                        if(count is 1 or 4)
                            await ActionCapture(output,$"{count}p-{clipGroup.Key}-{phase.Key:F2}");
                    }
                    if(OS.GetCmdlineUserArgs().Contains("--smooth-preview") && !angry &&
                        ((count==1 && clipGroup.Key=="alternating_jabs") ||
                         (count==4 && clipGroup.Key is "card_snatch" or "central_slam")))
                    {
                        controller.StartAttackAnim(clipGroup.Key);
                        float duration=clipGroup.Key=="central_slam"?3.75f:clipGroup.Key=="card_snatch"?3.2f:3.5f;
                        for(int frame=0;frame<=Math.Ceiling(duration*20);frame++)
                        {
                            if(frame>0)AdvanceAction(.05);
                            await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
                            RenderingServer.ForceDraw(false);
                            using var pixels=_actionViewport!.GetTexture().GetImage();
                            pixels.Resize(1280,720,Image.Interpolation.Lanczos);
                            pixels.SaveJpg(Path.Combine(motionDirectory,$"frame_{motionFrame++:D4}.jpg"),.92f);
                        }
                    }
                }
                foreach(var node in nodes.ToArray()){allies.RemoveChild(node);node.QueueFree();}
                nodes.Clear();await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            }
        }
        finally{harmony.UnpatchAll(harmony.Id);ActionRoom=null;}
        File.WriteAllText(Path.Combine(output,"contact-measurements.json"),JsonSerializer.Serialize(results,new JsonSerializerOptions{WriteIndented=true}));
        File.WriteAllText(Path.Combine(output,"motion.json"),JsonSerializer.Serialize(new{frames=motionFrame,fps=20}));
        foreach(var failure in failures)GD.Print("CONTACT_REVIEW: "+failure);
        Assert(failures.Count==0,string.Join("; ",failures));
    }
}
