using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;

namespace STS2_Things.Visuals;

/// <summary>
/// Origin Fogmog spore VFX (tools/OriginFogmogRig v3). Same contract as the vanilla
/// NFogmogVfx: Spine events <c>thrust_start</c>/<c>thrust_end</c> restart/stop the cap spore
/// jet (summon, cast); <c>ground_impact</c> emits the landing dust separately.
/// <c>spores_start</c>/<c>spores_end</c> drive the power_up exhale.
/// The particle nodes are SpineSlotNodes under %Visuals.
/// </summary>
[GlobalClass]
public partial class NThingsFogmogVfx : Node
{
    private GpuParticles2D? _thrustParticles;
    private GpuParticles2D? _dustLeftParticles;
    private GpuParticles2D? _dustRightParticles;
    private MegaSprite? _megaSprite;

    public override void _Ready()
    {
        _thrustParticles = GetNodeOrNull<GpuParticles2D>("../ThrustSlotNode/ThrustParticles");
        _dustLeftParticles = GetNodeOrNull<GpuParticles2D>("../DustSlotNode/DustLeftParticles");
        _dustRightParticles = GetNodeOrNull<GpuParticles2D>("../DustSlotNode/DustRightParticles");
        StopAll();
        if (GetParent() is not Node2D spineSprite)
            return;
        _megaSprite = new MegaSprite(spineSprite);
        _megaSprite.ConnectAnimationStarted(
            Callable.From<GodotObject, GodotObject, GodotObject>((_, _, _) => StopAll()));
        _megaSprite.ConnectAnimationEvent(
            Callable.From<GodotObject, GodotObject, GodotObject, GodotObject>(OnAnimationEvent));
    }

    public override void _ExitTree() => StopAll();

    private void OnAnimationEvent(GodotObject _, GodotObject __, GodotObject ___, GodotObject spineEvent)
    {
        string eventName = new MegaEvent(spineEvent).GetData().GetEventName();
        switch (eventName)
        {
            case "thrust_start":
                _thrustParticles?.Restart();
                break;
            case "ground_impact":
                _dustLeftParticles?.Restart();
                _dustRightParticles?.Restart();
                break;
            case "thrust_end":
                StopAll();
                break;
            case "spores_start":
                _thrustParticles?.Restart();
                break;
            case "spores_end":
                if (_thrustParticles != null)
                    _thrustParticles.Emitting = false;
                break;
        }
    }

    private void StopAll()
    {
        if (_thrustParticles != null)
            _thrustParticles.Emitting = false;
        if (_dustLeftParticles != null)
            _dustLeftParticles.Emitting = false;
        if (_dustRightParticles != null)
            _dustRightParticles.Emitting = false;
    }
}
