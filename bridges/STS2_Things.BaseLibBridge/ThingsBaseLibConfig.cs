using BaseLib.Config;

namespace STS2_Things.BaseLibBridge;

/// <summary>
/// BaseLib 配置页（可选集成，非前置依赖）。
///
/// 约束（BaseLib SimpleModConfig）：仅 static 属性；bool -> 复选框；文件为
/// <c>user://mod_configs/STS2_Things.cfg</c>（根命名空间推导）——与本模组独立模式、
/// RitsuLib 互操作入口共用同一份配置。
///
/// 键名必须与 <c>STS2_Things.Config.ThingsModConfig</c> 的键常量逐字一致
/// （verify_project.py 校验）。强制冲突：同一 ACT Boss 槽位最多一个强制项，
/// 本类用 [ConfigVisibleIf] 隐藏已被占用的强制开关；权威裁决仍在主模组
/// ThingsModConfig.Load/SetValue 中执行（先到先得 + 降级 + 警告）。
/// </summary>
public sealed class ThingsBaseLibConfig : SimpleModConfig
{
    // ---- 遭遇战：Boss ----

    [ConfigSection("Bosses")]
    public static bool BossOriginFogmogEnabled { get; set; } = true;

    [ConfigSection("Bosses")]
    [ConfigVisibleIf(nameof(CanForceOriginFogmog))]
    public static bool BossOriginFogmogForced { get; set; }

    [ConfigSection("Bosses")]
    public static bool BossScaleBeetleEnabled { get; set; } = true;

    [ConfigSection("Bosses")]
    [ConfigVisibleIf(nameof(CanForceScaleBeetle))]
    public static bool BossScaleBeetleForced { get; set; }

    [ConfigSection("Bosses")]
    public static bool BossGravetideSlugEnabled { get; set; } = true;

    [ConfigSection("Bosses")]
    [ConfigVisibleIf(nameof(CanForceGravetideSlug))]
    public static bool BossGravetideSlugForced { get; set; }

    [ConfigSection("Bosses")]
    public static bool BossTheLegacyEnabled { get; set; } = true;

    [ConfigSection("Bosses")]
    [ConfigVisibleIf(nameof(CanForceTheLegacy))]
    public static bool BossTheLegacyForced { get; set; }

    [ConfigSection("Bosses")]
    public static bool BossBowlbugProgenitorEnabled { get; set; } = true;

    [ConfigSection("Bosses")]
    [ConfigVisibleIf(nameof(CanForceBowlbugProgenitor))]
    public static bool BossBowlbugProgenitorForced { get; set; }

    [ConfigSection("Bosses")]
    public static bool BossLivingRockEnabled { get; set; } = true;

    [ConfigSection("Bosses")]
    [ConfigVisibleIf(nameof(CanForceLivingRock))]
    public static bool BossLivingRockForced { get; set; }

    // ---- 遭遇战：其他 ----

    [ConfigSection("Other Encounters")]
    public static bool EncounterSoulRoesEnabled { get; set; } = true;

    [ConfigSection("Other Encounters")]
    public static bool EncounterQuirkyHopperEnabled { get; set; } = true;

    // ---- 事件 ----

    [ConfigSection("Events")]
    public static bool EventRobberyFakeMerchantEnabled { get; set; } = true;

    [ConfigSection("Events")]
    public static bool EventBackroomsEnabled { get; set; } = true;

    [ConfigSection("Events")]
    public static bool EventMedusaEnabled { get; set; } = true;

    [ConfigSection("Events")]
    public static bool EventCuttingItCloseEnabled { get; set; } = true;

    // ---- 商人猜拳 ----

    [ConfigSection("Merchant Bargain")]
    public static bool FeatureMerchantBargainEnabled { get; set; } = true;

    // ---- 涅奥起始遗物 ----

    [ConfigSection("Neow Starting Relics")]
    public static bool NeowRelicCurseRemoverEnabled { get; set; } = true;

    [ConfigSection("Neow Starting Relics")]
    public static bool NeowRelicWhiteFlagEnabled { get; set; } = true;

    [ConfigSection("Neow Starting Relics")]
    public static bool NeowRelicMagicGloveEnabled { get; set; } = true;

    // ---- 强制冲突的条件可见（同槽位最多一个强制）----

    public static bool CanForceOriginFogmog() => !BossScaleBeetleForced;

    public static bool CanForceScaleBeetle() => !BossOriginFogmogForced;

    public static bool CanForceGravetideSlug() => !BossTheLegacyForced;

    public static bool CanForceTheLegacy() => !BossGravetideSlugForced;

    public static bool CanForceBowlbugProgenitor() => !BossLivingRockForced;

    public static bool CanForceLivingRock() => !BossBowlbugProgenitorForced;
}
