using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using STS2_Things.Config;
using STS2_Things.Encounters;

namespace STS2_Things.Audio;

/// <summary>Boss music is optional presentation; disabling it restores native act music.</summary>
public static class ModMusicPolicy
{
    private static readonly Dictionary<string, float> Parameters = new(StringComparer.Ordinal);
    private static bool _initialized;
    private static bool _lastEnabled;

    public static bool Enabled => ThingsModConfig.GetBool(ThingsModConfig.FeatureCustomBgmEnabled);

    public static void Initialize()
    {
        if (_initialized)
            return;
        _initialized = true;
        _lastEnabled = Enabled;
        ThingsModConfig.Changed += OnSettingsChanged;
    }

    public static void UpdateParameter(string label, float value)
    {
        Parameters[label] = value;
        if (Enabled)
            NRunMusicController.Instance?.UpdateMusicParameter(label, value);
    }

    private static void OnSettingsChanged()
    {
        if (_lastEnabled == Enabled)
            return;
        _lastEnabled = Enabled;
        // UI integrations may save asynchronously. Touch audio nodes on the Godot thread.
        Callable.From(RefreshCurrentCombat).CallDeferred();
    }

    private static void RefreshCurrentCombat()
    {
        if (RunManager.Instance.DebugOnlyGetState()?.CurrentRoom is not CombatRoom { Encounter: ModBossEncounter encounter } ||
            NRunMusicController.Instance is not { } controller)
            return;

        CustomMusicPlayPatch.StartAfterCombatSetup = false;
        NativeSfxPlayer.StopMusic();
        if (Enabled && CombatManager.Instance.IsInProgress && encounter.CustomBgm is { Length: > 0 } track)
        {
            controller.PlayCustomMusic(track);
            foreach ((string label, float value) in Parameters)
            {
                const string suffix = "_progress";
                if (label.EndsWith(suffix, StringComparison.Ordinal) &&
                    track.EndsWith(label[..^suffix.Length], StringComparison.Ordinal))
                    controller.UpdateMusicParameter(label, value);
            }
        }
        else
            controller.StopCustomMusic();
        controller.UpdateTrack();
    }
}
