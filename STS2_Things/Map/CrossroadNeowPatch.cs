using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Runs;
using STS2_Things.Modifiers;

namespace STS2_Things.Map;

// The route ledger uses native modifier persistence, but is not a custom-run
// rule. Neow otherwise sees a nonempty modifier list and skips its relic roll.
[HarmonyPatch]
internal static class CrossroadNeowPatch
{
    private static IEnumerable<MethodBase> TargetMethods()
    {
        yield return AccessTools.Method(typeof(Neow), "GenerateInitialOptions");
        yield return AccessTools.PropertyGetter(typeof(Neow), nameof(Neow.InitialDescription));
    }

    private static IEnumerable<CodeInstruction> Transpiler(IEnumerable<CodeInstruction> instructions)
    {
        MethodInfo getter = AccessTools.PropertyGetter(typeof(IRunState), nameof(IRunState.Modifiers));
        MethodInfo visibleRules = AccessTools.Method(typeof(CrossroadNeowPatch), nameof(GetNeowModifiers));
        foreach (CodeInstruction instruction in instructions)
        {
            if (instruction.Calls(getter))
            {
                instruction.opcode = OpCodes.Call;
                instruction.operand = visibleRules;
            }
            yield return instruction;
        }
    }

    private static IReadOnlyList<ModifierModel> GetNeowModifiers(IRunState run)
    {
        IReadOnlyList<ModifierModel> modifiers = run.Modifiers;
        return modifiers.Any(modifier => modifier is ThingsCrossroads)
            ? modifiers.Where(modifier => modifier is not ThingsCrossroads).ToArray()
            : modifiers;
    }
}

// A failed/older initialization can persist Neow as finished without ever
// granting a choice. Recover only that opening-room state; do not heal again,
// rewrite the save, or replay an ancient reward later in the run.
[HarmonyPatch(typeof(AncientEventModel), "SetInitialEventState")]
internal static class CrossroadNeowResumePatch
{
    private static void Prefix(AncientEventModel __instance, ref bool isPreFinished)
    {
        if (!isPreFinished || __instance is not Neow || __instance.Owner is not { } player)
            return;
        IRunState run = player.RunState;
        if (run.CurrentActIndex != 0 || run.TotalFloor != 1 ||
            !run.Modifiers.Any(m => m is ThingsCrossroads) ||
            run.Modifiers.Any(m => m is not ThingsCrossroads))
            return;
        var history = run.CurrentMapPointHistoryEntry;
        if (history == null || history.Rooms.Count != 1 || history.Rooms[0].ModelId != __instance.Id ||
            history.PlayerStats.Where(s => s.PlayerId == player.NetId)
                .Any(s => s.AncientChoices.Any(c => c.WasChosen)))
            return;
        var startingIds = player.Character.StartingRelics.Select(r => r.Id).OrderBy(id => id.ToString());
        if (!player.Relics.Select(r => r.Id).OrderBy(id => id.ToString()).SequenceEqual(startingIds))
            return;
        isPreFinished = false;
    }
}
