using MegaCrit.Sts2.Core.Entities.Creatures;
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
        SavedPropertiesTypeCache.InjectTypeIntoCache(typeof(CurseRemover));
#endif
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
}
