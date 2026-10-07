using System.Text.Json;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves.Runs;
using STS2_Things.Map;

namespace STS2_Things.Modifiers;

/// <summary>Run-owned route ledger; the native modifier save/network format carries it.</summary>
public sealed class ThingsCrossroads : ModifierModel
{
    public sealed class Ledger
    {
        public int Version { get; set; } = 1;
        public List<CrossroadActPlan> Acts { get; set; } = [];
    }

    private static readonly JsonSerializerOptions Options = new() { IncludeFields = true, IgnoreReadOnlyProperties = true };
    private string _data = "";
    private Ledger? _ledger;
    private RunState? _owner;
    private bool _invalid;

    [SavedProperty]
    public string Data
    {
        get => _data;
        set { AssertMutable(); _data = value; _ledger = null; _invalid = false; }
    }

    public override bool ShouldReceiveCombatHooks => false;
    public override LocString Title => new("settings_ui", "THINGS_CROSSROADS_TITLE");
    public override LocString Description => new("settings_ui", "THINGS_CROSSROADS_DESCRIPTION");
    protected override string IconPath => "res://images/packed/common_ui/locked_model.png";

    public void Bind(RunState owner) => _owner = owner;

    public override Task AfterMapGenerated(ActMap map, int actIndex)
    {
        if (_owner != null) EnsurePlan(_owner, map, actIndex);
        return Task.CompletedTask;
    }

    public CrossroadActPlan? EnsurePlan(RunState run, ActMap map, int act)
    {
        Ledger ledger = Read();
        if (_invalid || act < 0 || act >= 32) return null;
        ulong fingerprint = CrossroadPlan.Fingerprint(map);
        CrossroadActPlan? plan = ledger.Acts.FirstOrDefault(p => p.Act == act);
        if (plan == null)
        {
            plan = new CrossroadActPlan { Act = act, Fingerprint = fingerprint, Roads = CrossroadPlan.Generate(map, run.Rng.Seed, act),
                History = run.CurrentActIndex == act ? run.VisitedMapCoords.ToList() : [] };
            ledger.Acts.Add(plan);
            Commit();
        }
        else if (plan.Fingerprint != fingerprint)
        {
            var paid = plan.Roads.Where(r => r.IsOpen && ValidPair(map, r)).ToList();
            var generated = CrossroadPlan.Generate(map, run.Rng.Seed, act);
            plan.Roads = paid.Concat(generated.Where(r => paid.All(p => p.Row != r.Row))).Take(CrossroadPlan.MaxRoads).OrderBy(r => r.Row).ToList();
            plan.Fingerprint = fingerprint;
            Commit();
        }
        // Apply the choice filter to existing saves too. Keep paid roads so an
        // update cannot erase a purchased connection or break the visit history.
        if (plan.Roads.RemoveAll(r => !r.IsOpen && map.GetPoint(r.A) is { } a &&
                map.GetPoint(r.B) is { } b && a.PointType == b.PointType) > 0) Commit();
        foreach (CrossroadRecord road in plan.Roads.Where(r => r.IsOpen && ValidPair(map, r)))
        {
            MapPoint from = map.GetPoint(road.From)!, to = map.GetPoint(road.To)!;
            if (!to.Children.Contains(from)) from.AddChildPoint(to);
        }
        return plan;
    }

    public void RecordHistory(RunState run)
    {
        CrossroadActPlan? plan = Read().Acts.FirstOrDefault(p => p.Act == run.CurrentActIndex);
        if (plan == null || _invalid) return;
        plan.History = run.VisitedMapCoords.ToList();
        Commit();
    }

    public int? HistoryIndex(MapLocation location)
    {
        if (!location.coord.HasValue || _invalid) return null;
        var history = Read().Acts.FirstOrDefault(p => p.Act == location.actIndex)?.History;
        int index = history?.IndexOf(location.coord.Value) ?? -1;
        return index >= 0 ? index : null;
    }

    public void Commit()
    {
        AssertMutable();
        if (!_invalid && _ledger != null) _data = JsonSerializer.Serialize(_ledger, Options);
    }

    private Ledger Read()
    {
        if (_ledger != null) return _ledger;
        try
        {
            _ledger = string.IsNullOrEmpty(_data) ? new Ledger() : JsonSerializer.Deserialize<Ledger>(_data, Options);
            if (_ledger == null || _ledger.Version != 1 || _ledger.Acts == null || _ledger.Acts.Count > 32 ||
                _ledger.Acts.Any(p => p == null || p.Act < 0 || p.Act >= 32 || p.Roads == null || p.History == null ||
                    p.Roads.Count > 3 || p.History.Count > 256 || p.Roads.Any(r => r == null || r.Left < 0 || r.Right <= r.Left ||
                        r.Right > 254 || r.Row < 2 || r.Row > 254 || (r.FromColumn != -1 && !r.IsOpen))))
                throw new JsonException("Unsupported route ledger");
        }
        catch (JsonException)
        {
            _invalid = true;
            _ledger = new Ledger();
            Log.Warn("STS2_Things: invalid crossroads save data; purchases disabled for this run.");
        }
        return _ledger;
    }

    private static bool ValidPair(ActMap map, CrossroadRecord road) =>
        road.Left >= 0 && road.Right > road.Left && road.Right - road.Left <= 3 && road.Row >= 2 &&
        map.GetPoint(road.A) is { } a && map.GetPoint(road.B) is { } b && CrossroadPlan.Suitable(a) && CrossroadPlan.Suitable(b);
}
