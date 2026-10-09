using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Nodes.Combat;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Visuals;

/// <summary>Three hand-painted-colour filaments follow the animated foreleg.</summary>
public partial class NSilkCastThreads : Node2D
{
    [Export(PropertyHint.Range, "0,0.5,0.01")]
    public float ReleaseDelay { get; set; }
    private MegaSprite? _spine;
    private NCreature? _owner;
    private float _time = -1;
    private float _pixel;
    private readonly List<Vector2> _targets = [];
    public override void _Ready()
    {
        _spine = new MegaSprite(GetParent().GetParent());
        for(Node? node=GetParent();node!=null;node=node.GetParent())
            if(node is NCreature creature){_owner=creature;break;}
    }
    public override void _Process(double delta)
    {
        _time=-1;
        _pixel=1/Mathf.Max(.01f,GlobalTransform.X.Length());
        using var scope=TrackEntryScope(_spine?.TryGetAnimationState()?.GetCurrent(0),out MegaTrackEntry? track);
        if(track?.GetAnimationName()=="cast") _time=track.GetTrackTime()-ReleaseDelay;
        _targets.Clear();
        if(_time>=.45f && _time<1.10f && _owner?.Entity is { IsAlive:true } entity)
        {
            foreach(var player in entity.CombatState?.Players ?? [])
                if(player.Creature.IsAlive && player.Creature.GetCreatureNode() is { } target)
                    _targets.Add(ToLocal(target.VfxSpawnPosition));
            if(_targets.Count==0 && _owner.GetParent() is { } parent)
                foreach(var node in parent.FindChildren("*","",true,false).OfType<NCreature>())
                    if(node.Entity is { IsPlayer:true, IsAlive:true }) _targets.Add(ToLocal(node.VfxSpawnPosition));
        }
        QueueRedraw();
    }
    public override void _Draw()
    {
        if(_time<.45f || _time>=1.10f) return;
        float lead=Mathf.Clamp((_time-.45f)/.17f,0,1);
        float tail=Mathf.Clamp((_time-.75f)/.35f,0,1);
        if(lead<=tail)return;
        float opacity=Mathf.Min(1,(_time-.45f)/.07f)*(1-Mathf.Clamp((_time-.9f)/.2f,0,1));
        foreach(var target in _targets)
        for(int strand=0;strand<3;strand++)
        {
            Vector2[] points=new Vector2[33];
            for(int i=0;i<points.Length;i++)
            {
                float u=Mathf.Lerp(tail,lead,i/(float)(points.Length-1));
                float wave=Mathf.Sin(u*Mathf.Pi);
                points[i]=target*u+new Vector2(0,(-25-strand*13)*_pixel*wave+
                    4*_pixel*Mathf.Sin(u*12-_time*14+strand)*wave);
            }
            DrawPolyline(points,new Color(.22f,.35f,.31f,.64f*opacity),4*_pixel,true);
            DrawPolyline(points,new Color(.81f,.90f,.70f,.90f*opacity),1.65f*_pixel,true);
        }
    }
}
