using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Nodes.Combat;
using STS2_Things.Monsters;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Visuals;

/// <summary>Native Spine cylinder turns, column fall motion and unobstructed side UI.</summary>
[GlobalClass]
public partial class NHumanFaceColumnVisuals : NCreatureVisuals
{
    private NCreature? _host;
    private Node2D? _sprite;
    private Node2D? _shadow;
    private Control? _uiBounds;
    private Control? _intents;
    private NCreatureStateDisplay? _stateDisplay;
    private Control? _nameplate;
    private readonly List<Node2D> _reserveSprites = [];
    private Tween? _dropTween;
    private Vector2? _motionTarget;
    private string _rotation = "";
    private (string Clip, float Time)? _incomingPose;
    private IReadOnlyList<(string Clip, float Time)?>? _reserveStartPoses;
    private bool _entryStarted;
    private float _rotationSpeed = 1;
    private const float RotationDuration = 12f;

    public override void _Ready()
    {
        base._Ready();
        ProcessPriority = 30;
        _sprite = GetNode<Node2D>("Visuals");
        _shadow = GetNode<Node2D>("ContactShadow");
    }

    public override void _Process(double delta)
    {
        base._Process(delta);
        FindHost();
        if (_host?.Entity.Monster is not HumanFaceColumn column || _sprite == null) return;
        // The upper disc covers the lower disc's top plane at the contact seam.
        _host.ZIndex = 2 * column.Level;
        if (_shadow != null) _shadow.Visible = column.Level == 0 && _host.Entity.IsAlive;
        if (!_host.Entity.IsAlive)
        {
            ClearReserves();
            // Track 1 controls rotation; parent modulation fades every track,
            // including stone fragments, after the authored shatter motion.
            using (TrackEntryScope(SpineBody?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? death))
                if (death?.GetAnimationName() == "die")
                    _sprite.Modulate = new Color(1, 1, 1, 1 - Mathf.SmoothStep(.55f, 1.05f, death.GetTrackTime()));
            return;
        }

        string rotation = column.Level == 1 ? "rotate_ccw" : "rotate_cw";
        var state = SpineBody?.TryGetAnimationState();
        if (state != null && rotation != _rotation)
        {
            float phase = column.Level > 0 ? 4f : 0f;
            using (TrackEntryScope(state.GetCurrent(1), out MegaTrackEntry? previous))
                if (previous != null) phase = ReversePhase(previous.GetTrackTime());
            if (_incomingPose is { } incoming)
                phase = incoming.Clip == rotation ? incoming.Time % RotationDuration : ReversePhase(incoming.Time);
            state.SetAnimation(rotation, true, 1);
            using (TrackEntryScope(state.GetCurrent(1), out MegaTrackEntry? next))
            {
                next?.SetTrackTime(phase);
                next?.SetMixDuration(.22f);
            }
            _rotation = rotation;
            _incomingPose = null;
        }
        _rotationSpeed = Mathf.MoveToward(_rotationSpeed, column.IsDizzy ? .12f : 1,
            (float)delta * 2.4f);
        using (TrackEntryScope(state?.GetCurrent(1), out MegaTrackEntry? track)) track?.SetTimeScale(_rotationSpeed);
        UpdateReserves(column);

        UpdateSideUi();
    }

