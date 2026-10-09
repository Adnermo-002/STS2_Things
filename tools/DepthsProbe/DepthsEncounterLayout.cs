using System.Reflection;
using System.Text.Json;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Settings;
using STS2_Things.Acts;
using STS2_Things.Encounters;
using STS2_Things.Monsters;

public partial class DepthsProbeNode
{
    // Native creature HUDs and the native end-turn artwork, independently of a
    // live save. The button's shown position comes from the target game DLL.
    private async Task VerifyEncounterHudLayout()
    {
        var extension = GDExtensionManager.LoadExtension(Path.Combine(_root, "addons/spine/spine_godot_extension.gdextension"));
        Assert(extension is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded, "Spine extension loaded.");
        Godot.Bridge.ScriptManagerBridge.LookupScriptsInAssembly(typeof(ActModel).Assembly);
        SaveManager.Instance.PrefsSave.FastMode = FastModeType.Instant;
        var host = new Harmony("DepthsProbe.EncounterLayout");
        host.Patch(AccessTools.Method(typeof(CombatStateTracker), "NotifyCombatStateChanged"),
            prefix: new HarmonyMethod(typeof(DepthsProbeNode), nameof(SkipTestUiGuard)));
        Type? atlasType = typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Assets.AtlasResourceLoader");
        ResourceFormatLoader? atlas = atlasType == null ? null : (ResourceFormatLoader)Activator.CreateInstance(atlasType)!;
        if (atlas != null) ResourceLoader.AddResourceFormatLoader(atlas, true);
        var view = new SubViewport { Size = new Vector2I(1920, 1080), Disable3D = true,
            RenderTargetUpdateMode = SubViewport.UpdateMode.Always };
        AddChild(view);
        GetTree().Root.Size = view.Size;
        string output = Path.Combine(_output, "layout");
        Directory.CreateDirectory(output);
        bool sourceScenes = System.Environment.GetEnvironmentVariable("THINGS_LAYOUT_SOURCE_SCENES") == "1";
        string? only = System.Environment.GetEnvironmentVariable("THINGS_LAYOUT_ENCOUNTER");
        var rows = new List<object>();
        var failures = new List<string>();
        var encounters = ModelDb.AllEncounters
            .Where(e => e.GetType().Assembly == typeof(Depths).Assembly && e.HasScene)
            .Where(e => string.IsNullOrWhiteSpace(only) || e.Id.Entry == only)
            .OrderBy(e => e.Id.Entry).ToArray();
        Assert(encounters.Length > 0, "At least one authored encounter selected.");
        foreach (var canonical in encounters)
        {
            var b = await StrongBattle(canonical);
            // Exercise authored summon locations as well as opening formations.
            MonsterModel? summon = canonical switch
            {
                BowlbugProgenitorBossEncounter => ModelDb.Monster<BowlbugRock>(),
                GravetideSlugBossEncounter => ModelDb.Monster<GravetideCorpseSlug>(),
                SoulRoesEncounter => ModelDb.Monster<SoulRoe>(),
                _ => null,
            };
            if (summon != null)
                foreach (string slot in canonical.Slots.Where(s => b.Enemies.All(e => e.SlotName != s)))
                {
                    var monster = summon.ToMutable();
                    var entity = b.State.CreateCreature(monster, CombatSide.Enemy, slot);
                    b.State.AddCreature(entity);
                    monster.SetUpForCombat();
                    monster.RollMove(b.Players.Select(p => p.Creature));
                }
            // Legacy boss background scripts need their full room host. The HUD
            // fixture uses a native generic cave behind those actors instead.
            var background = canonical is ModBossEncounter and not CaveGodBossEncounter
                ? NCombatBackground.Create(ModelDb.Act<Depths>().GenerateBackgroundAssets(b.Run.Rng.UpFront))
                : b.Encounter.CreateBackground(b.Run.Act, b.Run.Rng.UpFront);
            background.Position = new Vector2(983, 540);
            view.AddChild(background);
            var world = new Control { Size = new Vector2(1920, 1080), PivotOffset = new Vector2(960, 540),
                Scale = Vector2.One * b.Encounter.GetCameraScaling(), Position = b.Encounter.GetCameraOffset() };
            view.AddChild(world);
            var slots = sourceScenes
                ? GD.Load<PackedScene>(Path.Combine(_root, "scenes/encounters", canonical.Id.Entry.ToLowerInvariant() + ".tscn")).Instantiate<Control>()
                : b.Encounter.CreateScene();
            world.AddChild(slots);
            var creatures = new List<NCreature>();
            foreach (var entity in b.Enemies)
            {
                var creature = GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
                typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(creature, entity);
                typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(creature, entity.Monster!.CreateVisuals());
                creature.Position = slots.GetNode<Node2D>(entity.SlotName!).Position;
                world.AddChild(creature);
                await creature.UpdateIntent(b.Players.Select(p => p.Creature));
                creature.IntentContainer.Modulate = Colors.White;
                creatures.Add(creature);
            }
            var team = new Node2D { Position = new Vector2(960, 540) };
            world.AddChild(team);
            var hero = GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
            typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(hero, b.Players[0].Creature);
            typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(hero, b.Players[0].Character.CreateVisuals());
            team.AddChild(hero);
            NCombatRoom.PositionPlayersAndPets([hero], b.Encounter.GetCameraScaling(), b.Encounter.FullyCenterPlayers);

            // Keep the button's native dimensions, textures, offsets and pivots;
            // detach only its combat-input behavior from this render fixture.
            var originalButton = GD.Load<PackedScene>("res://scenes/combat/end_turn_button.tscn").Instantiate<Control>();
            var buttonVisuals = originalButton.GetNode<Control>("Visuals");
            originalButton.RemoveChild(buttonVisuals);
            Vector2 shownRatio = (Vector2)AccessTools.Field(typeof(NEndTurnButton), "_showPosRatio").GetValue(null)!;
            var button = new Control { Size = originalButton.Size, Position = shownRatio * new Vector2(1920, 1080) };
            originalButton.Free();
            view.AddChild(button);
            button.AddChild(buttonVisuals);
            buttonVisuals.GetNode<Label>("Label").Text = "结束回合";
            await ToSignal(GetTree().CreateTimer(.65), SceneTreeTimer.SignalName.Timeout);
            await ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
            Rect2 blocker = buttonVisuals.GetNode<Control>("Image").GetGlobalRect();
            foreach (var creature in creatures)
            {
                var samples = new List<(string Kind, Control Node)>
                {
                    ("health", creature.GetNode<Control>("HealthBar/HealthBar/HpBarContainer")),
                    ("hp_text", creature.GetNode<Control>("HealthBar/HealthBar/HpBarContainer/HpLabel")),
                };
                if (creature.Entity.Block > 0)
                    samples.Add(("block", creature.GetNode<Control>("HealthBar/HealthBar/BlockContainer")));
                samples.AddRange(creature.GetNode("HealthBar/PowerContainer").GetChildren().OfType<Control>()
                    .Where(n => n.Visible).Select(n => ("power", n)));
                foreach (var (kind, node) in samples)
                {
                    Rect2 rect = node.GetGlobalRect();
                    bool overlap = rect.Intersects(blocker.Grow(12));
                    rows.Add(new { encounter = canonical.Id.Entry, slot = creature.Entity.SlotName,
                        monster = creature.Entity.Monster!.Id.Entry, kind,
                        rect = new[] { rect.Position.X, rect.Position.Y, rect.Size.X, rect.Size.Y },
                        button = new[] { blocker.Position.X, blocker.Position.Y, blocker.Size.X, blocker.Size.Y }, overlap });
                    if (overlap) failures.Add($"{canonical.Id.Entry}/{creature.Entity.SlotName}: {kind} {rect}");
                }
            }
            using (var image = view.GetTexture().GetImage())
                Assert(image.SavePng(Path.Combine(output, canonical.Id.Entry.ToLowerInvariant() + ".png")) == Error.Ok, "Layout capture saved.");
            foreach (var child in view.GetChildren()) { view.RemoveChild(child); child.QueueFree(); }
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            DeactivateSyntheticCombat();
        }
        File.WriteAllText(Path.Combine(output, "measurements.json"), JsonSerializer.Serialize(new { sourceScenes,
            encounters = encounters.Length, rows, failures }, new JsonSerializerOptions { WriteIndented = true }));
        view.QueueFree();
        await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
        host.UnpatchAll(host.Id);
        if (atlas != null) ResourceLoader.RemoveResourceFormatLoader(atlas);
        foreach (string failure in failures) GD.Print("HUD_OVERLAP " + failure);
        Assert(failures.Count == 0, $"{failures.Count} creature HUD rectangles overlap the end-turn button; see {output}.");
    }
}
