using System.Text.Json;
using System.Globalization;
using Godot;

namespace STS2_Things.Config;

/// <summary>
/// 单一配置源。文件为 <c>user://mod_configs/STS2_Things.cfg</c>（JSON），与 BaseLib 桥
/// 写入的路径、文件名与键名完全一致；RitsuLib 互操作提供器也读写同一文件。
///
/// 可配置范围（由设计决定）：
///   - 遭遇战：全部 Boss（启用 + 强制）与非 Boss 遭遇（启用）
///   - 事件（启用）
///   - 商人猜拳（启用）
///   - 涅奥起始遗物（启用）
/// 卡牌、事件遗物与附魔不是可配置项——它们是事件/遗物/附魔内容的一部分。
///
/// 冲突规则：同一 ACT 的同一 Boss 槽位最多一个强制 Boss；加载与每次写入后校验，
/// 按规范顺序"先到先得"，其余强制项自动降级并记录警告。强制启用隐含启用。
/// </summary>
public static class ThingsModConfig
{
    public enum Category
    {
        Boss,
        Encounter,
        Event,
        Feature,
        NeowRelic,
        Audio,
    }

    /// <summary>Boss 槽位（冲突分组）。同一槽位只能有一个强制 Boss。</summary>
    public const string SlotOvergrowth = "overgrowth";
    public const string SlotUnderdocks = "underdocks";
    public const string SlotHive = "hive";

    public sealed record Entry(
        string Key,
        Category Category,
        object Default,
        string? Slot = null,
        int Min = 0,
        int Max = 1000);

    // ===== 键常量（单一来源：BaseLib 桥属性名、RitsuLib schema 与门控代码都引用这里）=====
    public const string SchemaVersion = "SchemaVersion";
    public const string FeatureCustomBgmEnabled = "FeatureCustomBgmEnabled";
    public const string BossOnlyModBosses = "BossOnlyModBosses";
    public const string BossOriginFogmogWeightPercent = "BossOriginFogmogWeightPercent";
    public const string BossScaleBeetleWeightPercent = "BossScaleBeetleWeightPercent";
    public const string BossGravetideSlugWeightPercent = "BossGravetideSlugWeightPercent";
    public const string BossTheLegacyWeightPercent = "BossTheLegacyWeightPercent";
    public const string BossBowlbugProgenitorWeightPercent = "BossBowlbugProgenitorWeightPercent";
    public const string BossCaveGodWeightPercent = "BossCaveGodWeightPercent";
    public const string EncounterSoulRoesWeightPercent = "EncounterSoulRoesWeightPercent";

    // ---- 遭遇战：Boss ----
    public const string BossOriginFogmogEnabled = "BossOriginFogmogEnabled";
    public const string BossOriginFogmogForced = "BossOriginFogmogForced";
    public const string BossScaleBeetleEnabled = "BossScaleBeetleEnabled";
    public const string BossScaleBeetleForced = "BossScaleBeetleForced";
    public const string BossGravetideSlugEnabled = "BossGravetideSlugEnabled";
    public const string BossGravetideSlugForced = "BossGravetideSlugForced";
    public const string BossTheLegacyEnabled = "BossTheLegacyEnabled";
    public const string BossTheLegacyForced = "BossTheLegacyForced";
    public const string BossBowlbugProgenitorEnabled = "BossBowlbugProgenitorEnabled";
    public const string BossBowlbugProgenitorForced = "BossBowlbugProgenitorForced";
    public const string BossCaveGodEnabled = "BossCaveGodEnabled";
    public const string BossCaveGodForced = "BossCaveGodForced";

    // ---- 遭遇战：非 Boss ----
    public const string EncounterSoulRoesEnabled = "EncounterSoulRoesEnabled";
    public const string EncounterQuirkyHopperEnabled = "EncounterQuirkyHopperEnabled";

    // ---- 事件 ----
    public const string EventRobberyFakeMerchantEnabled = "EventRobberyFakeMerchantEnabled";
    public const string EventBackroomsEnabled = "EventBackroomsEnabled";
    public const string EventMedusaEnabled = "EventMedusaEnabled";
    public const string EventCuttingItCloseEnabled = "EventCuttingItCloseEnabled";
    public const string EventRealityAlignedHousesEnabled = "EventRealityAlignedHousesEnabled";
    public const string EventShadowCloakroomEnabled = "EventShadowCloakroomEnabled";
    public const string EventEchoingWellEnabled = "EventEchoingWellEnabled";
    public const string EventPoliteMawEnabled = "EventPoliteMawEnabled";
    public const string EventMycelialBankEnabled = "EventMycelialBankEnabled";
    public const string EventUnlitFireEnabled = "EventUnlitFireEnabled";
    public const string EventRelicWorkshopEnabled = "EventRelicWorkshopEnabled";
    public const string EventPotionTastingEnabled = "EventPotionTastingEnabled";
    public const string EventNarrowGateEnabled = "EventNarrowGateEnabled";

