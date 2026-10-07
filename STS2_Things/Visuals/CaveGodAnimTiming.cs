namespace STS2_Things.Visuals;

/// <summary>
/// 活体巨岩（Living Megalith）招式的打击帧时间，单位：秒。
/// Each value mirrors a Spine event in animations/monsters/cave_god/cave_god.spjson.
/// Gameplay still waits with native Cmd.Wait so rendered and headless peers resolve identically;
/// scripts/verify_project.py fails the build if a constant drifts from its Spine event.
/// </summary>
internal static class CaveGodAnimTiming
{
    // alternating_jabs: central_hit @ 0.64 / 1.34 / 2.32, attack_recover @ 3.45
    public const float JabsHit1 = 0.64f;
    public const float JabsHit2 = 1.34f;
    public const float JabsHit3 = 2.32f;

    // central_slam: central_hit @ 1.88, attack_recover @ 3.70
    public const float CentralSlamHit = 1.88f;

    // double_fist_crush: central_hit @ 1.25, attack_recover @ 3.30
    public const float DoubleFistCrushHit = 1.25f;

    // front_sweep / front_sweep_right: central_hit @ 1.35, attack_recover @ 3.40 (clip length 3.45)
    public const float FrontSweepHit = 1.35f;
    public const float FrontSweepLength = 3.45f;

    // card_snatch variants: palm contact, fingers close on the cards, settle.
    public const float CardSnatchLaunch = 1.00f;
    public const float CardSnatchTouch = 1.36f;
    public const float CardSnatchClose = 1.60f;
    public const float CardSnatchRetract = 1.68f;
    public const float CardSnatchSettled = 3.08f;
    public const float CardSnatchLength = 3.20f;

    /// <summary>Settle time after an impact before the enemy turn continues.</summary>
    public const float ImpactSettle = 0.80f;
}
