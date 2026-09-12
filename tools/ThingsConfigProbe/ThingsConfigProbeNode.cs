using System.Collections;
using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
using Godot;
using GodotFileAccess = Godot.FileAccess;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Acts;
using MegaCrit.Sts2.Core.TestSupport;
using STS2_Things;
using STS2_Things.Config;
using STS2_Things.Encounters;
using STS2_Things.Events;

public partial class ThingsConfigProbeNode : Node
{
    public override void _Ready()
    {
        try
        {
            TestMode.TurnOnInternal();
            MountPublishedPck();
            Assembly implementationAssembly = typeof(STS2_ThingsInit).Assembly;
            AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency;
            EnsureRuntimeDependency("System.IO.Hashing");
            RegisterSyntheticMod(implementationAssembly);
            STS2_ThingsInit.Initialize();
            InitializeModelDb(implementationAssembly);

            // 归一化：清掉上次探针运行遗留的配置写入，从默认值开始。
            ResetAll();
            ThingsModConfig.Save();

            VerifyConfigDefaultsAndFile();
            VerifyConfigRoundTrip();
            VerifyConflictRule();
            VerifyForceImpliesEnabled();
            VerifyCatalogGating();
            VerifyBossForcing();
            VerifyEventGating();

            GD.Print("Things config probe: PASS");
            GetTree().Quit(0);
        }
        catch (Exception exception)
        {
            GD.PushError(exception.ToString());
            GetTree().Quit(1);
        }
    }

    // ---- 配置模型 ----

    private static void VerifyConfigDefaultsAndFile()
    {
        foreach (ThingsModConfig.Entry entry in ThingsModConfig.Entries)
        {
            Assert(ThingsModConfig.GetBool(entry.Key) == entry.Default,
                $"{entry.Key} default is {ThingsModConfig.GetBool(entry.Key)}, expected {entry.Default}.");
        }

        string path = ThingsModConfig.ConfigPath;
        Assert(File.Exists(path), $"Config file was not created at {path}.");
        using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
        Assert(document.RootElement.ValueKind == JsonValueKind.Object, "Config file is not an object.");
        foreach (ThingsModConfig.Entry entry in ThingsModConfig.Entries)
        {
            Assert(document.RootElement.TryGetProperty(entry.Key, out _),
                $"Config file misses key {entry.Key}.");
        }

        Assert(document.RootElement.TryGetProperty(ThingsModConfig.SchemaVersion, out JsonElement schema) &&
              schema.ValueKind == JsonValueKind.True,
            "Config file misses SchemaVersion=true.");
    }

    private static void VerifyConfigRoundTrip()
    {
        ThingsModConfig.SetValue(ThingsModConfig.BossOriginFogmogEnabled, false);
        ThingsModConfig.Save();
        using JsonDocument document = JsonDocument.Parse(File.ReadAllText(ThingsModConfig.ConfigPath));
        Assert(document.RootElement.GetProperty(ThingsModConfig.BossOriginFogmogEnabled).GetBoolean() == false,
            "Config file did not persist BossOriginFogmogEnabled=false.");
        ThingsModConfig.Load();
        Assert(!ThingsModConfig.IsEnabled(ThingsModConfig.BossOriginFogmogEnabled),
            "Load() did not restore BossOriginFogmogEnabled=false.");
        ResetAll();
    }

