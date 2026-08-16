using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Resources;
using System.Runtime.Loader;
using System.Security.Cryptography;

if (args.Length is < 4 or > 5)
{
    Console.Error.WriteLine(
        "Usage: UnifiedPackageProbe <sts2-data-dir> <bootstrap-dll> " +
        "<expected-target> <expected-implementation-dll> [dependency-data-dir]");
    return 2;
}

var dataDir = Path.GetFullPath(args[0]);
var bootstrapPath = Path.GetFullPath(args[1]);
var expectedTarget = args[2];
var expectedImplementationPath = Path.GetFullPath(args[3]);
var dependencyDirectories = args
    .Skip(4)
    .Prepend(dataDir)
    .Select(Path.GetFullPath)
    .Distinct(StringComparer.OrdinalIgnoreCase)
    .ToArray();
var gamePath = Path.Combine(dataDir, "sts2.dll");

if (!File.Exists(gamePath) ||
    !File.Exists(bootstrapPath) ||
    !File.Exists(expectedImplementationPath))
{
    Console.Error.WriteLine(
        $"Missing probe input: game={gamePath}, bootstrap={bootstrapPath}, " +
        $"implementation={expectedImplementationPath}");
    return 2;
}

var expectedResource = expectedTarget switch
{
    "v107.1" => "STS2_Things.Implementations.v107.1.dll",
    "v110" => "STS2_Things.Implementations.v110.dll",
    _ => throw new ArgumentOutOfRangeException(nameof(expectedTarget), expectedTarget, null)
};
const string expectedAssemblyName = "STS2_Things";
const int minimumReasonableModelCount = 50;
const int maximumReasonableModelCount = 80;
string[] requiredModelNames =
[
    "STS2_Things.Cards.ThingsCollision",
    "STS2_Things.Enchantments.ThingsDisperse",
    "STS2_Things.Enchantments.ThingsSplit",
    "STS2_Things.Events.ThingsBackrooms",
    "STS2_Things.Events.CuttingItClose",
    "STS2_Things.Events.ThingsMedusa",
    "STS2_Things.Events.RobberyFakeMerchant",
    "STS2_Things.Encounters.GravetideSlugBossEncounter",
    "STS2_Things.Encounters.OriginFogmogBossEncounter",
    "STS2_Things.Encounters.QuirkyHopperWeak",
    "STS2_Things.Modifiers.QuirkyHopperRewardPolicy",
    "STS2_Things.Monsters.GravetideCorpseSlug",
    "STS2_Things.Monsters.GravetideSlug",
    "STS2_Things.Monsters.GravetideSlugCorpse",
    "STS2_Things.Monsters.OriginFogmog",
    "STS2_Things.Monsters.QuirkyHopper",
    "STS2_Things.Monsters.ThingsTheLegacy",
    "STS2_Things.Powers.GravetideDigestionPower",
    "STS2_Things.Powers.GravetideMinionPower",
    "STS2_Things.Powers.ThingsQuirkPower"
];

