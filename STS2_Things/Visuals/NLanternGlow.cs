using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Visuals;

/// <summary>A single warm flare attached to the animated lamp bone, with no screen strobe.</summary>
public partial class NLanternGlow : ColorRect
{
    private MegaSprite? _spine;
    private ShaderMaterial? _shader;
    public override void _Ready()
    {
        _spine = new MegaSprite(GetParent().GetParent());
        _shader = (ShaderMaterial?)Material;
        Material = _shader = (ShaderMaterial?)_shader?.Duplicate();
    }

    public override void _Process(double delta)
    {
        float glow = .08f;
        using var scope = TrackEntryScope(_spine?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? track);
        if (track != null)
        {
            string name = track.GetAnimationName();
            float t = track.GetTrackTime();
            if (name == "cast" || name == "power_up")
            {
                if (name == "power_up") t *= 1.8f / 1.6f;
                glow += .92f * Mathf.SmoothStep(.44f, .72f, t) * (1 - Mathf.SmoothStep(.94f, 1.4f, t));
            }
            else if (name == "die") glow *= 1 - Mathf.SmoothStep(0, 1.2f, t);
            else if (name == "guard") glow *= .3f;
        }
        _shader?.SetShaderParameter("intensity", glow);
    }
}
