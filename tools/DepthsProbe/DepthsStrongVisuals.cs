using System.Reflection;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using STS2_Things.Acts;

public partial class DepthsProbeNode
{
    private async Task RenderStrongVariety()
    {
        var host = new Harmony("DepthsProbe.StrongVarietyVisualHost");
        host.Patch(AccessTools.Method(typeof(CombatStateTracker), "NotifyCombatStateChanged"),
            prefix: new HarmonyMethod(typeof(DepthsProbeNode), nameof(SkipTestUiGuard)));
        Type? atlasType = typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Assets.AtlasResourceLoader");
        ResourceFormatLoader? atlas = atlasType == null ? null : (ResourceFormatLoader)Activator.CreateInstance(atlasType)!;
        if (atlas != null) ResourceLoader.AddResourceFormatLoader(atlas, true);
        var view = new SubViewport { Size = new Vector2I(1920, 1080), Disable3D = true, RenderTargetUpdateMode = SubViewport.UpdateMode.Always };
        AddChild(view);
        GetTree().Root.Size = view.Size;
        string output = Path.Combine(_output, "visuals");
        Directory.CreateDirectory(output);
        foreach (var canonical in ModelDb.Act<Depths>().AllRegularEncounters.Where(e => NewStrongTypes.Contains(e.GetType())))
        foreach (int players in new[] { 1, 4 })
        {
            var b = await StrongBattle(canonical, players);
            var bg = b.Encounter.CreateBackground(b.Run.Act, b.Run.Rng.UpFront);
            bg.Position = new Vector2(983, 540);
            view.AddChild(bg);
            var slots = b.Encounter.CreateScene();
            view.AddChild(slots);
            foreach (var entity in b.Enemies)
            {
                var creature = GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
                typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(creature, entity);
                typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(creature, entity.Monster!.CreateVisuals());
                creature.Position = slots.GetNode<Node2D>(entity.SlotName!).Position;
                view.AddChild(creature);
                await creature.UpdateIntent(b.Players.Select(p => p.Creature));
                creature.IntentContainer.Modulate = Colors.White;
            }
            var team = new Node2D { Position = new Vector2(960, 540) };
            view.AddChild(team);
            var heroes = new List<NCreature>();
            foreach (var player in b.Players)
            {
                var hero = GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
                typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(hero, player.Creature);
                typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(hero, player.Character.CreateVisuals());
                team.AddChild(hero);
                heroes.Add(hero);
            }
            NCombatRoom.PositionPlayersAndPets(heroes, b.Encounter.GetCameraScaling(), b.Encounter.FullyCenterPlayers);
            await ToSignal(GetTree().CreateTimer(.7), SceneTreeTimer.SignalName.Timeout);
            await ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
            using (var image = view.GetTexture().GetImage())
                Assert(image.SavePng(Path.Combine(output, $"{canonical.Id.Entry.ToLowerInvariant()}-{players}p.png")) == Error.Ok, "Native combined encounter capture.");
            foreach (var child in view.GetChildren()) { view.RemoveChild(child); child.QueueFree(); }
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            DeactivateSyntheticCombat();
        }
        view.QueueFree();
        await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
        host.UnpatchAll(host.Id);
        if (atlas != null) ResourceLoader.RemoveResourceFormatLoader(atlas);
        GD.Print("PASS twelve native render captures for all six new encounters in solo and four-player formations.");
    }
}