    private static void VerifyConflictRule()
    {
        // 同槽位（Overgrowth）两个强制：规范顺序先到先得，后者降级。
        ThingsModConfig.SetValue(ThingsModConfig.BossOriginFogmogForced, true);
        ThingsModConfig.SetValue(ThingsModConfig.BossScaleBeetleForced, true);
        Assert(ThingsModConfig.IsForced(ThingsModConfig.BossOriginFogmogForced),
            "First forced boss (Origin Fogmog) was demoted.");
        Assert(!ThingsModConfig.IsForced(ThingsModConfig.BossScaleBeetleForced),
            "Second forced boss (Scale Beetle) was not demoted.");
        Assert(ThingsModConfig.GetForcedBossKeyForSlot(ThingsModConfig.SlotOvergrowth) ==
               ThingsModConfig.BossOriginFogmogForced,
            "Overgrowth slot reports the wrong forced boss.");
        Assert(!ThingsModConfig.CanForce(ThingsModConfig.BossScaleBeetleForced),
            "CanForce(Scale Beetle) must be false while Origin Fogmog is forced.");
        Assert(ThingsModConfig.CanForce(ThingsModConfig.BossOriginFogmogForced),
            "CanForce(Origin Fogmog) must stay true.");

        // 不同槽位可同时强制。
        ThingsModConfig.SetValue(ThingsModConfig.BossGravetideSlugForced, true);
        Assert(ThingsModConfig.IsForced(ThingsModConfig.BossGravetideSlugForced),
            "Gravetide Slug (Underdocks) was demoted by an Overgrowth force.");
        Assert(ThingsModConfig.GetForcedBossKeyForSlot(ThingsModConfig.SlotUnderdocks) ==
               ThingsModConfig.BossGravetideSlugForced,
            "Underdocks slot reports the wrong forced boss.");
        ResetAll();
    }

    private static void VerifyForceImpliesEnabled()
    {
        ThingsModConfig.SetValue(ThingsModConfig.BossCaveGodEnabled, false);
        ThingsModConfig.SetValue(ThingsModConfig.BossCaveGodForced, true);
        Assert(ThingsModConfig.IsEnabled(ThingsModConfig.BossCaveGodEnabled),
            "Forcing Cave God must imply enabled.");
        ResetAll();
    }


    // ---- 门控集成（补丁已随 STS2_ThingsInit.Initialize 安装）----

    private static void VerifyCatalogGating()
    {
        Overgrowth act = (Overgrowth)ModelDb.Act<Overgrowth>().ToMutable();
        List<EncounterModel> encounters = act.GenerateAllEncounters().ToList();
        Assert(encounters.Any(e => e.Id == ModelDb.Encounter<OriginFogmogBossEncounter>().Id),
            "Origin Fogmog is missing from the default Overgrowth encounter pool.");
        Assert(encounters.Any(e => e.Id == ModelDb.Encounter<ScaleBeetleBossEncounter>().Id),
            "Scale Beetle is missing from the default Overgrowth encounter pool.");

        ThingsModConfig.SetValue(ThingsModConfig.BossOriginFogmogEnabled, false);
        encounters = act.GenerateAllEncounters().ToList();
        Assert(encounters.All(e => e.Id != ModelDb.Encounter<OriginFogmogBossEncounter>().Id),
            "Disabled Origin Fogmog is still in the Overgrowth encounter pool.");
        Assert(encounters.Any(e => e.Id == ModelDb.Encounter<ScaleBeetleBossEncounter>().Id),
            "Disabling Origin Fogmog removed Scale Beetle.");
        ResetAll();
    }

    private static void VerifyBossForcing()
    {
        Overgrowth act = (Overgrowth)ModelDb.Act<Overgrowth>().ToMutable();
        ThingsModConfig.SetValue(ThingsModConfig.BossScaleBeetleForced, true);
        List<EncounterModel> bosses = act.BossDiscoveryOrder.ToList();
        Assert(bosses.Count == 1 &&
               bosses[0].Id == ModelDb.Encounter<ScaleBeetleBossEncounter>().Id,
            $"Forced Scale Beetle produced {bosses.Count} boss candidate(s); expected only Scale Beetle.");
        ResetAll();

        // 无强制时：禁用项从 Boss 候选移除，其余保留。
        ThingsModConfig.SetValue(ThingsModConfig.BossOriginFogmogEnabled, false);
        bosses = act.BossDiscoveryOrder.ToList();
        Assert(bosses.All(b => b.Id != ModelDb.Encounter<OriginFogmogBossEncounter>().Id),
            "Disabled Origin Fogmog is still a boss candidate.");
        Assert(bosses.Any(b => b.Id == ModelDb.Encounter<ScaleBeetleBossEncounter>().Id),
            "Disabling Origin Fogmog removed Scale Beetle from boss candidates.");
        ResetAll();
    }

