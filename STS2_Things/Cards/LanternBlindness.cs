using System.Runtime.CompilerServices;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using STS2_Things.Powers;
using STS2_Things.Visuals;

namespace STS2_Things.Cards;

/// <summary>Presentation metadata only. Real costs use native end-of-turn modifiers.</summary>
public static class LanternBlindness
{
    private sealed record MarkedCard(ICombatState Combat, int? RolledCost);
    private static readonly ConditionalWeakTable<CardModel, MarkedCard> Marks = new();
    // Draw animates the card before AfterCardDrawn runs. Pre-cover its visuals without
    // rolling costs or consuming charges; the native draw hook still owns gameplay.
    private static readonly ConditionalWeakTable<CardModel, MarkedCard> PendingDrawVeils = new();

    public static bool IsVeiled(CardModel? card) => IsBlinded(card) ||
        (CombatManager.Instance.IsInProgress && card is { IsMutable: true } &&
         PendingDrawVeils.TryGetValue(card, out var pending) &&
         ReferenceEquals(card.CombatState, pending.Combat) && card.Pile?.Type == PileType.Hand);

    internal static void PrimeDrawVeil(CardModel card, CardPile destination)
    {
        if (!CombatManager.Instance.IsInProgress || destination.Type != PileType.Hand ||
            card.Pile?.Type != PileType.Draw || !card.IsMutable || IsBlinded(card) ||
            card.Owner.Creature.GetPower<LanternBlindnessPower>() is not { Amount: > 0 } power ||
            !ReferenceEquals(power.Owner, card.Owner.Creature) || card.CombatState is not { } combat)
            return;
        PendingDrawVeils.Remove(card);
        PendingDrawVeils.Add(card, new MarkedCard(combat, null));
    }

    public static bool IsBlinded(CardModel? card) => CombatManager.Instance.IsInProgress && card is { IsMutable: true } &&
        Marks.TryGetValue(card, out var mark) && ReferenceEquals(card.CombatState, mark.Combat);

    public static void Mark(CardModel card, int? rolledCost)
    {
        if (card.CombatState is not { } combat) return;
        PendingDrawVeils.Remove(card);
        Marks.Remove(card);
        Marks.Add(card, new MarkedCard(combat, rolledCost));
    }

    public static void Forget(CardModel card)
    {
        Marks.Remove(card);
        PendingDrawVeils.Remove(card);
    }

    internal static void Copy(CardModel source, CardModel clone)
    {
        if (!IsBlinded(source) || !Marks.TryGetValue(source, out var mark)) return;
        Marks.Remove(clone);
        Marks.Add(clone, mark);
    }
}

// CardPileCmd.Draw awaits the entire Add animation before invoking AfterCardDrawn.
// Prime only draw-pile -> hand moves, ahead of NCard creation and its first frame.
[HarmonyPatch(typeof(CardPileCmd), nameof(CardPileCmd.Add), typeof(CardModel), typeof(CardPile),
    typeof(CardPilePosition), typeof(AbstractModel), typeof(bool))]
internal static class LanternBlindnessDrawVisualPrimePatch
{
    private static void Prefix(CardModel card, CardPile newPile) => LanternBlindness.PrimeDrawVeil(card, newPile);
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
