using System.Reflection;
using BaseLib;
using BaseLib.Config;

namespace STS2_Things.BaseLibBridge;

/// <summary>
/// 桥注册入口：由主模组（STS2_Things.Config.LibraryIntegration）在检测到 BaseLib
/// 后经反射调用。配置写入/读取交给 BaseLib（user://mod_configs/STS2_Things.cfg），
/// 保存与重载后通知主模组重新加载内存副本。
/// </summary>
public static class BridgeEntry
{
    private const string ModId = "STS2_Things";

    public static void Register()
    {
        var config = new ThingsBaseLibConfig();
        config.ConfigChanged += (_, _) => NotifyMainModConfigReload();
        config.OnConfigReloaded += NotifyMainModConfigReload;
        ModConfigRegistry.Register(ModId, config);
    }

    private static void NotifyMainModConfigReload()
    {
        try
        {
            foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                if (assembly.GetName().Name != "STS2_Things")
                    continue;
                Type? configType = assembly.GetType(
                    "STS2_Things.Config.ThingsModConfig", throwOnError: false);
                MethodInfo? load = configType?.GetMethod(
                    "Load", BindingFlags.Public | BindingFlags.Static);
                load?.Invoke(null, null);
                return;
            }
        }
        catch (Exception exception)
        {
            BaseLibMain.Logger.Warn(
                $"STS2_Things.BaseLibBridge could not notify the main mod: {exception.Message}");
        }
    }
}
