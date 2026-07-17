using HarmonyLib;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using STS2_Things.Hooks;

namespace STS2_Things.Audio;

/// <summary>
/// 本 Mod 的本地循环音频生命周期清理。与怪物/遭遇注册分离，避免注册层接管房间视觉。
/// </summary>
[HarmonyPatch(typeof(NCombatRoom), nameof(NCombatRoom._ExitTree))]
internal static class CombatRoomAudioCleanupPatch
{
    [HarmonyPostfix]
    private static void Postfix()
    {
        NativeSfxPlayer.StopSequentialLoop();
        NativeSfxPlayer.StopMusic();
        NativeSfxPlayer.CleanupActivePlayers();
        SfxHooks.ResetDeathSfx();
    }
}
