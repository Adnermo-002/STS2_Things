using System.Collections;
using System.Reflection;
using System.Resources;
using System.Runtime.ExceptionServices;
using System.Runtime.Loader;
using HarmonyLib;
using MegaCrit.Sts2.Core.Modding;

namespace STS2_Things.Bootstrap;

[ModInitializer(nameof(Initialize))]
public static class UnifiedBootstrap
{
    private const string ModId = "STS2_Things";
    private const string V1071Target = "v107.1";
    private const string V110Target = "v110";
    private const string V1071Resource = "STS2_Things.Implementations.v107.1.dll";
    private const string V110Resource = "STS2_Things.Implementations.v110.dll";
    private const string ImplementationAssemblyName = "STS2_Things";
    private const string LegacyHarmonyId = "Adnermo.STS2_Things.UnifiedBootstrap.V1071";

    private static readonly object InitLock = new();
    private static Assembly? _gameAssembly;
    private static Assembly? _implementationAssembly;
    private static Harmony? _legacyHarmony;
    private static bool _initialized;

    public static string? SelectedTarget { get; private set; }

    public static void Initialize()
    {
        lock (InitLock)
        {
            if (_initialized)
            {
                Console.WriteLine("[STS2_Things] Unified bootstrap duplicate initialization ignored.");
                return;
            }

            _gameAssembly = typeof(ModInitializerAttribute).Assembly;
            SelectedTarget = DetectTarget(_gameAssembly);
            _implementationAssembly = LoadImplementation(SelectedTarget);

            if (SelectedTarget == V110Target)
                AssociateV110Implementation(_gameAssembly, _implementationAssembly);
            else
                InstallV1071RegistrationBridge(_gameAssembly);

            InvokeImplementationInitializer(_implementationAssembly);
            _initialized = true;
            Console.WriteLine(
                $"[STS2_Things] Unified package selected {SelectedTarget} implementation " +
                $"({_implementationAssembly.GetName().Name}).");
        }
    }

    public static string SelectImplementationResource(Assembly gameAssembly)
    {
        return DetectTarget(gameAssembly) switch
        {
            V1071Target => V1071Resource,
            V110Target => V110Resource,
            _ => throw new InvalidOperationException("Unsupported STS2 target.")
        };
    }

    private static string DetectTarget(Assembly gameAssembly)
    {
        var abstractModel = gameAssembly.GetType(
            "MegaCrit.Sts2.Core.Models.AbstractModel", throwOnError: true)!;
        var parameterCounts = abstractModel
            .GetMethods(BindingFlags.Instance | BindingFlags.Public)
            .Where(method => method.Name == "ModifyDamageMultiplicative")
            .Select(method => method.GetParameters().Length)
            .Distinct()
            .Order()
            .ToArray();

        if (parameterCounts.SequenceEqual([5]))
            return V1071Target;
        if (parameterCounts.SequenceEqual([6]) &&
            gameAssembly.GetType("MegaCrit.Sts2.Core.Combat.CombatId") is not null)
            return V110Target;

        throw new NotSupportedException(
            "STS2_Things 1.9.5 supports STS2 v0.107.1 and v0.110.x. " +
            $"Detected ModifyDamageMultiplicative parameter counts: {string.Join(", ", parameterCounts)}.");
    }

    private static Assembly LoadImplementation(string target)
    {
        var resourceName = target == V1071Target ? V1071Resource : V110Resource;
        var bootstrapAssembly = typeof(UnifiedBootstrap).Assembly;
        using var stream = bootstrapAssembly.GetManifestResourceStream(resourceName)
            ?? throw new MissingManifestResourceException(
                $"Embedded implementation resource is missing: {resourceName}");
        var loadContext = AssemblyLoadContext.GetLoadContext(bootstrapAssembly)
            ?? AssemblyLoadContext.Default;
        var implementation = loadContext.LoadFromStream(stream);
        if (!string.Equals(
                implementation.GetName().Name,
                ImplementationAssemblyName,
                StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                $"Embedded {target} implementation has assembly name " +
                $"'{implementation.GetName().Name}', expected '{ImplementationAssemblyName}'.");
        }
        return implementation;
    }

    private static void AssociateV110Implementation(
        Assembly gameAssembly,
        Assembly implementationAssembly)
    {
        var modManager = gameAssembly.GetType(
            "MegaCrit.Sts2.Core.Modding.ModManager", throwOnError: true)!;
        var associate = modManager.GetMethod(
            "AssociateAssemblyWithMod",
            BindingFlags.Public | BindingFlags.Static,
            binder: null,
            types: [typeof(string), typeof(Assembly)],
            modifiers: null)
            ?? throw new MissingMethodException(
                modManager.FullName, "AssociateAssemblyWithMod(string, Assembly)");
        InvokeAndUnwrap(associate, null, [ModId, implementationAssembly]);
    }

