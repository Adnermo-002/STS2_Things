using Godot;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Multiplayer;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Runs;

namespace STS2_Things.Map;

[GlobalClass]
public partial class NCrossroadLayer : Node2D
{
    private NMapScreen _screen = null!;
    private RunState _run = null!;
    private ActMap _map = null!;
    private CrossroadActPlan _plan = null!;
    private Dictionary<MapCoord, NMapPoint> _points = [];
    private readonly Dictionary<NCrossroadButton, CrossroadRecord> _buttons = [];
    private readonly List<RoadVisual> _roadVisuals = [];
    private Texture2D? _roadDot;

    private sealed class RoadVisual(NMapPoint a, NMapPoint b, NCrossroadButton button, bool isOpen)
    {
        public NMapPoint A { get; } = a;
        public NMapPoint B { get; } = b;
        public NCrossroadButton Button { get; } = button;
        public bool IsOpen { get; } = isOpen;
        public readonly List<TextureRect> Dots = [];
        public Vector2 LastStart = new(float.NaN, float.NaN);
        public Vector2 LastEnd = new(float.NaN, float.NaN);
    }
    private readonly Dictionary<NMapPoint, (NodePath Before, NodePath Road)> _focusLinks = [];
    private NGenericPopup? _popup;
    private bool _asking;

    public static void Attach(NMapScreen screen, RunState run, ActMap map)
    {
        var container = screen.GetNode<Control>("TheMap/Points");
        // SetMap queues its old children for deletion at the end of the frame.
        // Detach the old layer now so it cannot keep handling changes or keep
        // the replacement's name occupied during the same frame.
        foreach (var previous in container.GetChildren().OfType<NCrossroadLayer>())
        {
            container.RemoveChild(previous);
            previous.QueueFree();
        }
        var plan = Crossroads.Ledger(run)?.EnsurePlan(run, map, run.CurrentActIndex);
        if (plan == null || plan.Roads.Count == 0) return;
        var layer = new NCrossroadLayer
        {
            Name = "ThingsCrossroads", _screen = screen, _run = run, _map = map, _plan = plan,
            // Retiring points still share this container and the new points'
            // coordinates until Godot flushes its deletion queue.
            _points = container.GetChildren().OfType<NMapPoint>()
                .Where(p => !p.IsQueuedForDeletion()).ToDictionary(p => p.Point.coord),
        };
        container.AddChild(layer);
    }

    public override void _Ready()
    {
        Crossroads.Changed += OnChanged;
        _roadDot = GD.Load<Texture2D>("res://images/atlases/compressed.sprites/map/map_dot.tres");
        foreach (CrossroadRecord road in _plan.Roads)
        {
            if (!_points.TryGetValue(road.A, out var a) || !_points.TryGetValue(road.B, out var b)) continue;
            // Native map points can be re-anchored by the real map Control after
            // SetMap returns. Create the road here and follow the *live* point
            // transforms below, rather than freezing its icon over a room.
            var button = new NCrossroadButton
            {
                Name = $"Road_{road.Row}_{road.Left}_{road.Right}", Size = new Vector2(58, 58),
                FocusMode = Control.FocusModeEnum.All, MouseFilter = Control.MouseFilterEnum.Stop,
                IsOpenRoad = road.IsOpen, Activate = () => Activate(road),
            };
            AddChild(button);
            _buttons.Add(button, road);
            button.FocusNeighborLeft = a.GetPath(); button.FocusNeighborRight = b.GetPath();
            var visuals = new RoadVisual(a, b, button, road.IsOpen);
            _roadVisuals.Add(visuals);
            UpdateRoadPlacement(visuals);
        }
        RefreshInteraction(refreshNavigation: true);
    }

    public override void _Process(double delta)
    {
        // NMapScreen sets native map point positions before the Control anchor
        // layout has necessarily settled. Reposition icons and dashed roads when
        // the endpoints move (including viewport resizes or map rebuilds).
        foreach (var visuals in _roadVisuals) UpdateRoadPlacement(visuals);
        RefreshInteraction();
    }

    private void UpdateRoadPlacement(RoadVisual visuals)
    {
        if (!GodotObject.IsInstanceValid(visuals.A) || !GodotObject.IsInstanceValid(visuals.B) ||
            visuals.A.IsQueuedForDeletion() || visuals.B.IsQueuedForDeletion()) return;
        Vector2 start = ToLocal(visuals.A.GetGlobalTransform() * (visuals.A.Size / 2));
        Vector2 end = ToLocal(visuals.B.GetGlobalTransform() * (visuals.B.Size / 2));
        if (start.IsEqualApprox(visuals.LastStart) && end.IsEqualApprox(visuals.LastEnd)) return;
        float length = start.DistanceTo(end);
        if (length < 1f) return;
        visuals.LastStart = start; visuals.LastEnd = end;
        Vector2 mid = (start + end) / 2;
        var hitSize = new Vector2(Math.Max(58f, length - 100f), 58f);
        visuals.Button.Position = mid - hitSize / 2;
        visuals.Button.Size = hitSize;
        visuals.Button.CenterIcon();
        visuals.Button.QueueRedraw();

        if (visuals.IsOpen) return;
        Vector2 direction = (end - start) / length;
        int count = (int)MathF.Ceiling(Math.Max(0, length - 76f) / 22f);
        for (int i = visuals.Dots.Count; i < count; i++)
        {
            var dot = new TextureRect
            {
                Texture = _roadDot,
                ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
                StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
                Size = Vector2.One * 14, PivotOffset = Vector2.One * 7,
                Modulate = new Color(_run.Act.MapUntraveledColor, .7f),
                MouseFilter = Control.MouseFilterEnum.Ignore,
            };
            AddChild(dot);
            visuals.Dots.Add(dot);
        }
        for (int i = 0; i < visuals.Dots.Count; i++)
        {
            float distance = 38f + i * 22f;
            var dot = visuals.Dots[i];
            dot.Visible = distance < length - 38f && MathF.Abs(distance - length / 2f) >= 29f;
            if (!dot.Visible) continue;
            dot.Position = start + direction * distance - Vector2.One * 7;
            dot.Rotation = direction.Angle() + Mathf.Pi / 2;
        }
    }

