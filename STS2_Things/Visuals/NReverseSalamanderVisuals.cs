using Godot;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Nodes.Combat;

namespace STS2_Things.Visuals;

[GlobalClass]
public partial class NReverseSalamanderVisuals : NCreatureVisuals
{
    private NCreature? _host;
    private ShaderMaterial? _flow;
    private float _vigor;
    public override void _Ready()
    {
        base._Ready();
        _flow=(ShaderMaterial)GD.Load<ShaderMaterial>("res://materials/monsters/reverse_current.tres").Duplicate(true);
        SpineBody?.SetNormalMaterial(_flow);
    }
    public override void _Process(double delta)
    {
        base._Process(delta);
        if(_host==null)for(Node? p=GetParent();p!=null;p=p.GetParent())if(p is NCreature creature){_host=creature;break;}
        float strength=Math.Clamp((_host?.Entity.GetPower<StrengthPower>()?.Amount??0)/12f,0,1);
        _vigor=Mathf.Lerp(_vigor,strength,1-Mathf.Exp(-(float)delta*5));
        _flow?.SetShaderParameter("vigor",_vigor);
    }
}
