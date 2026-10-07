using System.Reflection;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using STS2_Things.Powers;
using STS2_Things.Visuals;

public partial class CaveGodProbeNode
{
    private static readonly List<string> UiAnimationTriggers = [];
    private static void RecordUiAnimation(string trigger) => UiAnimationTriggers.Add(trigger);

    private async Task VerifyUiRegression()
    {
        string root = Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "../.."));
        string output = Path.Combine(root, "build/cavegod-ui-20261002");
        Directory.CreateDirectory(output);
        // The synthetic mod is registered after the probe's initial locale load.
        MegaCrit.Sts2.Core.Localization.LocManager.Initialize();
        MegaCrit.Sts2.Core.Saves.SaveManager.Instance.InitPrefsDataForTest();
        MegaCrit.Sts2.Core.Saves.SaveManager.Instance.PrefsSave.FastMode = MegaCrit.Sts2.Core.Settings.FastModeType.Instant;
        var status = GDExtensionManager.LoadExtension(Path.Combine(root, "addons/spine/spine_godot_extension.gdextension"));
        Assert(status is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded, "Spine unavailable.");
        GetTree().Root.Size = new Vector2I(1920, 1080);
        var bg = GD.Load<PackedScene>("res://scenes/backgrounds/cave_god_boss_encounter/cave_god_boss_encounter_background.tscn").Instantiate<Control>();
        bg.Position = new Vector2(983, 540);
        bg.Scale = Vector2.One * 0.75f;
        bg.GetNode("Layer_00").AddChild(GD.Load<PackedScene>("res://scenes/backgrounds/cave_god_boss_encounter/layers/cave_god_boss_encounter_bg_00_a.tscn").Instantiate());
        bg.GetNode("Foreground").AddChild(GD.Load<PackedScene>("res://scenes/backgrounds/cave_god_boss_encounter/layers/cave_god_boss_encounter_fg_a.tscn").Instantiate());
        AddChild(bg);
        var controller = bg.GetNode<NCaveGodBossBackground>("CaveGod");
        var arms = bg.GetNode<Node2D>("CaveGodArms");
        var rig = new MegaSprite(arms);
        var state = Scenario();
        var enemies = new Control { Position = new Vector2(983, 540), Scale = Vector2.One * 0.75f };
        AddChild(enemies);
        var slots = GD.Load<PackedScene>("res://scenes/encounters/cave_god_boss_encounter.tscn").Instantiate<Control>();
        slots.Position = new Vector2(-960, -540);
        enemies.AddChild(slots);
        var creatures = new List<NCreature>();
        foreach (var (monster, side) in new[] { (state.Left as STS2_Things.Monsters.ThingsCaveGodHand, "left"), (state.Right as STS2_Things.Monsters.ThingsCaveGodHand, "right") })
        {
            var node = GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
            typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(node, monster.Creature);
            var visuals = GD.Load<PackedScene>($"res://scenes/creature_visuals/things_cave_god_{side}_hand.tscn").Instantiate<NCreatureVisuals>();
            typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(node, visuals);
            enemies.AddChild(node);
            node.GlobalPosition = slots.GetNode<Marker2D>(side + "_hand").GlobalPosition;
            creatures.Add(node);
        }
        for (int i = 0; i < 35; i++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
        controller.UpdateHandAnchors(creatures);
        async Task Capture(string name)
        {
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            await ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
            using var image = GetViewport().GetTexture().GetImage();
            image.SavePng(Path.Combine(output, name + ".png"));
        }
        await Capture("combat");
        var failures = new List<string>();
        for (int i = 0; i < 2; i++)
        {
            var hp = creatures[i].GetNode<Control>("%HealthBar");
            var bone = rig.GetGlobalBoneTransform(i == 0 ? "arm1_3" : "arm2_3")!.Value;
            GD.Print($"UI probe arm {i}: creature={creatures[i].GlobalPosition}, hp={hp.GlobalPosition}, bone={bone.Origin}, hitbox={creatures[i].Hitbox.GetGlobalRect()}");
            if (Math.Abs(creatures[i].GlobalPosition.X - bone.Origin.X) > 30)
                failures.Add($"arm {i} UI is not horizontally attached to its fist");
        }
        var hoverTips = (System.Collections.IEnumerable)typeof(ThingsCaveGodAgingPower)
            .GetProperty("ExtraHoverTips", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(ModelDb.Power<ThingsCaveGodAgingPower>())!;
        if (hoverTips.Cast<object>().Any(tip => tip.GetType().Name.Contains("CardHoverTip")))
            failures.Add("aging tooltip still creates a large card preview");

        foreach (float zoom in new[] { 0.60f, 0.75f, 1.0f })
        {
            bg.Scale = enemies.Scale = Vector2.One * zoom;
            foreach (string animation in new[] { "idle_front", "rightpunch", "front_sweep_right_angry", "weak_idle_angry" })
            {
                foreach (Node2D sprite in new[] { bg.GetNode<Node2D>("CaveGod/CaveGodBody"), arms })
                {
                    var animationState = sprite.Call("get_animation_state").AsGodotObject();
                    using Variant trackRef = animationState.Call("set_animation", animation, false, 0);
                    using GodotObject track = trackRef.AsGodotObject();
                    track.Call("set_track_time", 0.7f);
                    track.Call("set_time_scale", 0f);
                    track.Call("set_mix_duration", 0f);
                }
                await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
                await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
                controller.UpdateHandAnchors(creatures);
                for (int i = 0; i < 2; i++)
                {
                    Vector2 fist = rig.GetGlobalBoneTransform(i == 0 ? "arm1_3" : "arm2_3")!.Value.Origin;
                    Assert(Math.Abs(creatures[i].GlobalPosition.X - fist.X) < 30 * zoom,
                        $"Hand UI detached in {animation} at zoom {zoom}.");
                    Assert(creatures[i].Hitbox.GetGlobalRect().HasPoint(creatures[i].VfxSpawnPosition),
                        "Hand hit effect anchor lies outside its target bounds.");
                }
            }
        }
        bg.Scale = enemies.Scale = Vector2.One * 0.75f;

        var animationProbe = new Harmony("CaveGodProbe.CaptiveDeath");
        animationProbe.Patch(AccessTools.Method(typeof(NCreature), nameof(NCreature.SetAnimationTrigger)),
            prefix: new HarmonyMethod(typeof(CaveGodProbeNode), nameof(RecordUiAnimation)));
        try
        {
            var captured = (System.Collections.IList)typeof(NCaveGodBossBackground)
                .GetField("_capturedPlayers", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(controller)!;
            captured.Add((creatures[0], creatures[0].Position, creatures[0].Rotation, creatures[0].Scale));
            creatures[0].Entity.SetCurrentHpInternal(0);
            UiAnimationTriggers.Clear();
            controller.RestoreCapturedPlayersInstantly();
            if (UiAnimationTriggers.Contains("Idle")) failures.Add("dead captive returned to idle during cleanup");

            // A release tween must not move a corpse again after combat cleanup.
            Vector2 original = creatures[0].Position;
            captured.Add((creatures[0], original, creatures[0].Rotation, creatures[0].Scale));
            var hp = creatures[0].GetNode<Control>("%HealthBar");
            hp.Modulate = new Color(1, 1, 1, 0);
            Tween release = controller.CreateTween();
            release.TweenProperty(creatures[0], "position", original + Vector2.Right * 300, 0.1);
            typeof(NCaveGodBossBackground).GetField("_releaseTween", BindingFlags.Instance | BindingFlags.NonPublic)!
                .SetValue(controller, release);
            typeof(NCaveGodBossBackground).GetMethod("OnCombatEnded", BindingFlags.Instance | BindingFlags.NonPublic)!
                .Invoke(controller, [state.State.RunState.CurrentRoom]);
            await ToSignal(GetTree().CreateTimer(0.2), SceneTreeTimer.SignalName.Timeout);
            Assert(creatures[0].Position.IsEqualApprox(original) && hp.Modulate.A == 0,
                "A release tween or UI fade survived combat cleanup.");
        }
        finally { animationProbe.UnpatchAll(animationProbe.Id); }

        // This is the native layering pattern: a later sibling overlay at Z=0.
        // An absolute positive Z on world sprites makes them escape this overlay.
        var overlay = new ColorRect { Color = new Color(0.08f, 0.14f, 0.24f), Size = new Vector2(1920, 1080) };
        AddChild(overlay);
        await Capture("overlay");
        using (var frame = GetViewport().GetTexture().GetImage())
        {
            Color expected = frame.GetPixel(25, 25);
            int uncovered = 0;
            for (int y = 150; y < 950; y += 8)
                for (int x = 150; x < 1770; x += 8)
                    if (!frame.GetPixel(x, y).IsEqualApprox(expected)) uncovered++;
            if (uncovered > 0) failures.Add($"world sprites/UI cover the later overlay at {uncovered} sampled pixels");
        }
        overlay.QueueFree();
        enemies.QueueFree();
        bg.QueueFree();
        await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
        if (failures.Count > 0) throw new InvalidOperationException(string.Join("; ", failures));
        GD.Print("CaveGod UI regression: PASS");
    }
}
