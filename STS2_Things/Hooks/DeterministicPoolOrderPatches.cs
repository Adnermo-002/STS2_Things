using HarmonyLib;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Modding;
#if !STS2_V107_1
using MegaCrit.Sts2.Core.Multiplayer.Serialization;
#endif

namespace STS2_Things.Hooks;

/// <summary>
///     V108 的 ModHelper 按 Mod 初始化顺序追加池内容，而联机只校验 Mod 集合、
///     不要求两端加载顺序相同。保留原版前缀顺序，仅用官方 ContentSorter 对原版池的
///     Mod 后缀排序，避免随机奖励把同一 RNG 索引映射到不同模型。
/// </summary>
internal static class DeterministicContentOrder
{
    public static IEnumerable<TModel> SortBaseThenMods<TModel>(IEnumerable<TModel> source)
        where TModel : AbstractModel
    {
#if STS2_V107_1
        var baseGameAssembly = typeof(AbstractModel).Assembly;
        var models = source.ToList();
        var output = models
            .Where(model => model.GetType().Assembly == baseGameAssembly)
            .ToList();
        output.AddRange(models
            .Where(model => model.GetType().Assembly != baseGameAssembly)
            .OrderBy(model => ModelDb.GetId(model.GetType()).Category, StringComparer.Ordinal)
            .ThenBy(model => ModelDb.GetId(model.GetType()).Entry, StringComparer.Ordinal)
            .ThenBy(model => model.GetType().Assembly.GetName().Name, StringComparer.Ordinal)
            .ThenBy(model => model.GetType().FullName, StringComparer.Ordinal));
        return output;
#else
        if (AssemblyInfo.BaseGame == null || AssemblyInfo.ModMap == null)
            return source;

        var models = source.ToList();
        var moddedModels = models
            .Where(model => model.GetType().Assembly != AssemblyInfo.BaseGame)
            .ToList();
        if (moddedModels.Count <= 1)
            return models;

        var instancesByType = moddedModels
            .GroupBy(model => model.GetType())
            .ToDictionary(group => group.Key, group => new Queue<TModel>(group));
        var sortedTypes = ContentSorter<ModelId>.Sort(
            moddedModels.Select(model => model.GetType()),
            ModelDb.GetId);

        var output = models
            .Where(model => model.GetType().Assembly == AssemblyInfo.BaseGame)
            .ToList();
        foreach (var item in sortedTypes)
            output.Add(instancesByType[item.type].Dequeue());
        return output;
#endif
    }

    public static IEnumerable<TModel> SortNativePool<TModel>(
        AbstractModel pool,
        IEnumerable<TModel> source)
        where TModel : AbstractModel
    {
#if STS2_V107_1
        return pool.GetType().Assembly == typeof(AbstractModel).Assembly
            ? SortBaseThenMods(source)
            : source;
#else
        return pool.GetType().Assembly == AssemblyInfo.BaseGame
            ? SortBaseThenMods(source)
            : source;
#endif
    }
}

[HarmonyPatch(typeof(CardPoolModel), nameof(CardPoolModel.AllCards), MethodType.Getter)]
internal static class DeterministicCardPoolOrderPatch
{
    [HarmonyPriority(Priority.Last)]
    private static void Postfix(CardPoolModel __instance, ref IEnumerable<CardModel> __result)
    {
        __result = DeterministicContentOrder.SortNativePool(__instance, __result);
    }
}

[HarmonyPatch(typeof(RelicPoolModel), nameof(RelicPoolModel.AllRelics), MethodType.Getter)]
internal static class DeterministicRelicPoolOrderPatch
{
    [HarmonyPriority(Priority.Last)]
    private static void Postfix(RelicPoolModel __instance, ref IEnumerable<RelicModel> __result)
    {
        __result = DeterministicContentOrder.SortNativePool(__instance, __result);
    }
}

[HarmonyPatch(typeof(PotionPoolModel), nameof(PotionPoolModel.AllPotions), MethodType.Getter)]
internal static class DeterministicPotionPoolOrderPatch
{
    [HarmonyPriority(Priority.Last)]
    private static void Postfix(PotionPoolModel __instance, ref IEnumerable<PotionModel> __result)
    {
        __result = DeterministicContentOrder.SortNativePool(__instance, __result);
    }
}
