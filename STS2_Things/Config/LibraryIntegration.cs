using System.Reflection;
using HarmonyLib;

namespace STS2_Things.Config;

/// <summary>
/// BaseLib / RitsuLib 的可选配置页接入。
///
/// 原则：两库都不是前置依赖。检测到对应程序集才注册：
///   - RitsuLib：通过互操作镜像（字符串注册）注册本模组的设置页提供器；
///   - BaseLib：加载同目录可选桥程序集 <c>STS2_Things.BaseLibBridge.dll</c> 并调用其注册入口。
///
/// 加载时序：模组不声明对两库的依赖，两库可能在本模组之后才加载。因此在
/// ModManager.State 变为 Initialized（v111 全部模组加载完成）时经 Harmony 补丁重试一次；
/// 找不到该成员（如 v107.1）则跳过重试，仅依赖初始化时的检测。
/// </summary>
internal static class LibraryIntegration
{
    private const string BaseLibAssemblyName = "BaseLib";
    private const string RitsuLibAssemblyName = "STS2-RitsuLib";
    private const string BridgeFileName = "STS2_Things.BaseLibBridge.dll";
    private const string BridgeEntryTypeName = "STS2_Things.BaseLibBridge.BridgeEntry";
    private const string RitsuMirrorTypeName =
        "STS2RitsuLib.Settings.ModSettingsRuntimeReflectionInteropMirror";
    private const string HarmonyId = "Adnermo.STS2_Things.LibraryIntegration";

    private static readonly object Gate = new();
    private static bool _baseLibDone;
    private static bool _ritsuDone;
    private static Harmony? _retryHarmony;

    public static void Initialize()
    {
        lock (Gate)
        {
            TryIntegrate();
            InstallRetryHook();
        }
    }

    private static void TryIntegrate()
    {
        foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            string name = assembly.GetName().Name ?? string.Empty;
            if (name == BaseLibAssemblyName)
                TryRegisterBaseLib();
            else if (name == RitsuLibAssemblyName)
                TryRegisterRitsuLib(assembly);
        }
    }

    private static void TryRegisterBaseLib()
    {
        if (_baseLibDone)
            return;
        try
        {
            string? directory = FindModDirectory();
            if (directory is null)
            {
                MegaCrit.Sts2.Core.Logging.Log.Warn(
                    "STS2_Things: BaseLib detected but the mod directory is unavailable; skipping config bridge.");
                return;
            }

            string bridgePath = Path.Combine(directory, BridgeFileName);
            if (!File.Exists(bridgePath))
            {
                MegaCrit.Sts2.Core.Logging.Log.Info(
                    "STS2_Things: BaseLib detected but the optional config bridge DLL is not installed; " +
                    "falling back to the standalone config file.");
                return;
            }

            Assembly bridge = Assembly.LoadFrom(bridgePath);
            Type? entry = bridge.GetType(BridgeEntryTypeName, throwOnError: false);
            MethodInfo? register = entry?.GetMethod(
                "Register", BindingFlags.Public | BindingFlags.Static);
            if (register is null)
            {
                MegaCrit.Sts2.Core.Logging.Log.Warn(
                    "STS2_Things: BaseLib config bridge is missing BridgeEntry.Register; skipping.");
                return;
            }

            register.Invoke(null, null);
            MegaCrit.Sts2.Core.Logging.Log.Info(
                "STS2_Things: registered the config page with BaseLib.");
            _baseLibDone = true;
        }
        catch (Exception exception)
        {
            MegaCrit.Sts2.Core.Logging.Log.Warn(
                "STS2_Things: BaseLib config bridge failed; continuing standalone. " + exception);
        }
    }

    private static void TryRegisterRitsuLib(Assembly ritsuLib)
    {
        if (_ritsuDone)
            return;
        try
        {
            Type? mirror = ritsuLib.GetType(RitsuMirrorTypeName, throwOnError: false);
            MethodInfo? register = mirror?.GetMethod(
                "RegisterProviderTypeAndTryRegister",
                BindingFlags.Public | BindingFlags.Static,
                binder: null,
                types: [typeof(string), typeof(string)],
                modifiers: null);
            if (register is null)
            {
                MegaCrit.Sts2.Core.Logging.Log.Warn(
                    "STS2_Things: RitsuLib mirror API was not found; skipping settings page registration.");
                return;
            }

            int registered = (int)(register.Invoke(
                null,
                [typeof(RitsuLibInteropProvider).FullName,
                 typeof(RitsuLibInteropProvider).Assembly.GetName().Name]) ?? 0);
            MegaCrit.Sts2.Core.Logging.Log.Info(
                $"STS2_Things: registered the config page with RitsuLib ({registered} page(s)).");
            _ritsuDone = true;
        }
        catch (Exception exception)
        {
            MegaCrit.Sts2.Core.Logging.Log.Warn(
                "STS2_Things: RitsuLib settings registration failed; continuing standalone. " + exception);
        }
    }

    /// <summary>
    /// 全部模组加载完成后（ModManager.State -> Initialized）重试一次接入，
    /// 覆盖两库在本模组之后才加载的情况。v107.1 无 State 成员则静默跳过。
    /// </summary>
    private static void InstallRetryHook()
    {
        if (_retryHarmony is not null)
            return;
        try
        {
            Type? modManager = typeof(MegaCrit.Sts2.Core.Modding.ModManager);
            MethodInfo? stateSetter = AccessTools.PropertySetter(modManager, "State");
            if (stateSetter is null)
                return;

            _retryHarmony = new Harmony(HarmonyId);
            _retryHarmony.Patch(
                stateSetter,
                postfix: new HarmonyMethod(typeof(LibraryIntegration).GetMethod(
                    nameof(OnModManagerStateChanged),
                    BindingFlags.NonPublic | BindingFlags.Static)!));
        }
        catch (Exception exception)
        {
            MegaCrit.Sts2.Core.Logging.Log.Warn(
                "STS2_Things: could not install the config integration retry hook. " + exception.Message);
        }
    }

    private static void OnModManagerStateChanged(object? value)
    {
        if (value?.ToString() != "Initialized")
            return;
        lock (Gate)
            TryIntegrate();
    }

    /// <summary>模组目录：实现程序集从流加载时 Location 为空，退回引导程序集的目录。</summary>
    private static string? FindModDirectory()
    {
        string location = typeof(LibraryIntegration).Assembly.Location;
        if (!string.IsNullOrWhiteSpace(location))
            return Path.GetDirectoryName(location);

        foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
        {
            if (assembly.GetName().Name == "STS2_Things.Bootstrap" &&
                !string.IsNullOrWhiteSpace(assembly.Location))
            {
                return Path.GetDirectoryName(assembly.Location);
            }
        }

        return null;
    }
}
