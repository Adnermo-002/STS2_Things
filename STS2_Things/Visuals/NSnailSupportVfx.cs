using Godot;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rooms;

namespace STS2_Things.Visuals;

/// <summary>A short, matte droplet arc links the animated mouth to its recipient.</summary>
public partial class NSnailSupportVfx : Node2D
{
    private Vector2 _from;
    private Vector2 _to;
    private bool _repair;
    private float _age;

    public static void Play(Creature actor, Creature target, bool repair)
    {
        var room = NCombatRoom.Instance;
        var mouth = actor.GetCreatureNode()?.Visuals.GetNodeOrNull<Node2D>("Visuals/MouthSocket");
        var recipient = target.GetCreatureNode();
        if (room == null || mouth == null || recipient == null) return;
        var shell = recipient.Visuals.GetNodeOrNull<Node2D>("Visuals/ShellSocket");
        var effect = new NSnailSupportVfx
        {
            _from = mouth.GlobalPosition,
            _to = repair && shell != null ? shell.GlobalPosition : recipient.VfxSpawnPosition,
            _repair = repair,
        };
        room.CombatVfxContainer.AddChildSafely(effect);
    }

    public override void _Process(double delta)
    {
        _age += (float)delta;
        if (_age > .69f) { this.QueueFreeSafely(); return; }
        QueueRedraw();
    }

    public override void _Draw()
    {
        Color dark = new("467e73"), light = new(_repair ? "b7dbb5" : "9ccfb3");
        float alpha = 1 - Mathf.SmoothStep(.49f, .68f, _age);
        for (int i = 3; i >= 0; i--)
        {
            float t = Mathf.Clamp((_age - i * .029f) / .47f, 0, 1);
            if (t <= 0 || t >= 1) continue;
            Vector2 p = ToLocal(_from.Lerp(_to, t) + Vector2.Up * (70 * Mathf.Sin(t * Mathf.Pi)));
            float radius = 6 - i * .9f;
            dark.A = alpha; light.A = alpha;
            DrawCircle(p, radius + 1, dark);
            DrawCircle(p + new Vector2(-1, -1), radius, light);
        }
        float splash = Mathf.Clamp((_age - .43f) / .25f, 0, 1);
        if (splash <= 0) return;
        light.A = (1 - splash) * .8f;
        for (int i = 0; i < 5; i++)
            DrawCircle(ToLocal(_to) + Vector2.FromAngle(i * Mathf.Tau / 5) * (5 + 19 * splash), 3 * (1 - splash), light);
    }
}
