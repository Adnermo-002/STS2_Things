using System.Reflection;

// RitsuLib（STS2-RitsuLib）的互操作镜像通过程序集级 AssemblyMetadata 自动发现配置页
// 提供器（见 RuntimeInteropMirrorSource.ReadProviderTypeNames），无需任何编译期引用。
// 若 RitsuLib 在模组之后才加载，镜像会在程序集集合变化时重新扫描，仍可发现本提供器。
[assembly: AssemblyMetadata(
    "RitsuLib.ModSettingsInterop.ProviderType",
    "STS2_Things.Config.RitsuLibInteropProvider")]

namespace STS2_Things.Config;

/// <summary>
/// RitsuLib 配置页互操作提供器（零编译依赖）。
///
/// 契约（RitsuLib v0.5.12，RuntimeInteropMirrorSource）：
///   - 静态 <c>CreateRitsuLibSettingsSchema()</c> 返回 schema（字典 / JSON 字符串 / 文件路径），
///     这里使用字典，旧式单页格式：pageId/title/description/sortOrder/sections[]；
///   - 静态值访问器：Get/SetRitsuLibSettingValue(string[, object])（必需）、
///     Get/SetRitsuLibSettingBool（可选类型化）、SaveRitsuLibSettings；
///   - visibleWhenMethod 允许 <c>Foo()</c> 或 <c>Foo(string)</c> 返回 bool，用于
///     同槽位强制冲突时的条件可见。
///
/// 所有键读写都委托给 <see cref="ThingsModConfig"/>（同一份
/// user://mod_configs/STS2_Things.cfg，与 BaseLib 桥、独立模式共用）。
/// </summary>
public static class RitsuLibInteropProvider
{
    public static IDictionary<string, object?> CreateRitsuLibSettingsSchema()
    {
        return new Dictionary<string, object?>
        {
            ["modId"] = "STS2_Things",
            ["pageId"] = "things",
            ["title"] = Text("STS2_Things Settings", "尖塔：琐事 设置"),
            ["description"] = Text(
                "Encounters, events, merchant bargain and Neow relic offers.",
                "遭遇战、事件、商人猜拳与涅奥起始遗物。"),
            ["sortOrder"] = 10040,
            ["sections"] = new object[]
            {
                BossSection(),
                EncounterSection(),
                EventSection(),
                MerchantSection(),
                NeowRelicSection(),
            },
        };
    }

    // ---- 值访问器（RitsuLib 经反射定位；全部委托 ThingsModConfig）----

    public static object? GetRitsuLibSettingValue(string key) => ThingsModConfig.GetValue(key);

    public static void SetRitsuLibSettingValue(string key, object? value) => ThingsModConfig.SetValue(key, value);

    public static bool GetRitsuLibSettingBool(string key) => ThingsModConfig.GetBool(key);

    public static void SetRitsuLibSettingBool(string key, bool value) => ThingsModConfig.SetValue(key, value);

    public static void SaveRitsuLibSettings() => ThingsModConfig.Save();

    /// <summary>强制开关的可见条件：同槽位没有其他强制 Boss（或强制者正是本键）。</summary>
    public static bool IsBossForceVisible(string key)
    {
        return ThingsModConfig.CanForce(key);
    }

    // ---- schema 构建 ----

    private static Dictionary<string, object?> BossSection()
    {
        return Section("bosses", "Boss Encounters", "遭遇战·Boss",
            BossEntry("origin_fogmog_enabled", ThingsModConfig.BossOriginFogmogEnabled, "Origin Fogmog", "始源雾菇"),
            BossForceEntry("origin_fogmog_forced", ThingsModConfig.BossOriginFogmogForced, "Origin Fogmog", "始源雾菇"),
            BossEntry("scale_beetle_enabled", ThingsModConfig.BossScaleBeetleEnabled, "Scale Beetle", "缩放巨甲虫"),
            BossForceEntry("scale_beetle_forced", ThingsModConfig.BossScaleBeetleForced, "Scale Beetle", "缩放巨甲虫"),
            BossEntry("gravetide_slug_enabled", ThingsModConfig.BossGravetideSlugEnabled, "Gravetide Slug", "盛碗虫族母"),
            BossForceEntry("gravetide_slug_forced", ThingsModConfig.BossGravetideSlugForced, "Gravetide Slug", "盛碗虫族母"),
            BossEntry("the_legacy_enabled", ThingsModConfig.BossTheLegacyEnabled, "The Legacy", "腐化之遗"),
            BossForceEntry("the_legacy_forced", ThingsModConfig.BossTheLegacyForced, "The Legacy", "腐化之遗"),
            BossEntry("bowlbug_progenitor_enabled", ThingsModConfig.BossBowlbugProgenitorEnabled, "Bowlbug Progenitor", "盛碗虫族母（原版系）"),
            BossForceEntry("bowlbug_progenitor_forced", ThingsModConfig.BossBowlbugProgenitorForced, "Bowlbug Progenitor", "盛碗虫族母（原版系）"),
            BossEntry("living_rock_enabled", ThingsModConfig.BossLivingRockEnabled, "Living Rock", "生命之岩"),
            BossForceEntry("living_rock_forced", ThingsModConfig.BossLivingRockForced, "Living Rock", "生命之岩"));
    }

