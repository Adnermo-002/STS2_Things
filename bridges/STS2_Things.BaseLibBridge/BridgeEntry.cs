using System.Reflection;
using BaseLib;
using BaseLib.Config;
using HarmonyLib;

namespace STS2_Things.BaseLibBridge;

/// <summary>
/// 桥注册入口：由主模组（STS2_Things.Config.LibraryIntegration）在检测到 BaseLib
/// 后经反射调用。界面修改先同步到主模组，规范化后再保存共享文件；
/// 主模组/RitsuLib 的修改也会同步回桥属性，避免延迟保存覆盖新值。
/// </summary>
public static class BridgeEntry
{
    private const string ModId = "STS2_Things";
    private static bool _synchronizing;
    private static Type? _mainConfig;
    private static ThingsBaseLibConfig? _config;
    private static readonly PropertyInfo[] Settings = typeof(ThingsBaseLibConfig)
        .GetProperties(BindingFlags.Public | BindingFlags.Static)
        .Where(property => property.CanRead && property.CanWrite &&
                           (property.PropertyType == typeof(bool) || property.PropertyType == typeof(int))).ToArray();

    public static void Register()
    {
        _mainConfig = FindMainConfig();
        // BaseLib's delayed save reads UI properties, which display the host's
        // values. During a session only the main store may persist preferences.
        new Harmony("Adnermo.STS2_Things.BaseLibConfigSave").Patch(
            AccessTools.Method(typeof(ModConfig), "SaveInternal"),
            prefix: new HarmonyMethod(typeof(BridgeEntry), nameof(SaveLocalPreferences)));
        var config = new ThingsBaseLibConfig();
        _config = config;
        config.ConfigChanged += (_, _) => SynchronizeToMain();
        config.OnConfigReloaded += SynchronizeToMain;
        ModConfigRegistry.Register(ModId, config);
        _mainConfig?.GetEvent("Changed", BindingFlags.Public | BindingFlags.Static)
            ?.AddEventHandler(null, (Action)SynchronizeFromMain);
        SynchronizeToMain();
    }

    public static bool CanEdit(string key) =>
        (bool?)_mainConfig?.GetMethod("CanEdit")?.Invoke(null, [key]) ?? true;

    private static bool SaveLocalPreferences(ModConfig __instance)
    {
        if (__instance is not ThingsBaseLibConfig ||
            _mainConfig?.GetProperty("IsUsingSession")?.GetValue(null) is not true) return true;
        _mainConfig.GetMethod("Save")!.Invoke(null, null);
        return false;
    }

    private static Type? FindMainConfig()
    {
        return AppDomain.CurrentDomain.GetAssemblies()
            .Where(assembly => assembly.GetName().Name == "STS2_Things")
            .Select(assembly => assembly.GetType("STS2_Things.Config.ThingsModConfig", throwOnError: false))
            .FirstOrDefault(type => type is not null);
    }

    private static void SynchronizeToMain()
    {
        if (_synchronizing)
            return;
        try
        {
            _mainConfig ??= FindMainConfig();
            if (_mainConfig is null)
                return;
            _synchronizing = true;
            var changes = Settings.ToDictionary(property => property.Name, property => property.GetValue(null));
            _mainConfig.GetMethod("SetValues", BindingFlags.Public | BindingFlags.Static)!.Invoke(null, [changes]);
            CopyNormalizedValues();
            _config?.RefreshSessionAccess();
            _mainConfig.GetMethod("Save", BindingFlags.Public | BindingFlags.Static)!.Invoke(null, null);
        }
        catch (Exception exception)
        {
            BaseLibMain.Logger.Warn(
                $"STS2_Things.BaseLibBridge could not synchronize settings: {exception.Message}");
        }
        finally { _synchronizing = false; }
    }

    private static void SynchronizeFromMain()
    {
        if (_synchronizing) return;
        try
        {
            _synchronizing = true;
            CopyNormalizedValues();
            _config?.ConfigReloaded();
            _config?.RefreshSessionAccess();
        }
        finally { _synchronizing = false; }
    }

    private static void CopyNormalizedValues()
    {
        MethodInfo? get = _mainConfig?.GetMethod("GetValue", BindingFlags.Public | BindingFlags.Static);
        if (get is null)
            return;
        foreach (PropertyInfo property in Settings)
            if (get.Invoke(null, [property.Name]) is { } value)
                property.SetValue(null, value);
    }
}
