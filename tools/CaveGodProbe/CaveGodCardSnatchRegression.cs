using System.Reflection;
using System.Text.Json;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Pooling;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Settings;
using STS2_Things.Monsters;
using STS2_Things.Visuals;

public partial class CaveGodProbeNode
{
    private static readonly List<float> SnatchCardFrames = [];
    private static void RecordSnatchCard()
    {
        SnatchCardFrames.Add(ReadActionTrackTime());
    }

    private async Task VerifyCardSnatchRegression(string output, NCaveGodBossBackground controller, MegaSprite rig,
        CaveGodProbeCaptive captive, List<NCreature> nodes, Harmony harmony)
    {
        string root = Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "../.."));
        using var motion = JsonDocument.Parse(File.ReadAllText(Path.Combine(root, "source_assets/monsters/cave_god_motion/card_snatch_motion.json")));
        float launch = motion.RootElement.GetProperty("launch").GetSingle();
        float touch = motion.RootElement.GetProperty("touch").GetSingle();
        float close = motion.RootElement.GetProperty("close").GetSingle();
        float duration = motion.RootElement.GetProperty("duration").GetSingle();
        int closeFrame = (int)Math.Round(close * 120) + 1;
        bool smoothPreview = OS.GetCmdlineUserArgs().Contains("--smooth-preview");
        var cardPool = NodePool.Init<NCard>("res://scenes/cards/card.tscn", 0);
        foreach (var silhouette in captive.GetChildren().OfType<ColorRect>()) silhouette.Visible = false;
        var playerVisuals = captive.Entity.Player!.Character.CreateVisuals();
        captive.AddChild(playerVisuals);
        typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(captive, playerVisuals);
        await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
        if (playerVisuals.SpineBody is { } playerRig && playerRig.HasAnimation("idle_loop"))
            playerRig.GetAnimationState()?.SetAnimation("idle_loop", true);
        playerVisuals.Body.Call("set_update_mode", ClassDB.ClassGetIntegerConstant("SpineConstant", "UpdateMode_Manual"));
        playerVisuals.Body.Call("update_skeleton", 0f);
        var measurements = new List<object>();
        var failures = new List<string>();
        var skeleton = ActionSprites[1].Call("get_skeleton").AsGodotObject();
        Assert(skeleton.HasMethod("set_attachment"), "Native Spine attachment API unavailable.");
        string Attachment(string name)
        {
            using Variant slotRef = skeleton.Call("find_slot", name);
            GodotObject slot = slotRef.AsGodotObject();
            using Variant attachmentRef = slot.Call("get_attachment");
            using GodotObject attachment = attachmentRef.AsGodotObject();
            string result = attachment.Call("get_attachment_name").AsString();
            GC.KeepAlive(slot);
            GC.KeepAlive(attachment);
            return result;
        }
        foreach (bool right in new[] { false, true })
        foreach (bool angry in new[] { false, true })
        {
            controller.ClearAllStolenCards();
            controller.SetAngry(angry);
            AdvanceAction(.4);
            controller.StartCardSnatchAnim(!right, [captive.Entity]);
            AdvanceAction(0);
            string wrist = right ? "arm2_3" : "arm1_3";
            string side = right ? "right" : "left";
            string[] chain = ["arm1_1","arm1_2","arm1_3","arm2_1","arm2_2","arm2_3"];
            var previous = chain.Select(b=>rig.GetGlobalBoneTransform(b)!.Value).ToArray();
            float maxStep=0,maxTwist=0,maxGripDrift=0,contactDistance=0;
            Vector2 initialWrist = rig.GetGlobalBoneTransform(wrist)!.Value.Origin;
            Vector2 previousWrist = initialWrist, previousStep = Vector2.Zero;
            float highestWrist = initialWrist.Y, windupPeak = 0, lungePeak = 0;
            float lungeMinStep = float.PositiveInfinity, maxVelocityChange = 0;
            Vector2? gripLocal=null;
            bool opened=false,closed=false;
            var frames = new List<object>();
            for (int frame=0;frame<=(int)Math.Round((duration + .4f) * 120);frame++)
            {
                if (frame>0)
                {
                    AdvanceAction(1.0/120);
                    playerVisuals.Body.Call("update_skeleton", 1f/120);
                }
                controller._Process(0);
                float time=frame/120f;
                if (frame==closeFrame)
                {
                    controller.AttachStolenCard(!right,(CardModel)ModelDb.Card<Inflame>().ToMutable());
                    AdvanceAction(0);
                }
                var pose=rig.GetGlobalBoneTransform(wrist)!.Value;
                Vector2 wristStep = pose.Origin - previousWrist;
                if (time <= launch)
                {
                    highestWrist = Math.Min(highestWrist, pose.Origin.Y);
                    windupPeak = Math.Max(windupPeak, wristStep.Length());
                }
                if (time > launch && time < touch) lungePeak = Math.Max(lungePeak, wristStep.Length());
                if (time > launch + .09f && time < touch - .09f) lungeMinStep = Math.Min(lungeMinStep, wristStep.Length());
                if (frame > 1) maxVelocityChange = Math.Max(maxVelocityChange, (wristStep - previousStep).Length());
                previousWrist = pose.Origin;
                previousStep = wristStep;
                var current=chain.Select(b=>rig.GetGlobalBoneTransform(b)!.Value).ToArray();
                float step=current.Select((p,i)=>p.Origin.DistanceTo(previous[i].Origin)).Max();
                float twist=current.Select((p,i)=>Math.Abs(Mathf.RadToDeg(WrapRadians(p.X.Angle()-previous[i].X.Angle())))).Max();
                maxStep=Math.Max(maxStep,step);maxTwist=Math.Max(maxTwist,twist);
                previous=current;
                if (time > launch && time < close - .01f) opened |= Attachment(wrist)==wrist+"_2";
                if (frame==closeFrame)
                {
                    closed=Attachment(wrist)==wrist;
                    var palm=pose*new Vector2(82,0);
                    contactDistance=palm.DistanceTo(captive.VfxSpawnPosition);
                }
                var marker=controller.GetStolenCardPos(!right)!;
                if (marker.Visible)
                {
                    Vector2 local=pose.AffineInverse()*marker.GlobalPosition;
                    gripLocal??=local;
                    maxGripDrift=Math.Max(maxGripDrift,local.DistanceTo(gripLocal.Value));
                    if (time>close + .012f && Attachment(wrist)!=wrist) failures.Add($"{side}/{angry}: opened hand while holding cards at {time:F3}");
                }
                frames.Add(new {time,step,twist,x=pose.Origin.X,y=pose.Origin.Y,attachment=Attachment(wrist)});
                // The smooth preview records the left action at 30 fps, with
                // keyframes of the other variants. All variants are measured at 120 Hz.
                bool capture = smoothPreview
                    ? (!right && !angry && frame%4==0) || frame == 108 || frame == closeFrame || frame == 272
                    : (!angry && frame%8==0) || (angry && (frame == closeFrame || frame == 272));
                if (!OS.GetCmdlineUserArgs().Contains("--no-images") && capture)
                {
                    await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
                    RenderingServer.ForceDraw(false);
                    using var image=_actionViewport!.GetTexture().GetImage();
                    image.Resize(960,540,Image.Interpolation.Lanczos);
                    image.SavePng(Path.Combine(output,$"snatch-{side}{(angry ? "-angry" : "")}-{frame:D3}.png"));
                }
            }
            float windupHeight = initialWrist.Y - highestWrist;
            measurements.Add(new {side,angry,kind="motion",opened,closed,contactDistance,maxStep,maxTwist,maxGripDrift,windupHeight,windupPeak,lungePeak,lungeMinStep,maxVelocityChange,frames});
            if (!opened || !closed) failures.Add($"{side}/{angry}: missing open palm -> closed fist sequence");
            if (contactDistance>85) failures.Add($"{side}/{angry}: palm misses player by {contactDistance:F1}px");
            if (maxStep>65 || maxTwist>18) failures.Add($"{side}/{angry}: discontinuity {maxStep:F1}px/{maxTwist:F1}deg");
            if (maxGripDrift>0.05) failures.Add($"{side}/{angry}: card grip drifts by {maxGripDrift:F2}px");
            if (windupHeight < 300) failures.Add($"{side}/{angry}: windup only lifts the wrist {windupHeight:F1}px");
            if (lungePeak < windupPeak*1.3f || lungeMinStep < 6)
                failures.Add($"{side}/{angry}: lunge lacks continuous acceleration ({windupPeak:F1}/{lungePeak:F1}, minimum {lungeMinStep:F1}px/frame)");
            if (maxVelocityChange > 3) failures.Add($"{side}/{angry}: wrist velocity jumps by {maxVelocityChange:F2}px/frame");
            controller.ClearAllStolenCards();
            await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        }

        nodes.Clear();
        harmony.Patch(AccessTools.Method(typeof(Cmd),nameof(Cmd.Wait),[typeof(float),typeof(CancellationToken),typeof(bool)]),
            prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(ActionWait)));
        harmony.Patch(AccessTools.Method(typeof(Cmd),nameof(Cmd.CustomScaledWait)),
            prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(ActionScaledWait)));
        harmony.Patch(AccessTools.Method(typeof(AttackCommand),nameof(AttackCommand.Execute)),
            prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(RecordActionHit)));
        harmony.Patch(AccessTools.Method(typeof(NCaveGodBossBackground),nameof(NCaveGodBossBackground.AttachStolenCard)),
            prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(RecordSnatchCard)));
        foreach (int playerCount in new[] {1,2,4})
        foreach (bool right in new[] {false,true})
        foreach (var mode in new[] {FastModeType.Normal,FastModeType.Fast,FastModeType.Instant})
        {
            var fixture=Scenario(playerCount);
            foreach(var player in fixture.State.Players) AddTestCard<Inflame>(fixture,player);
            var hand=right?(ThingsCaveGodHand)fixture.Right:fixture.Left;
            controller.SetAngry(false);
            SaveManager.Instance.PrefsSave.FastMode=mode;
            ActionClock=0;ActionHits.Clear();ActionPoseHits.Clear();ActionFistHits.Clear();SnatchCardFrames.Clear();
            await (Task)typeof(ThingsCaveGodHand).GetMethod("Sweep",BindingFlags.Instance|BindingFlags.NonPublic)!
                .Invoke(hand,[fixture.State.PlayerCreatures.ToArray()])!;
            measurements.Add(new {kind="gameplay",playerCount,right,mode=mode.ToString(),hits=ActionPoseHits.ToArray(),cards=SnatchCardFrames.ToArray(),count=hand.StolenCards.Count});
            if(ActionPoseHits.Count!=1 || Math.Abs(ActionPoseHits[0]-touch)>.025) failures.Add($"{right}/{mode}/{playerCount}: palm contact is not damage frame");
            if(ActionFistHits.Count!=1 || Math.Abs(ActionFistHits[0].X-983)>160)
                failures.Add($"{right}/{mode}/{playerCount}: damage ran before the hand actually reached the player ({string.Join(",",ActionFistHits)})");
            if(hand.StolenCards.Count!=playerCount || SnatchCardFrames.Count!=playerCount || SnatchCardFrames.Any(t=>Math.Abs(t-close)>.025))
                failures.Add($"{right}/{mode}/{playerCount}: card ownership/appearance is not the closing frame");
            await hand.ReleaseStolenCards();
            controller.ClearAllStolenCards();
            await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        }
        File.WriteAllText(Path.Combine(output,"snatch-measurements.json"),JsonSerializer.Serialize(measurements,new JsonSerializerOptions{WriteIndented=true}));
        controller.ClearAllStolenCards();
        await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        foreach (var card in cardPool.DebugFreeObjects.ToArray())
            if (GodotObject.IsInstanceValid(card)) card.Free();
        foreach(string failure in failures.Distinct()) GD.Print("SNATCH_REGRESSION: "+failure);
        Assert(failures.Count==0,string.Join("; ",failures.Distinct()));
    }
}
