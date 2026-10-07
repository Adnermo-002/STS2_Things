using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Nodes.Combat;
using STS2_Things.Monsters;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Visuals;

/// <summary>A pressure jet tied to the animated nozzle and actual player positions.</summary>
public partial class NSpongeWaterJet : Node2D
{
    private MegaSprite? _spine;
    private NCreature? _owner;
    private readonly List<Vector2> _targets = [];
    private float _time = -1;
    private float _pixel = 1;
    private const float LaunchTime = WaterSponge.SprayContact - .14f;
    private const float FinishTime = 1.23f;
    private Vector2 Mouth => new(-9 * _pixel, 0);

    public override void _Ready()
    {
        _spine = new MegaSprite(GetParent().GetParent());
        for (Node? parent = GetParent(); parent != null; parent = parent.GetParent())
            if (parent is NCreature creature) { _owner = creature; break; }
    }

    public override void _Process(double delta)
    {
        _time = -1;
        // SpineBoneNode can inherit both rig and creature scaling. Author the
        // stream thickness in world pixels so it does not collapse into a line.
        _pixel = 1 / Mathf.Max(.01f, GlobalTransform.X.Length());
        using var scope = TrackEntryScope(_spine?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? track);
        if (track != null && track.GetAnimationName() == "cast") _time = track.GetTrackTime();
        _targets.Clear();
        if (_time >= LaunchTime && _time < FinishTime && _owner?.Entity is { IsAlive: true } entity)
        {
            foreach (var player in entity.CombatState?.Players ?? [])
                if (player.Creature.IsAlive && player.Creature.GetCreatureNode() is { } target)
                    _targets.Add(ToLocal(target.VfxSpawnPosition));
            // Standalone native render fixtures have real NCreature siblings but
            // no singleton combat room. Keep their projection identical to play.
            if (_targets.Count == 0 && _owner.GetParent() is { } parent)
                foreach (var node in parent.FindChildren("*", "", true, false).OfType<NCreature>())
                    if (node.Entity is { IsPlayer: true, IsAlive: true }) _targets.Add(ToLocal(node.VfxSpawnPosition));
        }
        QueueRedraw();
    }

    public override void _Draw()
    {
        if (_time < LaunchTime || _time >= FinishTime || _owner?.Entity.IsDead == true) return;
        if (_targets.Count == 0) DrawJet(new Vector2(-2200, 120));
        else foreach (var target in _targets) DrawJet(target);
    }

    private Vector2 Along(Vector2 end, float progress)
    {
        Vector2 vector = end - Mouth;
        Vector2 normal = vector.Normalized().Orthogonal();
        float envelope = Mathf.Sin(progress * Mathf.Pi);
        float arc = -.045f * vector.Length() * envelope;
        float ripple = 3.2f * _pixel * Mathf.Sin(progress * 15 - (_time - LaunchTime) * 22) * envelope;
        return Mouth.Lerp(end, progress) + normal * (arc + ripple);
    }

    private void DrawJet(Vector2 target)
    {
        float lead = Mathf.SmoothStep(0, 1, Mathf.Clamp((_time - LaunchTime) / .14f, 0, 1));
        float tail = Mathf.Clamp((_time - .91f) / .25f, 0, 1);
        float opacity = Mathf.SmoothStep(0, 1, Mathf.Clamp((_time - LaunchTime) / .04f, 0, 1))
            * (1 - Mathf.SmoothStep(0, 1, Mathf.Clamp((_time - 1.01f) / .22f, 0, 1)));
        if (lead <= tail || opacity <= 0) return;
        // At the first/last fractional frame the stream can be shorter than a
        // pixel. Do not submit effectively collapsed geometry to the renderer.
        if (target.DistanceTo(Mouth) * (lead - tail) < .5f * _pixel) return;
        Ribbon(target, tail, lead, 8.5f * _pixel, new Color(.20f, .43f, .50f, .82f * opacity));
        Ribbon(target, tail, lead, 6.4f * _pixel, new Color(.43f, .72f, .82f, .91f * opacity));
        Ribbon(target, tail, lead, 1.7f * _pixel, new Color(.78f, .91f, .92f, .65f * opacity), -2 * _pixel);

        Vector2 direction = (target - Mouth).Normalized();
        Vector2 normal = direction.Orthogonal();
        for (int index = 0; index < 8; index++)
        {
            float age = _time - LaunchTime - index * .055f;
            float travel = age / .31f;
            if (travel <= 0 || travel >= 1) continue;
            Vector2 at = Along(target, travel) + normal * ((index % 2 == 0 ? 1 : -1) * (5 + 14 * travel) * _pixel);
            float radius = (1.9f + (index % 3) * .5f) * _pixel;
            Vector2[] droplet = [at - direction * radius * 1.8f, at + normal * radius * .65f,
                at + direction * radius, at - normal * radius * .65f];
            DrawColoredPolygon(droplet, new Color(.65f, .85f, .89f, opacity * .8f));
        }
    }

    private void Ribbon(Vector2 target, float start, float end, float width, Color color, float offset = 0)
    {
        const int segments = 28;
        Vector2[] polygon = new Vector2[(segments + 1) * 2];
        Vector2 normal = (target - Mouth).Normalized().Orthogonal();
        for (int index = 0; index <= segments; index++)
        {
            float u = index / (float)segments;
            float position = Mathf.Lerp(start, end, u);
            float taper = Mathf.Max(.025f, Mathf.Pow(Mathf.Max(0, Mathf.Sin(u * Mathf.Pi)), .32f));
            float radius = width * (.72f + .28f * Mathf.Sin(position * Mathf.Pi)) * taper;
            Vector2 center = Along(target, position) + normal * offset;
            polygon[index] = center + normal * radius;
            polygon[polygon.Length - 1 - index] = center - normal * radius;
        }
        // The two banks are already a strip. Drawing its convex cells directly
        // avoids ear-clipping a very thin 58-vertex polygon during launch/tail.
        Vector2[] cell = new Vector2[4];
        Color[] colors = [color];
        for (int index = 0; index < segments; index++)
        {
            cell[0] = polygon[index];
            cell[1] = polygon[index + 1];
            cell[2] = polygon[polygon.Length - 2 - index];
            cell[3] = polygon[polygon.Length - 1 - index];
            DrawPrimitive(cell, colors, []);
        }
    }
}
