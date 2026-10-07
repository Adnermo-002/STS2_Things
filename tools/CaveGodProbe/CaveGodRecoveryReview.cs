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
    private async Task VerifyRecoveryReview(string output,NCaveGodBossBackground controller,MegaSprite rig,
        CaveGodProbeRoom room,NCombatBackground background)
    {
        var harmony=new Harmony("CaveGodProbe.Recovery");ActionRoom=room;
        harmony.Patch(AccessTools.PropertyGetter(typeof(NCombatRoom),nameof(NCombatRoom.Instance)),
            prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(ActionRoomGetter)));
        background.Position=new Vector2(977.25f,575);
        var fixture=Scenario();
        var hero=new CaveGodProbeCaptive{Position=new Vector2(960,815),Scale=Vector2.One*.75f};
        typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(hero,fixture.State.Players[0].Creature);
        var visuals=fixture.State.Players[0].Character.CreateVisuals();hero.AddChild(visuals);
        typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(hero,visuals);room.AddChild(hero);
        var nodes=(List<NCreature>)typeof(NCombatRoom).GetField("_creatureNodes",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(room)!;nodes.Add(hero);
        await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        var args=OS.GetCmdlineUserArgs();int selected=Array.IndexOf(args,"--recovery-clip");
        if(args.Contains("--recovery-no-aim"))nodes.Clear();
        string[] baseClips=["central_slam","alternating_jabs","double_fist_crush","card_snatch","card_snatch_right",
            "front_sweep","front_sweep_right","weak_attack","weak_attack_right","grab_slam","grab_slam_right"];
        string[] clips=selected>=0?[args[selected+1]]:baseClips.SelectMany(c=>new[]{c,c+"_angry"}).ToArray();
        string[] chain=["arm1_1","arm1_2","arm1_3","arm2_1","arm2_2","arm2_3"];
        var reports=new List<object>();var failures=new List<string>();
        try
        {
            foreach(string clip in clips)
            {
                controller.SetAngry(clip.EndsWith("_angry"));AdvanceAction(.5);
                if(clip.StartsWith("weak_attack"))controller.StartWeakAttackAnim(!clip.Contains("right"));
                else if(clip.StartsWith("card_snatch"))controller.StartCardSnatchAnim(!clip.Contains("right"),[hero.Entity]);
                else controller.StartAttackAnim(clip);
                float duration;
                using(var entry=rig.GetAnimationState()!.GetCurrent(0))duration=entry!.GetAnimationDuration();
                var previous=chain.Select(n=>rig.GetGlobalBoneTransform(n)!.Value).ToArray();
                var previousDelta=new Vector2[chain.Length];
                float maxStep=0,maxTurn=0,maxJerk=0,worstTime=0,worstTurnTime=0;string worstBone="";
                var frames=new List<object>();
                for(int frame=1;frame<=(int)Math.Ceiling((duration+.7)*120);frame++)
                {
                    AdvanceAction(1.0/120);
                    float t=frame/120f;
                    var current=chain.Select(n=>rig.GetGlobalBoneTransform(n)!.Value).ToArray();
                    float step=0,turn=0,jerk=0;string turningBone="";
                    for(int i=0;i<chain.Length;i++)
                    {
                        var delta=current[i].Origin-previous[i].Origin;
                        step=Math.Max(step,delta.Length());
                        float twist=Math.Abs(Mathf.RadToDeg(WrapRadians(current[i].X.Angle()-previous[i].X.Angle())));
                        if(twist>turn){turn=twist;turningBone=chain[i];}
                        jerk=Math.Max(jerk,(delta-previousDelta[i]).Length());previousDelta[i]=delta;
                    }
                    if(t>=duration-.025f)
                    {
                        if(step>maxStep)worstTime=t;
                        if(turn>maxTurn){worstTurnTime=t;worstBone=turningBone;}
                        maxStep=Math.Max(maxStep,step);maxTurn=Math.Max(maxTurn,turn);maxJerk=Math.Max(maxJerk,jerk);
                        frames.Add(new{time=t,step,turn,jerk,turningBone,wrists=new[]{new[]{current[2].Origin.X,current[2].Origin.Y,Mathf.RadToDeg(current[2].X.Angle())},new[]{current[5].Origin.X,current[5].Origin.Y,Mathf.RadToDeg(current[5].X.Angle())}}});
                        if(frame%4==0 && !args.Contains("--no-images"))await ActionCapture(output,$"recovery-{clip}-{frame:D4}");
                    }
                    previous=current;
                }
                reports.Add(new{clip,duration,maxStep,maxTurn,maxJerk,worstTime,worstTurnTime,worstBone,frames});
                GD.Print($"RECOVERY {clip}: step={maxStep:F3}px turn={maxTurn:F3}deg jerk={maxJerk:F3}px/frame; wrist jump={worstBone}@{worstTurnTime:F3}s");
                if(maxStep>5||maxTurn>3||maxJerk>5)failures.Add($"{clip}: post-attack hand twitch ({maxStep:F2}px/{maxTurn:F2}deg)");
            }
        }
        finally{harmony.UnpatchAll(harmony.Id);ActionRoom=null;}
        File.WriteAllText(Path.Combine(output,"recovery-measurements.json"),JsonSerializer.Serialize(reports,new JsonSerializerOptions{WriteIndented=true}));
        Assert(failures.Count==0,string.Join("; ",failures));
    }
}
