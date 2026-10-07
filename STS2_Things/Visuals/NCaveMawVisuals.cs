using Godot;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Nodes.Combat;

namespace STS2_Things.Visuals;

/// <summary>The well-fed rim visibly broadens around its fixed floor origin.</summary>
[GlobalClass]
public partial class NCaveMawVisuals : NCreatureVisuals
{
    private NCreature? _host;
    private Node2D? _body;
    private Vector2 _baseScale;
    public override void _Ready()
    {
        base._Ready();
        _body = GetNode<Node2D>("Visuals");
        _baseScale = _body.Scale;
    }
    public override void _Process(double delta)
    {
        base._Process(delta);
        if (_body == null) return;
        if (_host == null)
            for (Node? p = GetParent(); p != null; p = p.GetParent())
                if (p is NCreature creature) { _host = creature; break; }
        float fullness = Math.Clamp((_host?.Entity.GetPower<StrengthPower>()?.Amount ?? 0) / 9f, 0, 1);
        Vector2 target = _baseScale * new Vector2(1 + fullness * .10f, 1 + fullness * .08f);
        _body.Scale = _body.Scale.Lerp(target, 1 - Mathf.Exp(-(float)delta * 5));
    }
}
