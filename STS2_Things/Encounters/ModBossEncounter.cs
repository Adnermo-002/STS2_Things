using MegaCrit.Sts2.Core.Models;
using STS2_Things.Audio;

namespace STS2_Things.Encounters;

/// <summary>
///     Mod Boss 遭遇基类 — 统一地图图标路径为 res://images/map/{IconName}_boss_icon
/// </summary>
public abstract class ModBossEncounter : EncounterModel
{
    protected abstract string IconName { get; }

    protected static string ConfiguredBgm(string track) => ModMusicPolicy.Enabled ? track : string.Empty;

    public override string BossNodePath =>
        $"res://images/map/{IconName}_boss_icon";
}