    private void UpdateSideUi()
    {
        if (_host == null) return;
        if (_uiBounds == null)
        {
            _stateDisplay = _host.GetNode<NCreatureStateDisplay>("%HealthBar");
            _nameplate = _stateDisplay.GetNode<Control>("%NameplateContainer");
            // Native encounters can scale each copy of a monster differently.
            // Share the creature's coordinate space with Intents so these UI
            // rows stay aligned, independent of the stone's visual scale.
            _uiBounds = new Control
            {
                Name = "ColumnUiBounds",
                Position = new Vector2(-426, -HumanFaceColumn.LayerSpacing * .5f - 22),
                Size = new Vector2(184, 74),
                MouseFilter = Control.MouseFilterEnum.Ignore,
            };
            _host.AddChild(_uiBounds);
            // Preserve the state display's native show/hide tween on its root.
            foreach (var child in _stateDisplay.GetChildren().OfType<Control>())
                child.Position += Vector2.Up * (HumanFaceColumn.LayerSpacing * .5f + 9);
            _stateDisplay.SetCreatureBounds(_uiBounds);
            _intents = _host.IntentContainer;
            _intents.Resized += AlignIntents;
        }

        // UpdateBounds can restore the native layout after initialization.
        // Only reapply when displaced; repeatedly refreshing the health bar
        // would interfere with its damage/block animations.
        if (_stateDisplay != null && _nameplate != null &&
            (!Mathf.IsEqualApprox(_nameplate.GlobalPosition.X, _uiBounds.GlobalPosition.X) ||
             !Mathf.IsEqualApprox(_nameplate.Size.X, _uiBounds.Size.X)))
            _stateDisplay.SetCreatureBounds(_uiBounds);
        AlignIntents();
    }

    private void AlignIntents()
    {
        if (_intents == null || _uiBounds == null) return;
        var center = new Vector2(_uiBounds.Position.X + _uiBounds.Size.X * .5f,
            -HumanFaceColumn.LayerSpacing * .5f - 55);
        // Native UpdateBounds runs before the first 64px intent expands the
        // initially 40px HBox. Recenter using its settled size, including after
        // replacement/stun, without changing NIntent's own bob or fade.
        _intents.Position = center - _intents.Size * .5f;
    }

    private void FindHost()
    {
        if (_host != null) return;
        for (Node? node = GetParent(); node != null; node = node.GetParent())
            if (node is NCreature creature) { _host = creature; break; }
    }

    private void UpdateReserves(HumanFaceColumn column)
    {
        int count = column.IsTopVisible ? column.ReserveLayers : 0;
        while (_reserveSprites.Count > count)
        {
            var last = _reserveSprites[^1];
            last.Visible = false;
            last.QueueFree();
            _reserveSprites.RemoveAt(_reserveSprites.Count - 1);
        }
        while (_reserveSprites.Count < count && _sprite != null)
        {
            int i = _reserveSprites.Count;
            var copy = (Node2D)_sprite.Duplicate();
            copy.Name = "ReserveDisc" + i;
            copy.Position = Vector2.Up * HumanFaceColumn.LayerSpacing * (i + 1);
            copy.Modulate = ReserveTint(i);
            copy.ZIndex = 5 + i;
            AddChild(copy);
            using Variant stateValue = copy.Call("get_animation_state");
            var rawState = stateValue.AsGodotObject();
            string name = (i + column.Level + 1) % 2 == 1 ? "rotate_ccw" : "rotate_cw";
            using Variant ignored = rawState.Call("set_animation", name, true, 1);
            if (_reserveStartPoses != null && i < _reserveStartPoses.Count && _reserveStartPoses[i] is { } pose)
            {
                using Variant trackValue = rawState.Call("get_current", 1);
                using (TrackEntryScope(new MegaTrackEntry(trackValue), out MegaTrackEntry? entry))
                {
                    entry?.SetTrackTime(pose.Clip == name ? pose.Time % RotationDuration : ReversePhase(pose.Time));
                    entry?.SetMixDuration(0);
                }
            }
            _reserveSprites.Add(copy);
        }
    }

    private static Color ReserveTint(int index)
    {
        // These are solid stone reserves. Darken RGB, never their opacity.
        float shade = Math.Max(.35f, .76f - .13f * index);
        return new Color(shade * .94f, shade, shade * .96f, 1);
    }

    private void ClearReserves()
    {
        foreach (var node in _reserveSprites) { node.Visible = false; node.QueueFree(); }
        _reserveSprites.Clear();
    }

