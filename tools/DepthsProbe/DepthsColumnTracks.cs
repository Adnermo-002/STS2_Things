using System.Reflection;
using Godot;
using Godot.Bridge;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Combat;
using STS2_Things.Encounters;
using STS2_Things.Monsters;

public partial class DepthsProbeNode
{
    private async Task VerifyColumnTracks()
    {
        var extension = GDExtensionManager.LoadExtension(Path.Combine(_root, "addons/spine/spine_godot_extension.gdextension"));
        Assert(extension is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded, "Spine extension");
        ScriptManagerBridge.LookupScriptsInAssembly(typeof(ActModel).Assembly);
        var host = new Harmony("DepthsProbe.ColumnTracksHost");
        host.Patch(AccessTools.Method(typeof(CombatStateTracker), "NotifyCombatStateChanged"),
            prefix: new HarmonyMethod(typeof(DepthsProbeNode), nameof(SkipTestUiGuard)));
        try
        {
            var battle = await StrongBattle(ModelDb.Encounter<HumanFaceColumnEncounter>());
            var stage = new Node2D();AddChild(stage);
            var creatures = new List<NCreature>();
            foreach (var entity in battle.Enemies)
            {
                var node = GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
                typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(node, entity);
                typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(node, entity.Monster!.CreateVisuals());
                node.Position = new Vector2(1000, 800 - ((HumanFaceColumn)entity.Monster!).Level * HumanFaceColumn.LayerSpacing);
                stage.AddChild(node);creatures.Add(node);
            }
            for (int frame = 0; frame < 2; frame++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            foreach (var node in creatures)
            {
                var current = node.Visuals.SpineBody!.GetAnimationState().GetCurrent(1);
                GD.Print($"COLUMN TRACK {((HumanFaceColumn)node.Entity.Monster!).Level}: wrapper={current != null}, native={current?.BoundObject != null}");
                Assert(current?.BoundObject != null && GodotObject.IsInstanceValid(current.BoundObject), "Column must start its actual rotation track after entering the scene");
                Assert(current!.GetAnimationName() == (((HumanFaceColumn)node.Entity.Monster!).Level == 1 ? "rotate_ccw" : "rotate_cw"), "Alternating native rotation tracks");
                (current as object as IDisposable)?.Dispose();
            }
            Assert(creatures.Single(n => ((HumanFaceColumn)n.Entity.Monster!).Level == 2).Visuals.GetChildren().Count(n => n.Name.ToString().StartsWith("ReserveDisc")) == 3,
                "Three reserves really render above the visible column");
            for (int frame = 0; frame < 120; frame++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            foreach (var entity in battle.Enemies)
            {
                for (int turn = 0; turn < 4; turn++)
                {
                    await entity.Monster!.PerformMove();
                    entity.Monster.RollMove(battle.Players.Select(p => p.Creature));
                }
            }
            stage.QueueFree();await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            DeactivateSyntheticCombat();
        }
        finally { host.UnpatchAll(host.Id); }
    }
}
