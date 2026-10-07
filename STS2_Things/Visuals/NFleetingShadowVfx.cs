using Godot;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rooms;

namespace STS2_Things.Visuals;

/// <summary>A painted shadow fragment follows the actual attacker; contains no gameplay state.</summary>
public partial class NFleetingShadowVfx : Node2D
{
    private Sprite2D? _fragment;
    private Creature? _recipient;
    private Vector2 _start;
    private float _time;

    public static void Play(Creature source, Creature recipient)
    {
        if (NCombatRoom.Instance is not { } room || source.GetCreatureNode() is not { } from ||
            recipient.GetCreatureNode() == null) return;
        var effect = new NFleetingShadowVfx
        {
            _recipient = recipient, _start = from.VfxSpawnPosition,
            _fragment = new Sprite2D { Texture = GD.Load<Texture2D>("res://images/vfx/fleeting_shadow.png") }
        };
        room.CombatVfxContainer.AddChildSafely(effect);
        effect.AddChildSafely(effect._fragment);
        effect.GlobalPosition = effect._start;
    }

    public override void _Process(double delta)
    {
        if (_fragment == null || _recipient?.GetCreatureNode() is not { } target)
        { this.QueueFreeSafely(); return; }
        _time += (float)delta;
        float t = Mathf.Clamp(_time / .46f, 0, 1);
        float u = t * t * (3 - 2 * t);
        GlobalPosition = _start.Lerp(target.VfxSpawnPosition, u) + Vector2.Up * (62 * Mathf.Sin(t * Mathf.Pi));
        _fragment.Rotation = -.3f + .6f * t;
        _fragment.Scale = Vector2.One * (1 - .5f * t);
        _fragment.Modulate = new Color(1, 1, 1, Mathf.SmoothStep(0, .10f, t) * (1 - Mathf.SmoothStep(.76f, 1, t)));
        if (t >= 1) this.QueueFreeSafely();
    }
}