    private static float ReversePhase(float time)
    {
        time = (time % RotationDuration + RotationDuration) % RotationDuration;
        float local = time % 4f;
        float turn = MathF.Floor(time / 4f) + Mathf.SmoothStep(1.1f, 2.75f, local);
        float reversed = (3 - turn) % 3;
        float whole = MathF.Floor(reversed), fraction = reversed - whole;
        if (fraction < .0001f) return whole * 4 + .55f;
        float low = 0, high = 1;
        for (int i = 0; i < 18; i++)
        {
            float middle = (low + high) * .5f;
            if (middle * middle * (3 - 2 * middle) < fraction) low = middle;
            else high = middle;
        }
        return whole * 4 + 1.1f + (low + high) * .825f;
    }

    public static (string Clip, float Time)? IncomingPose(Creature? top, int reserveIndex = 0)
    {
        if (top?.GetCreatureNode()?.Visuals is not NHumanFaceColumnVisuals visuals || visuals._reserveSprites.Count <= reserveIndex)
            return null;
        var reserve = visuals._reserveSprites[reserveIndex];
        using Variant stateValue = reserve.Call("get_animation_state");
        using Variant trackValue = stateValue.AsGodotObject().Call("get_current", 1);
        var track = trackValue.AsGodotObject();
        if (track == null) return null;
        // Read through the shared wrapper to keep both supported APIs aligned.
        using (TrackEntryScope(new MegaTrackEntry(trackValue), out MegaTrackEntry? entry))
            return entry == null ? null : (entry.GetAnimationName(), entry.GetTrackTime());
    }

    public static void Drop(Creature creature, int levels)
    {
        if (creature.GetCreatureNode()?.Visuals is NHumanFaceColumnVisuals visuals)
            visuals.AnimateDrop(levels, entering: false);
    }

    public static void RestoreReservePoses(Creature? top, IReadOnlyList<(string Clip, float Time)?> poses)
    {
        if (top?.GetCreatureNode()?.Visuals is NHumanFaceColumnVisuals visuals)
        {
            visuals.ClearReserves();
            visuals._reserveStartPoses = poses;
        }
    }

    public static void DropIn(Creature creature, (string Clip, float Time)? incomingPose = null, int levels = 1, int reserveIndex = 0)
    {
        if (creature.GetCreatureNode()?.Visuals is NHumanFaceColumnVisuals visuals)
        {
            visuals._incomingPose = incomingPose;
            visuals._rotation = "";
            visuals.AnimateDrop(levels, entering: true, reserveIndex);
        }
    }

    private void AnimateDrop(int levels, bool entering, int reserveIndex = 0)
    {
        FindHost();
        if (_host == null) return;
        if (entering && _entryStarted) return;
        if (entering) _entryStarted = true;
        _dropTween?.Kill();
        float distance = levels * HumanFaceColumn.LayerSpacing;
        Vector2 target;
        if (entering)
        {
            target = _host.Position;
            _host.Position -= Vector2.Down * distance;
        }
        else target = (_motionTarget ?? _host.Position) + Vector2.Down * distance;
        _motionTarget = target;
        _dropTween = CreateTween();
        _dropTween.TweenProperty(_host, "position", target, .32 * Math.Sqrt(levels)).SetTrans(Tween.TransitionType.Quad).SetEase(Tween.EaseType.In);
        if (entering && _sprite != null)
        {
            _sprite.Modulate = ReserveTint(reserveIndex);
            _dropTween.Parallel().TweenProperty(_sprite, "modulate", Colors.White, .32 * Math.Sqrt(levels));
        }
        _dropTween.TweenProperty(_host, "position", target + Vector2.Right * 3, .10).SetTrans(Tween.TransitionType.Quad).SetEase(Tween.EaseType.Out);
        _dropTween.TweenProperty(_host, "position", target, .13).SetTrans(Tween.TransitionType.Sine).SetEase(Tween.EaseType.Out);
    }

    public override void _ExitTree()
    {
        if (GodotObject.IsInstanceValid(_intents)) _intents!.Resized -= AlignIntents;
        _dropTween?.Kill();
        base._ExitTree();
    }
}