try
{
    var loadContext = new ProbeLoadContext(dependencyDirectories);
    var gameAssembly = loadContext.LoadFromAssemblyPath(gamePath);
    var bootstrapAssembly = loadContext.LoadFromAssemblyPath(bootstrapPath);
    var bootstrapType = bootstrapAssembly.GetType(
        "STS2_Things.Bootstrap.UnifiedBootstrap", throwOnError: true)!;
    var selector = bootstrapType.GetMethod(
        "SelectImplementationResource", BindingFlags.Public | BindingFlags.Static)
        ?? throw new MissingMethodException(bootstrapType.FullName, "SelectImplementationResource");
    var selectedResource = (string?)selector.Invoke(null, [gameAssembly]);
    if (!string.Equals(selectedResource, expectedResource, StringComparison.Ordinal))
    {
        throw new InvalidOperationException(
            $"Target selection returned '{selectedResource}', expected '{expectedResource}'.");
    }

    var resources = bootstrapAssembly.GetManifestResourceNames()
        .Where(name => name.StartsWith(
            "STS2_Things.Implementations.", StringComparison.Ordinal))
        .Order(StringComparer.Ordinal)
        .ToArray();
    var expectedResources = new[]
    {
        "STS2_Things.Implementations.v107.1.dll",
        "STS2_Things.Implementations.v110.dll"
    };
    if (!resources.SequenceEqual(expectedResources, StringComparer.Ordinal))
    {
        throw new InvalidOperationException(
            $"Unexpected implementation resources: {string.Join(", ", resources)}");
    }

    using var implementationStream = bootstrapAssembly.GetManifestResourceStream(expectedResource)
        ?? throw new MissingManifestResourceException(expectedResource);
    var embeddedHash = Convert.ToHexString(SHA256.HashData(implementationStream));
    var expectedHash = Convert.ToHexString(SHA256.HashData(
        File.ReadAllBytes(expectedImplementationPath)));
    if (!string.Equals(embeddedHash, expectedHash, StringComparison.Ordinal))
        throw new InvalidOperationException($"Embedded {expectedTarget} implementation hash differs.");

    implementationStream.Position = 0;
    var implementationAssembly = loadContext.LoadFromStream(implementationStream);
    if (!string.Equals(
            implementationAssembly.GetName().Name,
            expectedAssemblyName,
            StringComparison.Ordinal))
    {
        throw new InvalidOperationException(
            $"Selected assembly is {implementationAssembly.GetName().Name}, " +
            $"expected {expectedAssemblyName}.");
    }
    if (implementationAssembly.GetName().Version != bootstrapAssembly.GetName().Version)
        throw new InvalidOperationException("Bootstrap and implementation versions differ.");

    var implementationTypes = GetLoadableTypes(implementationAssembly);
    var initializer = implementationAssembly.GetType(
        "STS2_ThingsInit", throwOnError: true)!;
    if (initializer.GetMethod("Initialize", BindingFlags.Public | BindingFlags.Static) is null)
        throw new MissingMethodException(initializer.FullName, "Initialize");

    var abstractModel = gameAssembly.GetType(
        "MegaCrit.Sts2.Core.Models.AbstractModel", throwOnError: true)!;
    var modelNames = implementationTypes
        .Where(type =>
            type != abstractModel &&
            !type.IsAbstract &&
            abstractModel.IsAssignableFrom(type))
        .Select(type => type.FullName ?? type.Name)
        .ToHashSet(StringComparer.Ordinal);
    var modelCount = modelNames.Count;
    if (modelCount is < minimumReasonableModelCount or > maximumReasonableModelCount)
    {
        throw new InvalidOperationException(
            $"Selected implementation exposes {modelCount} AbstractModel types; " +
            $"expected a total between {minimumReasonableModelCount} and " +
            $"{maximumReasonableModelCount}.");
    }

    var missingRequiredModels = requiredModelNames
        .Where(required => !modelNames.Contains(required))
        .Order(StringComparer.Ordinal)
        .ToArray();
    if (missingRequiredModels.Length > 0)
    {
        throw new InvalidOperationException(
            "Selected implementation is missing required models: " +
            string.Join(", ", missingRequiredModels));
    }

    var embeddedModelNames = expectedResources.ToDictionary(
        resource => resource,
        resource => ReadEmbeddedModelNames(bootstrapAssembly, resource),
        StringComparer.Ordinal);
    if (!embeddedModelNames[expectedResource].SetEquals(modelNames))
    {
        throw new InvalidOperationException(
            $"Runtime and metadata model sets differ for {expectedResource}: " +
            DescribeSetDifference(modelNames, embeddedModelNames[expectedResource]));
    }

    var v1071Models = embeddedModelNames["STS2_Things.Implementations.v107.1.dll"];
    var v110Models = embeddedModelNames["STS2_Things.Implementations.v110.dll"];
    if (!v1071Models.SetEquals(v110Models))
    {
        throw new InvalidOperationException(
            "V107.1 and V110 implementation model sets differ: " +
            DescribeSetDifference(v1071Models, v110Models));
    }

    var modManager = gameAssembly.GetType(
        "MegaCrit.Sts2.Core.Modding.ModManager", throwOnError: true)!;
    var savedPropertiesTypeCache = gameAssembly.GetType(
        "MegaCrit.Sts2.Core.Saves.Runs.SavedPropertiesTypeCache");
    if (expectedTarget == "v107.1")
    {
        if (savedPropertiesTypeCache is null)
            throw new InvalidOperationException("V107.1 SavedPropertiesTypeCache is missing.");
        foreach (var bridgeMethod in new[]
                 {
                     "AppendV1071ImplementationTypes",
                     "PromoteV1071ImplementationAssembly"
                 })
        {
            if (bootstrapType.GetMethod(
                    bridgeMethod, BindingFlags.NonPublic | BindingFlags.Static) is null)
                throw new MissingMethodException(bootstrapType.FullName, bridgeMethod);
        }
        VerifyLegacyRegistrationBridge(
            gameAssembly,
            bootstrapAssembly,
            bootstrapType,
            implementationAssembly,
            implementationTypes);
    }
    else
    {
        if (savedPropertiesTypeCache is not null)
            throw new InvalidOperationException("V110 still exposes SavedPropertiesTypeCache.");
        if (modManager.GetMethod(
                "AssociateAssemblyWithMod",
                BindingFlags.Public | BindingFlags.Static,
                binder: null,
                types: [typeof(string), typeof(Assembly)],
                modifiers: null) is null)
        {
            throw new MissingMethodException(
                modManager.FullName, "AssociateAssemblyWithMod(string, Assembly)");
        }
    }

    Console.WriteLine(
        $"Unified package probe: PASS ({expectedTarget}, {expectedAssemblyName}, " +
        $"models={modelCount}, sha256={embeddedHash})");
    return 0;
}
catch (Exception exception)
{
    Console.Error.WriteLine($"Unified package probe: FAIL ({expectedTarget})");
    Console.Error.WriteLine(exception);
    return 1;
}

