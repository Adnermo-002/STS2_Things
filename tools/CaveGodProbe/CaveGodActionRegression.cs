using System.Reflection;
using System.Text.Json;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Settings;
using STS2_Things.Cards;
using STS2_Things.Monsters;
using STS2_Things.Powers;
using STS2_Things.Visuals;

public partial class CaveGodProbeNode
{
    private static NCombatRoom? ActionRoom;
    private static Node2D[] ActionSprites = [];
    private static double ActionClock;
    private static System.Action? ActionFrame;
    private static readonly List<double> ActionHits = [];
    private static readonly List<double> ActionPoseHits = [];
    private static readonly List<Vector2> ActionFistHits = [];
    private SubViewport? _actionViewport;
    private static bool ActionRoomGetter(ref NCombatRoom? __result) { __result = ActionRoom; return false; }
    private static bool ActionWait(float seconds, ref Task __result)
    {
        if (SaveManager.Instance.PrefsSave.FastMode != FastModeType.Instant) AdvanceAction(Math.Max(0, seconds));
        __result = Task.CompletedTask;
        return false;
    }
    private static bool ActionScaledWait(float fastSeconds, float standardSeconds, ref Task __result)
        => ActionWait(SaveManager.Instance.PrefsSave.FastMode == FastModeType.Fast ? fastSeconds : standardSeconds, ref __result);
    private static void RecordActionHit(AttackCommand __instance)
    {
        if (__instance.Attacker?.Monster is ThingsCaveGodBody or ThingsCaveGodHand)
            __instance.BeforeDamage(() =>
            {
                ActionHits.Add(ActionClock);
                ActionPoseHits.Add(ReadActionTrackTime());
                if (__instance.Attacker.Monster is ThingsCaveGodHand hand)
                    ActionFistHits.Add(new MegaSprite(ActionSprites[1]).GetGlobalBoneTransform(hand.IsLeft ? "arm1_3" : "arm2_3")!.Value.Origin);
                return Task.CompletedTask;
            });
    }
    private static float ReadActionTrackTime()
    {
        // These accessors mint native RefCounted wrappers. Release them on this
        // thread rather than allowing a later GC finalizer to disconnect signals.
        using Variant native = ActionSprites[1].Call("get_animation_state");
        using var state = new MegaAnimationState(native);
        using var entry = state.GetCurrent(0);
        return entry?.GetTrackTime() ?? 0;
    }
    private static void AdvanceAction(double seconds)
    {
        for (double remaining = seconds; remaining > 0.000001;)
        {
            double delta = Math.Min(1.0 / 120.0, remaining);
            foreach (Node2D sprite in ActionSprites) sprite.Call("update_skeleton", (float)delta);
            remaining -= delta;
            ActionClock += delta;
            ActionFrame?.Invoke();
        }
        foreach (Node2D sprite in ActionSprites) sprite.Call("update_skeleton", 0f);
    }