    // ---- 商人猜拳 ----
    public const string FeatureMerchantBargainEnabled = "FeatureMerchantBargainEnabled";

    // ---- 涅奥起始遗物 ----
    public const string NeowRelicCurseRemoverEnabled = "NeowRelicCurseRemoverEnabled";
    public const string NeowRelicWhiteFlagEnabled = "NeowRelicWhiteFlagEnabled";
    public const string NeowRelicMagicGloveEnabled = "NeowRelicMagicGloveEnabled";

    /// <summary>规范顺序即冲突裁决顺序：同槽位第一个强制项生效。</summary>
    public static readonly IReadOnlyList<Entry> Entries =
    [
        new(FeatureCustomBgmEnabled, Category.Audio, Default: true),
        new(BossOnlyModBosses, Category.Boss, Default: false),
        new(BossOriginFogmogEnabled, Category.Boss, Default: true, Slot: SlotOvergrowth),
        new(BossOriginFogmogForced, Category.Boss, Default: false, Slot: SlotOvergrowth),
        new(BossOriginFogmogWeightPercent, Category.Boss, Default: 100, Slot: SlotOvergrowth),
        new(BossScaleBeetleEnabled, Category.Boss, Default: true, Slot: SlotOvergrowth),
        new(BossScaleBeetleForced, Category.Boss, Default: false, Slot: SlotOvergrowth),
        new(BossScaleBeetleWeightPercent, Category.Boss, Default: 100, Slot: SlotOvergrowth),
        new(BossGravetideSlugEnabled, Category.Boss, Default: true, Slot: SlotUnderdocks),
        new(BossGravetideSlugForced, Category.Boss, Default: false, Slot: SlotUnderdocks),
        new(BossGravetideSlugWeightPercent, Category.Boss, Default: 100, Slot: SlotUnderdocks),
        new(BossTheLegacyEnabled, Category.Boss, Default: true, Slot: SlotUnderdocks),
        new(BossTheLegacyForced, Category.Boss, Default: false, Slot: SlotUnderdocks),
        new(BossTheLegacyWeightPercent, Category.Boss, Default: 100, Slot: SlotUnderdocks),
        new(BossBowlbugProgenitorEnabled, Category.Boss, Default: true, Slot: SlotHive),
        new(BossBowlbugProgenitorForced, Category.Boss, Default: false, Slot: SlotHive),
        new(BossBowlbugProgenitorWeightPercent, Category.Boss, Default: 100, Slot: SlotHive),
        new(BossCaveGodEnabled, Category.Boss, Default: true, Slot: SlotHive),
        new(BossCaveGodForced, Category.Boss, Default: false, Slot: SlotHive),
        new(BossCaveGodWeightPercent, Category.Boss, Default: 100, Slot: SlotHive),
        new(EncounterSoulRoesEnabled, Category.Encounter, Default: true),
        new(EncounterSoulRoesWeightPercent, Category.Encounter, Default: 100),
        new(EncounterQuirkyHopperEnabled, Category.Encounter, Default: true),
        new(EventRobberyFakeMerchantEnabled, Category.Event, Default: true),
        new(EventBackroomsEnabled, Category.Event, Default: true),
        new(EventMedusaEnabled, Category.Event, Default: true),
        new(EventCuttingItCloseEnabled, Category.Event, Default: true),
        new(EventRealityAlignedHousesEnabled, Category.Event, Default: true),
        new(FeatureMerchantBargainEnabled, Category.Feature, Default: true),
        new(NeowRelicCurseRemoverEnabled, Category.NeowRelic, Default: true),
        new(NeowRelicWhiteFlagEnabled, Category.NeowRelic, Default: true),
        new(NeowRelicMagicGloveEnabled, Category.NeowRelic, Default: true),
        new(EventShadowCloakroomEnabled, Category.Event, Default: true),
        new(EventEchoingWellEnabled, Category.Event, Default: true),
        new(EventPoliteMawEnabled, Category.Event, Default: true),
        new(EventMycelialBankEnabled, Category.Event, Default: true),
        new(EventUnlitFireEnabled, Category.Event, Default: true),
        new(EventRelicWorkshopEnabled, Category.Event, Default: true),
        new(EventPotionTastingEnabled, Category.Event, Default: true),
        new(EventNarrowGateEnabled, Category.Event, Default: true),
    ];

