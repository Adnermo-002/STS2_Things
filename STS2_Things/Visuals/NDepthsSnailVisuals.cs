using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Nodes.Combat;
using STS2_Things.Monsters;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Visuals;

/// <summary>Painted shells follow a native Spine bone; movement reads the native crawl state.</summary>
[GlobalClass]
public partial class NDepthsSnailVisuals : NCreatureVisuals
{
    private NCreature? _host;
    private Sprite2D? _shell;
    private readonly List<(Node2D Node, Vector2 Origin)> _movingNodes = [];
    private Control? _bounds;
    private Vector2 _boundsOrigin;
    private float _shellAlpha = 1;
    private float _crawlOffset;
    private float _moveFrom;
    private float _moveTo;
    private float _moveElapsed;
    private float _moveDuration = .6f;
    private string? _moveClip;
    private float _moveTrackStart;
    private int? _lastProgress;
    private float? _deathShellAlpha;

    public override void _Ready()
    {
        base._Ready();
        ProcessPriority = 20;
        _shell = GetNodeOrNull<Sprite2D>("Visuals/ShellSocket/Shell");
        foreach (string path in new[] { "Visuals", "ContactShadow", "CenterPos", "IntentPos" })
            if (GetNodeOrNull<Node2D>(path) is { } node) _movingNodes.Add((node, node.Position));
        _bounds = GetNodeOrNull<Control>("Bounds");
        if (_bounds != null) _boundsOrigin = _bounds.Position;
    }

    public void HideBrokenShell()
    {
        _shellAlpha = 0;
        _deathShellAlpha = 0;
        if (_shell != null) _shell.Modulate = new Color(1, 1, 1, 0);
    }

    public override void _Process(double delta)
    {
        base._Process(delta);
        if (_host == null)
            for (Node? node = GetParent(); node != null; node = node.GetParent())
                if (node is NCreature creature) { _host = creature; break; }
        if (_host?.Entity.Monster is not DepthsSnail snail) return;

        string? clip = null;
        float trackTime = 0;
        using (TrackEntryScope(SpineBody?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? entry))
        {
            clip = entry?.GetAnimationName();
            trackTime = entry?.GetTrackTime() ?? 0;
        }
        if (snail is RockSnail rock && _host.Entity.IsAlive)
        {
            int remaining = rock.CrawlsRemaining;
            float target = remaining switch { 0 => -36, 1 => -18, 3 => 12, _ => 0 };
            if (_lastProgress != remaining)
            {
                if (_lastProgress == null) _crawlOffset = target;
                _moveFrom = _crawlOffset;
                _moveTo = target;
                _moveElapsed = 0;
                _moveDuration = clip == "crawl" ? .64f : .42f;
                _moveClip = clip;
                _moveTrackStart = trackTime;
                _lastProgress = remaining;
            }
            _moveElapsed += (float)delta;
            // Respect native fast-mode track jumps, but allow an interrupted
            // gesture to finish moving. Gameplay progress never depends on this.
            if (_moveClip == clip && trackTime >= _moveTrackStart)
                _moveElapsed = Math.Max(_moveElapsed, trackTime - _moveTrackStart);
            _crawlOffset = Mathf.Lerp(_moveFrom, _moveTo, Mathf.SmoothStep(0, _moveDuration, _moveElapsed));
            foreach (var (node, origin) in _movingNodes) node.Position = origin + Vector2.Right * _crawlOffset;
            if (_bounds != null) _bounds.Position = _boundsOrigin + Vector2.Right * _crawlOffset;
        }
        if (_shell == null) return;
        // Native death clears powers before the collapse finishes. Keep an
        // intact shell attached throughout the death pose; a shattered one
        // stays absent because HideBrokenShell already set its alpha to zero.
        if (!_host.Entity.IsAlive || clip == "die") _deathShellAlpha ??= _shellAlpha;
        else _deathShellAlpha = null;
        _shellAlpha = _deathShellAlpha ?? Mathf.MoveToward(_shellAlpha, snail.HasShell ? 1 : 0, (float)delta * 4.5f);
        float lifeAlpha = 1;
        if (clip == "die") lifeAlpha = 1 - Mathf.SmoothStep(1.35f, 1.8f, trackTime);
        else if (clip is "summon" or "revive") lifeAlpha = Mathf.SmoothStep(0, .38f, trackTime);
        float dull = clip == "die" ? Mathf.SmoothStep(.25f, 1.18f, trackTime) : 0;
        _shell.Modulate = new Color(1 - .15f * dull, 1 - .13f * dull, 1 - .11f * dull, _shellAlpha * lifeAlpha);
        _shell.Scale = Vector2.One * Mathf.Lerp(.86f, 1, _shellAlpha);
    }
}
