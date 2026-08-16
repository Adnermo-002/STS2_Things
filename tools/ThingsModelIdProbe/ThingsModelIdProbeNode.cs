using System.Collections;
using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
using Godot;
using GodotFileAccess = Godot.FileAccess;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.CardPools;
using MegaCrit.Sts2.Core.Models.RelicPools;
using MegaCrit.Sts2.Core.TestSupport;
using STS2_Things;
using STS2_Things.Cards;
using STS2_Things.Enchantments;
using STS2_Things.Encounters;
using STS2_Things.Events;
using STS2_Things.Monsters;
using STS2_Things.Powers;
using STS2_Things.Relics;

namespace Hoursmod
{
    public sealed class Recall : CardModel
    {
        public Recall() : base(1, CardType.Skill, CardRarity.Common, TargetType.Self)
        {
        }
    }
}

public partial class ThingsModelIdProbeNode : Node
{
    private sealed record ModelExpectation(
        Type Type,
        string Category,
        string Entry,
        string LocalizationTable,
        string LocalizationSuffix);

    private static readonly ModelExpectation[] RenamedModels =
    [
        new(typeof(ThingsRecall), "CARD", "THINGS_RECALL", "cards", "title"),
        new(typeof(ThingsReuse), "CARD", "THINGS_REUSE", "cards", "title"),
        new(typeof(ThingsSurrender), "CARD", "THINGS_SURRENDER", "cards", "title"),
        new(typeof(ThingsPackUp), "CARD", "THINGS_PACK_UP", "cards", "title"),
        new(typeof(ThingsDisperse), "ENCHANTMENT", "THINGS_DISPERSE", "enchantments", "title"),
        new(typeof(ThingsBackrooms), "EVENT", "THINGS_BACKROOMS", "events", "title"),
        new(typeof(ThingsMedusa), "EVENT", "THINGS_MEDUSA", "events", "title"),
        new(typeof(ThingsAlmondWater), "RELIC", "THINGS_ALMOND_WATER", "relics", "title"),
        new(typeof(ThingsCurseRemover), "RELIC", "THINGS_CURSE_REMOVER", "relics", "title"),
        new(typeof(ThingsMagicGlove), "RELIC", "THINGS_MAGIC_GLOVE", "relics", "title"),
        new(typeof(ThingsMedusaHair), "RELIC", "THINGS_MEDUSA_HAIR", "relics", "title"),
        new(typeof(ThingsWhiteFlag), "RELIC", "THINGS_WHITE_FLAG", "relics", "title"),
        new(typeof(ThingsDazedPower), "POWER", "THINGS_DAZED_POWER", "powers", "title"),
        new(typeof(ThingsOriginPower), "POWER", "THINGS_ORIGIN_POWER", "powers", "title"),
        new(typeof(ThingsQuirkPower), "POWER", "THINGS_QUIRK_POWER", "powers", "title"),
        new(typeof(ThingsRecallPower), "POWER", "THINGS_RECALL_POWER", "powers", "title"),
        new(typeof(ThingsReusePower), "POWER", "THINGS_REUSE_POWER", "powers", "title"),
        new(typeof(ThingsScaleBeetlePower), "POWER", "THINGS_SCALE_BEETLE_POWER", "powers", "title"),
        new(typeof(ThingsScaleDownPower), "POWER", "THINGS_SCALE_DOWN_POWER", "powers", "title"),
        new(typeof(ThingsScaleUpPower), "POWER", "THINGS_SCALE_UP_POWER", "powers", "title"),
        new(typeof(ThingsScaleBeetle), "MONSTER", "THINGS_SCALE_BEETLE", "monsters", "name"),
        new(typeof(ThingsTheLegacy), "MONSTER", "THINGS_THE_LEGACY", "monsters", "name")
    ];

    private static Type _hoursmodRecallType = typeof(Hoursmod.Recall);