    private static readonly Dictionary<string, object> Values =
        Entries.ToDictionary(entry => entry.Key, entry => entry.Default);

    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    /// <summary>配置发生变化（含强制冲突裁决后的降级）时触发。</summary>
    public static event Action? Changed;

    internal static event Action? LocalChanged;

    public static bool IsUsingSession => MultiplayerConfig.IsActive;

    public static bool CanEdit(string key) => MultiplayerConfig.CanEdit(key);

    internal static void NotifyEffectiveChanged() => Changed?.Invoke();

    internal static object? GetLocalValue(string key) => Values.GetValueOrDefault(key);

    public static string ConfigPath =>
        Path.Combine(OS.GetUserDataDir(), "mod_configs", "STS2_Things.cfg");

    public static bool IsEnabled(string key)
    {
        return GetBool(key);
    }

    public static bool IsForced(string key)
    {
        return GetBool(key);
    }

    /// <summary>读取任意布尔键（含 Forced 键）。</summary>
    public static bool GetBool(string key)
    {
        return GetValue(key) is true;
    }

    public static int GetInt(string key) =>
        GetValue(key) is int integer ? integer : 0;

    public static bool HasBossWeightOverrides(string slot) =>
        Entries.Any(entry => entry.Slot == slot && entry.Default is int && GetInt(entry.Key) != (int)entry.Default);

    /// <summary>
    /// 返回指定槽位当前的强制 Boss 键（如 <see cref="BossOriginFogmogEnabled"/>），没有则为 null。
    /// UI 条件可见与门控代码共用此方法，保证同一裁决结果。
    /// </summary>
    public static string? GetForcedBossKeyForSlot(string slot)
    {
        foreach (Entry entry in Entries)
        {
            if (entry.Slot != slot || !entry.Key.EndsWith("Forced", StringComparison.Ordinal))
                continue;
            if (IsForced(entry.Key))
                return entry.Key;
        }

        return null;
    }

    /// <summary>该强制键是否可开启：同槽位尚无其他强制 Boss，或强制者正是本键。</summary>
    public static bool CanForce(string forcedKey)
    {
        Entry? entry = Entries.FirstOrDefault(candidate => candidate.Key == forcedKey);
        if (entry?.Slot is not { } slot)
            return false;
        string? current = GetForcedBossKeyForSlot(slot);
        return current is null || current == forcedKey;
    }

    public static void Load()
    {
        Dictionary<string, object> previous = new(Values);
        Values.Clear();
        foreach (Entry entry in Entries)
            Values[entry.Key] = entry.Default;

        string path = ConfigPath;
        bool needsSave = !File.Exists(path);
        if (File.Exists(path))
        {
            try
            {
                using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
                if (document.RootElement.ValueKind != JsonValueKind.Object)
                    throw new JsonException("Configuration root must be an object.");
                // BaseLib deserializes Dictionary<string, string>. Migrate legacy
                // bool/number JSON before its optional page loads the shared file.
                needsSave |= document.RootElement.EnumerateObject().Any(property => property.Value.ValueKind != JsonValueKind.String);
                foreach (Entry entry in Entries)
                {
                    if (document.RootElement.TryGetProperty(entry.Key, out JsonElement element) &&
                        TryNormalize(entry, element, out object normalized))
                    {
                        Values[entry.Key] = normalized;
                    }
                    else
                        needsSave = true;
                }
            }
            catch (Exception exception)
            {
                needsSave = true;
                foreach (Entry entry in Entries)
                    Values[entry.Key] = entry.Default;
                MegaCrit.Sts2.Core.Logging.Log.Warn(
                    $"STS2_Things config '{path}' is unreadable ({exception.Message}); backing it up and using defaults.");
                try
                {
                    File.Copy(path, path + ".corrupt-" + DateTime.Now.ToString("yyyyMMddHHmmss"), overwrite: true);
                }
                catch
                {
                    // 备份失败不影响回退默认值。
                }
            }
        }
        needsSave |= ResolveConflicts(logWarnings: true);
        if (needsSave)
            Save();
        if (Values.Any(pair => !previous.TryGetValue(pair.Key, out object? old) || !Equals(old, pair.Value)))
        {
            LocalChanged?.Invoke();
            Changed?.Invoke();
        }
    }

