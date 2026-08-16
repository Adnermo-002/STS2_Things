using System.Reflection;
using Godot;

public partial class MerchantBargainVisualProbeNode : Node
{
    private static readonly Vector2 CanvasSize = new(2048f, 1152f);

    public override void _Ready()
    {
        _ = RenderAsync();
    }

    private async Task RenderAsync()
    {
        try
        {
            string[] args = OS.GetCmdlineUserArgs();
            if (args.Length != 5 || args[0] != "visual")
            {
                throw new ArgumentException(
                    "Expected: visual <rug-png> <player-hand-png> <merchant-hand-png> <output-png>");
            }

            GetWindow().Size = new Vector2I((int)CanvasSize.X, (int)CanvasSize.Y);
            var surface = new Control
            {
                Name = "MerchantBargainVisualSurface",
                Size = CanvasSize,
                MouseFilter = Control.MouseFilterEnum.Ignore
            };
            AddChild(surface);
            surface.AddChild(new ColorRect
            {
                Color = new Color("11191b"),
                Size = CanvasSize,
                MouseFilter = Control.MouseFilterEnum.Ignore
            });
            surface.AddChild(CreateTextureRect(LoadTexture(args[1]), CanvasSize));

            Texture2D playerHand = LoadTexture(args[2]);
            Texture2D merchantHand = LoadTexture(args[3]);
            Type overlayType = typeof(STS2_ThingsInit).Assembly.GetType(
                "STS2_Things.Features.MerchantBargain.NMerchantBargainRps",
                throwOnError: true)!;
            var overlay = (Control)(Activator.CreateInstance(overlayType, nonPublic: true)
                ?? throw new InvalidOperationException("Could not construct the bargain overlay."));
            overlay.Name = "ProductionMerchantBargainOverlay";
            overlay.Size = CanvasSize;
            SetTextureField(overlayType, overlay, "_playerRock", playerHand);
            SetTextureField(overlayType, overlay, "_playerPaper", playerHand);
            SetTextureField(overlayType, overlay, "_playerScissors", playerHand);
            SetTextureField(overlayType, overlay, "_merchantRock", merchantHand);
            SetTextureField(overlayType, overlay, "_merchantPaper", merchantHand);
            SetTextureField(overlayType, overlay, "_merchantScissors", merchantHand);
            Invoke(overlayType, overlay, "BuildVisuals", CanvasSize);
            surface.AddChild(overlay);

            await (Task)(Invoke(overlayType, overlay, "PlayEntrance")
                ?? throw new InvalidOperationException("PlayEntrance returned null."));
            for (int frame = 0; frame < 3; frame++)
            {
                await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            }
            RenderingServer.ForceDraw();

            Image screenshot = GetViewport().GetTexture().GetImage();
            Error error = screenshot.SavePng(args[4]);
            if (error != Error.Ok)
            {
                throw new InvalidOperationException($"Could not save visual probe: {error}.");
            }

            GD.Print($"Merchant bargain visual probe: PASS ({args[4]})");
            GetTree().Quit(0);
        }
        catch (Exception exception)
        {
            GD.PushError(exception.ToString());
            GetTree().Quit(1);
        }
    }

    private static TextureRect CreateTextureRect(Texture2D texture, Vector2 size)
    {
        return new TextureRect
        {
            Texture = texture,
            Size = size,
            ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
            StretchMode = TextureRect.StretchModeEnum.Scale,
            MouseFilter = Control.MouseFilterEnum.Ignore
        };
    }

    private static Texture2D LoadTexture(string path)
    {
        Image image = Image.LoadFromFile(path);
        if (image.IsEmpty())
        {
            throw new InvalidOperationException($"Could not load visual probe texture: {path}");
        }
        GD.Print($"Visual probe texture bounds: {path} => {image.GetUsedRect()}");
        return ImageTexture.CreateFromImage(image);
    }

    private static void SetTextureField(
        Type overlayType,
        object overlay,
        string name,
        Texture2D texture)
    {
        FieldInfo field = overlayType.GetField(name, BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingFieldException(overlayType.FullName, name);
        field.SetValue(overlay, texture);
    }

    private static object? Invoke(Type type, object instance, string method, params object[] args)
    {
        MethodInfo methodInfo = type.GetMethod(method, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
            ?? throw new MissingMethodException(type.FullName, method);
        return methodInfo.Invoke(instance, args);
    }
}
