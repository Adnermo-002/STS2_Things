using System.Reflection;
using System.Runtime.Loader;
using HarmonyLib;

if (args.Length is < 2 or > 3)
{
    Console.Error.WriteLine(
        "Usage: HarmonyTargetProbe <sts2-data-dir> <mod-dll> [dependency-data-dir]");
    return 2;
}

var dataDirectories = args
    .Where((_, index) => index != 1)
    .Select(Path.GetFullPath)
    .Distinct(StringComparer.OrdinalIgnoreCase)
    .ToArray();
var modDll = Path.GetFullPath(args[1]);
var gameDll = Path.Combine(dataDirectories[0], "sts2.dll");

if (!File.Exists(gameDll) || !File.Exists(modDll))
{
    Console.Error.WriteLine($"Missing probe input: game={gameDll}, mod={modDll}");
    return 2;
}

AssemblyLoadContext.Default.Resolving += (_, name) =>
{
    var loaded = AppDomain.CurrentDomain.GetAssemblies()
        .FirstOrDefault(assembly => assembly.GetName().Name == name.Name);
    if (loaded != null)
        return loaded;

    foreach (var directory in dataDirectories)
    {
        var candidate = Path.Combine(directory, $"{name.Name}.dll");
        if (File.Exists(candidate))
            return AssemblyLoadContext.Default.LoadFromAssemblyPath(candidate);
    }
    return null;
};

try
{
    var gameAssembly = AssemblyLoadContext.Default.LoadFromAssemblyPath(gameDll);
    var modAssembly = AssemblyLoadContext.Default.LoadFromAssemblyPath(modDll);
    var harmony = new Harmony($"Adnermo.STS2_Things.TargetProbe.{Guid.NewGuid():N}");
    harmony.PatchAll(modAssembly);

    var savedCache = gameAssembly.GetType("MegaCrit.Sts2.Core.Saves.Runs.SavedPropertiesTypeCache");
    if (savedCache?.GetMethod("Init", BindingFlags.Public | BindingFlags.Static) == null)
    {
        var compatibilityType = modAssembly.GetType(
            "STS2_Things.Compatibility.Sts2VersionCompatibility", throwOnError: true)!;
        compatibilityType.GetMethod(
                "InitializeBeforeModelDatabase",
                BindingFlags.Public | BindingFlags.Static)!
            .Invoke(null, null);
        var curseRemover = modAssembly.GetType("STS2_Things.Relics.CurseRemover", throwOnError: true)!;
        var properties = (IEnumerable<PropertyInfo>?)savedCache!
            .GetMethod("GetJsonPropertiesForType", BindingFlags.Public | BindingFlags.Static)!
            .Invoke(null, [curseRemover]);
        if (properties?.Any(property => property.Name == "TimesUsed") != true)
            throw new InvalidOperationException("V107.1 SavedProperty cache is missing CurseRemover.TimesUsed.");
        Console.WriteLine("V107.1 SavedProperty bridge: PASS");
    }

    Console.WriteLine($"Harmony target probe: PASS ({modAssembly.GetName().Version})");
    return 0;
}
catch (Exception exception)
{
    Console.Error.WriteLine("Harmony target probe: FAIL");
    Console.Error.WriteLine(exception);
    return 1;
}
