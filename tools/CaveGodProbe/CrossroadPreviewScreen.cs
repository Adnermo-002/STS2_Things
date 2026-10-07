using System.Reflection;
using Godot;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Runs;
using STS2_Things.Map;

// A viewport fixture for the production road controls and native popup. It has
// no gameplay room, scroll controller or Steam overlay.
public partial class CrossroadPreviewScreen : NMapScreen
{
    public RunState Run = null!;
    public ActMap ActMap = null!;
    public override void _Ready() { }
    public override void _Process(double delta) { }
    public override void _Input(InputEvent input) { }
    public override void _Notification(int what) { }
    public override void _ExitTree() { }

    public void Populate()
    {
        var map=GetNodeOrNull<Control>("TheMap");
        if(map==null)
        {
            map=new Control{Name="TheMap",Size=new Vector2(1400,1000),MouseFilter=MouseFilterEnum.Ignore};
            AddChild(map);
            map.AddChild(new Control{Name="Points",Size=new Vector2(1400,1000),MouseFilter=MouseFilterEnum.Ignore});
        }
        var points=map.GetNode<Control>("Points");
        // Native SetMap keeps its container and queues children for end-of-frame
        // deletion. Immediate Free() hid duplicate coordinates during redraws.
        foreach(var child in points.GetChildren())child.QueueFree();
        var dot=GD.Load<Texture2D>("res://images/atlases/compressed.sprites/map/map_dot.tres");
        Vector2 PositionFor(MapCoord c)=>new(240+c.col*140+(c.row%3-1)*9,930-c.row*58+(c.col%3-1)*17);
        foreach(var p in ActMap.GetAllMapPoints())
        foreach(var c in p.Children.Where(c=>c.PointType!=MapPointType.Boss))
        {
            var start=PositionFor(p.coord)+Vector2.One*28;var end=PositionFor(c.coord)+Vector2.One*28;var dir=(end-start).Normalized();
            for(float distance=24;distance<start.DistanceTo(end)-24;distance+=20)
                points.AddChild(new TextureRect{Texture=dot,Position=start+dir*distance-Vector2.One*6,Size=Vector2.One*12,
                    PivotOffset=Vector2.One*6,Rotation=dir.Angle()+Mathf.Pi/2,Modulate=Run.Act.MapUntraveledColor,
                    ExpandMode=TextureRect.ExpandModeEnum.IgnoreSize,MouseFilter=MouseFilterEnum.Ignore});
        }
        foreach(var p in ActMap.GetAllMapPoints())
        {
            var node=new CrossroadPreviewPoint();node.SetPoint(p);node.Position=PositionFor(p.coord);points.AddChild(node);
        }
        typeof(NMapScreen).GetProperty(nameof(IsOpen))!.SetValue(this,true);
        typeof(NMapScreen).GetProperty(nameof(IsTravelEnabled))!.SetValue(this,true);
        typeof(NMapScreen).GetProperty(nameof(Drawings))!.SetValue(this,new NMapDrawings());
    }
}