static Type[] GetLoadableTypes(Assembly assembly)
{
    try
    {
        return assembly.GetTypes();
    }
    catch (ReflectionTypeLoadException exception)
    {
        var loaderMessages = exception.LoaderExceptions
            .Where(loaderException => loaderException is not null)
            .Select(loaderException => loaderException!.ToString());
        throw new InvalidOperationException(
            "Implementation type loading failed:\n" + string.Join("\n", loaderMessages),
            exception);
    }
}

static HashSet<string> ReadEmbeddedModelNames(Assembly assembly, string resourceName)
{
    using var resourceStream = assembly.GetManifestResourceStream(resourceName)
        ?? throw new MissingManifestResourceException(resourceName);
    using var assemblyBytes = new MemoryStream();
    resourceStream.CopyTo(assemblyBytes);
    assemblyBytes.Position = 0;

    using var peReader = new PEReader(assemblyBytes, PEStreamOptions.LeaveOpen);
    var metadata = peReader.GetMetadataReader();
    var modelMemo = new Dictionary<TypeDefinitionHandle, bool>();
    var modelNames = new HashSet<string>(StringComparer.Ordinal);

    foreach (var handle in metadata.TypeDefinitions)
    {
        var definition = metadata.GetTypeDefinition(handle);
        if ((definition.Attributes & TypeAttributes.Abstract) != 0)
            continue;
        if (!DerivesFromModel(metadata, handle, modelMemo, []))
            continue;

        var name = metadata.GetString(definition.Name);
        var @namespace = metadata.GetString(definition.Namespace);
        modelNames.Add(string.IsNullOrEmpty(@namespace) ? name : $"{@namespace}.{name}");
    }

    return modelNames;
}

static bool DerivesFromModel(
    MetadataReader metadata,
    TypeDefinitionHandle handle,
    Dictionary<TypeDefinitionHandle, bool> memo,
    HashSet<TypeDefinitionHandle> visiting)
{
    if (memo.TryGetValue(handle, out var cached))
        return cached;
    if (!visiting.Add(handle))
        throw new InvalidOperationException("Implementation metadata contains a cyclic base-type graph.");

    var rowNumber = MetadataTokens.GetRowNumber(handle);
    if (rowNumber <= 0 || rowNumber > metadata.TypeDefinitions.Count)
    {
        throw new InvalidOperationException(
            $"Implementation metadata references invalid TypeDef row {rowNumber}; " +
            $"table size is {metadata.TypeDefinitions.Count}.");
    }

    var baseType = metadata.GetTypeDefinition(handle).BaseType;
    var result = !baseType.IsNil && baseType.Kind switch
        {
            HandleKind.TypeDefinition => DerivesFromModel(
                metadata,
                (TypeDefinitionHandle)baseType,
                memo,
                visiting),
            HandleKind.TypeReference => IsKnownModelBase(metadata, (TypeReferenceHandle)baseType),
            _ => false
        };

    visiting.Remove(handle);
    memo[handle] = result;
    return result;
}

