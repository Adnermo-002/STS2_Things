using HarmonyLib;
using System.Runtime.CompilerServices;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Runs.History;
using STS2_Things.Modifiers;

namespace STS2_Things.Map;

[HarmonyPatch(typeof(RunState), "CreateShared")]
internal static class CrossroadRunPatch
{
    private static void Prefix(ref IReadOnlyList<ModifierModel> modifiers)
    {
        if (!modifiers.OfType<ThingsCrossroads>().Any())
            modifiers = modifiers.Append(ModelDb.Modifier<ThingsCrossroads>().ToMutable()).ToArray();
    }

    private static void Postfix(RunState __result) => Crossroads.Ledger(__result)?.Bind(__result);
}

[HarmonyPatch(typeof(RunState), nameof(RunState.AddVisitedMapCoord))]
internal static class CrossroadHistoryRecordPatch
{
    private static void Postfix(RunState __instance, bool __result)
    {
        if (__result) Crossroads.Ledger(__instance)?.RecordHistory(__instance);
    }
}

// Native histories normally use row as their index. A side room adds another
// history entry on the same row, so use the saved visit order for these runs.
[HarmonyPatch(typeof(RunState), nameof(RunState.GetHistoryEntryFor))]
internal static class CrossroadHistoryLookupPatch
{
    private static bool Prefix(RunState __instance, MapLocation location, ref MapPointHistoryEntry? __result)
    {
        int? index = Crossroads.Ledger(__instance)?.HistoryIndex(location);
        if (!index.HasValue || location.actIndex < 0 || location.actIndex >= __instance.MapPointHistory.Count) return true;
        var history = __instance.MapPointHistory[location.actIndex];
        __result = index.Value < history.Count ? history[index.Value] : null;
        return false;
    }
}

[HarmonyPatch(typeof(MapTravel), nameof(MapTravel.GetTravelablePointsFrom))]
internal static class CrossroadFreeTravelPatch
{
    private static void Postfix(IRunState runState, MapPoint currentPoint, ref IEnumerable<MapPoint> __result)
    {
        if (runState is not RunState run) return;
        // Free-travel relics replace Children with the next row. Retain a paid
        // horizontal option, while never making a visited room reachable again.
        var plan = Crossroads.Ledger(runState)?.EnsurePlan(run, runState.Map, runState.CurrentActIndex);
        var destinations = plan?.Roads.Where(r => r.IsOpen && r.From == currentPoint.coord && !run.VisitedMapCoords.Contains(r.To))
            .Select(r => runState.Map.GetPoint(r.To)).OfType<MapPoint>() ?? [];
        __result = __result.Concat(destinations).Distinct();
    }
}

[HarmonyPatch(typeof(NMapScreen), nameof(NMapScreen.SetMap))]
internal static class CrossroadMapDisplayPatch
{
    internal static readonly ConditionalWeakTable<NMapScreen, RunState> Owners = new();
    private static void Postfix(NMapScreen __instance, ActMap map)
    {
        if (Owners.TryGetValue(__instance, out var run)) NCrossroadLayer.Attach(__instance, run, map);
    }
}

[HarmonyPatch(typeof(NMapScreen), nameof(NMapScreen.Initialize))]
internal static class CrossroadMapOwnerPatch
{
    private static void Postfix(NMapScreen __instance, IRunState __0)
    {
        if (__0 is not RunState run) return;
        CrossroadMapDisplayPatch.Owners.Remove(__instance);
        CrossroadMapDisplayPatch.Owners.Add(__instance, run);
    }
}