    private static void InstallV1071RegistrationBridge(Assembly gameAssembly)
    {
        var reflectionHelper = gameAssembly.GetType(
            "MegaCrit.Sts2.Core.Helpers.ReflectionHelper", throwOnError: true)!;
        var modTypesGetter = reflectionHelper
            .GetProperty("ModTypes", BindingFlags.Public | BindingFlags.Static)?
            .GetMethod
            ?? throw new MissingMethodException(reflectionHelper.FullName, "get_ModTypes");
        var modelIdCache = gameAssembly.GetType(
            "MegaCrit.Sts2.Core.Multiplayer.Serialization.ModelIdSerializationCache",
            throwOnError: true)!;
        var modelIdInit = modelIdCache.GetMethod(
            "Init", BindingFlags.Public | BindingFlags.Static)
            ?? throw new MissingMethodException(modelIdCache.FullName, "Init");

        _legacyHarmony = new Harmony(LegacyHarmonyId);
        _legacyHarmony.Patch(
            modTypesGetter,
            postfix: new HarmonyMethod(typeof(UnifiedBootstrap).GetMethod(
                nameof(AppendV1071ImplementationTypes),
                BindingFlags.NonPublic | BindingFlags.Static)!));
        _legacyHarmony.Patch(
            modelIdInit,
            prefix: new HarmonyMethod(typeof(UnifiedBootstrap).GetMethod(
                nameof(PromoteV1071ImplementationAssembly),
                BindingFlags.NonPublic | BindingFlags.Static)!));
    }

    private static void AppendV1071ImplementationTypes(ref Type[] __result)
    {
        var implementation = _implementationAssembly
            ?? throw new InvalidOperationException("V107.1 implementation is not loaded.");
        var original = __result ?? [];
        var existing = new HashSet<Type>(original);
        __result = [.. original, .. implementation.GetTypes().Where(existing.Add)];
    }

    private static void PromoteV1071ImplementationAssembly()
    {
        var gameAssembly = _gameAssembly
            ?? throw new InvalidOperationException("STS2 assembly is not initialized.");
        var implementation = _implementationAssembly
            ?? throw new InvalidOperationException("V107.1 implementation is not loaded.");
        var modManager = gameAssembly.GetType(
            "MegaCrit.Sts2.Core.Modding.ModManager", throwOnError: true)!;
        var mods = modManager.GetProperty(
                "Mods", BindingFlags.Public | BindingFlags.Static)?
            .GetValue(null) as IEnumerable
            ?? throw new InvalidOperationException("ModManager.Mods is unavailable.");

        foreach (var mod in mods)
        {
            if (mod is null || !IsLoadedTargetMod(mod))
                continue;
            var assemblyField = mod.GetType().GetField(
                "assembly", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
                ?? throw new MissingFieldException(mod.GetType().FullName, "assembly");
            assemblyField.SetValue(mod, implementation);
            return;
        }

        throw new InvalidOperationException(
            "Could not promote the V107.1 implementation to the loaded STS2_Things Mod.");
    }

    private static bool IsLoadedTargetMod(object mod)
    {
        var type = mod.GetType();
        var manifest = type.GetField(
                "manifest", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?
            .GetValue(mod);
        if (manifest is null)
            return false;
        var id = manifest.GetType().GetField(
                "id", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?
            .GetValue(manifest) as string;
        var state = type.GetField(
                "state", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?
            .GetValue(mod)?.ToString();
        return string.Equals(id, ModId, StringComparison.Ordinal) &&
               string.Equals(state, "Loaded", StringComparison.Ordinal);
    }

    private static void InvokeImplementationInitializer(Assembly implementationAssembly)
    {
        var initializerType = implementationAssembly.GetType(
            "STS2_ThingsInit", throwOnError: true)!;
        var initializer = initializerType.GetMethod(
            "Initialize", BindingFlags.Public | BindingFlags.Static)
            ?? throw new MissingMethodException(initializerType.FullName, "Initialize");
        InvokeAndUnwrap(initializer, null, null);
    }

    private static object? InvokeAndUnwrap(
        MethodInfo method,
        object? instance,
        object?[]? arguments)
    {
        try
        {
            return method.Invoke(instance, arguments);
        }
        catch (TargetInvocationException exception) when (exception.InnerException is not null)
        {
            ExceptionDispatchInfo.Capture(exception.InnerException).Throw();
            throw;
        }
    }
}
