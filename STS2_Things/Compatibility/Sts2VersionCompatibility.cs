using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Saves.Runs;
using STS2_Things.Relics;

namespace STS2_Things.Compatibility;

internal static class Sts2VersionCompatibility
{
    // V107.1 can return a non-null wrapper for an empty native track. Normalize
    // it before reading: calling through that wrapper dereferences a null object.
    // V111 already returns null for an empty track and owns disposable wrappers.
    public static IDisposable? TrackEntryScope(MegaTrackEntry? entry, out MegaTrackEntry? track)
    {
        if (entry?.BoundObject == null || !GodotObject.IsInstanceValid(entry.BoundObject))
        {
            track = null;
            return null;
        }
        track = entry;
        return (object?)entry as IDisposable;
    }

#if STS2_V107_1
    // The native Spine API exists in both versions; only the C# binding is new.
    public static Transform2D? GetGlobalBoneTransform(this MegaSprite sprite, string name)
    {
        using Variant transform = sprite.BoundObject.Call("get_global_bone_transform", name);
        return transform.VariantType == Variant.Type.Nil ? null : transform.AsTransform2D();
    }
#endif

    public static void InitializeBeforeModelDatabase()
    {
#if STS2_V107_1
        // V107.1 caches only base-game SavedProperty owners. TimesUsed is already
        // a native property name, so adding this owner keeps the network ID map
        // and bit width unchanged while enabling save/clone serialization.
        SavedPropertiesTypeCache.InjectTypeIntoCache(typeof(ThingsCurseRemover));
        SavedPropertiesTypeCache.InjectTypeIntoCache(typeof(STS2_Things.Modifiers.ThingsCrossroads));
        // Register the receipt's card snapshot, act index and redeemed flag on
        // every peer before calculating the legacy saved-property ID bit width.
        SavedPropertiesTypeCache.InjectTypeIntoCache(typeof(ShadowClaimTicket));
        SavedPropertiesTypeCache.InjectTypeIntoCache(typeof(BottledEcho));
        SavedPropertiesTypeCache.InjectTypeIntoCache(typeof(MycelialDeposit));
        SavedPropertiesTypeCache.InjectTypeIntoCache(typeof(BorrowedEmber));
        // The route ledger introduces a saved string property in V107. Keep the
        // native property-ID bit width consistent after extending that cache.
        var names = (System.Collections.ICollection)typeof(SavedPropertiesTypeCache)
            .GetField("_netIdToPropertyNameMap", System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic)!
            .GetValue(null)!;
        typeof(SavedPropertiesTypeCache).GetProperty(nameof(SavedPropertiesTypeCache.NetIdBitSize))!
            .SetValue(null, (int)Math.Ceiling(Math.Log2(names.Count)));
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
