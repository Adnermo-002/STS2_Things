using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using STS2_Things.Audio;

namespace STS2_Things.Hooks;

public static class SfxHooks
{
    private const float OriginFogmogHurtChance = 0.35f;

    /// <summary>
    ///     兼容旧的战斗退出清理调用。死亡音效不再使用跨实例的全局去重状态。
    /// </summary>
    public static void ResetDeathSfx()
    {
    }

    private static bool CanPlayCombatAudio()
    {
        return !NonInteractiveMode.IsActive && !CombatManager.Instance.IsEnding;
    }

    private static bool CanPlayDeathAudio()
    {
        // IsEnding becomes true as soon as no primary enemy remains. Native
        // Spine death SFX still play in that state, so the Sprite2D fallback must
        // allow the normal death window but reject bestiary/previews and rooms
        // that have already completed combat teardown.
        return !NonInteractiveMode.IsActive && CombatManager.Instance.IsInProgress;
    }

    private static string? MapToNativePath(string fmodPath)
    {
        var segments = fmodPath.Split('/');
        if (segments.Length < 2) return null;
        var actionName = segments[^1];
        var monsterId = CustomSfxMonsters.Entries.FirstOrDefault(e => fmodPath.ToLowerInvariant().Contains(e));
        if (monsterId == null) return null;
        return $"res://sfx/{monsterId}/{actionName}";
    }

    private static string MapToNativePathForMonster(string monsterId, string actionName)
    {
        return $"res://sfx/{monsterId}/{monsterId}_{actionName}";
    }

    private static void PreloadMonsterSfx(string monsterId)
    {
        var resDir = $"res://sfx/{monsterId}";
        var files = ListAudioFiles(resDir);
        if (files.Count == 0)
        {
            var modRoot = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location)
                ?? AppContext.BaseDirectory;
            var absDir = Path.Combine(modRoot, "sfx", monsterId);
            if (Directory.Exists(absDir))
                foreach (var filePath in Directory.GetFiles(absDir))
                    if (IsAudioFile(filePath))
                        files.Add($"{resDir}/{Path.GetFileName(filePath)}");
        }

