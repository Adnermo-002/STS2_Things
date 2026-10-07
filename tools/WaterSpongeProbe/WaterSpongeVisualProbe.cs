using Godot;
using Godot.Bridge;
using HarmonyLib;
using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Assets;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Intents;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Saves;
using STS2_Things.Monsters;
using STS2_Things.Powers;

public partial class WaterSpongeProbeNode
{
    private async Task RenderProbe()
    {
        string output = Path.Combine(System.Environment.GetEnvironmentVariable("THINGS_PROBE_OUTPUT")
            ?? Path.Combine(_root, "build/water_sponge"), "visuals"); Directory.CreateDirectory(output);
        var extension = GDExtensionManager.LoadExtension(Path.Combine(_root, "addons/spine/spine_godot_extension.gdextension"));
        Assert(extension is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded, "Spine extension loaded.");
        var ui = new Harmony("WaterSpongeProbe.VisualHost");
        Assert(IntentAnimData.GetAnimationFrameCount("buff") == 30, "Uses the unmodified native thirty-frame Buff animation.");
        ui.Patch(AccessTools.Method(typeof(CombatStateTracker), "NotifyCombatStateChanged"), prefix: new HarmonyMethod(typeof(WaterSpongeProbeNode), nameof(SkipUiGuard)));
        ScriptManagerBridge.LookupScriptsInAssembly(typeof(NCard).Assembly);
        ScriptManagerBridge.LookupScriptsInAssembly(typeof(WaterSponge).Assembly);
        var loaderType = typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Assets.AtlasResourceLoader");
        var loader = loaderType == null ? null : (ResourceFormatLoader)Activator.CreateInstance(loaderType)!;
        if (loader != null) ResourceLoader.AddResourceFormatLoader(loader, true);
        SaveManager.Instance.SettingsSave.Language = "zhs"; LocManager.Initialize();
        GetTree().Root.Size = new Vector2I(1920, 1080);
        var view = new SubViewport { Size = new Vector2I(1920, 1080), Disable3D = true, RenderTargetUpdateMode = SubViewport.UpdateMode.Always };
        AddChild(view);

        async Task Capture(string name)
        {
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            RenderingServer.ForceDraw();
            using var image = view.GetTexture().GetImage();
            Assert(image.SavePng(Path.Combine(output, name + ".png")) == Error.Ok, "Captured " + name);
        }
        async Task Clear()
        {
            foreach (var child in view.GetChildren()) { view.RemoveChild(child); child.QueueFree(); }
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            RenderingServer.ForceDraw();
        }
        static void Pose(Node2D sprite, string animation, float time)
        {
            sprite.Call("get_skeleton").AsGodotObject().Call("set_to_setup_pose");
            var state = sprite.Call("get_animation_state").AsGodotObject(); state.Call("clear_tracks");
            var track = state.Call("set_animation", animation, false, 0).AsGodotObject();
            track.Call("set_track_time", time); track.Call("set_mix_duration", 0f); sprite.Call("update_skeleton", 0f);
        }
        NCreature AddCreature(Creature entity, string path, Vector2 position)
        {
            var node = GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
            typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(node, entity);
            typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(node, GD.Load<PackedScene>(path).Instantiate<NCreatureVisuals>());
            node.Position = position; view.AddChild(node); return node;
        }
        foreach (bool weak in new[] { true, false })
        {
            var s = await Scenario(weak);
            var bg = NCombatBackground.Create(new BackgroundAssets(s.Encounter.Id.Entry.ToLowerInvariant(), new Rng()));
            bg.Position = new Vector2(983, 540); view.AddChild(bg);
            var slots = s.Encounter.CreateScene(); view.AddChild(slots);
            AddCreature(s.Player.Creature, "res://scenes/creature_visuals/ironclad.tscn", new Vector2(480, 746));
            NCreature? spongeNode = null;
            foreach (var (monster, _) in s.Encounter.MonstersWithSlots)
            {
                string slug = monster is WaterSponge ? "water_sponge" : "sanguine_leech";
                var node = AddCreature(monster.Creature, $"res://scenes/creature_visuals/{slug}.tscn", slots.GetNode<Node2D>(monster.Creature.SlotName!).Position);
                await node.UpdateIntent(s.Players.Select(p => p.Creature).ToArray()); node.IntentContainer.Modulate = Colors.White;
                var sprite = node.Visuals.GetNode<Node2D>("Visuals");
                sprite.Call("set_update_mode", ClassDB.ClassGetIntegerConstant("SpineConstant", "UpdateMode_Manual"));
                Pose(sprite, "idle_loop", 0);
                if (monster is WaterSponge) spongeNode = node;
            }
            for (int frame = 0; frame < 12; frame++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            await Capture(weak ? "weak_pair" : "strong_colony");
            foreach (var power in new PowerModel[] { ModelDb.Power<AbsorbentSpongePower>(), ModelDb.Power<SpongeReservoirPower>(), ModelDb.Power<SpongeRinsePower>(), ModelDb.Power<LanternBlindnessPower>(), ModelDb.Power<LeechInfestationPower>() })
            {
                // V111's original AtlasResourceLoader resolves new mod powers via
                // its documented BigIcon fallback; V107 reads the 64px .tres.
                Assert(power.Icon.GetSize() == (loader == null ? new Vector2(64, 64) : new Vector2(256, 256)), "Native version-specific HUD icon resolution: " + power.Id);
                Assert(power.BigIcon.GetSize() == new Vector2(256, 256), "Native flash/hover icon: " + power.Id);
            }
            var spongeSprite = spongeNode!.Visuals.GetNode<Node2D>("Visuals");
            Vector2 dryScale = spongeSprite.Scale;
            var waterMaterial = spongeNode.Visuals.SpineBody!.GetNormalMaterial() as ShaderMaterial;
            Assert(waterMaterial?.Shader?.ResourcePath == "res://shaders/monsters/sponge_water.gdshader", "Spine renders the actual water material.");
            int previousWetPixels = -1;
            for (int level = 0; level <= 3; level++)
            {
                if (level > 0) await PowerCmd.Apply<SpongeReservoirPower>(Choice, s.Sponge.Creature, 1, s.Sponge.Creature, null);
                await ToSignal(GetTree().CreateTimer(.85), SceneTreeTimer.SignalName.Timeout);
                Assert(Math.Abs(waterMaterial!.GetShaderParameter("water_level").AsSingle() - level / 3f) < .02f, "Animated material settles at water level " + level);
                await Capture($"{(weak ? "weak" : "strong")}_water_{level}");
                using var pixels = view.GetTexture().GetImage();
                int wetPixels = 0;
                Vector2I corner = (Vector2I)spongeNode.Position + new Vector2I(-60, -100);
                for (int y = 0; y < 85; y++)
                for (int x = 0; x < 65; x++)
                {
                    Color color = pixels.GetPixel(corner.X + x, corner.Y + y);
                    if (color.B > color.R + .04f && color.G > color.R + .04f) wetPixels++;
                }
                GD.Print($"Water belly pixels at {level}: {wetPixels}");
                Assert(wetPixels > previousWetPixels + (level == 0 ? 0 : 100), "Rendered belly water visibly rises at every level.");
                previousWetPixels = wetPixels;
            }
            await spongeNode.UpdateIntent(s.Players.Select(p => p.Creature).ToArray()); spongeNode.IntentContainer.Modulate = Colors.White;
            for (int frame = 0; frame < 24; frame++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            var reservoir = s.Sponge.Creature.GetPower<SpongeReservoirPower>()!;
            var tip = reservoir.HoverTips.OfType<HoverTip>().First();
            Assert(tip.IsSmart && tip.Description.Contains("3") && !tip.Description.Contains("{Amount}"), "Native smart hover tip formats the live water amount.");
            var hud = spongeNode.FindChildren("*", "", true, false).OfType<NPower>().Single(power => power.Model == reservoir);
            Assert(hud.GetNode<Label>("%AmountLabel").Text == "3", "Original NPower shows the actual stack count.");
            var parasiteTips = ModelDb.Card<STS2_Things.Cards.LeechParasite>().HoverTips.OfType<HoverTip>().Select(t => t.Id).ToHashSet();
            Assert(parasiteTips.Contains(ModelDb.Power<MegaCrit.Sts2.Core.Models.Powers.RegenPower>().Id.ToString())
                && parasiteTips.Contains(ModelDb.Power<MegaCrit.Sts2.Core.Models.Powers.StrengthPower>().Id.ToString()), "Parasitism exposes the native Regeneration and Strength hover tips.");
            Assert(spongeSprite.Scale.X > dryScale.X * 1.10f, "Actual creature swells with stored water.");
            Assert(s.Sponge.NextMove.Intents.Count == 3 && s.Sponge.NextMove.Intents[0].GetType() == typeof(SingleAttackIntent)
                && s.Sponge.NextMove.Intents[1].GetType() == typeof(BuffIntent)
                && s.Sponge.NextMove.Intents[2].GetType() == typeof(HealIntent), "Spray uses the original attack, buff and heal intent classes.");
            var nativeBuffFrames = Enumerable.Range(0, IntentAnimData.GetAnimationFrameCount("buff"))
                .Select(frame => PreloadManager.Cache.GetTexture2D(IntentAnimData.GetAnimationFrame("buff", frame)).GetInstanceId()).ToHashSet();
            var buffSprite = spongeNode.IntentContainer.FindChildren("*", "Sprite2D", true, false).OfType<Sprite2D>()
                .Single(sprite => sprite.Texture != null && nativeBuffFrames.Contains(sprite.Texture.GetInstanceId()));
            ulong firstFrame = buffSprite.Texture!.GetInstanceId();
            await ToSignal(GetTree().CreateTimer(.11), SceneTreeTimer.SignalName.Timeout);
            Assert(buffSprite.Texture!.GetInstanceId() != firstFrame, "Native NIntent advances the Buff frames without a registration patch.");
            await Capture(weak ? "weak_full_water" : "strong_full_water");
            Pose(spongeSprite, "cast", .86f); await Capture(weak ? "weak_spray" : "strong_spray");
            await PowerCmd.Remove(s.Sponge.Creature.GetPower<SpongeReservoirPower>()!);
            await ToSignal(GetTree().CreateTimer(.85), SceneTreeTimer.SignalName.Timeout);
            Assert(waterMaterial!.GetShaderParameter("water_level").AsSingle() < .02f && spongeSprite.Scale.DistanceTo(dryScale) < .002f, "Spraying drains the belly and shrinks the body.");
            Pose(spongeSprite, "idle_loop", 0); await Capture(weak ? "weak_drained" : "strong_drained");
            if (!weak)
            {
                foreach (var (trigger, clip) in new[] { (CreatureAnimator.attackTrigger, "attack"), (CreatureAnimator.castTrigger, "cast"), ("Soak", "soak"), (CreatureAnimator.hitTrigger, "hurt"), (CreatureAnimator.deathTrigger, "die") })
                {
                    spongeNode.SetAnimationTrigger(trigger);
                    var track = spongeSprite.Call("get_animation_state").AsGodotObject().Call("get_current", 0).AsGodotObject();
                    Assert(track.Call("get_animation").AsGodotObject().Call("get_name").AsString() == clip, "Native animation trigger " + trigger);
                }
                foreach (var (clip, duration) in new[] { ("idle_loop", 4f), ("attack", 1.15f), ("cast", 1.5f), ("soak", 1.35f), ("hurt", .58f), ("die", 1.5f), ("revive", 1.4f), ("summon", 1.2f), ("power_up", 1.2f) })
                    for (int phase = 0; phase < 3; phase++)
                    {
                        Pose(spongeSprite, clip, duration * phase / 2);
                        await Capture($"pose_{clip}_{phase}");
                    }
            }
            if (weak && OS.GetCmdlineUserArgs().Contains("--motion")) await RenderMotionClips(view, s, output);
            await Clear(); DeactivateSyntheticCombat();
        }
        view.QueueFree(); await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
        RenderingServer.ForceDraw();
        ui.UnpatchAll(ui.Id);
        if (loader != null) ResourceLoader.RemoveResourceFormatLoader(loader);
        var cache = PreloadManager.Cache; cache.GetType().GetMethod("UnloadMissedCacheAssets")?.Invoke(cache, null);
        GC.Collect(); GC.WaitForPendingFinalizers();
        await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame); RenderingServer.ForceDraw();
        GD.Print("PASS packaged scenes, four actual belly water levels, draining, spray intent/VFX and nine native animations.");
    }
    private static bool SkipUiGuard() => false;
}
