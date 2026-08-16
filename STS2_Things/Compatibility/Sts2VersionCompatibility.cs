using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Saves.Runs;
using STS2_Things.Relics;

namespace STS2_Things.Compatibility;

internal static class Sts2VersionCompatibility
{
    public static void InitializeBeforeModelDatabase()
    {
#if STS2_V107_1
        // V107.1 caches only base-game SavedProperty owners. TimesUsed is already
        // a native property name, so adding this owner keeps the network ID map
        // and bit width unchanged while enabling save/clone serialization.
        SavedPropertiesTypeCache.InjectTypeIntoCache(typeof(ThingsCurseRemover));
#endif
        // V110 folds SavedProperty discovery into ModelIdSerializationCache.Init(),
        // which deterministically scans every model after ModelDb.Init().
    }

    public static void SetCreatureNodeVisible(Creature creature, bool visible)
    {
#if STS2_V107_1
        var node = creature.GetCreatureNode();
        if (node != null)
            node.Visible = visible;
#else
        creature.SetNodeVisible(visible);
#endif
    }

    /// <summary>
    /// Removes a living combat object without firing death hooks or recording
    /// an escape. This follows CreatureCmd.Escape's cleanup order while keeping
    /// consumed encounter objects out of escaped-creature reward accounting.
    /// </summary>
    public static void RemoveCreatureWithoutDeathOrEscape(Creature creature)
    {
        if (creature.IsDead)
            return;

        var combatState = creature.CombatState;
        if (combatState == null || !combatState.IsLiveCombat() ||
            !combatState.ContainsCreature(creature))
            return;

        creature.RemoveAllPowersInternalExcept();

#if STS2_V107_1
        var node = creature.GetCreatureNode();
#else
        var node = NCombatRoom.Instance?.GetCreatureNode(creature);
#endif
        if (node != null)
        {
            NCombatRoom.Instance?.RemoveCreatureNode(node);
            node.ToggleIsInteractable(on: false);
            node.Visible = false;
        }

        CombatManager.Instance.RemoveCreature(creature);
        combatState.RemoveCreature(creature);
    }
}