    private static void VerifyEventGating()
    {
        Overgrowth act = (Overgrowth)ModelDb.Act<Overgrowth>().ToMutable();
        List<EventModel> events = act.AllEvents.ToList();
        Assert(events.Any(e => e.Id == ModelDb.Event<ThingsBackrooms>().Id),
            "The ThingsBackrooms event is missing from the default Overgrowth events.");
        Assert(events.Any(e => e.Id == ModelDb.Event<CuttingItClose>().Id),
            "Cutting It Close is missing from the default Overgrowth events.");

        ThingsModConfig.SetValue(ThingsModConfig.EventBackroomsEnabled, false);
        events = act.AllEvents.ToList();
        Assert(events.All(e => e.Id != ModelDb.Event<ThingsBackrooms>().Id),
            "The disabled ThingsBackrooms event is still offered in Overgrowth events.");
        Assert(events.Any(e => e.Id == ModelDb.Event<CuttingItClose>().Id),
            "Disabling the ThingsBackrooms event removed Cutting It Close.");
        ResetAll();

        Hive hive = (Hive)ModelDb.Act<Hive>().ToMutable();
        Assert(hive.AllEvents.Any(e => e.Id == ModelDb.Event<ThingsMedusa>().Id),
            "The ThingsMedusa event is missing from the default Hive events.");
        ThingsModConfig.SetValue(ThingsModConfig.EventMedusaEnabled, false);
        Assert(hive.AllEvents.All(e => e.Id != ModelDb.Event<ThingsMedusa>().Id),
            "The disabled ThingsMedusa event is still offered in Hive events.");
        ResetAll();
    }

    private static void ResetAll()
    {
        foreach (ThingsModConfig.Entry entry in ThingsModConfig.Entries)
            ThingsModConfig.SetValue(entry.Key, entry.Default);
    }

    // ---- 脚手架（沿用 ModelId 探针模式）----

    private static void MountPublishedPck()
    {
        string[] args = OS.GetCmdlineUserArgs();
        Assert(args.Length == 1, "Probe requires an absolute PCK path.");
        Assert(ProjectSettings.LoadResourcePack(args[0], replaceFiles: true),
            $"Could not mount published PCK: {args[0]}");
    }

    private static void RegisterSyntheticMod(Assembly implementationAssembly)
    {
        IList mods = (IList)typeof(ModManager).GetField("_mods", BindingFlags.NonPublic | BindingFlags.Static)!
            .GetValue(null)!;
        mods.Clear();
        mods.Add(CreateSyntheticMod("STS2_Things", "STS2_Things Config Probe", implementationAssembly));
    }

    private static object CreateSyntheticMod(string id, string name, Assembly assembly)
    {
        Assembly gameAssembly = typeof(ModManager).Assembly;
        Type modType = gameAssembly.GetType("MegaCrit.Sts2.Core.Modding.Mod", throwOnError: true)!;
        Type manifestType = gameAssembly.GetType("MegaCrit.Sts2.Core.Modding.ModManifest", throwOnError: true)!;
        object mod = Activator.CreateInstance(modType)!;
        object manifest = Activator.CreateInstance(manifestType)!;
        manifestType.GetField("id")!.SetValue(manifest, id);
        manifestType.GetField("name")?.SetValue(manifest, name);
        manifestType.GetField("affectsGameplay")?.SetValue(manifest, true);
        modType.GetField("path")!.SetValue(mod, $"probe://{id}");
        modType.GetField("manifest")!.SetValue(mod, manifest);
        FieldInfo state = modType.GetField("state")!;
        state.SetValue(mod, Enum.Parse(state.FieldType, "Loaded"));
        if (modType.GetField("assemblies")?.GetValue(mod) is IList assemblies)
            assemblies.Add(assembly);
        else
            modType.GetField("assembly")!.SetValue(mod, assembly);
        return mod;
    }

