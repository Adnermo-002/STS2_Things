using Godot;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;

namespace STS2_Things.Map;

[GlobalClass]
public partial class NCrossroadButton : NButton
{
    public Func<Task>? Activate { get; set; }
    public bool IsOpenRoad { get; set; }
    private TextureRect? _icon;
    private bool _focused;

    public override void _Ready()
    {
        _ignoreDragThreshold = 18f;
        ConnectSignals();
        _icon = new TextureRect
        {
            Texture = GD.Load<Texture2D>(IsOpenRoad ? "res://images/packed/character_select/char_select_lock3_unlocked.png" : "res://images/packed/common_ui/locked_model.png"),
            ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
            StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
            Position = (Size - new Vector2(38, 42)) / 2, Size = new Vector2(38, 42),
            MouseFilter = MouseFilterEnum.Ignore,
        };
        AddChild(_icon);
    }

    public override void _Draw()
    {
        DrawCircle(Size / 2, 23, new Color(0.12f, 0.10f, 0.08f, 0.32f), true, -1, true);
        if (_focused) DrawArc(Size / 2, 26, 0, Mathf.Tau, 40, new Color("e8c878"), 2f, true);
    }

    protected override void OnRelease()
    {
        if (IsEnabled && Activate != null) TaskHelper.RunSafely(Activate());
    }

    protected override void OnFocus()
    {
        base.OnFocus();
        _focused = true;
        if (_icon != null) _icon.Modulate = new Color(1.2f, 1.2f, 1.1f);
        QueueRedraw();
    }

    protected override void OnUnfocus()
    {
        _focused = false;
        if (_icon != null) _icon.Modulate = Colors.White;
        QueueRedraw();
    }
}