        foreach (var resPath in files) NativeSfxPlayer.Preload(resPath);
    }

    private static List<string> ListAudioFiles(string resDir)
    {
        var result = new List<string>();
        var da = DirAccess.Open(resDir);
        if (da == null) return result;
        da.ListDirBegin();
        var fileName = da.GetNext();
        while (fileName != string.Empty)
        {
            if (!da.CurrentIsDir() && IsAudioFile(fileName)) result.Add($"{resDir}/{fileName}");
            fileName = da.GetNext();
        }

        da.ListDirEnd();
        return result;
    }

    private static bool IsAudioFile(string fileName)
    {
        if (!fileName.Contains('.')) return false;
        var ext = fileName[fileName.LastIndexOf('.')..].ToLowerInvariant();
        return ext == ".ogg" || ext == ".wav" || ext == ".mp3";
    }

    [HarmonyPatch(typeof(SfxCmd), nameof(SfxCmd.Play), typeof(string), typeof(float))]
    public static class SfxCmdPlayPatch
    {
        [HarmonyPrefix]
        public static bool Prefix(ref string sfx, float volume)
        {
            if (sfx == null) return true;
            var entries = CustomSfxMonsters.Entries;
            if (entries.Count == 0) return true;
            // 避免 ToLower 分配，直接用 OrdinalIgnoreCase 比较
            foreach (var e in entries)
                if (sfx.IndexOf(e, StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    // SfxCmd 的 volume 是线性增益；Godot AudioStreamPlayer 使用 dB。
                    // 0（以及非法/负值）表示静音，不创建无意义的播放器。
                    if (!CanPlayCombatAudio() || !float.IsFinite(volume) || volume <= 0f) return false;
                    var nativePath = MapToNativePath(sfx);
                    if (nativePath != null)
                        NativeSfxPlayer.Play(nativePath, volumeDb: Mathf.LinearToDb(volume));
                    return false;
                }

            return true;
        }
    }

    [HarmonyPatch(typeof(SfxCmd), nameof(SfxCmd.PlayDamage))]
    public static class SfxCmdPlayDamagePatch
    {
        [HarmonyPrefix]
        public static bool Prefix(MonsterModel? monster, int damageAmount)
        {
            if (monster == null) return true;
            var entry = monster.Id.Entry.ToLowerInvariant();
            if (!CustomSfxMonsters.Entries.Contains(entry)) return true;
            if (!CanPlayCombatAudio()) return false;

            // Keep the normal material impact on non-vocal hits. The custom
            // Origin Fogmog hurt variant replaces it only on a local 35% roll.
            if (entry == "origin_fogmog" && !NativeSfxPlayer.RollChance(OriginFogmogHurtChance))
                return true;

            var nativePath = MapToNativePathForMonster(entry, "hurt");
            if (nativePath != null) NativeSfxPlayer.Play(nativePath, volumeDb: 0f);
            return false;
        }
    }

    [HarmonyPatch(typeof(SfxCmd), nameof(SfxCmd.PlayDeath), typeof(MonsterModel))]
    public static class SfxCmdPlayDeathPatch
    {
        [HarmonyPrefix]
        public static bool Prefix(MonsterModel? monster)
        {
            if (monster == null) return true;
            var entry = monster.Id.Entry.ToLowerInvariant();
            if (!CustomSfxMonsters.Entries.Contains(entry)) return true;
            if (!CanPlayDeathAudio()) return false;
            var nativePath = MapToNativePathForMonster(entry, "die");
            if (nativePath != null)
                NativeSfxPlayer.Play(nativePath, volumeDb: 0f, allowCombatEnding: true);
            return false;
        }
    }

    [HarmonyPatch(typeof(MonsterModel), nameof(MonsterModel.CreateVisuals))]
    public static class MonsterCreateVisualsPostfix
    {
        public static void Postfix(MonsterModel __instance)
        {
            var entry = __instance.Id.Entry.ToLowerInvariant();
            if (CustomSfxMonsters.Entries.Contains(entry)) PreloadMonsterSfx(entry);
        }
    }

    [HarmonyPatch(typeof(NCreature), nameof(NCreature.StartDeathAnim))]
    public static class StartDeathAnimPatch
    {
        [HarmonyPrefix]
        public static void Prefix(NCreature __instance, out bool __state)
        {
            __state = false;
            var monster = __instance.Entity?.Monster;
            if (monster == null || !monster.HasDeathSfx || __instance.HasSpineAnimation) return;

            // 原方法在死亡动画仍运行时会提前返回；此时不能重复播放兜底音效。
            var deathAnimationTask = __instance.DeathAnimationTask;
            if (deathAnimationTask != null && !deathAnimationTask.IsCompleted) return;

            // The vanilla method only calls SfxCmd.PlayDeath when it created a Spine
            // animator. Our native Godot Sprite2D scenes intentionally have no Spine
            // controller, so provide the same lifecycle call for this mod's models only.
            // SfxCmdPlayDeathPatch below still redirects monsters with bundled audio.
            __state = monster.GetType().Assembly == typeof(SfxHooks).Assembly && CanPlayDeathAudio();
        }

        [HarmonyPostfix]
        public static void Postfix(NCreature __instance, bool __state)
        {
            // 有 Spine 时，原方法会调用 SfxCmd.PlayDeath，由上面的 PlayDeath patch
            // 完成唯一一次替换；这里只为原方法不会播放死亡音效的无 Spine 怪物兜底。
            if (!__state || __instance.HasSpineAnimation || !CanPlayDeathAudio()) return;
            var entity = __instance.Entity;
            var monster = entity?.Monster;
            if (monster == null || !monster.HasDeathSfx) return;
            SfxCmd.PlayDeath(monster);
        }
    }
}
