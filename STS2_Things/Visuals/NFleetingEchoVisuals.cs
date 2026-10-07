using Godot;
using MegaCrit.Sts2.Core.Nodes.Combat;
using STS2_Things.Monsters;
using STS2_Things.Powers;

namespace STS2_Things.Visuals;

[GlobalClass]
public partial class NFleetingEchoVisuals : NCreatureVisuals
{
    private NCreature? _host;
    private ShaderMaterial? _material;
    public override void _Ready()
    {
        base._Ready();
        var sprite = GetNode<Node2D>("Visuals");
        // Own a local material: another enemy or a preview must not share its
        // countdown. The shader only changes the painted edge, not its hitbox.
        if (sprite.Material is ShaderMaterial source)
            sprite.Material = _material = (ShaderMaterial)source.Duplicate();
    }

    public override void _Process(double delta)
    {
        base._Process(delta);
        if (_material == null) return;
        if (_host == null)
            for (Node? p = GetParent(); p != null; p = p.GetParent())
                if (p is NCreature creature) { _host = creature; break; }
        if (_host?.Entity is not { IsAlive: true } entity) return;
        int remaining = entity.GetPower<FleetingFadePower>()?.Amount ?? FleetingEcho.Lifetime;
        _material.SetShaderParameter("erosion", (FleetingEcho.Lifetime - remaining) * .055f);
    }
}
