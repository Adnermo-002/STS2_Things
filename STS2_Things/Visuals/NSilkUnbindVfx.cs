using Godot;
using MegaCrit.Sts2.Core.Assets;

namespace STS2_Things.Visuals;

/// <summary>Let the same masked material dissolve after its affliction is cleared.</summary>
public partial class NSilkUnbindVfx : Control
{
    private float _age;
    public override void _Ready()
    {
        MouseFilter = MouseFilterEnum.Ignore;
        ProcessMode = ProcessModeEnum.Always;
        var effect = PreloadManager.Cache.GetScene(NSilkCardOverlay.EffectScenePath).Instantiate<Control>();
        AddChild(effect);
        effect.GetNode<AnimationPlayer>("AnimationPlayer").Play("release");
    }
    public override void _Process(double delta)
    {
        _age += (float)delta;
        if (_age > .55f) QueueFree();
    }
}