    private static void InitializeModelDb(Assembly implementationAssembly)
    {
        Type[] implementationTypes = implementationAssembly.GetTypes();
        Type[] modTypes = implementationTypes;
        Type[] modelTypes = [
            .. AbstractModelSubtypes.All,
            .. implementationTypes.Where(type => !type.IsAbstract && typeof(AbstractModel).IsAssignableFrom(type))
        ];
        modelTypes = modelTypes.Distinct().ToArray();
        typeof(ReflectionHelper).GetField("_modTypes", BindingFlags.NonPublic | BindingFlags.Static)!
            .SetValue(null, modTypes);
        SetModManagerStateInitialized();
        Type? assemblyInfo = typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Modding.AssemblyInfo");
        assemblyInfo?.GetMethod("Init", BindingFlags.Public | BindingFlags.Static)?.Invoke(null, null);
        typeof(ModelDb).GetMethod("ResetForTest", BindingFlags.Public | BindingFlags.Static)?
            .Invoke(null, null);
        MethodInfo init = typeof(ModelDb).GetMethods(BindingFlags.Public | BindingFlags.Static)
            .Single(method => method.Name == "Init");
        init.Invoke(null, init.GetParameters().Length == 0 ? null : [modelTypes]);
        Type serializationCache = typeof(ModelDb).Assembly.GetType(
            "MegaCrit.Sts2.Core.Multiplayer.Serialization.ModelIdSerializationCache",
            throwOnError: true)!;
        serializationCache.GetMethod("Init", BindingFlags.Public | BindingFlags.Static)!
            .Invoke(null, null);
        typeof(ModelDb).GetMethod("InitIds", BindingFlags.Public | BindingFlags.Static)!
            .Invoke(null, null);
    }

    private static void SetModManagerStateInitialized()
    {
        PropertyInfo? state = typeof(ModManager).GetProperty("State", BindingFlags.Public | BindingFlags.Static);
        if (state != null)
        {
            state.SetValue(null, Enum.Parse(state.PropertyType, "Initialized"));
        }
    }

    private static void EnsureRuntimeDependency(string assemblyName)
    {
        if (AppDomain.CurrentDomain.GetAssemblies().Any(
                assembly => string.Equals(assembly.GetName().Name, assemblyName, StringComparison.Ordinal)))
        {
            return;
        }

        string? path = FindRuntimeDependencyPath(assemblyName);
        if (path != null)
            AssemblyLoadContext.Default.LoadFromAssemblyPath(path);
    }

    private static Assembly? ResolveRuntimeDependency(AssemblyLoadContext context, AssemblyName assemblyName)
    {
        if (string.IsNullOrWhiteSpace(assemblyName.Name))
            return null;
        string? path = FindRuntimeDependencyPath(assemblyName.Name);
        return path == null ? null : context.LoadFromAssemblyPath(path);
    }

    private static string? FindRuntimeDependencyPath(string assemblyName)
    {
        string projectRoot = ProjectSettings.GlobalizePath("res://");
        string? assemblyDirectory = Path.GetDirectoryName(typeof(ThingsConfigProbeNode).Assembly.Location);
        string[] candidates =
        [
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", "Debug", $"{assemblyName}.dll"),
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", "Release", $"{assemblyName}.dll"),
            Path.Combine(assemblyDirectory ?? string.Empty, $"{assemblyName}.dll"),
        ];
        return candidates.FirstOrDefault(File.Exists);
    }

    private static void Assert(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException("Things config probe: " + message);
    }
}
