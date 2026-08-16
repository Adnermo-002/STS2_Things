using System.Reflection;
using System.Runtime.Loader;
using Godot;
using MegaCrit.Sts2.Core.Models;
using STS2_Things.Config;

public partial class BaseLibBridgeProbeNode : Node
{
    public override void _Ready()
    {
        try
        {
            string[] args = OS.GetCmdlineUserArgs();
            Assert(args.Length == 2,
                "Probe requires BaseLib.dll and the bridge DLL paths.");
            string baseLibPath = Path.GetFullPath(args[0]);
            string bridgePath = Path.GetFullPath(args[1]);
            Assert(File.Exists(baseLibPath), $"BaseLib.dll was not found: {baseLibPath}");
            Assert(File.Exists(bridgePath), $"Bridge DLL was not found: {bridgePath}");

            // 与模组 LibraryIntegration 相同的加载路径：BaseLib 先入 ALC，桥随后。
            // 必须使用与 sts2 相同的加载上下文（Godot 主机的游戏 ALC，ModelId 探针同款）。
            AssemblyLoadContext loadContext =
                AssemblyLoadContext.GetLoadContext(typeof(ModelDb).Assembly)
                ?? AssemblyLoadContext.Default;
            Assembly baseLib = loadContext.LoadFromAssemblyPath(baseLibPath);
            Assembly bridge = loadContext.LoadFromAssemblyPath(bridgePath);

            Type? entry = bridge.GetType("STS2_Things.BaseLibBridge.BridgeEntry", throwOnError: true);
            MethodInfo? register = entry?.GetMethod("Register", BindingFlags.Public | BindingFlags.Static);
            Assert(register is not null, "BridgeEntry.Register was not found.");
            register!.Invoke(null, null);

            // BaseLib 注册表必须包含 STS2_Things 配置。
            Type registry = baseLib.GetType("BaseLib.Config.ModConfigRegistry", throwOnError: true)!;
            MethodInfo? get = registry.GetMethod(
                "Get", BindingFlags.Public | BindingFlags.Static, binder: null,
                types: [typeof(string)], modifiers: null);
            Assert(get is not null, "ModConfigRegistry.Get(string) was not found.");
            object? config = get!.Invoke(null, ["STS2_Things"]);
            Assert(config is not null, "BaseLib registry has no STS2_Things config.");

            // 桥属性默认值（与 ThingsModConfig 默认一致）。
            Assert(GetBridgeBool(bridge, "BossOriginFogmogEnabled"),
                "Bridge BossOriginFogmogEnabled default is false.");
            Assert(!GetBridgeBool(bridge, "BossOriginFogmogForced"),
                "Bridge BossOriginFogmogForced default is true.");

            // 强制冲突可见规则（与主模组规则一致）。
            Assert(GetBridgeBool(bridge, "CanForceScaleBeetle"),
                "CanForceScaleBeetle must be true while nothing is forced.");
            SetBridgeBool(bridge, "BossOriginFogmogForced", true);
            Assert(!GetBridgeBool(bridge, "CanForceScaleBeetle"),
                "CanForceScaleBeetle must hide once Origin Fogmog is forced.");
            SetBridgeBool(bridge, "BossOriginFogmogForced", false);

            // 桥保存后：配置文件存在且主模组可重载同一份值。
            SetBridgeBool(bridge, "BossScaleBeetleForced", true);
            InvokeBridgeSave(bridge, config!);
            Assert(File.Exists(ThingsModConfig.ConfigPath),
                $"Bridge did not create the shared config file at {ThingsModConfig.ConfigPath}.");
            ThingsModConfig.Load();
            Assert(ThingsModConfig.IsForced(ThingsModConfig.BossScaleBeetleForced),
                "Main mod did not reload the bridge-written forced flag.");
            SetBridgeBool(bridge, "BossScaleBeetleForced", false);
            InvokeBridgeSave(bridge, config!);

            GD.Print("BaseLib bridge probe: PASS");
            GetTree().Quit(0);
        }
        catch (Exception exception)
        {
            GD.PushError(exception.ToString());
            GetTree().Quit(1);
        }
    }

    private static bool GetBridgeBool(Assembly bridge, string member)
    {
        Type? type = bridge.GetType("STS2_Things.BaseLibBridge.ThingsBaseLibConfig", throwOnError: true);
        PropertyInfo? property = type?.GetProperty(member, BindingFlags.Public | BindingFlags.Static);
        if (property is not null)
            return (bool)property.GetValue(null)!;
        MethodInfo? method = type?.GetMethod(member, BindingFlags.Public | BindingFlags.Static);
        Assert(method is not null, $"Bridge member {member} was not found.");
        return (bool)method!.Invoke(null, null)!;
    }

    private static void SetBridgeBool(Assembly bridge, string property, bool value)
    {
        Type? type = bridge.GetType("STS2_Things.BaseLibBridge.ThingsBaseLibConfig", throwOnError: true);
        PropertyInfo? propertyInfo = type?.GetProperty(property, BindingFlags.Public | BindingFlags.Static);
        Assert(propertyInfo is not null, $"Bridge property {property} was not found.");
        propertyInfo!.SetValue(null, value);
    }

    private static void InvokeBridgeSave(Assembly bridge, object config)
    {
        MethodInfo? save = config.GetType().GetMethod(
            "Save", BindingFlags.Public | BindingFlags.Instance | BindingFlags.NonPublic);
        Assert(save is not null, "Bridge config Save() was not found.");
        save!.Invoke(config, null);
    }

    private static void Assert(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException("BaseLib bridge probe: " + message);
    }
}
