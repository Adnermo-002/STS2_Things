using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using STS2_Things.Encounters;

namespace STS2_Things.Hooks;

/// <summary>Place the whole party on the forward floor of the authored Depths caves.</summary>
[HarmonyPatch(typeof(NCombatRoom), nameof(NCombatRoom.PositionPlayersAndPets))]
public static class MycorrhizalPlayerLayoutPatch
{
    public const float VerticalOffset = 60f;

    [HarmonyPostfix]
    private static void Postfix(List<NCreature> creatureNodes)
    {
        if (creatureNodes.FirstOrDefault()?.Entity?.CombatState?.Encounter is not
            (MycorrhizalTwinsElite or ReverseSalamanderElite or CaveMawWeak or CaveMawEncounter or RadioJellyfishElite or SnailTrioWeak))
            return;

        // The native method first resets the formation, including pets and rear
        // rows. Applying one shared offset preserves that arrangement on reflow.
        foreach (var creature in creatureNodes)
            creature.Position += Vector2.Down * VerticalOffset;
    }
}
