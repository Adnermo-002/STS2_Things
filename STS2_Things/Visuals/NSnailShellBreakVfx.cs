using Godot;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rooms;

namespace STS2_Things.Visuals;

/// <summary>Eight pieces of the actual painted shell, with no gameplay randomness.</summary>
public partial class NSnailShellBreakVfx : Node2D
{
    private readonly List<(Polygon2D Node, Vector2 Start, Vector2 Velocity, float Spin)> _pieces = [];
    private float _age;

    public static void Play(Creature target)
    {
        var room = NCombatRoom.Instance;
        var visuals = target.GetCreatureNode()?.Visuals as NDepthsSnailVisuals;
        var shell = visuals?.GetNodeOrNull<Sprite2D>("Visuals/ShellSocket/Shell");
        if (room == null || shell?.Texture == null) return;
        var effect = new NSnailShellBreakVfx();
        room.CombatVfxContainer.AddChildSafely(effect);
        Vector2 size = shell.Texture.GetSize(), half = size / 2;
        Vector2[] rim = [Vector2.Zero, new(half.X, 0), new(size.X, 0), new(size.X, half.Y),
            size, new(half.X, size.Y), new(0, size.Y), new(0, half.Y)];
        for (int i = 0; i < rim.Length; i++)
        {
            Vector2[] uv = [half, rim[i], rim[(i + 1) % rim.Length]];
            Vector2 centre = (uv[0] + uv[1] + uv[2]) / 3;
            var piece = new Polygon2D
            {
                Texture = shell.Texture, UV = uv,
                Polygon = uv.Select(v => v - centre).ToArray(),
                Scale = shell.GlobalScale, Rotation = shell.GlobalRotation,
            };
            effect.AddChildSafely(piece);
            piece.GlobalPosition = shell.GlobalPosition + ((centre - half) * shell.GlobalScale).Rotated(shell.GlobalRotation);
            float side = (centre.X / size.X - .5f) * 2;
            effect._pieces.Add((piece, piece.Position, new Vector2(side * 115, -90 - (i % 3) * 24), (i % 2 == 0 ? -1 : 1) * 1.9f));
        }
        visuals!.HideBrokenShell();
    }

    public override void _Process(double delta)
    {
        _age += (float)delta;
        foreach (var (node, start, velocity, spin) in _pieces)
        {
            node.Position = start + velocity * _age + Vector2.Down * (220 * _age * _age);
            node.Rotation += spin * (float)delta;
            node.Modulate = new Color(1, 1, 1, 1 - Mathf.SmoothStep(.28f, .72f, _age));
        }
        if (_age >= .74f) this.QueueFreeSafely();
    }
}
