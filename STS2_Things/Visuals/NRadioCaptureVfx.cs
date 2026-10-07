using Godot;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rooms;

namespace STS2_Things.Visuals;

/// <summary>A sound trace, never a stolen/duplicated gameplay card.</summary>
public partial class NRadioCaptureVfx : Node2D
{
    private Vector2 _start;
    private Node2D? _receiver;
    private Color _color;
    private float _age;
    private readonly List<Vector2> _trail = [];

    public static void Play(CardModel card, Creature actor, Creature receiver, int beat)
    {
        var room = NCombatRoom.Instance;
        var socket = receiver.GetCreatureNode()?.Visuals.GetNodeOrNull<Node2D>($"Visuals/Channel{beat}");
        if (room == null || socket == null) return;
        var from = NCard.FindOnTable(card)?.GlobalPosition ?? actor.GetCreatureNode()?.VfxSpawnPosition;
        if (from == null) return;
        var effect = new NRadioCaptureVfx
        {
            ProcessPriority = 20, _start = from.Value, _receiver = socket,
            _color = RadioColors.ForMask(card.Type == CardType.Attack ? 1 : 2),
        };
        room.CombatVfxContainer.AddChildSafely(effect);
    }

    public override void _Process(double delta)
    {
        if (_receiver == null || !IsInstanceValid(_receiver)) { this.QueueFreeSafely(); return; }
        _age += (float)delta;
        if (_age > .62f) { this.QueueFreeSafely(); return; }
        _trail.Clear();
        float head = Mathf.Clamp(_age / .53f, 0, 1);
        for (int i = 0; i < 13; i++)
        {
            float t = Mathf.Clamp(head - i * .012f, 0, 1);
            float progress = t * t * (3 - 2 * t);
            _trail.Add(ToLocal(_start.Lerp(_receiver.GlobalPosition, progress) + Vector2.Up * (70 * Mathf.Sin(t * Mathf.Pi))));
        }
        QueueRedraw();
    }

    public override void _Draw()
    {
        if (_trail.Count < 2) return;
        float alpha = Math.Min(1, _age / .05f) * (1 - Mathf.SmoothStep(.51f, .62f, _age));
        var color = _color; color.A = .68f * alpha;
        DrawPolyline(_trail.ToArray(), color, 3.8f, true);
        color.A = .9f * alpha;
        Vector2 head = _trail[0];
        DrawArc(head, 6, -.7f, .7f, 10, color, 2, true);
        DrawArc(head, 10, -.7f, .7f, 10, color, 1.4f, true);
    }
}
