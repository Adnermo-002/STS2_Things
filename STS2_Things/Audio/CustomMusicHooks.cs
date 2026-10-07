using System;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Nodes.Audio;

namespace STS2_Things.Audio;

/// <summary>
/// Routes mod-owned res:// music through Godot. The native controller requests
/// the custom track while combat is still being assembled, so actual playback
/// waits for its post-setup track update to avoid room-transition cleanup.
/// </summary>
[HarmonyPatch(typeof(NRunMusicController), nameof(NRunMusicController.PlayCustomMusic))]
internal static class CustomMusicPlayPatch
{
    internal const string GravetideTheme =
        "res://music/gravetide_slug/gravetide_slug_boss_theme.wav";

    internal static bool StartAfterCombatSetup { get; set; }

    [HarmonyPrefix]
    private static bool Prefix(NRunMusicController __instance, string customMusic)
    {
        try
        {
            if (!string.Equals(customMusic, GravetideTheme, StringComparison.Ordinal))
                return true;

            if (!ModMusicPolicy.Enabled)
            {
                StartAfterCombatSetup = false;
                NativeSfxPlayer.StopMusic();
                return false;
            }

            StartAfterCombatSetup = true;
            __instance.GetNodeOrNull<Node>("Proxy")?.Call("stop_music");
            NativeSfxPlayer.StopMusic();
            return false;
        }
        catch (Exception ex)
        {
            Log.Warn($"[CustomMusicPlayPatch] Prefix error: {ex.Message}");
            return true;
        }
    }
}

[HarmonyPatch(
    typeof(NRunMusicController),
    nameof(NRunMusicController.UpdateTrack),
    new Type[] { })]
internal static class CustomMusicStartAfterCombatSetupPatch
{
    [HarmonyPostfix]
    private static void Postfix()
    {
        try
        {
            if (!ModMusicPolicy.Enabled)
            {
                CustomMusicPlayPatch.StartAfterCombatSetup = false;
                if (NativeSfxPlayer.ActiveMusicPath == CustomMusicPlayPatch.GravetideTheme)
                    NativeSfxPlayer.StopMusic();
                return;
            }
            if (!CustomMusicPlayPatch.StartAfterCombatSetup ||
                !CombatManager.Instance.IsInProgress)
            {
                return;
            }

            CustomMusicPlayPatch.StartAfterCombatSetup = false;
            NativeSfxPlayer.PlayMusic(CustomMusicPlayPatch.GravetideTheme, "Master", -2f);
        }
        catch (Exception ex)
        {
            Log.Warn($"[CustomMusicStartAfterCombatSetupPatch] Postfix error: {ex.Message}");
        }
    }
}
