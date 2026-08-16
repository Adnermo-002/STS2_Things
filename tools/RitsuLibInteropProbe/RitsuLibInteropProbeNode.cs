using System.Reflection;
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
            string[] args = OS.GetCmdlineUserArgs();
            Assert(args.Length == 1, "Probe requires the RitsuLib DLL path.");
            string ritsuLibPath = Path.GetFullPath(args[0]);
            Assert(File.Exists(ritsuLibPath), $"RitsuLib DLL was not found: {ritsuLibPath}");

            AssemblyLoadContext loadContext =
                AssemblyLoadContext.GetLoadContext(typeof(ModelDb).Assembly)
                ?? AssemblyLoadContext.Default;
            Assembly ritsuLib = loadContext.LoadFromAssemblyPath(ritsuLibPath);

            // 与 LibraryIntegration 相同的注册路径：互操作镜像 + 字符串注册。
            Type? mirror = ritsuLib.GetType(
                "STS2RitsuLib.Settings.ModSettingsRuntimeReflectionInteropMirror",
                throwOnError: true);
            MethodInfo? register = mirror?.GetMethod(
                "RegisterProviderTypeAndTryRegister",
                BindingFlags.Public | BindingFlags.Static,
                binder: null,
                types: [typeof(string), typeof(string)],
                modifiers: null);
            Assert(register is not null, "RitsuLib mirror registration API was not found.");

            string providerFullName = typeof(RitsuLibInteropProvider).FullName!;
            string providerAssembly = typeof(RitsuLibInteropProvider).Assembly.GetName().Name!;
            int registered = (int)(register!.Invoke(null, [providerFullName, providerAssembly]) ?? 0);
            Assert(registered >= 1,
                $"RitsuLib registered {registered} page(s); expected at least 1.");

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

            GD.Print("RitsuLib interop probe: PASS");
            GetTree().Quit(0);
        }
        catch (Exception exception)
        {
            GD.PushError(exception.ToString());
            GetTree().Quit(1);
        }
    }

    private static void Assert(bool condition, string message)
    {
        if (!condition)
            throw new InvalidOperationException("RitsuLib interop probe: " + message);
    }
}
