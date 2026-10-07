using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Visuals;

/// <summary>
/// Lets each whip recover into the following windup while native damage hooks
/// finish. A long multiplayer power application cannot play the next hit early.
/// Uncontrolled animation previews play the complete clip without waiting.
/// </summary>
[GlobalClass]
public partial class NThingsScaleBeetleMotion : Node
{
    private MegaSprite? _sprite;
    private int _allowedBeat;
    private bool _controlled;

    public override void _Ready()
    {
        if (GetParent() is not Node2D sprite) return;
        _sprite = new MegaSprite(sprite);
        _sprite.ConnectAnimationStarted(Callable.From<GodotObject, GodotObject, GodotObject>(
            (_, _, _) => { _controlled = false; _allowedBeat = 0; }));
        _sprite.ConnectAnimationEvent(Callable.From<GodotObject, GodotObject, GodotObject, GodotObject>(OnEvent));
    }

    public void AllowBeat(int beat)
    {
        _controlled = true;
        _allowedBeat = beat;
        SetWhipSpeed(1f);
    }

    public void FinishCombo()
    {
        _controlled = false;
        SetWhipSpeed(1f);
    }

    public override void _ExitTree()
    {
        _controlled = false;
        _sprite = null;
    }

    private void OnEvent(GodotObject _, GodotObject __, GodotObject ___, GodotObject spineEvent)
    {
        if (!_controlled) return;
        string name = new MegaEvent(spineEvent).GetData().GetEventName();
        int nextBeat = name switch { "whip_ready_second" => 2, "whip_ready_third" => 3, _ => 0 };
        if (nextBeat > _allowedBeat) SetWhipSpeed(0f);
    }

    private void SetWhipSpeed(float speed)
    {
        using var scope = TrackEntryScope(_sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? track);
        // A hit reaction or death takes precedence over the interrupted combo.
        if (track != null && track.GetAnimationName() == "whip") track.SetTimeScale(speed);
    }
}
