using System.Reflection;
using HarmonyLib;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Multiplayer.Game.Lobby;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;

namespace STS2_Things.Config;

[HarmonyPatch]
internal static class ConfigSessionAttachPatch
{
    private static IEnumerable<MethodBase> TargetMethods()
    {
        yield return AccessTools.Constructor(typeof(StartRunLobby),
            [typeof(GameMode), typeof(INetGameService), typeof(IStartRunLobbyListener), typeof(int)]);
        yield return AccessTools.Constructor(typeof(LoadRunLobby),
            [typeof(INetGameService), typeof(ILoadRunLobbyListener), typeof(SerializableRun)]);
        foreach (ConstructorInfo constructor in AccessTools.GetDeclaredConstructors(typeof(NetClientGameService)))
            yield return constructor;
        if (AccessTools.Constructor(typeof(JoinFlow), [typeof(INetClientGameService)]) is { } joinConstructor)
            yield return joinConstructor;
    }

    private static void Postfix(object __instance)
    {
        switch (__instance)
        {
            case StartRunLobby start: MultiplayerConfig.Bind(start.NetService); break;
            case LoadRunLobby load: MultiplayerConfig.Bind(load.NetService, lockForLoadedRun: true); break;
            case JoinFlow join when join.NetService is { } service: MultiplayerConfig.Bind(service); break;
            case NetClientGameService client: MultiplayerConfig.Bind(client); break;
        }
    }
}

// Host sends the final snapshot BEFORE the native reliable start message. The
// client checks it before any act/event/relic generation consumes seeded RNG.
[HarmonyPatch(typeof(StartRunLobby), "BeginRunForAllPlayers")]
internal static class ConfigHostStartPatch
{
    private static bool Prefix(StartRunLobby __instance) => MultiplayerConfig.PrepareRun(__instance.NetService);
}

[HarmonyPatch(typeof(StartRunLobby), "BeginRunLocally")]
internal static class ConfigLocalStartPatch
{
    private static bool Prefix(StartRunLobby __instance) => MultiplayerConfig.PrepareRun(__instance.NetService);
}

[HarmonyPatch(typeof(LoadRunLobby), "BeginRunLocally")]
internal static class ConfigLocalResumePatch
{
    private static bool Prefix(LoadRunLobby __instance) => MultiplayerConfig.PrepareRun(__instance.NetService);
}

[HarmonyPatch]
internal static class ConfigJoinResponseGuardPatch
{
    private static IEnumerable<MethodBase> TargetMethods()
    {
        yield return AccessTools.Method(typeof(JoinFlow), "HandleLoadJoinResponseMessage");
        yield return AccessTools.Method(typeof(JoinFlow), "HandleRejoinResponseMessage");
    }

    private static bool Prefix(JoinFlow __instance) =>
        __instance.NetService is { } service && MultiplayerConfig.PrepareRun(service);
}

[HarmonyPatch(typeof(JoinFlow), nameof(JoinFlow.Begin))]
internal static class ConfigFailedJoinCleanupPatch
{
    private static void Postfix(JoinFlow __instance, ref Task<JoinResult> __result) =>
        __result = ObserveJoin(__result, __instance);

    private static async Task<JoinResult> ObserveJoin(Task<JoinResult> pending, JoinFlow flow)
    {
        try { return await pending; }
        catch
        {
            MultiplayerConfig.Detach(flow.NetService);
            throw;
        }
    }
}

[HarmonyPatch]
internal static class ConfigSessionCleanupPatch
{
    private static IEnumerable<MethodBase> TargetMethods()
    {
        yield return AccessTools.Method(typeof(RunManager), nameof(RunManager.CleanUp));
        yield return AccessTools.Method(typeof(RunManager), nameof(RunManager.SetUpNewSingleplayer));
        yield return AccessTools.Method(typeof(RunManager), nameof(RunManager.SetUpSavedSingleplayer));
        yield return AccessTools.Method(typeof(RunManager), nameof(RunManager.SetUpReplay));
    }

    private static void Prefix() => MultiplayerConfig.Clear();
}

[HarmonyPatch]
internal static class ConfigLobbyCleanupPatch
{
    private static IEnumerable<MethodBase> TargetMethods()
    {
        yield return AccessTools.Method(typeof(StartRunLobby), nameof(StartRunLobby.CleanUp));
        yield return AccessTools.Method(typeof(LoadRunLobby), nameof(LoadRunLobby.CleanUp));
    }

    private static void Postfix(bool disconnectSession)
    {
        if (disconnectSession) MultiplayerConfig.Clear();
    }
}
