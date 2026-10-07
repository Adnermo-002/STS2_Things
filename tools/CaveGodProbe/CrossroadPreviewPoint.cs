using Godot;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;

public partial class CrossroadPreviewPoint : NMapPoint
{
    protected override Color TraveledColor=>Colors.White;
    protected override Color UntravelableColor=>Colors.White;
    protected override Color HoveredColor=>Colors.White;
    protected override Vector2 HoverScale=>Vector2.One;
    protected override Vector2 DownScale=>Vector2.One;
    public void SetPoint(MapPoint point)=>Point=point;
    public override void _Ready()
    {
        // Match the native normal_map_point.tscn root: the icon is centered
        // inside a 56 px Control, not on the Control's top-left position.
        Size=Vector2.One*56;PivotOffset=Size/2;
        string icon=Point.PointType switch {MapPointType.Shop=>"shop",MapPointType.RestSite=>"rest",MapPointType.Treasure=>"chest",MapPointType.Elite=>"elite",MapPointType.Unknown=>"unknown",_=>"monster"};
        var texture=GD.Load<Texture2D>($"res://images/atlases/ui_atlas.sprites/map/icons/map_{icon}.tres");
        AddChild(new TextureRect{Texture=texture,
            ExpandMode=TextureRect.ExpandModeEnum.IgnoreSize,StretchMode=TextureRect.StretchModeEnum.KeepAspectCentered,
            Position=(Size-Vector2.One*50)/2,Size=Vector2.One*50,
            MouseFilter=MouseFilterEnum.Ignore});
    }
}