    private bool CanInteract(CrossroadRecord road) =>
        _screen.IsOpen && _screen.IsTravelEnabled && !_screen.IsTraveling &&
        _run.CurrentMapCoord is { } current && road.Touches(current) &&
        !_run.VisitedMapCoords.Contains(road.Other(current)) && (!road.IsOpen || road.From == current) &&
        _screen.Drawings.GetLocalDrawingMode() == DrawingMode.None;

    private void RefreshInteraction(bool refreshNavigation = false)
    {
        foreach (var (button, road) in _buttons)
        {
            bool enabled = CanInteract(road);
            if (button.IsEnabled != enabled)
            {
                if (enabled) button.Enable(); else button.Disable();
                refreshNavigation = true;
            }
            // Disabled locks must also let map scrolling/drawing pass through.
            button.MouseFilter = enabled ? Control.MouseFilterEnum.Stop : Control.MouseFilterEnum.Ignore;
        }
        if (!refreshNavigation) return;
        RestoreFocusLinks();
        foreach (var (button, _) in _buttons.Where(entry => entry.Key.IsEnabled))
        {
            foreach (MapPoint child in _run.CurrentMapPoint!.Children)
            {
                if (!_points.TryGetValue(child.coord, out var node)) continue;
                NodePath path = button.GetPath();
                _focusLinks[node] = (node.FocusNeighborBottom, path);
                node.FocusNeighborBottom = path;
            }
        }
    }

    private void RestoreFocusLinks()
    {
        foreach (var (node, paths) in _focusLinks)
            if (GodotObject.IsInstanceValid(node) && node.FocusNeighborBottom == paths.Road)
                node.FocusNeighborBottom = paths.Before;
        _focusLinks.Clear();
    }

    public override void _ExitTree()
    {
        Crossroads.Changed -= OnChanged;
        RestoreFocusLinks();
        if (_popup != null && GodotObject.IsInstanceValid(_popup))
        {
            if (NModalContainer.Instance?.OpenModal == _popup) NModalContainer.Instance.Clear();
            else _popup.QueueFree();
        }
    }

    private void OnChanged(IRunState run)
    {
        if (ReferenceEquals(run, _run) && GodotObject.IsInstanceValid(_screen))
            Callable.From(() => { if (GodotObject.IsInstanceValid(_screen)) _screen.SetMap(_map, _run.Rng.Seed, clearDrawings: false); }).CallDeferred();
    }

    private async Task Activate(CrossroadRecord road)
    {
        if (_asking || !CanInteract(road) ||
            NModalContainer.Instance is not { OpenModal: null } modal) return;
        Player? payer = LocalContext.NetId is { } localId ? _run.GetPlayer(localId) : null;
        if (payer == null) return;
        MapCoord current = _run.CurrentMapCoord!.Value;
        MapCoord target = road.Other(current);
        if (road.IsOpen)
        {
            if (_points.TryGetValue(target, out var destination)) _screen.OnMapPointSelectedLocally(destination);
            return;
        }

        string key = payer.Gold < CrossroadPlan.Price ? "THINGS_CROSSROAD_POOR" : "THINGS_CROSSROAD_ASK";
        var body = Text(key);
        body.Add("Price", CrossroadPlan.Price); body.Add("Gold", payer.Gold);
        body.Add("Room", RoomName(_map.GetPoint(target)!.PointType));
        body.Add("GoldIcon", "[img=top]res://images/packed/sprite_fonts/gold_icon.png[/img]");
        bool canPay = payer.Gold >= CrossroadPlan.Price;
        NGenericPopup? popup = NGenericPopup.Create();
        if (popup == null) return;
        _asking = true; _popup = popup;
        var closed = new TaskCompletionSource<bool>();
        popup.TreeExiting += () => closed.TrySetResult(false);
        modal.Add(popup);
        Task<bool> answer = popup.WaitForConfirmation(body, Text("THINGS_CROSSROAD_HEADER"),
            Text("THINGS_CROSSROAD_CANCEL"), Text("THINGS_CROSSROAD_BUY"));
        if (!canPay) popup.GetNode<NVerticalPopup>("VerticalPopup").YesButton.Disable();
        int act = _run.CurrentActIndex; ulong fingerprint = _plan.Fingerprint;
        try
        {
            await Task.WhenAny(answer, closed.Task);
            if (!canPay || !answer.IsCompletedSuccessfully || !answer.Result || !GodotObject.IsInstanceValid(this) ||
                !GodotObject.IsInstanceValid(_screen) || !CanInteract(road) || _run.CurrentMapCoord != current) return;
            RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(new UnlockCrossroadAction(payer, act, fingerprint,
                current, target, CrossroadPlan.Price));
        }
        finally { _asking = false; _popup = null; }
    }

    private static LocString Text(string key) => new("settings_ui", key);
    private static string RoomName(MapPointType type) => Text("THINGS_CROSSROAD_ROOM_" + type.ToString().ToUpperInvariant()).GetFormattedText();
}
