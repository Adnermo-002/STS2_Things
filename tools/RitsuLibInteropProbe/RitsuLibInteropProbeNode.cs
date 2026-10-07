using System.Reflection;
using System.Collections;
using System.Runtime.Loader;
using Godot;
using MegaCrit.Sts2.Core.Models;
using STS2_Things.Config;

public partial class RitsuLibInteropProbeNode : Node
{
    public override void _Ready()
    {
        try
        {
            Assert(OS.GetUserDataDir().Contains("RitsuLib Interop Probe", StringComparison.Ordinal),
                "Refusing to change settings outside the isolated probe profile.");
            ThingsModConfig.SetValues(ThingsModConfig.Entries.ToDictionary(entry => entry.Key, entry => (object?)entry.Default));
            string[] args = OS.GetCmdlineUserArgs();
            Assert(args.Length == 1, "Probe requires the RitsuLib DLL path.");
            string ritsuLibPath = Path.GetFullPath(args[0]);
            Assert(File.Exists(ritsuLibPath), $"RitsuLib DLL was not found: {ritsuLibPath}");

            AssemblyLoadContext loadContext =
                AssemblyLoadContext.GetLoadContext(typeof(ModelDb).Assembly)
                ?? AssemblyLoadContext.Default;
            // Modular RitsuLib keeps Settings and its dependencies together.
            loadContext.Resolving += (context, name) =>
            {
                string candidate = Path.Combine(Path.GetDirectoryName(ritsuLibPath)!, name.Name + ".dll");
                return File.Exists(candidate) ? context.LoadFromAssemblyPath(candidate) : null;
            };
            Assembly ritsuLib = loadContext.LoadFromAssemblyPath(ritsuLibPath);

            // Exercise the actual production discovery path, including split assemblies.
            Type integration = typeof(ThingsModConfig).Assembly.GetType("STS2_Things.Config.LibraryIntegration", true)!;
            integration.GetMethod("Initialize", BindingFlags.Public | BindingFlags.Static)!.Invoke(null, null);

            // 注册表必须包含 STS2_Things::things 页面。
            Type? registry = ritsuLib.GetType(
                "STS2RitsuLib.Settings.ModSettingsRegistry", throwOnError: true);
            MethodInfo? tryGetPage = registry?
                .GetMethods(BindingFlags.Public | BindingFlags.Static)
                .FirstOrDefault(method =>
                    method.Name == "TryGetPage" &&
                    method.GetParameters().Length == 3 &&
                    method.GetParameters()[2].IsOut);
            Assert(tryGetPage is not null, "ModSettingsRegistry.TryGetPage was not found.");
            object?[] pageArgs = ["STS2_Things", "things", null];
            bool pageFound = (bool)tryGetPage!.Invoke(null, pageArgs)!;
            Assert(pageFound, "Registered page STS2_Things::things is missing from the registry.");

            // 文本映射必须使用游戏语言码（zhs/zht/en）。历史回归：旧实现用 zh-CN 键，
            // 与 LocManager 语言码 zhs 不匹配，ResolveLangMap 只能退回 en → 页面全英文。
            IDictionary<string, object?> schema =
                RitsuLibInteropProvider.CreateRitsuLibSettingsSchema();
            Assert(schema.TryGetValue("title", out object? title) &&
                   title is IDictionary<string, object?> titleMap &&
                   titleMap.ContainsKey("en") &&
                   titleMap.ContainsKey("zhs") &&
                   titleMap.ContainsKey("zht"),
                "Provider text map must carry the en/zhs/zht game language codes.");

            // Inspect the page produced by the real library, then edit through
            // its actual bindings (a schema-only test would miss dropped sliders).
            object page = pageArgs[2]!;
            object[] decoratedEntries = ((IEnumerable)Get(page, "Sections")).Cast<object>()
                .SelectMany(section => ((IEnumerable)Get(section, "Entries")).Cast<object>()).ToArray();
            object[] actualEntries = decoratedEntries.Select(Unwrap).ToArray();
            object[] sliders = actualEntries.Where(entry => entry.GetType().Name == "IntSliderModSettingsEntryDefinition").ToArray();
            Assert(sliders.Length == 7, $"Expected seven registered sliders, got {sliders.Length}.");
            var entriesById = ((object[])schema["sections"]!).Cast<IDictionary<string, object?>>()
                .SelectMany(section => (IDictionary<string, object?>[])section["entries"]!)
                .ToDictionary(entry => (string)entry["id"]!);
            foreach (object slider in sliders)
            {
                Assert((int)Get(slider, "MinValue") == 0 && (int)Get(slider, "MaxValue") == 1000 &&
                       (int)Get(slider, "Step") == 10, "Registered slider has incorrect bounds.");
                string key = (string)entriesById[(string)Get(slider, "Id")]["key"]!;
                object binding = Get(slider, "Binding");
                binding.GetType().GetMethod("Write")!.Invoke(binding, [370]);
                Assert(ThingsModConfig.GetInt(key) == 370, $"Real slider binding did not update {key}.");
                Assert((int)binding.GetType().GetMethod("Read")!.Invoke(binding, null)! == 370,
                    "Real slider binding did not read its current value.");
                binding.GetType().GetMethod("Write")!.Invoke(binding, [100]);
            }
            foreach ((string id, string key, bool value) in new[]
                     { ("custom_bgm", ThingsModConfig.FeatureCustomBgmEnabled, false),
                       ("only_mod_bosses", ThingsModConfig.BossOnlyModBosses, true) })
            {
                object entry = actualEntries.Single(entry => (string)Get(entry, "Id") == id);
                object binding = Get(entry, "Binding");
                binding.GetType().GetMethod("Write")!.Invoke(binding, [value]);
                Assert(ThingsModConfig.GetBool(key) == value, $"Real toggle binding did not update {key}.");
            }

            // 值访问器往返（与 ThingsModConfig 共享同一内存态）。
            Assert(RitsuLibInteropProvider.GetRitsuLibSettingBool(
                       ThingsModConfig.BossOriginFogmogEnabled),
                "Provider default read is false.");
            RitsuLibInteropProvider.SetRitsuLibSettingBool(ThingsModConfig.BossOriginFogmogEnabled, false);
            Assert(!RitsuLibInteropProvider.GetRitsuLibSettingBool(ThingsModConfig.BossOriginFogmogEnabled),
                "Provider write did not round-trip.");
            RitsuLibInteropProvider.SetRitsuLibSettingValue(ThingsModConfig.BossOriginFogmogEnabled, true);
            Assert(RitsuLibInteropProvider.GetRitsuLibSettingValue(
                       ThingsModConfig.BossOriginFogmogEnabled) is true,
                "Object accessor did not round-trip.");

            // 冲突可见方法可经 RitsuLib 的 visibleWhenMethod 契约调用。
            Assert(RitsuLibInteropProvider.IsBossForceVisible(ThingsModConfig.BossScaleBeetleForced),
                "IsBossForceVisible(Scale Beetle) must be true while nothing is forced.");
            RitsuLibInteropProvider.SetRitsuLibSettingBool(ThingsModConfig.BossOriginFogmogForced, true);
            Assert(!RitsuLibInteropProvider.IsBossForceVisible(ThingsModConfig.BossScaleBeetleForced),
                "IsBossForceVisible(Scale Beetle) must hide when Origin Fogmog is forced.");
            RitsuLibInteropProvider.SetRitsuLibSettingBool(ThingsModConfig.BossOriginFogmogForced, false);

            var (client, wire) = ConfigNetworkFake.Peer();
            MultiplayerConfig.Bind(client);
            int[] hostValues = ThingsModConfig.Entries.Select(entry => Convert.ToInt32(entry.Default)).ToArray();
            int weightIndex = ThingsModConfig.Entries.ToList().FindIndex(entry => entry.Key == ThingsModConfig.BossScaleBeetleWeightPercent);
            hostValues[weightIndex] = 610;
            wire.Deliver(new ThingsConfigSnapshotMessage
            {
                Version = ThingsConfigSnapshotMessage.Protocol, SchemaHash = ThingsConfigSnapshotMessage.Schema,
                Revision = 1, Locked = true, Values = hostValues,
            });
            Assert(decoratedEntries.All(entry => !((Func<bool>)Get(entry, "VisibilityPredicate"))()),
                "RitsuLib did not hide editing controls for the client.");
            object weightEntry = actualEntries.Single(entry => (string)Get(entry, "Id") == "scale_beetle_weight");
            object weightBinding = Get(weightEntry, "Binding");
            weightBinding.GetType().GetMethod("Write")!.Invoke(weightBinding, [0]);
            Assert((int)weightBinding.GetType().GetMethod("Read")!.Invoke(weightBinding, null)! == 610,
                "Client RitsuLib binding overrode host values.");
            MultiplayerConfig.Clear();
            Assert(decoratedEntries.All(entry => ((Func<bool>)Get(entry, "VisibilityPredicate"))()),
                "Leaving did not restore local editing controls.");

            ThingsModConfig.SetValues(ThingsModConfig.Entries.ToDictionary(entry => entry.Key, entry => (object?)entry.Default));
            ThingsModConfig.Save();

            GD.Print("RitsuLib interop probe: PASS");
            GetTree().Quit(0);
        }
        catch (Exception exception)
        {
            GD.PushError(exception.ToString());
            GetTree().Quit(1);
        }
    }

    private static object Get(object target, string property) => target.GetType().GetProperty(property)!.GetValue(target)!;

    private static object Unwrap(object entry)
    {
        for (Type? type = entry.GetType(); type is not null; type = type.BaseType)
            if (type.GetProperty("Inner", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly) is { } inner)
                return Unwrap(inner.GetValue(entry)!);
        return entry;
    }

    private static void Assert(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException("RitsuLib interop probe: " + message);
    }
}