static bool IsKnownModelBase(MetadataReader metadata, TypeReferenceHandle handle)
{
    var name = metadata.GetString(metadata.GetTypeReference(handle).Name);
    return name is
        "AbstractModel" or
        "CardModel" or
        "EncounterModel" or
        "EnchantmentModel" or
        "EventModel" or
        "ModifierModel" or
        "MonsterModel" or
        "PotionModel" or
        "PowerModel" or
        "RelicModel";
}

static string DescribeSetDifference(
    IReadOnlySet<string> left,
    IReadOnlySet<string> right)
{
    var onlyLeft = left.Except(right, StringComparer.Ordinal).Order(StringComparer.Ordinal);
    var onlyRight = right.Except(left, StringComparer.Ordinal).Order(StringComparer.Ordinal);
    return $"only-left=[{string.Join(", ", onlyLeft)}], " +
           $"only-right=[{string.Join(", ", onlyRight)}]";
}

static void VerifyLegacyRegistrationBridge(
    Assembly gameAssembly,
    Assembly bootstrapAssembly,
    Type bootstrapType,
    Assembly implementationAssembly,
    Type[] implementationTypes)
{
    bootstrapType.GetField(
            "_gameAssembly", BindingFlags.NonPublic | BindingFlags.Static)!
        .SetValue(null, gameAssembly);
    bootstrapType.GetField(
            "_implementationAssembly", BindingFlags.NonPublic | BindingFlags.Static)!
        .SetValue(null, implementationAssembly);

    var append = bootstrapType.GetMethod(
        "AppendV1071ImplementationTypes", BindingFlags.NonPublic | BindingFlags.Static)!;
    object?[] appendArguments = [Array.Empty<Type>()];
    append.Invoke(null, appendArguments);
    var appendedTypes = (Type[]?)appendArguments[0]
        ?? throw new InvalidOperationException("Legacy type bridge returned null.");
    if (!implementationTypes.All(appendedTypes.Contains))
        throw new InvalidOperationException("Legacy type bridge omitted implementation types.");

    var modManager = gameAssembly.GetType(
        "MegaCrit.Sts2.Core.Modding.ModManager", throwOnError: true)!;
    var mods = modManager.GetField(
            "_mods", BindingFlags.NonPublic | BindingFlags.Static)?
        .GetValue(null) as System.Collections.IList
        ?? throw new InvalidOperationException("ModManager._mods is unavailable.");
    mods.Clear();

    var modType = gameAssembly.GetType(
        "MegaCrit.Sts2.Core.Modding.Mod", throwOnError: true)!;
    var manifestType = gameAssembly.GetType(
        "MegaCrit.Sts2.Core.Modding.ModManifest", throwOnError: true)!;
    var stateType = gameAssembly.GetType(
        "MegaCrit.Sts2.Core.Modding.ModLoadState", throwOnError: true)!;
    var mod = Activator.CreateInstance(modType)
        ?? throw new InvalidOperationException("Could not create synthetic Mod.");
    var manifest = Activator.CreateInstance(manifestType)
        ?? throw new InvalidOperationException("Could not create synthetic ModManifest.");
    manifestType.GetField("id")!.SetValue(manifest, "STS2_Things");
    modType.GetField("path")!.SetValue(mod, "probe://STS2_Things");
    modType.GetField("manifest")!.SetValue(mod, manifest);
    modType.GetField("state")!.SetValue(mod, Enum.Parse(stateType, "Loaded"));
    var assemblyField = modType.GetField("assembly")
        ?? throw new MissingFieldException(modType.FullName, "assembly");
    assemblyField.SetValue(mod, bootstrapAssembly);
    mods.Add(mod);

    try
    {
        bootstrapType.GetMethod(
                "PromoteV1071ImplementationAssembly",
                BindingFlags.NonPublic | BindingFlags.Static)!
            .Invoke(null, null);
        if (!ReferenceEquals(assemblyField.GetValue(mod), implementationAssembly))
            throw new InvalidOperationException("Legacy Mod assembly promotion failed.");
    }
    finally
    {
        mods.Clear();
    }
}

sealed class ProbeLoadContext(IEnumerable<string> dependencyDirectories)
    : AssemblyLoadContext(isCollectible: false)
{
    private readonly string[] _dependencyDirectories = dependencyDirectories.ToArray();

    protected override Assembly? Load(AssemblyName assemblyName)
    {
        foreach (var directory in _dependencyDirectories)
        {
            var candidate = Path.Combine(directory, $"{assemblyName.Name}.dll");
            if (File.Exists(candidate))
                return LoadFromAssemblyPath(candidate);
        }
        return null;
    }
}