    private static Dictionary<string, object?> EncounterSection()
    {
        return Section("encounters", "Other Encounters", "遭遇战·其他",
            Entry("soul_roes_enabled", ThingsModConfig.EncounterSoulRoesEnabled, "Soul Roes", "灵魂鱼子团"),
            Entry("quirky_hopper_enabled", ThingsModConfig.EncounterQuirkyHopperEnabled, "Quirky Hopper", "怪癖草蜢"));
    }

    private static Dictionary<string, object?> EventSection()
    {
        return Section("events", "Events", "事件",
            Entry("robbery_fake_merchant_enabled", ThingsModConfig.EventRobberyFakeMerchantEnabled,
                "Fake Merchant Robbery", "假商人抢劫"),
            Entry("backrooms_enabled", ThingsModConfig.EventBackroomsEnabled, "Backrooms", "Backrooms"),
            Entry("medusa_enabled", ThingsModConfig.EventMedusaEnabled, "Medusa", "美杜莎"),
            Entry("cutting_it_close_enabled", ThingsModConfig.EventCuttingItCloseEnabled,
                "Cutting It Close", "命悬一线"));
    }

    private static Dictionary<string, object?> MerchantSection()
    {
        return Section("merchant", "Merchant Bargain", "商人猜拳",
            Entry("merchant_bargain_enabled", ThingsModConfig.FeatureMerchantBargainEnabled,
                "Merchant Rock-Paper-Scissors", "商人猜拳（讨价还价）",
                "Toggle the merchant bargaining mini-game.", "开关商人处的猜拳讨价还价小游戏。"));
    }

    private static Dictionary<string, object?> NeowRelicSection()
    {
        return Section("neow", "Neow Starting Relics", "涅奥起始遗物",
            Entry("neow_curse_remover_enabled", ThingsModConfig.NeowRelicCurseRemoverEnabled,
                "Curse Remover", "诅咒清除器"),
            Entry("neow_white_flag_enabled", ThingsModConfig.NeowRelicWhiteFlagEnabled,
                "White Flag", "白旗"),
            Entry("neow_magic_glove_enabled", ThingsModConfig.NeowRelicMagicGloveEnabled,
                "Magic Glove", "魔法手套"));
    }

    private static Dictionary<string, object?> Section(
        string id,
        string titleEn,
        string titleZh,
        params Dictionary<string, object?>[] entries)
    {
        return new Dictionary<string, object?>
        {
            ["id"] = id,
            ["title"] = Text(titleEn, titleZh),
            ["entries"] = entries,
        };
    }

    private static Dictionary<string, object?> BossEntry(
        string id, string key, string nameEn, string nameZh)
    {
        return Entry(id, key, $"{nameEn} — enabled", $"{nameZh} — 启用",
            "Can this boss appear as the act boss or in the act pool?",
            "该 Boss 是否能出现在本幕的遭遇池/Boss 候选中？");
    }

    private static Dictionary<string, object?> BossForceEntry(
        string id, string key, string nameEn, string nameZh)
    {
        return Entry(id, key, $"{nameEn} — force", $"{nameZh} — 强制",
            "Always fight this boss at the act end (one forced boss per act).",
            "本幕结尾必定遭遇该 Boss（每幕最多一个强制）。",
            visibleWhenMethod: nameof(IsBossForceVisible));
    }

    private static Dictionary<string, object?> Entry(
        string id,
        string key,
        string labelEn,
        string labelZh,
        string? descriptionEn = null,
        string? descriptionZh = null,
        string? visibleWhenMethod = null)
    {
        var entry = new Dictionary<string, object?>
        {
            ["id"] = id,
            ["type"] = "toggle",
            ["key"] = key,
            ["label"] = Text(labelEn, labelZh),
        };
        if (descriptionEn is not null)
            entry["description"] = Text(descriptionEn, descriptionZh ?? descriptionEn);
        if (visibleWhenMethod is not null)
            entry["visibleWhenMethod"] = visibleWhenMethod;
        return entry;
    }

    /// <summary>
    /// 语言映射文本：键为游戏本地化语言码（LocManager：eng/zhs/zht…）。
    /// RitsuLib 的 ResolveLangMap 按当前语言码精确/前缀匹配，最后回退 "en"；
    /// 简体与繁体中文均显示中文，其余语言回退英文。
    /// </summary>
    private static Dictionary<string, object?> Text(string en, string zhCn)
    {
        return new Dictionary<string, object?>
        {
            ["en"] = en,
            ["zhs"] = zhCn,
            ["zht"] = zhCn,
        };
    }
}
