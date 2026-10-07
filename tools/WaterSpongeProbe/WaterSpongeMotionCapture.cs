using System.Text.Json;
using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Nodes.Combat;
using STS2_Things.Monsters;
using STS2_Things.Powers;

public partial class WaterSpongeProbeNode
{
    private async Task RenderMotionClips(SubViewport view, Fixture scenario, string output)
    {
        const int fps = 20;
        string framesDir = Path.Combine(output, "motion"); Directory.CreateDirectory(framesDir);
        var actors = view.GetChildren().OfType<NCreature>().Where(n => n.Entity.IsEnemy).ToArray();
        static void Pose(Node2D sprite, string animation, float time)
        {
            sprite.Call("get_skeleton").AsGodotObject().Call("set_to_setup_pose");
            var state = sprite.Call("get_animation_state").AsGodotObject(); state.Call("clear_tracks");
            var track = state.Call("set_animation", animation, false, 0).AsGodotObject();
            track.Call("set_mix_duration", 0f); track.Call("set_track_time", time); sprite.Call("update_skeleton", 0f);
        }
        var clips = new List<object>();
        int count = 0;
        foreach (bool sponge in new[] { true, false })
        {
            var focus = actors.Single(n => sponge ? n.Entity.Monster is WaterSponge : n.Entity.Monster is SanguineLeech);
            (string name, float length)[] motions = sponge
                ? [("idle_loop", 4f), ("attack", 1.15f), ("cast", 1.5f), ("soak", 1.35f), ("hurt", .58f), ("power_up", 1.2f), ("die", 1.5f), ("revive", 1.4f), ("summon", 1.2f)]
                : [("idle_loop", 4f), ("attack", 1.12f), ("cast", 1.45f), ("curl", 1.1f), ("feed", .85f), ("hurt", .6f), ("power_up", 1.3f), ("die", 1.5f), ("revive", 1.4f), ("summon", 1.2f)];
            foreach (var (name, length) in motions)
            {
                string slug = (sponge ? "sponge_" : "leech_") + name;
                if (sponge && name == "cast") await PowerCmd.Apply<SpongeReservoirPower>(Choice, scenario.Sponge.Creature, 3, scenario.Sponge.Creature, null);
                int frameCount = (int)Math.Ceiling(length * fps) + 1;
                bool drained = false;
                for (int i = 0; i < frameCount; i++)
                {
                    float time = Math.Min(i / (float)fps, length);
                    if (sponge && name == "cast" && time >= WaterSponge.SprayContact && !drained)
                    {
                        await PowerCmd.Remove(scenario.Sponge.Creature.GetPower<SpongeReservoirPower>());
                        drained = true;
                    }
                    foreach (var node in actors)
                        Pose(node.Visuals.GetNode<Node2D>("Visuals"), node == focus ? name : "idle_loop", node == focus ? time : time % 4);
                    await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
                    await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
                    RenderingServer.ForceDraw();
                    using var image = view.GetTexture().GetImage();
                    image.Resize(1280, 720, Image.Interpolation.Lanczos);
                    if (image.SaveJpg(Path.Combine(framesDir, $"{slug}_{i:D4}.jpg"), .94f) != Error.Ok) throw new Exception("Motion frame capture failed");
                    count++;
                }
                clips.Add(new { slug, name, monster = sponge ? "sponge" : "leech", duration = length, frames = frameCount });
                GD.Print("Captured native motion clip " + slug);
            }
        }
        File.WriteAllText(Path.Combine(framesDir, "report.json"), JsonSerializer.Serialize(new { fps, frames = count, clips }, new JsonSerializerOptions { WriteIndented = true }));
        Assert(count > 500, "All nineteen native motion clips captured.");
    }
}
