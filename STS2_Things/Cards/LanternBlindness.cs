using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using STS2_Things.Visuals;

namespace STS2_Things.Cards;

/// <summary>Presentation metadata only. Real costs use native end-of-turn modifiers.</summary>
public static class LanternBlindness
{
    private sealed record MarkedCard(ICombatState Combat, int? RolledCost);
    private static readonly ConditionalWeakTable<CardModel, MarkedCard> Marks = new();

    public static bool IsBlinded(CardModel? card) => CombatManager.Instance.IsInProgress && card is { IsMutable: true } &&
        Marks.TryGetValue(card, out var mark) && ReferenceEquals(card.CombatState, mark.Combat);

    public static void Mark(CardModel card, int? rolledCost)
    {
        if (card.CombatState is not { } combat) return;
        Marks.Remove(card);
        Marks.Add(card, new MarkedCard(combat, rolledCost));
    }

    public static void Forget(CardModel card) => Marks.Remove(card);

    internal static void Copy(CardModel source, CardModel clone)
    {
        if (!IsBlinded(source) || !Marks.TryGetValue(source, out var mark)) return;
        Marks.Remove(clone);
        Marks.Add(clone, mark);
    }
}

[HarmonyPatch(typeof(CardModel), nameof(CardModel.EndOfTurnCleanup))]
internal static class LanternBlindnessTurnCleanupPatch
{
    // Clear before the native cost-change event refreshes any visible card.
    private static void Prefix(CardModel __instance) => LanternBlindness.Forget(__instance);
    private static void Postfix(CardModel __instance) => NBlindCardVeil.RefreshOnTable(__instance);
}

[HarmonyPatch(typeof(CardEnergyCost), nameof(CardEnergyCost.Clone))]
internal static class LanternBlindnessClonePatch
{
    private static void Postfix(CardModel ____card, CardModel newCard) => LanternBlindness.Copy(____card, newCard);
}