    public static void Save()
    {
        try
        {
            string directory = Path.GetDirectoryName(ConfigPath)!;
            Directory.CreateDirectory(directory);
            Dictionary<string, string> payload = Values.ToDictionary(pair => pair.Key,
                pair => Convert.ToString(pair.Value, CultureInfo.InvariantCulture)!);
            payload[SchemaVersion] = "2";
            string temporary = ConfigPath + ".things-new";
            File.WriteAllText(temporary, JsonSerializer.Serialize(payload, JsonOptions));
            File.Move(temporary, ConfigPath, overwrite: true);
        }
        catch (Exception exception)
        {
            MegaCrit.Sts2.Core.Logging.Log.Warn(
                $"STS2_Things config could not be saved: {exception.Message}");
        }
    }

    /// <summary>读取一个键（RitsuLib 互操作访问器用；缺失返回 null）。</summary>
    public static object? GetValue(string key)
    {
        return MultiplayerConfig.GetOverride(key) ?? GetLocalValue(key);
    }

    /// <summary>写入一个键并执行冲突裁决（RitsuLib 互操作访问器与测试用）。</summary>
    public static void SetValue(string key, object? value)
    {
        SetValues(new Dictionary<string, object?> { [key] = value });
    }

    /// <summary>UI adapters apply a complete edit atomically before conflict resolution.</summary>
    public static void SetValues(IDictionary<string, object?> changes)
    {
        bool changed = false;
        foreach ((string key, object? value) in changes)
        {
            Entry? entry = Entries.FirstOrDefault(candidate => candidate.Key == key);
            if (entry is null || !CanEdit(key) || !TryNormalize(entry, value, out object normalized) || Equals(Values[key], normalized))
                continue;
            Values[key] = normalized;
            changed = true;
        }
        if (!changed)
            return;
        ResolveConflicts(logWarnings: true);
        LocalChanged?.Invoke();
        Changed?.Invoke();
    }

    private static bool TryNormalize(Entry entry, object? value, out object normalized)
    {
        normalized = entry.Default;
        if (value is JsonElement element)
        {
            value = element.ValueKind switch
            {
                JsonValueKind.True => true,
                JsonValueKind.False => false,
                JsonValueKind.String => element.GetString(),
                JsonValueKind.Number when element.TryGetDouble(out double number) => number,
                _ => null,
            };
        }
        if (entry.Default is bool)
        {
            if (value is bool boolean)
                normalized = boolean;
            else if (value is string text && bool.TryParse(text, out boolean))
                normalized = boolean;
            else
                return false;
            return true;
        }
        if (value is not (byte or short or int or long or float or double or decimal or string))
            return false;
        if (!double.TryParse(Convert.ToString(value, CultureInfo.InvariantCulture),
                NumberStyles.Float, CultureInfo.InvariantCulture, out double numeric) || !double.IsFinite(numeric))
            return false;
        normalized = (int)Math.Round(Math.Clamp(numeric, entry.Min, entry.Max), MidpointRounding.AwayFromZero);
        return true;
    }

    /// <summary>
    /// 强制启用隐含启用；同一 Boss 槽位最多一个强制项（规范顺序先到先得，其余降级）。
    /// 返回是否发生过任何改动。
    /// </summary>
    private static bool ResolveConflicts(bool logWarnings)
    {
        bool changed = false;
        foreach (Entry entry in Entries)
        {
            if (entry.Key.EndsWith("Enabled", StringComparison.Ordinal) &&
                entry.Slot is { } slot && Values.GetValueOrDefault(ForcedKeyFor(slot, entry.Key)) is true && Values[entry.Key] is false)
            {
                Values[entry.Key] = true;
                changed = true;
            }
        }

        foreach (string slot in new[] { SlotOvergrowth, SlotUnderdocks, SlotHive })
        {
            string? first = null;
            foreach (Entry entry in Entries)
            {
                if (entry.Slot != slot || !entry.Key.EndsWith("Forced", StringComparison.Ordinal))
                    continue;
                if (Values[entry.Key] is not true)
                    continue;
                if (first is null)
                {
                    first = entry.Key;
                    continue;
                }

                Values[entry.Key] = false;
                changed = true;
                if (logWarnings)
                {
                    MegaCrit.Sts2.Core.Logging.Log.Warn(
                        $"STS2_Things config: '{entry.Key}' was demoted because '{first}' is already " +
                        $"forced for the same act boss slot ({slot}).");
                }
            }
        }

        return changed;
    }

    private static string ForcedKeyFor(string slot, string enabledKey)
    {
        string prefix = enabledKey[..^"Enabled".Length];
        return prefix + "Forced";
    }
}
