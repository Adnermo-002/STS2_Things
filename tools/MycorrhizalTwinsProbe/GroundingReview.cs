using System.Text.Json;
using Godot;
using MegaCrit.Sts2.Core.Nodes.Combat;

public partial class MycorrhizalTwinsProbeNode
{
    private static Node2D FootProbe(Node2D sprite, string bone, Vector2 offset)
    {
        var attachment=ClassDB.Instantiate("SpineBoneNode").As<Node2D>();
        attachment.Name="GroundingProbe";attachment.Set("bone_name",bone);sprite.AddChild(attachment);
        var marker=new Node2D{Position=offset};attachment.AddChild(marker);sprite.Call("update_skeleton",0f);
        return marker;
    }

    private void CheckGrounding(SubViewport view, NCreature hero, NCreature tall, NCreature small, string output, string phase="grounding")
    {
        Rect2 protectedZone=new(hero.GlobalPosition+new Vector2(-105,-165),new Vector2(210,170));
        int foliageHits=0;
        foreach(var layer in view.FindChildren("PaintedLayer","TextureRect",true,false).OfType<TextureRect>())
        {
            if(layer.GetMeta("plane").AsString()!="bg_03")continue;
            using var image=layer.Texture.GetImage();
            if(image.IsCompressed())image.Decompress();
            Rect2 rect=layer.GetGlobalRect();
            for(float y=protectedZone.Position.Y;y<protectedZone.End.Y;y+=2)
            for(float x=protectedZone.Position.X;x<protectedZone.End.X;x+=2)
            {
                Vector2 uv=(new Vector2(x,y)-rect.Position)/rect.Size;
                if(uv.X<0||uv.Y<0||uv.X>=1||uv.Y>=1)continue;
                if(image.GetPixel((int)(uv.X*image.GetWidth()),(int)(uv.Y*image.GetHeight())).A>.15f)foliageHits++;
            }
        }
        var a=tall.Visuals.GetNode<Node2D>("Visuals");var b=small.Visuals.GetNode<Node2D>("Visuals");
        var start=FootProbe(a,"foot_near",new Vector2(65,25));
        var end=FootProbe(b,"foot_far",new Vector2(-55,25));
        var root=tall.Visuals.GetNode<Node2D>("RootLink");
        var line=root.GetNodeOrNull<Line2D>("PaintedRoot");
        Vector2 actualStart=line is { Points.Length:>1 }?line.ToGlobal(line.Points[0]):root.GlobalPosition;
        Vector2 actualEnd;
        if(line is { Points.Length:>1 })actualEnd=line.ToGlobal(line.Points[^1]);
        else
        {
            var field=root.GetType().GetField("_end",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Instance);
            actualEnd=field?.GetValue(root) is Vector2 p?root.ToGlobal(p):root.GlobalPosition;
        }
        float startError=actualStart.DistanceTo(start.GlobalPosition),endError=actualEnd.DistanceTo(end.GlobalPosition);
        var result=new{foliageHits,allowedFoliageSamples=20,startError,endError,allowedRootError=3,
            expectedStart=start.GlobalPosition.ToString(),expectedEnd=end.GlobalPosition.ToString()};
        File.WriteAllText(Path.Combine(output,phase+".json"),JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true}));
        GD.Print("GROUNDING "+JsonSerializer.Serialize(result));
        Assert(foliageHits<=20,"Standing zone intersects tall decoration: "+foliageHits);
        Assert(startError<3&&endError<3,"Root is detached from animated feet: "+startError+", "+endError);
    }
}