    private async Task VerifyActionRegression()
    {
        string root = Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "../.."));
        string output = Path.Combine(root, "build/cavegod-actions-20261002");
        var args = OS.GetCmdlineUserArgs();
        int outputArg = Array.IndexOf(args, "--action-output");
        if (outputArg >= 0) output = args[outputArg + 1];
        Directory.CreateDirectory(output);
        MegaCrit.Sts2.Core.Localization.LocManager.Initialize();
        SaveManager.Instance.InitPrefsDataForTest();
        SaveManager.Instance.PrefsSave.FastMode = FastModeType.Normal;
        var extension = GDExtensionManager.LoadExtension(Path.Combine(root, "addons/spine/spine_godot_extension.gdextension"));
        Assert(extension is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded, "Spine unavailable.");
        GetTree().Root.Size = new Vector2I(1920, 1080);
        _actionViewport = new SubViewport
        {
            Size = new Vector2I(1920, 1080), Disable3D = true,
            RenderTargetUpdateMode = SubViewport.UpdateMode.Always,
        };
        AddChild(_actionViewport);
        var bg = GD.Load<PackedScene>("res://scenes/backgrounds/cave_god_boss_encounter/cave_god_boss_encounter_background.tscn").Instantiate<NCombatBackground>();
        bg.Position = new Vector2(983, 540);
        bg.Scale = Vector2.One * 0.75f;
        bg.GetNode("Layer_00").AddChild(GD.Load<PackedScene>("res://scenes/backgrounds/cave_god_boss_encounter/layers/cave_god_boss_encounter_bg_00_a.tscn").Instantiate());
        bg.GetNode("Foreground").AddChild(GD.Load<PackedScene>("res://scenes/backgrounds/cave_god_boss_encounter/layers/cave_god_boss_encounter_fg_a.tscn").Instantiate());
        var room = new CaveGodProbeRoom();
        _actionViewport.AddChild(room);
        room.AddChild(bg);
        typeof(NCombatRoom).GetProperty(nameof(NCombatRoom.Background))!.SetValue(room, bg);
        var controller = bg.GetNode<NCaveGodBossBackground>("CaveGod");
        ActionSprites = [bg.GetNode<Node2D>("CaveGod/CaveGodBody"), bg.GetNode<Node2D>("CaveGodArms")];
        for (int i = 0; i < 20; i++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
        foreach (var sprite in ActionSprites)
            sprite.Call("set_update_mode", ClassDB.ClassGetIntegerConstant("SpineConstant", "UpdateMode_Manual"));
        controller.SetProcess(false);
        var rig = new MegaSprite(ActionSprites[1]);
        if (args.Contains("--bake-card-snatch"))
        {
            BakeCardSnatch(root, output, rig);
            room.QueueFree();
            _actionViewport.QueueFree();
            GD.Print("CaveGod action regression: PASS (card snatch bake)");
            return;
        }
        if (OS.GetCmdlineUserArgs().Contains("--bake-right-grab"))
        {
            BakeRightGrab(root, output, rig);
            room.QueueFree();
            _actionViewport.QueueFree();
            GD.Print("CaveGod action regression: PASS (motion bake)");
            return;
        }
        if (args.Contains("--recovery-review"))
        {
            await VerifyRecoveryReview(output, controller, rig, room, bg);
            room.QueueFree();_actionViewport.QueueFree();
            GD.Print("CaveGod action regression: PASS (recovery review)");return;
        }
        if (args.Contains("--contact-review"))
        {
            await VerifyContactReview(output, controller, rig, room, bg);
            room.QueueFree();
            _actionViewport.QueueFree();
            GD.Print("CaveGod action regression: PASS (contact review)");
            return;
        }
        var fixture = Scenario();
        var captive = new CaveGodProbeCaptive { Position = new Vector2(980, 730), Scale = new Vector2(0.75f, 0.75f) };
        typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(captive, fixture.State.Players[0].Creature);
        var stateDisplay = new NCreatureStateDisplay();
        typeof(NCreature).GetField("_stateDisplay", BindingFlags.Instance | BindingFlags.NonPublic)!.SetValue(captive, stateDisplay);
        // An unambiguous silhouette makes the exact tracked feet/torso anchor visible.
        captive.AddChild(new ColorRect { Position = new Vector2(-20, -110), Size = new Vector2(40, 110), Color = Colors.Gold });
        room.AddChild(captive);
        var nodes = (List<NCreature>)typeof(NCombatRoom).GetField("_creatureNodes", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(room)!;
        nodes.Add(captive);
        var harmony = new Harmony("CaveGodProbe.Actions");
        var failures = new List<string>();
        var samples = new List<object>();
        ActionRoom = room;
        harmony.Patch(AccessTools.PropertyGetter(typeof(NCombatRoom), nameof(NCombatRoom.Instance)),
            prefix: new HarmonyMethod(typeof(CaveGodProbeNode), nameof(ActionRoomGetter)));
        try
        {
            if (args.Contains("--card-snatch"))
            {
                await VerifyCardSnatchRegression(output, controller, rig, captive, nodes, harmony);
                GD.Print("CaveGod action regression: PASS (card snatch)");
                return;
            }
            foreach (CardModel card in new CardModel[] { ModelDb.Card<CaveGodBrokenBladeTrial>(), ModelDb.Card<CaveGodShatteredShieldTrial>() })
                if (!card.HasPortrait || !ResourceLoader.Exists(card.PortraitPath)) failures.Add($"trial portrait unavailable: {card.Id}");
            foreach (PowerModel power in new PowerModel[] { ModelDb.Power<CaveGodBrokenBladePower>(), ModelDb.Power<CaveGodShatteredShieldPower>(), ModelDb.Power<CaveGodMartialPower>(), ModelDb.Power<CaveGodArcanePower>() })
                if (!ResourceLoader.Exists(power.PackedIconPath) || power.ResolvedBigIconPath.Contains("missing_power"))
                    failures.Add($"trial icon unavailable: {power.Id}");
                else if (power.Icon is not { } icon || icon.GetWidth() == 0 || icon.GetHeight() == 0)
                    failures.Add($"trial icon could not decode: {power.Id}");

            foreach (bool angry in new[] { false, true })
            foreach (bool right in new[] { false, true })
            {
                controller.RestoreCapturedPlayersInstantly();
                controller.SetAngry(angry);
                controller.StartAttackAnim(right ? "grab_player_right" : "grab_player", right);
                AdvanceAction(2.60);
                controller.StartGrabTracking([captive.Entity], right);
                controller.HoldGrabAnim();
                AdvanceAction(0);
                controller._Process(0);
                string side = right ? "right" : "left";
                string fistName = right ? "arm2_3" : "arm1_3";
                Transform2D holdTransform = rig.GetGlobalBoneTransform(fistName)!.Value;
                string[] chain = right ? ["arm2_1", "arm2_2", "arm2_3"] : ["arm1_1", "arm1_2", "arm1_3"];
                var heldChain = chain.Select(bone => rig.GetGlobalBoneTransform(bone)!.Value).ToArray();
                Vector2 hold = holdTransform.Origin;
                Vector2 anchor = captive.GlobalPosition;
                samples.Add(new { side, angry, state = "hold", fist = new[] { hold.X, hold.Y }, anchor = new[] { anchor.X, anchor.Y }, angle = Mathf.RadToDeg(holdTransform.X.Angle()) });
                if (Math.Abs(anchor.X - hold.X) > 100) failures.Add($"{side} grab offset: {Math.Abs(anchor.X-hold.X):F1}px (angry={angry})");
                await ActionCapture(output, $"{side}-{angry}-hold");
                controller.ResumeSlamAnim();
                AdvanceAction(0);
                Vector2 first = rig.GetGlobalBoneTransform(fistName)!.Value.Origin;
                float angleDelta = rig.GetGlobalBoneTransform(fistName)!.Value.X.Angle() - holdTransform.X.Angle();
                float seamAngle = Math.Abs(Mathf.RadToDeg(MathF.Atan2(MathF.Sin(angleDelta), MathF.Cos(angleDelta))));
                float seam = hold.DistanceTo(first);
                float chainShift = chain.Select((bone, i) => heldChain[i].Origin.DistanceTo(rig.GetGlobalBoneTransform(bone)!.Value.Origin)).Max();
                float chainTwist = chain.Select((bone, i) => Math.Abs(Mathf.RadToDeg(WrapRadians(
                    rig.GetGlobalBoneTransform(bone)!.Value.X.Angle() - heldChain[i].X.Angle())))).Max();
                if (seam > 12) failures.Add($"{side} hold-to-slam jump: {seam:F1}px (angry={angry})");
                Vector2 previous = first;
                float maxStep = 0;
                string[] restingChain = right ? ["arm1_1", "arm1_2", "arm1_3"] : ["arm2_1", "arm2_2", "arm2_3"];
                var previousResting = restingChain.Select(bone => rig.GetGlobalBoneTransform(bone)!.Value).ToArray();
                float restingMaxStep = 0, restingMaxTwist = 0;
                var restingFrames = new List<object>();
                for (int frame = 1; frame <= 264; frame++)
                {
                    AdvanceAction(1.0 / 120.0);
                    controller._Process(0);
                    Vector2 point = rig.GetGlobalBoneTransform(fistName)!.Value.Origin;
                    maxStep = Math.Max(maxStep, point.DistanceTo(previous));
                    previous = point;
                    var resting = restingChain.Select(bone => rig.GetGlobalBoneTransform(bone)!.Value).ToArray();
                    float step = resting.Select((pose, i) => pose.Origin.DistanceTo(previousResting[i].Origin)).Max();
                    float twist = resting.Select((pose, i) => Math.Abs(Mathf.RadToDeg(WrapRadians(pose.X.Angle() - previousResting[i].X.Angle())))).Max();
                    restingMaxStep = Math.Max(restingMaxStep, step);
                    restingMaxTwist = Math.Max(restingMaxTwist, twist);
                    restingFrames.Add(new { time = frame / 120.0, step, twist, bones = resting.Select(pose => new[] { pose.Origin.X, pose.Origin.Y, Mathf.RadToDeg(pose.X.Angle()) }).ToArray() });
                    previousResting = resting;
                    if (frame is 54 or 90) await ActionCapture(output, $"{side}-{angry}-slam-{frame}");
                    if (!right && !angry && frame is 89 or 91 or 198 or 199 or 200 or 205)
                        await ActionCapture(output, $"{side}-{angry}-resting-arm-{frame}");
                }
                samples.Add(new { side, angry, state = "resting-arm", restingMaxStep, restingMaxTwist, frames = restingFrames });
                if (restingMaxStep > 40 || restingMaxTwist > 15)
                    failures.Add($"{side} slam resting arm discontinuity: {restingMaxStep:F1}px, {restingMaxTwist:F1}deg/frame (angry={angry})");
                samples.Add(new { side, angry, state = "slam", seam, seamAngle, maxStep, chainShift, chainTwist, startAngle = Mathf.RadToDeg(holdTransform.X.Angle() + angleDelta) });
                if (chainShift > 12 || chainTwist > 8) failures.Add($"{side} arm-chain seam: {chainShift:F1}px, {chainTwist:F1}deg (angry={angry})");
                if (seamAngle > 5) failures.Add($"{side} hold-to-slam twist: {seamAngle:F1}deg (angry={angry})");
                if (maxStep > 80) failures.Add($"{side} slam discontinuity: {maxStep:F1}px/frame (angry={angry})");
            }

            controller.RestoreCapturedPlayersInstantly();
            nodes.Clear();
            harmony.Patch(AccessTools.Method(typeof(Cmd), nameof(Cmd.Wait), [typeof(float), typeof(CancellationToken), typeof(bool)]),
                prefix: new HarmonyMethod(typeof(CaveGodProbeNode), nameof(ActionWait)));
            harmony.Patch(AccessTools.Method(typeof(Cmd), nameof(Cmd.CustomScaledWait)),
                prefix: new HarmonyMethod(typeof(CaveGodProbeNode), nameof(ActionScaledWait)));
            harmony.Patch(AccessTools.Method(typeof(AttackCommand), nameof(AttackCommand.Execute)),
                prefix: new HarmonyMethod(typeof(CaveGodProbeNode), nameof(RecordActionHit)));
            // Exercise the actual damage -> release -> forced idle transition too.
            // Natural clip completion alone misses early cleanup in fast/instant mode.
            foreach (bool angry in new[] { false, true })
            foreach (bool right in new[] { false, true })
            foreach (var mode in new[] { FastModeType.Normal, FastModeType.Fast, FastModeType.Instant })
            {
                controller.RestoreCapturedPlayersInstantly();
                controller.SetAngry(angry);
                controller.StartAttackAnim(right ? "grab_player_right" : "grab_player", right);
                AdvanceAction(2.60);
                nodes.Add(captive);
                controller.StartGrabTracking([captive.Entity], right);
                nodes.Clear();
                controller.HoldGrabAnim();
                AdvanceAction(0);
                var hand = right ? (ThingsCaveGodHand)fixture.Right : fixture.Left;
                typeof(ThingsCaveGodHand).GetProperty(nameof(ThingsCaveGodHand.IsGrabbing))!.SetValue(hand, true);
                SaveManager.Instance.PrefsSave.FastMode = mode;
                string[] restingChain = right ? ["arm1_1", "arm1_2", "arm1_3"] : ["arm2_1", "arm2_2", "arm2_3"];
                var previous = restingChain.Select(bone => rig.GetGlobalBoneTransform(bone)!.Value).ToArray();
                float maxStep = 0, maxTwist = 0;
                double worstTime = 0;
                var frames = new List<object>();
                ActionClock = 0;
                bool firstRecoveryFrame = true;
                int hitsBeforeSlam = ActionPoseHits.Count;
                ActionFrame = () =>
                {
                    controller._Process(0);
                    var current = restingChain.Select(bone => rig.GetGlobalBoneTransform(bone)!.Value).ToArray();
                    float step = current.Select((pose, i) => pose.Origin.DistanceTo(previous[i].Origin)).Max();
                    float twist = current.Select((pose, i) => Math.Abs(Mathf.RadToDeg(WrapRadians(pose.X.Angle() - previous[i].X.Angle())))).Max();
                    // Instant mode deliberately seeks from the held pose to the
                    // hit pose before resolving damage. Check that seek separately;
                    // continuity here covers the subsequent rendered recovery.
                    if (firstRecoveryFrame && mode == FastModeType.Instant) { step = 0; twist = 0; }
                    firstRecoveryFrame = false;
                    if (step > maxStep) worstTime = ActionClock;
                    maxStep = Math.Max(maxStep, step);
                    maxTwist = Math.Max(maxTwist, twist);
                    frames.Add(new { time = ActionClock, step, twist });
                    previous = current;
                };
                try
                {
                    await (Task)typeof(ThingsCaveGodHand).GetMethod("Slam", BindingFlags.Instance | BindingFlags.NonPublic)!
                        .Invoke(hand, [fixture.State.PlayerCreatures.ToArray()])!;
                    AdvanceAction(0.65);
                }
                finally { ActionFrame = null; }
                if (ActionPoseHits.Count <= hitsBeforeSlam || Math.Abs(ActionPoseHits[^1] - .75) > .025)
                    failures.Add($"Slam damage did not use the contact pose ({mode}, right={right}, angry={angry}).");
                samples.Add(new { side = right ? "right" : "left", angry, state = "slam-release", mode = mode.ToString(), maxStep, maxTwist, worstTime, frames });
                if (maxStep > 40 || maxTwist > 15)
                    failures.Add($"{(right ? "right" : "left")} slam release resting arm: {maxStep:F1}px, {maxTwist:F1}deg/frame at {worstTime:F3}s ({mode}, angry={angry})");
                if (controller.HasCapturedPlayers || hand.IsGrabbing) failures.Add("Slam did not release captive.");
            }
            foreach (var mode in new[] { FastModeType.Normal, FastModeType.Fast, FastModeType.Instant })
            {
                SaveManager.Instance.PrefsSave.FastMode = mode;
                controller.SetAngry(false);
                ActionClock = 0;
                ActionHits.Clear();
                ActionPoseHits.Clear();
                await (Task)typeof(ThingsCaveGodBody).GetMethod("JabsMove", BindingFlags.Instance | BindingFlags.NonPublic)!
                    .Invoke(fixture.Body, [fixture.State.PlayerCreatures.ToArray()])!;
                samples.Add(new { state = "jabs", mode = mode.ToString(), hits = ActionHits.ToArray(), poses = ActionPoseHits.ToArray() });
                double[] expected = [0.64, 1.34, 2.32];
                if (ActionPoseHits.Count != 3 || ActionPoseHits.Where((hit, index) => Math.Abs(hit - expected[index]) > 0.025).Any())
                    failures.Add($"Jabs contact poses ({mode}) do not match damage events.");
                if (ActionHits.Count != 3 || mode != FastModeType.Instant && ActionHits.Where((hit, index) => Math.Abs(hit - expected[index]) > 0.025).Any())
                    failures.Add($"Jabs VFX/damage clock ({mode}): {string.Join(", ", ActionHits.Select(hit => hit.ToString("F3")))}; expected 0.640, 1.340, 2.320");
            }
        }
        finally
        {
            harmony.UnpatchAll(harmony.Id);
            ActionRoom = null;
            ActionSprites = [];
            room.QueueFree();
            _actionViewport.QueueFree();
            stateDisplay.Free();
        }
        File.WriteAllText(Path.Combine(output, "measurements.json"), JsonSerializer.Serialize(samples, new JsonSerializerOptions { WriteIndented = true }));
        foreach (string failure in failures) GD.Print("ACTION_REGRESSION: " + failure);
        Assert(failures.Count == 0, string.Join("; ", failures));
        GD.Print("CaveGod action regression: PASS");
    }

    private async Task ActionCapture(string output, string name)
    {
        if (OS.GetCmdlineUserArgs().Contains("--no-images")) return;
        await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
        RenderingServer.ForceDraw(false);
        using var frame = _actionViewport!.GetTexture().GetImage();
        frame.SavePng(Path.Combine(output, name + ".png"));
    }
}