    public override void _Ready()
    {
        try
        {
            TestMode.TurnOnInternal();
            MountPublishedPck();
            Assembly implementationAssembly = typeof(STS2_ThingsInit).Assembly;
            AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency;
            EnsureRuntimeDependency("System.IO.Hashing");
            RegisterSyntheticMods(implementationAssembly);
            STS2_ThingsInit.Initialize();
            InitializeModelDb(implementationAssembly);
            VerifyHoursmodFixtureCoexists();
            VerifyRenamedModelIds();
            VerifyPools();
            VerifyLocalization();
            VerifyDerivedResources();
            GD.Print("Things ModelId namespace probe: PASS");
            GetTree().Quit(0);
        }
        catch (Exception exception)
        {
            GD.PushError(exception.ToString());
            GetTree().Quit(1);
        }
    }

    private static void MountPublishedPck()
    {
        string[] args = OS.GetCmdlineUserArgs();
        Assert(args.Length is 1 or 2,
            "Probe requires an absolute PCK path and accepts an optional Hoursmod DLL path.");
        Assert(ProjectSettings.LoadResourcePack(args[0], replaceFiles: true),
            $"Could not mount published PCK: {args[0]}");
        if (args.Length == 2)
        {
            string hoursmodDll = Path.GetFullPath(args[1]);
            Assert(File.Exists(hoursmodDll), $"Actual Hoursmod DLL was not found: {hoursmodDll}");
            AssemblyLoadContext loadContext = AssemblyLoadContext.GetLoadContext(typeof(ModelDb).Assembly)
                ?? AssemblyLoadContext.Default;
            Assembly assembly = loadContext.LoadFromAssemblyPath(hoursmodDll);
            Type? recallType = assembly.GetType("Hoursmod.Recall", throwOnError: false);
            if (recallType == null || !typeof(CardModel).IsAssignableFrom(recallType))
            {
                string actualBase = recallType?.BaseType?.AssemblyQualifiedName ?? "<missing>";
                throw new InvalidOperationException(
                    $"Actual Hoursmod Recall base does not bind to the active CardModel. " +
                    $"Expected {typeof(CardModel).AssemblyQualifiedName}; actual {actualBase}; DLL={hoursmodDll}");
            }
            _hoursmodRecallType = recallType;
            GD.Print($"ModelId probe loaded actual Hoursmod fixture: {hoursmodDll}");
        }
    }

