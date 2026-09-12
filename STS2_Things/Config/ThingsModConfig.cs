using System.Text.Json;
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
    }

    /// <summary>Boss 槽位（冲突分组）。同一槽位只能有一个强制 Boss。</summary>
    public const string SlotOvergrowth = "overgrowth";
    public const string SlotUnderdocks = "underdocks";
    public const string SlotHive = "hive";

    public sealed record Entry(
        string Key,
        Category Category,
        bool Default,
        string? Slot = null);

    // ===== 键常量（单一来源：BaseLib 桥属性名、RitsuLib schema 与门控代码都引用这里）=====
    public const string SchemaVersion = "SchemaVersion";

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

    // ---- 商人猜拳 ----
    public const string FeatureMerchantBargainEnabled = "FeatureMerchantBargainEnabled";

    // ---- 涅奥起始遗物 ----
    public const string NeowRelicCurseRemoverEnabled = "NeowRelicCurseRemoverEnabled";
    public const string NeowRelicWhiteFlagEnabled = "NeowRelicWhiteFlagEnabled";
    public const string NeowRelicMagicGloveEnabled = "NeowRelicMagicGloveEnabled";

    /// <summary>规范顺序即冲突裁决顺序：同槽位第一个强制项生效。</summary>
    public static readonly IReadOnlyList<Entry> Entries =
    [
        new(BossOriginFogmogEnabled, Category.Boss, Default: true, Slot: SlotOvergrowth),
        new(BossOriginFogmogForced, Category.Boss, Default: false, Slot: SlotOvergrowth),
        new(BossScaleBeetleEnabled, Category.Boss, Default: true, Slot: SlotOvergrowth),
        new(BossScaleBeetleForced, Category.Boss, Default: false, Slot: SlotOvergrowth),
        new(BossGravetideSlugEnabled, Category.Boss, Default: true, Slot: SlotUnderdocks),
        new(BossGravetideSlugForced, Category.Boss, Default: false, Slot: SlotUnderdocks),
        new(BossTheLegacyEnabled, Category.Boss, Default: true, Slot: SlotUnderdocks),
        new(BossTheLegacyForced, Category.Boss, Default: false, Slot: SlotUnderdocks),
        new(BossBowlbugProgenitorEnabled, Category.Boss, Default: true, Slot: SlotHive),
        new(BossBowlbugProgenitorForced, Category.Boss, Default: false, Slot: SlotHive),
        new(BossCaveGodEnabled, Category.Boss, Default: true, Slot: SlotHive),
        new(BossCaveGodForced, Category.Boss, Default: false, Slot: SlotHive),
        new(EncounterSoulRoesEnabled, Category.Encounter, Default: true),
        new(EncounterQuirkyHopperEnabled, Category.Encounter, Default: true),
        new(EventRobberyFakeMerchantEnabled, Category.Event, Default: true),
        new(EventBackroomsEnabled, Category.Event, Default: true),
        new(EventMedusaEnabled, Category.Event, Default: true),
        new(EventCuttingItCloseEnabled, Category.Event, Default: true),
        new(FeatureMerchantBargainEnabled, Category.Feature, Default: true),
        new(NeowRelicCurseRemoverEnabled, Category.NeowRelic, Default: true),
        new(NeowRelicWhiteFlagEnabled, Category.NeowRelic, Default: true),
        new(NeowRelicMagicGloveEnabled, Category.NeowRelic, Default: true),
    ];

    private static readonly Dictionary<string, bool> Values =
        Entries.ToDictionary(entry => entry.Key, entry => entry.Default);

    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    /// <summary>配置发生变化（含强制冲突裁决后的降级）时触发。</summary>
    public static event Action? Changed;

    public static string ConfigPath =>
        Path.Combine(OS.GetUserDataDir(), "mod_configs", "STS2_Things.cfg");

    public static bool IsEnabled(string key)
    {
        return Values.TryGetValue(key, out bool value) && value;
    }

    public static bool IsForced(string key)
    {
        return Values.TryGetValue(key, out bool value) && value;
    }

    /// <summary>读取任意布尔键（含 Forced 键）。</summary>
    public static bool GetBool(string key)
    {
        return Values.TryGetValue(key, out bool value) && value;
    }

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
        Values.Clear();
        foreach (Entry entry in Entries)
            Values[entry.Key] = entry.Default;

        string path = ConfigPath;
        if (File.Exists(path))
        {
            try
            {
                using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
                if (document.RootElement.ValueKind == JsonValueKind.Object)
                {
                    foreach (JsonProperty property in document.RootElement.EnumerateObject())
                    {
                        if (!Values.ContainsKey(property.Name))
                            continue;
                        // BaseLib 的 ModConfig 把 bool 属性写成 "True"/"False" 字符串；
                        // 独立模式写 JSON 布尔。两种都接受。
                        if (property.Value.ValueKind == JsonValueKind.True)
                            Values[property.Name] = true;
                        else if (property.Value.ValueKind == JsonValueKind.False)
                            Values[property.Name] = false;
                        else if (property.Value.ValueKind == JsonValueKind.String &&
                                 bool.TryParse(property.Value.GetString(), out bool parsed))
                            Values[property.Name] = parsed;
                    }
                }
            }
            catch (Exception exception)
            {
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
        else
        {
            Save();
        }

        ResolveConflicts(logWarnings: true);
    }

    public static void Save()
    {
        try
        {
            string directory = Path.GetDirectoryName(ConfigPath)!;
            Directory.CreateDirectory(directory);
            Dictionary<string, bool> payload = new(Values) { [SchemaVersion] = true };
            File.WriteAllText(ConfigPath, JsonSerializer.Serialize(payload, JsonOptions));
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
        return Values.TryGetValue(key, out bool value) ? value : null;
    }

    /// <summary>写入一个键并执行冲突裁决（RitsuLib 互操作访问器与测试用）。</summary>
    public static void SetValue(string key, object? value)
    {
        if (!Values.ContainsKey(key) || value is not bool boolean)
            return;

        bool changed = Values[key] != boolean;
        if (!changed)
            return;

        Values[key] = boolean;
        ResolveConflicts(logWarnings: true);
        Changed?.Invoke();
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
                entry.Slot is { } slot && IsForced(ForcedKeyFor(slot, entry.Key)) && !IsEnabled(entry.Key))
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
                if (!IsForced(entry.Key))
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
