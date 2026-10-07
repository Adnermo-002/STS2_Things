using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves.Runs;

namespace STS2_Things.Relics;

public sealed class BorrowedEmber : RelicModel
{
    public const int KindledHeal = 12;
    private bool _kindled;
    private int _state; // 0: waiting for the next map camp, 1: arrived, 2: settled.
    public override RelicRarity Rarity => RelicRarity.Event;
    public override bool IsUsedUp => State == 2;
    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new StringVar("Terms", new LocString("relics", "BORROWED_EMBER.debtTerms").GetFormattedText())];

    [SavedProperty]
    public bool Kindled
    {
        get => _kindled;
        private set { AssertMutable(); _kindled = value; Refresh(); }
    }
    [SavedProperty]
    public int State
    {
        get => _state;
        private set { AssertMutable(); _state = value; Refresh(); }
    }
    [SavedProperty] public int CampAct { get; private set; } = -1;
    [SavedProperty] public int CampColumn { get; private set; } = -1;
    [SavedProperty] public int CampRow { get; private set; } = -1;

    internal void Configure(bool kindled) { Kindled = kindled; State = 0; }
    private void Refresh()
    {
        var terms = new LocString("relics", Kindled ? "BORROWED_EMBER.kindledTerms" : "BORROWED_EMBER.debtTerms");
        terms.Add("Heal", KindledHeal);
        ((StringVar)DynamicVars["Terms"]).StringValue = terms.GetFormattedText();
        Status = IsUsedUp ? RelicStatus.Disabled : State == 1 ? RelicStatus.Active : RelicStatus.Normal;
    }

    public bool IsSpentCampHere => !Kindled && Owner.RunState.CurrentRoom is RestSiteRoom &&
        Owner.RunState.CurrentActIndex == CampAct && Owner.RunState.CurrentMapCoord is { } coord &&
        coord.col == CampColumn && coord.row == CampRow;

    internal void FinishPassing() { State = 2; ClearMarks(Owner.RunState.Map); }

    public static IReadOnlyList<MapPoint> FindNextRestSites(IRunState run, ActMap? map = null)
    {
        map ??= run.Map;
        var current = run.CurrentMapCoord is { } coord ? map.GetPoint(coord) : null;
        var queue = new Queue<MapPoint>((current?.Children ?? map.startMapPoints).OrderBy(point => point));
        var seen = new HashSet<MapPoint>();
        var visited = run is RunState state ? state.VisitedMapCoords.ToHashSet() : [];
        var result = new List<MapPoint>();
        while (queue.TryDequeue(out var point))
        {
            if (!seen.Add(point) || visited.Contains(point.coord)) continue;
            if (point.PointType == MapPointType.RestSite) { result.Add(point); continue; }
            if (point.PointType == MapPointType.Boss) continue;
            foreach (var child in point.Children.OrderBy(child => child)) queue.Enqueue(child);
        }
        return result.OrderBy(point => point).ToArray();
    }

    private void ClearMarks(ActMap map)
    {
        foreach (var point in map.GetAllMapPoints())
            if (point.Quests.Contains(this)) point.RemoveQuest(this);
    }

    private void MarkNextCamps(ActMap map)
    {
        ClearMarks(map);
        if (State != 0) return;
        foreach (var point in FindNextRestSites(Owner.RunState, map)) point.AddQuest(this);
    }

    public override Task AfterObtained() { MarkNextCamps(Owner.RunState.Map); return Task.CompletedTask; }
    public override Task AfterActEntered() { MarkNextCamps(Owner.RunState.Map); return Task.CompletedTask; }
    public override Task AfterRemoved() { ClearMarks(Owner.RunState.Map); return Task.CompletedTask; }
    public override ActMap ModifyGeneratedMapLate(IRunState run, ActMap map, int actIndex)
    {
        MarkNextCamps(map);
        return map;
    }

    public override Task BeforeRoomEntered(AbstractRoom room)
    {
        if (State == 0 && room is RestSiteRoom && ReferenceEquals(room, Owner.RunState.BaseRoom) &&
            Owner.RunState.CurrentMapPoint is { PointType: MapPointType.RestSite } point)
        {
            CampAct = Owner.RunState.CurrentActIndex;
            CampColumn = point.coord.col;
            CampRow = point.coord.row;
            State = 1;
            ClearMarks(Owner.RunState.Map);
        }
        else if (State == 1 && !Kindled && !IsSpentCampHere)
            State = 2;
        return Task.CompletedTask;
    }

    public override async Task AfterRoomEntered(AbstractRoom room)
    {
        if (State == 0) MarkNextCamps(Owner.RunState.Map);
        if (State == 1 && Kindled && room is RestSiteRoom)
        {
            State = 2;
            if (!Owner.Creature.IsDead)
            {
                Flash();
                await CreatureCmd.Heal(Owner.Creature, KindledHeal);
            }
        }
        if (IsSpentCampHere && LocalContext.IsMe(Owner) && NRestSiteRoom.Instance is { } node)
        {
            if (node.GetNode<Control>("BgContainer").FindChild("RestSiteLighting", true, false) is CanvasItem light)
                light.Visible = false;
            foreach (var character in node.Characters) character.HideFlameGlow();
            for (int i = 1; i <= Owner.RunState.Players.Count; i++)
                if (node.GetNodeOrNull<CanvasItem>($"BgContainer/Character_{i}") is { } character)
                    character.Modulate = Colors.DarkGray;
            node.SetText(new LocString("rest_site_ui", "OPTION_THINGS_SPENT_EMBER.description").GetFormattedText());
        }
    }
}
