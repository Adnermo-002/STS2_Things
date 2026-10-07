using Godot;
using MegaCrit.Sts2.Core.Nodes.Combat;
using STS2_Things.Monsters;

namespace STS2_Things.Visuals;

[GlobalClass]
public partial class NMycorrhizalVisuals : NCreatureVisuals
{
    private NCreature? _host;
    private Node2D? _sprite;
    private Vector2 _scale;
    private float _fury;
    private float _form;
    private string _pose = "";
    public override void _Ready()
    {
        base._Ready();_sprite=GetNode<Node2D>("Visuals");_scale=_sprite.Scale;
    }
    public override void _Process(double delta)
    {
        base._Process(delta);
        if(_sprite==null)return;
        if(_host==null)for(Node? p=GetParent();p!=null;p=p.GetParent())if(p is NCreature n){_host=n;break;}
        float target=_host?.Entity?.Monster is MycorrhizalTwin { IsFurious:true }?1:0;
        _fury=Mathf.MoveToward(_fury,target,(float)delta*2.5f);
        bool robust=_host?.Entity?.Monster is MycorrhizalTwin { IsRobust:true };
        _form=Mathf.MoveToward(_form,robust?1:-1,(float)delta*2.5f);
        _sprite.Scale=_scale*new Vector2(1+.14f*_form+.04f*_fury,1+.085f*_form+.035f*_fury);
        Color formColor=Colors.White.Lerp(new Color(.78f,.83f,.76f),Mathf.Max(0,-_form)*.65f);
        _sprite.SelfModulate=formColor.Lerp(new Color(1,.78f,.65f),_fury*.65f);
        string pose=robust?"robust":"withered";
        if(_pose!=pose)
        {
            _pose=pose;
            var state=_sprite.Call("get_animation_state").AsGodotObject();
            state.Call("set_animation",pose,true,1);
        }
    }
}
