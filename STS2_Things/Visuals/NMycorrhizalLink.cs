using Godot;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Nodes.Combat;
using STS2_Things.Monsters;

namespace STS2_Things.Visuals;

/// <summary>A painted, flexible rhizome attached to the two animated root feet.</summary>
[GlobalClass]
public partial class NMycorrhizalLink : Node2D
{
    public const string TexturePath = "res://images/vfx/mycorrhizal_root.png";
    private static readonly Dictionary<Creature,NMycorrhizalLink> Instances = [];
    private NCreature? _host;
    private Line2D? _root, _shadow;
    private Texture2D? _mote;
    private Vector2[] _points = [];
    private float _age, _pulse = -1, _visibility;
    private bool _connected;
    public bool HasPartner => _connected;

    public static void Pulse(Creature first, Creature second)
    {
        if(Instances.TryGetValue(first,out var link)&&IsInstanceValid(link))link._pulse=0;
    }

    public override void _Ready()
    {
        // Run after Spine and the creature's form update, not one pose behind.
        ProcessPriority=20;
        var texture=GD.Load<Texture2D>(TexturePath);
        _mote=GD.Load<Texture2D>("res://images/vfx/dot.png");
        _shadow=MakeLine("RootShadow",texture,27,new Color(.07f,.08f,.045f,.24f));
        _root=MakeLine("PaintedRoot",texture,24,Colors.White);
        AddChild(_shadow);AddChild(_root);
    }

    private static Line2D MakeLine(string name,Texture2D texture,float width,Color color) => new()
    {
        Name=name,Texture=texture,TextureMode=Line2D.LineTextureMode.Stretch,
        Width=width,DefaultColor=color,Antialiased=true,
        JointMode=Line2D.LineJointMode.Round,RoundPrecision=8,
        TextureFilter=TextureFilterEnum.Linear,
    };

    public override void _ExitTree()
    {
        if(_host?.Entity is { } entity&&Instances.GetValueOrDefault(entity)==this)Instances.Remove(entity);
    }

    public override void _Process(double delta)
    {
        if(_root==null||_shadow==null)return;
        if(_host==null)
        {
            for(Node? p=GetParent();p!=null;p=p.GetParent())if(p is NCreature n){_host=n;break;}
            if(_host?.Entity.Monster is MycorrhizalVanguard)Instances[_host.Entity]=this;
        }
        if(_host?.Entity.Monster is not MycorrhizalVanguard twin){Visible=false;return;}
        _age+=(float)delta;
        if(_pulse>=0){_pulse+=(float)delta;if(_pulse>1.15f)_pulse=-1;}
        var peer=twin.Partner?.Creature;
        var other=peer?.GetCreatureNode()??_host.GetParent().GetChildren().OfType<NCreature>().FirstOrDefault(n=>n.Entity==peer);
        var from=_host.Visuals.GetNodeOrNull<Node2D>("Visuals/RootSocket");
        var to=other?.Visuals.GetNodeOrNull<Node2D>("Visuals/RootSocket");
        _connected=from!=null&&to!=null&&_host.Entity.IsAlive&&peer?.IsAlive==true;
        if(_connected)
        {
            Vector2 start=ToLocal(from!.GlobalPosition),end=ToLocal(to!.GlobalPosition);
            _points=new Vector2[49];
            for(int i=0;i<_points.Length;i++)
            {
                float t=i/(float)(_points.Length-1),envelope=Mathf.Sin(t*Mathf.Pi);
                float breath=Mathf.Sin(_age*1.8f-t*4)*1.15f;
                _points[i]=start.Lerp(end,t)+new Vector2(0,(7+breath)*envelope);
            }
            _root.Points=_points;
            _shadow.Points=_points.Select(p=>p+new Vector2(0,3)).ToArray();
        }
        _visibility=Mathf.MoveToward(_visibility,_connected?1:0,(float)delta*3.5f);
        _root.Modulate=_shadow.Modulate=new Color(1,1,1,_visibility);
        float surge=_pulse>=0?Mathf.Sin(Mathf.Clamp(_pulse/1.15f,0,1)*Mathf.Pi):0;
        _root.Width=24+surge*2.2f;
        QueueRedraw();
    }

    private Vector2 Along(float t)
    {
        float p=Mathf.Clamp(t,0,1)*(_points.Length-1);int i=Math.Min((int)p,_points.Length-2);
        return _points[i].Lerp(_points[i+1],p-i);
    }
    public override void _Draw()
    {
        if(_pulse<0||_points.Length<2||_mote==null)return;
        float progress=Mathf.Clamp(_pulse/.92f,0,1),fade=Mathf.Sin(progress*Mathf.Pi)*_visibility;
        for(int direction=0;direction<2;direction++)for(int i=0;i<3;i++)
        {
            float t=direction==0?progress-i*.018f:1-progress+i*.018f;
            Vector2 p=Along(t);float size=15-i*3;
            Color color=new(direction==0?"eed597":"bfd9b1");color.A=fade*(.58f-i*.12f);
            DrawTextureRect(_mote,new Rect2(p-Vector2.One*size/2,Vector2.One*size),false,color);
        }
    }
}
