using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Multiplayer.Serialization;
using System.Collections;

public partial class BaseLibBridgeProbeNode : Node
{
    public override void _Ready()
    {
        try
        {
            Assert(OS.GetUserDataDir().Contains("BaseLib Bridge Probe", StringComparison.Ordinal),
                "Refusing to change settings outside the isolated probe profile.");
            string[] args = OS.GetCmdlineUserArgs();
            Assert(args.Length == 3,
                "Probe requires BaseLib.dll, the implementation DLL and the bridge DLL paths.");
            string baseLibPath = Path.GetFullPath(args[0]);
            string implementationPath = Path.GetFullPath(args[1]);
            string bridgePath = Path.GetFullPath(args[2]);
            Assert(File.Exists(baseLibPath), $"BaseLib.dll was not found: {baseLibPath}");
            Assert(File.Exists(implementationPath), $"Implementation DLL was not found: {implementationPath}");
            Assert(File.Exists(bridgePath), $"Bridge DLL was not found: {bridgePath}");

            // 与真实游戏一致：BaseLib 先装入游戏 ALC（官方加载器把全部模组 DLL 都放进
            // 游戏程序集上下文；探针里即 sts2/ModelDb 所在上下文）。
            AssemblyLoadContext gameContext =
                AssemblyLoadContext.GetLoadContext(typeof(ModelDb).Assembly)
                ?? AssemblyLoadContext.Default;
            Assembly baseLib = gameContext.LoadFromAssemblyPath(baseLibPath);

            // ---- ALC 拓扑回归（真实游戏失败模式）----
            // 真实游戏日志（2026-08-16）确认：旧实现用 Assembly.LoadFrom 加载桥，桥落入
            // 默认上下文，解析不到 BaseLib → FileNotFoundException。这里显式用
            // AssemblyLoadContext.Default.LoadFromAssemblyPath 复现同一条路径（无上下文
            // 反射时 Assembly.LoadFrom 与它等价），断言它确实失败——防止有人改回朴素加载。
            Assembly naiveBridge = AssemblyLoadContext.Default.LoadFromAssemblyPath(bridgePath);
            Type? naiveEntry = naiveBridge.GetType(
                "STS2_Things.BaseLibBridge.BridgeEntry", throwOnError: true);
            MethodInfo? naiveRegister = naiveEntry?.GetMethod(
                "Register", BindingFlags.Public | BindingFlags.Static);
            Assert(naiveRegister is not null, "BridgeEntry.Register was not found.");
            try
            {
                naiveRegister!.Invoke(null, null);
                throw new InvalidOperationException(
                    "BaseLib bridge probe: naive default-ALC load unexpectedly resolved BaseLib " +
                    "(ALC topology regression: the real game fails this way).");
            }
            catch (TargetInvocationException exception) when (
                exception.InnerException is FileNotFoundException fileNotFound &&
                fileNotFound.Message.Contains("BaseLib", StringComparison.Ordinal))
            {
                // 预期失败：桥在默认上下文解析不到 BaseLib。
            }

            // ---- 端到端：走主模组 LibraryIntegration 的真实代码路径 ----
            // Godot 探针主机会把脚本程序集从流加载（Location 为空），因此这里显式从路径
            // 加载实现程序集（与官方加载器一致），使 FindModDirectory 能定位模组目录；
            // 再把桥 DLL 放进该目录（FindModDirectory 的预期位置），经反射调用
            // LibraryIntegration.Initialize()：它必须找到 BaseLib 程序集、按 BaseLib
            // 所在上下文加载桥并注册成功。
            Assembly implementation = gameContext.LoadFromAssemblyPath(implementationPath);
            Type thingsConfig = implementation.GetType("STS2_Things.Config.ThingsModConfig", true)!;
            string sharedPath = (string)thingsConfig.GetProperty("ConfigPath")!.GetValue(null)!;
            Directory.CreateDirectory(Path.GetDirectoryName(sharedPath)!);
            // Simulate an older config containing JSON primitives. Main startup
            // must migrate it before BaseLib's Dictionary<string,string> reader.
            File.WriteAllText(sharedPath, """{"FeatureCustomBgmEnabled":false,"BossScaleBeetleWeightPercent":240}""");
            thingsConfig.GetMethod("Load")!.Invoke(null, null);
            string modDir = Path.GetDirectoryName(implementationPath)!;
            string stagedBridgePath = Path.Combine(modDir, "STS2_Things.BaseLibBridge.dll");
            if (!string.Equals(stagedBridgePath, bridgePath, StringComparison.OrdinalIgnoreCase))
                File.Copy(bridgePath, stagedBridgePath, overwrite: true);

            Type? integration = implementation.GetType(
                "STS2_Things.Config.LibraryIntegration", throwOnError: true);
            MethodInfo? initialize = integration?.GetMethod(
                "Initialize", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
            Assert(initialize is not null, "LibraryIntegration.Initialize was not found.");
            initialize!.Invoke(null, null);

            Type registry = baseLib.GetType("BaseLib.Config.ModConfigRegistry", throwOnError: true)!;
            MethodInfo? get = registry.GetMethod(
                "Get", BindingFlags.Public | BindingFlags.Static, binder: null,
                types: [typeof(string)], modifiers: null);
            Assert(get is not null, "ModConfigRegistry.Get(string) was not found.");
            object? config = get!.Invoke(null, ["STS2_Things"]);
            Assert(config is not null,
                "BaseLib registry has no STS2_Things config after LibraryIntegration.Initialize.");

            // 桥必须被加载进游戏 ALC（而不是默认上下文）。
            Assembly? bridge = null;
            foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                if (assembly.GetName().Name != "STS2_Things.BaseLibBridge")
                    continue;
                if (AssemblyLoadContext.GetLoadContext(assembly) == gameContext)
                {
                    bridge = assembly;
                    break;
                }
            }

            if (bridge is null)
                throw new InvalidOperationException(
                    "BaseLib bridge probe: Bridge was not loaded into the game ALC.");

            // 桥属性默认值（与 ThingsModConfig 默认一致）。
            Assert(GetBridgeBool(bridge, "BossOriginFogmogEnabled"),
                "Bridge BossOriginFogmogEnabled default is false.");
            Assert(!GetBridgeBool(bridge, "BossOriginFogmogForced"),
                "Bridge BossOriginFogmogForced default is true.");
            Assert(!GetBridgeBool(bridge, "FeatureCustomBgmEnabled") &&
                   (int)GetBridgeValue(bridge, "BossScaleBeetleWeightPercent") == 240,
                "BaseLib lost migrated boolean/numeric preferences during construction.");
            Assert((int)config!.GetType().GetMethod("GetDefaultValue")!.MakeGenericMethod(typeof(int))
                       .Invoke(config, ["BossScaleBeetleWeightPercent"])! == 100,
                "BaseLib captured the persisted weight as its reset default.");

            // 强制冲突可见规则（与主模组规则一致）。
            Assert(GetBridgeBool(bridge, "CanForceScaleBeetle"),
                "CanForceScaleBeetle must be true while nothing is forced.");
            SetBridgeBool(bridge, "BossOriginFogmogForced", true);
            Assert(!GetBridgeBool(bridge, "CanForceScaleBeetle"),
                "CanForceScaleBeetle must hide once Origin Fogmog is forced.");
            SetBridgeBool(bridge, "BossOriginFogmogForced", false);

            // Real controls call Changed BEFORE Save. The live model must receive
            // the new properties immediately instead of reloading stale disk state.
            SetBridgeValue(bridge, "BossScaleBeetleWeightPercent", 370);
            SetBridgeBool(bridge, "FeatureCustomBgmEnabled", true);
            SetBridgeBool(bridge, "BossOnlyModBosses", true);
            InvokeBridge(config!, "Changed");
            Assert((int)thingsConfig.GetMethod("GetInt")!.Invoke(null, ["BossScaleBeetleWeightPercent"])! == 370,
                "Slider change did not reach the live model before Save.");
            Assert((bool)thingsConfig.GetMethod("GetBool")!.Invoke(null, ["FeatureCustomBgmEnabled"])! &&
                   (bool)thingsConfig.GetMethod("GetBool")!.Invoke(null, ["BossOnlyModBosses"])!,
                "New toggle changes did not reach the live model before Save.");
            // RitsuLib/main writes must also update the mirror before a delayed
            // BaseLib save, or switching pages would silently discard the edit.
            thingsConfig.GetMethod("SetValue")!.Invoke(null, ["BossScaleBeetleWeightPercent", 620]);
            Assert((int)GetBridgeValue(bridge, "BossScaleBeetleWeightPercent") == 620,
                "Main-to-BaseLib numeric synchronization failed.");
            InvokeBridge(config!, "Save");
            thingsConfig.GetMethod("Load")!.Invoke(null, null);
            Assert((int)thingsConfig.GetMethod("GetInt")!.Invoke(null, ["BossScaleBeetleWeightPercent"])! == 620,
                "Delayed BaseLib save overwrote another settings page's change.");
            using (JsonDocument saved = JsonDocument.Parse(File.ReadAllText(sharedPath)))
                Assert(saved.RootElement.EnumerateObject().All(property => property.Value.ValueKind == JsonValueKind.String),
                    "Shared settings cannot be read by BaseLib's string dictionary.");

            // 桥保存后：配置文件存在且主模组可重载同一份值。
            PropertyInfo? configPath = thingsConfig.GetProperty(
                "ConfigPath", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
            Assert(configPath is not null, "ThingsModConfig.ConfigPath was not found.");
            MethodInfo? load = thingsConfig.GetMethod(
                "Load", BindingFlags.Public | BindingFlags.Static);
            MethodInfo? isForced = thingsConfig.GetMethod(
                "IsForced", BindingFlags.Public | BindingFlags.Static);
            Assert(load is not null && isForced is not null,
                "ThingsModConfig.Load/IsForced were not found.");
            SetBridgeBool(bridge, "BossScaleBeetleForced", true);
            SetBridgeBool(bridge, "BossScaleBeetleEnabled", false);
            SetBridgeValue(bridge, "BossScaleBeetleWeightPercent", 0);
            InvokeBridge(config!, "Changed");
            Assert(GetBridgeBool(bridge, "BossScaleBeetleEnabled"),
                "Forced implies enabled was not reflected back to BaseLib.");
            InvokeBridge(config!, "Save");
            Assert(File.Exists((string)configPath!.GetValue(null)!),
                $"Bridge did not create the shared config file at {configPath}.");
            load!.Invoke(null, null);
            Assert((bool)isForced!.Invoke(null, ["BossScaleBeetleForced"])!,
                "Main mod did not reload the bridge-written forced flag.");
            SetBridgeBool(bridge, "BossScaleBeetleForced", false);
            SetBridgeBool(bridge, "BossOnlyModBosses", false);
            SetBridgeValue(bridge, "BossScaleBeetleWeightPercent", 100);
            InvokeBridge(config!, "Changed");
            InvokeBridge(config!, "Save");

            // A client's UI shows the host snapshot, but neither normal nor
            // debounced BaseLib saves may write it into the client's preferences.
            thingsConfig.GetMethod("Save")!.Invoke(null, null);
            string personalFile = File.ReadAllText(sharedPath);
            Type multiplayer = implementation.GetType("STS2_Things.Config.MultiplayerConfig", true)!;
            var (client, wire) = ConfigNetworkFake.Peer();
            multiplayer.GetMethod("Bind")!.Invoke(null, [client, false]);
            object[] settings = ((IEnumerable)thingsConfig.GetField("Entries")!.GetValue(null)!).Cast<object>().ToArray();
            string Key(object entry) => (string)entry.GetType().GetProperty("Key")!.GetValue(entry)!;
            int[] values = settings.Select(entry => Convert.ToInt32(thingsConfig.GetMethod("GetValue")!.Invoke(null, [Key(entry)]))).ToArray();
            values[Array.FindIndex(settings, entry => Key(entry) == "BossScaleBeetleWeightPercent")] = 900;
            values[Array.FindIndex(settings, entry => Key(entry) == "FeatureCustomBgmEnabled")] = 0;
            Type messageType = implementation.GetType("STS2_Things.Config.ThingsConfigSnapshotMessage", true)!;
            object snapshot = Activator.CreateInstance(messageType)!;
            foreach (var pair in new Dictionary<string, object>
                     { ["Version"] = 1, ["SchemaHash"] = messageType.GetField("Schema")!.GetValue(null)!,
                       ["Revision"] = 1u, ["Locked"] = true, ["Values"] = values })
                messageType.GetField(pair.Key)!.SetValue(snapshot, pair.Value);
            wire.Deliver((INetMessage)snapshot);
            Assert((int)GetBridgeValue(bridge, "BossScaleBeetleWeightPercent") == 900,
                "BaseLib did not display the host snapshot.");
            SetBridgeValue(bridge, "BossScaleBeetleWeightPercent", 0);
            InvokeBridge(config!, "Changed");
            Assert((int)GetBridgeValue(bridge, "BossScaleBeetleWeightPercent") == 900,
                "Client BaseLib edit overrode the host.");
            InvokeBridge(config!, "Save");
            config!.GetType().GetMethod("SaveDebounced", BindingFlags.Public | BindingFlags.Instance, [typeof(int)])!
                .Invoke(config, [0]);
            Assert(File.ReadAllText(sharedPath) == personalFile, "BaseLib persisted the host's temporary values.");
            multiplayer.GetMethod("Clear")!.Invoke(null, null);
            Assert((int)GetBridgeValue(bridge, "BossScaleBeetleWeightPercent") == 100,
                "BaseLib did not restore personal values after leaving.");

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
        => SetBridgeValue(bridge, property, value);

    private static object GetBridgeValue(Assembly bridge, string property)
        => bridge.GetType("STS2_Things.BaseLibBridge.ThingsBaseLibConfig", true)!
            .GetProperty(property, BindingFlags.Public | BindingFlags.Static)!.GetValue(null)!;

    private static void SetBridgeValue(Assembly bridge, string property, object value)
    {
        Type? type = bridge.GetType("STS2_Things.BaseLibBridge.ThingsBaseLibConfig", throwOnError: true);
        PropertyInfo? propertyInfo = type?.GetProperty(property, BindingFlags.Public | BindingFlags.Static);
        Assert(propertyInfo is not null, $"Bridge property {property} was not found.");
        propertyInfo!.SetValue(null, value);
    }

    private static void InvokeBridge(object config, string method)
    {
        MethodInfo? save = config.GetType().GetMethod(
            method, BindingFlags.Public | BindingFlags.Instance | BindingFlags.NonPublic);
        Assert(save is not null, $"Bridge config {method}() was not found.");
        save!.Invoke(config, null);
    }

    private static void Assert(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException("BaseLib bridge probe: " + message);
    }
}