    private static void InitializeModelDb(Assembly implementationAssembly)
    {
        Type[] implementationTypes = implementationAssembly.GetTypes();
        Type[] modTypes = implementationTypes.Concat([_hoursmodRecallType]).ToArray();
        Type[] modelTypes = [
            _hoursmodRecallType,
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

    private static void VerifyHoursmodFixtureCoexists()
    {
        ModelId hoursmodId = ModelDb.GetId(_hoursmodRecallType);
        ModelId thingsId = ModelDb.GetId<ThingsRecall>();
        Assert(hoursmodId.ToString() == "CARD.RECALL", $"Hoursmod fixture ID drifted to {hoursmodId}.");
        Assert(thingsId.ToString() == "CARD.THINGS_RECALL", $"Things Recall ID drifted to {thingsId}.");
        Assert(ModelDb.GetById<CardModel>(hoursmodId).GetType() == _hoursmodRecallType,
            "Hoursmod fixture was overwritten by Things Recall.");
        Assert(ModelDb.Card<ThingsRecall>().GetType() == typeof(ThingsRecall),
            "Things Recall was overwritten by Hoursmod fixture.");
    }

    private static void VerifyRenamedModelIds()
    {
        foreach (ModelExpectation expectation in RenamedModels)
        {
            ModelId id = ModelDb.GetId(expectation.Type);
            Assert(id.Category == expectation.Category && id.Entry == expectation.Entry,
                $"{expectation.Type.FullName} generated {id}, expected " +
                $"{expectation.Category}.{expectation.Entry}.");
            AbstractModel canonical = ModelDb.GetById<AbstractModel>(id);
            Assert(canonical.GetType() == expectation.Type,
                $"{id} resolves to {canonical.GetType().FullName}, expected {expectation.Type.FullName}.");
        }
    }

    private static void VerifyPools()
    {
        VerifyCardPool<DefectCardPool, ThingsReuse>();
        VerifyCardPool<EventCardPool, ThingsSurrender>();
        VerifyCardPool<SilentCardPool, ThingsRecall>();
        VerifyCardPool<SilentCardPool, ThingsPackUp>();
        VerifyRelicPool<EventRelicPool, ThingsWhiteFlag>();
        VerifyRelicPool<EventRelicPool, ThingsCurseRemover>();
        VerifyRelicPool<EventRelicPool, ThingsMagicGlove>();
        VerifyRelicPool<EventRelicPool, ThingsAlmondWater>();
        VerifyRelicPool<EventRelicPool, ThingsMedusaHair>();
    }

    private static void VerifyCardPool<TPool, TCard>()
        where TPool : CardPoolModel
        where TCard : CardModel
    {
        Assert(ModelDb.CardPool<TPool>().AllCards.Any(card => card is TCard),
            $"{typeof(TCard).Name} is missing from {typeof(TPool).Name}.");
    }

    private static void VerifyRelicPool<TPool, TRelic>()
        where TPool : RelicPoolModel
        where TRelic : RelicModel
    {
        Assert(ModelDb.RelicPool<TPool>().AllRelics.Any(relic => relic is TRelic),
            $"{typeof(TRelic).Name} is missing from {typeof(TPool).Name}.");
    }

    private static void VerifyLocalization()
    {
        foreach (string language in new[] { "eng", "zhs" })
        {
            var tables = new Dictionary<string, JsonDocument>(StringComparer.Ordinal);
            try
            {
                foreach (ModelExpectation expectation in RenamedModels)
                {
                    if (!tables.TryGetValue(expectation.LocalizationTable, out JsonDocument? document))
                    {
                        string path = $"res://STS2_Things/localization/{language}/{expectation.LocalizationTable}.json";
                        Assert(GodotFileAccess.FileExists(path), $"Missing localization table in PCK: {path}");
                        document = JsonDocument.Parse(GodotFileAccess.GetFileAsString(path));
                        tables.Add(expectation.LocalizationTable, document);
                    }

                    string key = $"{expectation.Entry}.{expectation.LocalizationSuffix}";
                    Assert(document.RootElement.TryGetProperty(key, out JsonElement value) &&
                           value.ValueKind == JsonValueKind.String &&
                           !string.IsNullOrWhiteSpace(value.GetString()),
                        $"Missing non-empty localization key {key} in {language}/{expectation.LocalizationTable}.json.");

                    string legacyEntry = expectation.Entry["THINGS_".Length..];
                    Assert(!document.RootElement.EnumerateObject().Any(
                            property => property.Name.StartsWith(legacyEntry + ".", StringComparison.Ordinal)),
                        $"Legacy localization keys remain for {legacyEntry} in {language}/{expectation.LocalizationTable}.json.");
                }
            }
            finally
            {
                foreach (JsonDocument document in tables.Values)
                {
                    document.Dispose();
                }
            }
        }
    }

    private static void VerifyDerivedResources()
    {
        VerifyTexture("res://images/packed/card_portraits/defect/things_reuse.png");
        VerifyTexture("res://images/packed/card_portraits/event/things_surrender.png");
        VerifyTexture("res://images/packed/card_portraits/silent/things_recall.png");
        VerifyTexture("res://images/packed/card_portraits/silent/things_pack_up.png");
        VerifyTexture("res://images/enchantments/things_disperse.png");
        VerifyTexture("res://images/events/things_backrooms.png");
        VerifyTexture("res://images/events/things_medusa.png");

        foreach (RelicModel relic in new RelicModel[]
                 {
                     ModelDb.Relic<ThingsAlmondWater>(),
                     ModelDb.Relic<ThingsCurseRemover>(),
                     ModelDb.Relic<ThingsMagicGlove>(),
                     ModelDb.Relic<ThingsMedusaHair>(),
                     ModelDb.Relic<ThingsWhiteFlag>()
                 })
        {
            Assert(relic.PackedIconPath.Contains("/things_", StringComparison.Ordinal),
                $"{relic.GetType().Name} still derives an unprefixed icon path: {relic.PackedIconPath}");
            VerifyTexture(relic.PackedIconPath);
        }

        foreach (PowerModel power in new PowerModel[]
                 {
                     ModelDb.Power<ThingsDazedPower>(),
                     ModelDb.Power<ThingsOriginPower>(),
                     ModelDb.Power<ThingsQuirkPower>(),
                     ModelDb.Power<ThingsRecallPower>(),
                     ModelDb.Power<ThingsReusePower>(),
                     ModelDb.Power<ThingsScaleBeetlePower>(),
                     ModelDb.Power<ThingsScaleDownPower>(),
                     ModelDb.Power<ThingsScaleUpPower>()
                 })
        {
            Assert(power.ResolvedBigIconPath.Contains("/things_", StringComparison.Ordinal),
                $"{power.GetType().Name} still derives an unprefixed icon path: {power.ResolvedBigIconPath}");
            VerifyTexture(power.ResolvedBigIconPath);
        }

        VerifyScene("res://scenes/creature_visuals/things_scale_beetle.tscn");
        VerifyScene("res://scenes/creature_visuals/things_the_legacy.tscn");
    }

    private static void VerifyTexture(string path)
    {
        Assert(ResourceLoader.Load<Texture2D>(path) != null, $"Texture did not load from PCK: {path}");
    }

    private static void VerifyScene(string path)
    {
        Assert(ResourceLoader.Load<PackedScene>(path) != null, $"Scene did not load from PCK: {path}");
    }

    private static void RegisterSyntheticMods(Assembly implementationAssembly)
    {
        IList mods = (IList)typeof(ModManager).GetField("_mods", BindingFlags.NonPublic | BindingFlags.Static)!
            .GetValue(null)!;
        mods.Clear();
        mods.Add(CreateSyntheticMod("Hoursmod", "Hoursmod fixture", _hoursmodRecallType.Assembly));
        mods.Add(CreateSyntheticMod("STS2_Things", "STS2_Things ModelId Probe", implementationAssembly));
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
        {
            assemblies.Add(assembly);
        }
        else
        {
            modType.GetField("assembly")!.SetValue(mod, assembly);
        }

        return mod;
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
        {
            AssemblyLoadContext.Default.LoadFromAssemblyPath(path);
        }
    }

    private static Assembly? ResolveRuntimeDependency(AssemblyLoadContext context, AssemblyName assemblyName)
    {
        if (string.IsNullOrWhiteSpace(assemblyName.Name))
        {
            return null;
        }

        string? path = FindRuntimeDependencyPath(assemblyName.Name);
        return path == null ? null : context.LoadFromAssemblyPath(path);
    }

    private static string? FindRuntimeDependencyPath(string assemblyName)
    {
        string projectRoot = ProjectSettings.GlobalizePath("res://");
        string? assemblyDirectory = Path.GetDirectoryName(typeof(ThingsModelIdProbeNode).Assembly.Location);
        string[] candidates =
        [
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", "Debug", $"{assemblyName}.dll"),
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", "Release", $"{assemblyName}.dll"),
            Path.Combine(assemblyDirectory ?? string.Empty, $"{assemblyName}.dll")
        ];
        return candidates.FirstOrDefault(File.Exists);
    }

    private static void Assert(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }
}
