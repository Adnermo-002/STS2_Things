using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Nodes.Combat;
using STS2_Things.Monsters;
using STS2_Things.Powers;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Visuals;

internal static class RadioColors
{
    public static Color ForMask(int mask) => mask switch
    {
        1 => new Color("e6a078"),
        2 => new Color("83d1d2"),
        3 => new Color("c8a7e0"),
        _ => new Color("847d69"),
    };
}

/// <summary>Two physical glass chambers display the merged programme.</summary>
[GlobalClass]
public partial class NRadioJellyfishVisuals : NCreatureVisuals
{
    private NCreature? _host;
    private Sprite2D? _first;
    private Sprite2D? _second;
    private int _revision = -1;
    private float _capturePulse;

    public override void _Ready()
    {
        base._Ready();
        ProcessPriority = 20;
        _first = GetNode<Sprite2D>("Visuals/Channel0/Light");
        _second = GetNode<Sprite2D>("Visuals/Channel1/Light");
    }

    public override void _Process(double delta)
    {
        base._Process(delta);
        if (_host == null)
            for (Node? p = GetParent(); p != null; p = p.GetParent())
                if (p is NCreature creature) { _host = creature; break; }
        if (_host?.Entity.Monster is not RadioJellyfish jelly || _first == null || _second == null) return;
        var receiver = _host.Entity.GetPower<RadioReceptionPower>();
        if (receiver != null && receiver.Revision != _revision)
        {
            _capturePulse = _revision < 0 ? 0 : 1;
            _revision = receiver.Revision;
        }
        _capturePulse = Mathf.MoveToward(_capturePulse, 0, (float)delta * 2.8f);
        var program = jelly.CurrentProgram;
        float time = -1;
        float tuningTime = -1;
        using (TrackEntryScope(SpineBody?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? entry))
        {
            if (entry?.GetAnimationName().StartsWith("playback_", StringComparison.Ordinal) == true)
                time = entry.GetTrackTime();
            else if (entry?.GetAnimationName() == "power_up")
                tuningTime = entry.GetTrackTime();
        }
        if (tuningTime >= 0)
        {
            // Both chambers brighten with the existing, native power-up pose.
            SetLight(_first, 3, tuningTime, .50f);
            SetLight(_second, 3, tuningTime, .50f);
            return;
        }
        SetLight(_first, program.First.Mask, time, .50f);
        SetLight(_second, program.Second.Mask, time, 1.00f);
    }

    private void SetLight(Sprite2D light, int mask, float time, float release)
    {
        float flash = time >= 0 ? Math.Max(0, 1 - Math.Abs(time - release) / .19f) : 0;
        Color color = RadioColors.ForMask(mask);
        color.A = mask == 0 ? 0 : .68f + .18f * _capturePulse + .14f * flash;
        light.Modulate = color;
    }
}
