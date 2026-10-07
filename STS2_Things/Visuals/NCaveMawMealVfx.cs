using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Visuals;

/// <summary>Native card visuals follow the animated throat; no card/pile state lives here.</summary>
public partial class NCaveMawMealVfx : Node2D
{
    private NCard? _card;
    private Node2D? _mouth;
    private Vector2 _start;
    private float _age;
    private float _delay;
    private MegaSprite? _spine;
    private float _launchTime;
    private bool _followsDevour;

    public static Vector2 GetCardOrigin(CardModel card)
    {
        if (NCard.FindOnTable(card) is { } node) return node.GlobalPosition;
        if (NCombatRoom.Instance?.Ui is { } ui) return ui.DiscardPile.GetGlobalRect().GetCenter();
        return card.Owner.Creature.GetCreatureNode()?.VfxSpawnPosition ?? Vector2.Zero;
    }

    public static void Play(CardModel card, Creature maw, Vector2 start, float delay)
    {
        var room = NCombatRoom.Instance;
        var creature = maw.GetCreatureNode();
        var mouth = creature?.Visuals.GetNodeOrNull<Node2D>("Visuals/MouthSocket");
        if (room == null || mouth == null) return;
        var visual = NCard.Create(card);
        if (visual == null) return;
        var effect = new NCaveMawMealVfx
        {
            ProcessPriority = 20,
            _card = visual, _mouth = mouth, _start = start, _delay = delay,
            _spine = creature?.Visuals.SpineBody,
        };
        using (TrackEntryScope(effect._spine?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? entry))
        {
            effect._followsDevour = entry?.GetAnimationName() == "devour";
            effect._launchTime = entry?.GetTrackTime() ?? 0;
        }
        room.CombatVfxContainer.AddChildSafely(effect);
        effect.AddChildSafely(visual);
        visual.UpdateVisuals(PileType.None, CardPreviewMode.Normal);
        visual.MouseFilter = Control.MouseFilterEnum.Ignore;
        visual.GlobalPosition = start;
        visual.Scale = Vector2.One * .32f;
    }

    public override void _Process(double delta)
    {
        if (_card == null || !IsInstanceValid(_card) || _mouth == null || !IsInstanceValid(_mouth))
        { Finish(); return; }
        _age += (float)delta;
        // Follow native clip jumps in fast combat mode. A stopped/interrupted
        // clip still lets its visual finish, without holding gameplay on a tween.
        if (_followsDevour)
        {
            using var scope = TrackEntryScope(_spine?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? entry);
            if (entry?.GetAnimationName() == "devour")
                _age = Math.Max(_age, entry.GetTrackTime() - _launchTime);
            else if (entry?.GetAnimationName() == "idle_loop")
                _age = Math.Max(_age, .62f + _delay);
        }
        float t = Mathf.Clamp((_age - _delay) / .62f, 0, 1);
        float travel = t * t * (3 - 2 * t);
        _card.GlobalPosition = _start.Lerp(_mouth.GlobalPosition, travel) + Vector2.Up * (90 * Mathf.Sin(t * Mathf.Pi));
        _card.Scale = Vector2.One * Mathf.Lerp(.32f, .025f, t);
        _card.Rotation = -.25f * Mathf.Sin(t * Mathf.Pi) + .35f * t;
        _card.Modulate = new Color(1, 1, 1, 1 - Mathf.SmoothStep(.78f, 1, t));
        if (t >= 1) Finish();
    }

    private void Finish()
    {
        if (_card != null && IsInstanceValid(_card)) _card.QueueFreeSafely();
        _card = null;
        this.QueueFreeSafely();
    }

    public override void _ExitTree()
    {
        if (_card != null && IsInstanceValid(_card)) _card.QueueFreeSafely();
        _card = null;
    }
}
