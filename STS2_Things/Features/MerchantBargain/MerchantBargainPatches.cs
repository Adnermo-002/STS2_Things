#if STS2_V111
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Nodes.Rooms;

namespace STS2_Things.Features.MerchantBargain;

[HarmonyPatch]
internal static class MerchantEntryOnTryPurchaseWrapperPatch
{
    private static MethodBase TargetMethod()
    {
        return AccessTools.Method(
            typeof(MerchantEntry),
            nameof(MerchantEntry.OnTryPurchaseWrapper),
            [typeof(MerchantInventory), typeof(bool)])
            ?? throw new MissingMethodException(
                typeof(MerchantEntry).FullName,
                nameof(MerchantEntry.OnTryPurchaseWrapper));
    }

    private static bool Prefix(
        MerchantEntry __instance,
        MerchantInventory? inventory,
        bool ignoreCost,
        ref Task<bool> __result)
    {
        if (!MerchantBargainManager.TryIntercept(
                __instance,
                inventory,
                ignoreCost,
                out Task<bool> bargainResult))
        {
            return true;
        }

        __result = bargainResult;
        return false;
    }
}

[HarmonyPatch]
internal static class MerchantEntryCostPatch
{
    private static MethodBase TargetMethod()
    {
        return AccessTools.PropertyGetter(typeof(MerchantEntry), nameof(MerchantEntry.Cost))
            ?? throw new MissingMethodException(typeof(MerchantEntry).FullName, nameof(MerchantEntry.Cost));
    }

    private static bool Prefix(MerchantEntry __instance, ref int __result)
    {
        if (!MerchantBargainManager.TryGetPriceOverride(__instance, out int price))
        {
            return true;
        }

        __result = price;
        return false;
    }
}

[HarmonyPatch(typeof(NMerchantRoom), nameof(NMerchantRoom.AssetPaths), MethodType.Getter)]
internal static class MerchantBargainAssetPreloadPatch
{
    [HarmonyPostfix]
    private static void Postfix(ref IEnumerable<string> __result)
    {
        __result = __result
            .Concat(MerchantBargainAssets.PreloadPaths)
            .Distinct(StringComparer.Ordinal);
    }
}
#endif
