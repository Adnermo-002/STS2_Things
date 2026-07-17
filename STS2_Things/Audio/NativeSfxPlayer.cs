using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Logging;
using FileAccess = Godot.FileAccess;

namespace STS2_Things.Audio;

public static class NativeSfxPlayer
{
    private static readonly Dictionary<string, AudioStream> _streamCache = new();
    private static readonly List<AudioStreamPlayer> _activePlayers = new();
    private static readonly object _activePlayersLock = new();
    // 缓存目录到候选文件列表，避免每次播放随机变体都进行IO遍历
    private static readonly Dictionary<string, string[]> _variantCache = new();
    private static readonly object _variantCacheLock = new();
    // 独立于游戏玩法 RNG 的本地音频变体 RNG。
    private static readonly RandomNumberGenerator _variantRng = new();
    private static readonly object _variantRngLock = new();
    private static AudioStreamPlayer? _musicPlayer;
    private static AudioStreamPlayer? _seqLooper;
    private static string[]? _seqPaths;
    private static int _seqIndex;
    private static float _seqVolumeDb;

    static NativeSfxPlayer()
    {
        _variantRng.Randomize();
    }

    /// <summary>
    /// Rolls a presentation-only probability using the audio RNG. This stream is
    /// deliberately isolated from combat RNG so SFX variation cannot affect saves
    /// or multiplayer simulation state.
    /// </summary>
    public static bool RollChance(float chance)
    {
        if (!float.IsFinite(chance) || chance <= 0f) return false;
        if (chance >= 1f) return true;
        lock (_variantRngLock)
        {
            return _variantRng.Randf() < chance;
        }
    }

    private static bool CanPlayAudio(bool allowCombatEnding = false)
    {
        return !NonInteractiveMode.IsActive
               && (allowCombatEnding || !CombatManager.Instance.IsEnding);
    }

    public static void Preload(string resPath)
    {
        LoadStream(resPath);
    }

    public static void Play(
        string resPath,
        string bus = "Master",
        float volumeDb = 6f,
        bool allowCombatEnding = false)
    {
        if (!CanPlayAudio(allowCombatEnding)) return;
        if (!HasAudioExtension(resPath))
        {
            var resolved = ResolveRandomVariant(resPath);
            if (resolved != null)
                PlayExact(resolved, bus, volumeDb);
            else
                Log.Warn($"[NativeSfxPlayer] No variant found for: {resPath}");
            return;
        }

        PlayExact(resPath, bus, volumeDb);
    }

    public static void PlayMusic(string resPath, string bus = "Master", float volumeDb = -6f)
    {
        if (!CanPlayAudio()) return;
        StopMusic();
        var stream = LoadStream(resPath);
        if (stream == null)
        {
            Log.Warn($"[NativeSfxPlayer] PlayMusic: stream is null for {resPath}");
            return;
        }

        _musicPlayer = new AudioStreamPlayer { Stream = stream, Bus = bus, VolumeDb = volumeDb };
        var tree = Engine.GetMainLoop();
        if (tree is SceneTree sceneTree)
        {
            sceneTree.Root.AddChild(_musicPlayer);
            _musicPlayer.Finished += () =>
            {
                if (_musicPlayer != null && _musicPlayer.IsInsideTree())
                    _musicPlayer.Play();
            };
            _musicPlayer.Play();
        }
        else
        {
            Log.Warn("[NativeSfxPlayer] PlayMusic: Cannot get SceneTree!");
        }
    }

    public static void StopMusic()
    {
        if (_musicPlayer != null)
        {
            if (_musicPlayer.Playing) _musicPlayer.Stop();
            if (_musicPlayer.IsInsideTree()) _musicPlayer.QueueFree();
            _musicPlayer = null;
        }
    }

    /// <summary>
    ///     依次循环播放多个音频文件
    /// </summary>
    public static void PlaySequentialLoop(string[]? paths, float volumeDb = -10f)
    {
        StopSequentialLoop();
        if (!CanPlayAudio() || paths == null || paths.Length == 0) return;
        _seqPaths = paths;
        _seqIndex = 0;
        _seqVolumeDb = volumeDb;
        PlayNextInSequence();
    }

    public static void StopSequentialLoop()
    {
        if (_seqLooper != null)
        {
            if (_seqLooper.Playing) _seqLooper.Stop();
            if (_seqLooper.IsInsideTree()) _seqLooper.QueueFree();
            _seqLooper = null;
        }

        _seqPaths = null;
        _seqIndex = 0;
    }

    private static void PlayNextInSequence()
    {
        if (!CanPlayAudio())
        {
            StopSequentialLoop();
            return;
        }
        var paths = _seqPaths;
        if (paths == null || paths.Length == 0)
        {
            StopSequentialLoop();
            return;
        }

        if (_seqIndex >= paths.Length) _seqIndex = 0;
        var path = paths[_seqIndex];
        _seqIndex++;
        if (_seqIndex >= paths.Length) _seqIndex = 0;

        var stream = LoadStream(path);
        if (stream == null)
        {
            Log.Warn($"[NativeSfxPlayer] SeqLoop stream is null for {path}");
            return;
        }

        _seqLooper?.QueueFree();
        _seqLooper = new AudioStreamPlayer { Stream = stream, Bus = "Master", VolumeDb = _seqVolumeDb };
        var tree = Engine.GetMainLoop();
        if (tree is SceneTree sceneTree)
        {
            sceneTree.Root.AddChild(_seqLooper);
            _seqLooper.Finished += () =>
            {
                if (_seqLooper != null && _seqLooper.IsInsideTree())
                    PlayNextInSequence();
            };
            _seqLooper.Play();
        }
    }

    private static AudioStream? LoadStream(string resPath)
    {
        if (_streamCache.TryGetValue(resPath, out var cached)) return cached;
        try
        {
            if (ResourceLoader.Exists(resPath))
            {
                var stream = ResourceLoader.Load<AudioStream>(resPath);
                if (stream != null)
                {
                    _streamCache[resPath] = stream;
                    return stream;
                }
            }

            var bytes = ReadBytesFromDisk(resPath);
            if (bytes != null && bytes.Length > 0)
            {
                var ext = Path.GetExtension(resPath).ToLowerInvariant();
                AudioStream? stream = ext switch
                {
                    ".ogg" => AudioStreamOggVorbis.LoadFromBuffer(bytes),
                    ".mp3" => AudioStreamMP3.LoadFromBuffer(bytes),
                    ".wav" => LoadWavFromBuffer(bytes),
                    _ => null
                };
                if (stream != null)
                {
                    _streamCache[resPath] = stream;
                    return stream;
                }
            }

            Log.Warn($"[NativeSfxPlayer] Failed to load: {resPath}");
            return null;
        }
        catch (Exception e)
        {
            Log.Warn($"[NativeSfxPlayer] Load error {resPath}: {e.Message}");
            return null;
        }
    }

    private static byte[]? ReadBytesFromDisk(string resPath)
    {
        var absPath = ToAbsolutePath(resPath);
        if (File.Exists(absPath)) return File.ReadAllBytes(absPath);
        var fa = FileAccess.Open(resPath, FileAccess.ModeFlags.Read);
        if (fa != null)
        {
            var len = fa.GetLength();
            if (len > 0)
            {
                var buf = fa.GetBuffer((long)len);
                fa.Dispose();
                if (buf != null && buf.Length > 0) return buf;
            }

            fa.Dispose();
        }

        return null;
    }

    private static AudioStreamWav? LoadWavFromBuffer(byte[] bytes)
    {
        if (bytes.Length < 44) return null;
        var riff = Encoding.ASCII.GetString(bytes, 0, 4);
        var wave = Encoding.ASCII.GetString(bytes, 8, 4);
        if (riff != "RIFF" || wave != "WAVE") return null;
        var stream = new AudioStreamWav();
        var offset = 12;
        byte[]? dataBytes = null;
        while (offset < bytes.Length - 8)
        {
            var chunkId = Encoding.ASCII.GetString(bytes, offset, 4);
            var chunkSize = BitConverter.ToInt32(bytes, offset + 4);
            if (chunkId == "fmt ")
            {
                int channels = BitConverter.ToInt16(bytes, offset + 10);
                var sampleRate = BitConverter.ToInt32(bytes, offset + 12);
                int bitsPerSample = BitConverter.ToInt16(bytes, offset + 22);
                if (bitsPerSample == 32) return null;
                stream.Format = bitsPerSample switch
                {
                    8 => AudioStreamWav.FormatEnum.Format8Bits,
                    _ => AudioStreamWav.FormatEnum.Format16Bits
                };
                stream.MixRate = sampleRate;
                stream.Stereo = channels == 2;
            }
            else if (chunkId == "data")
            {
                var dataSize = chunkSize;
                dataBytes = new byte[dataSize];
                Array.Copy(bytes, offset + 8, dataBytes, 0, dataSize);
                break;
            }

            offset += 8 + chunkSize;
            if (chunkSize % 2 == 1) offset++;
        }

        if (dataBytes == null) return null;
        stream.Data = dataBytes;
        return stream;
    }

    private static void PlayExact(string resPath, string bus, float volumeDb)
    {
        var stream = LoadStream(resPath);
        if (stream == null) return;
        var player = new AudioStreamPlayer { Stream = stream, Bus = bus, VolumeDb = volumeDb };
        var tree = Engine.GetMainLoop();
        if (tree is SceneTree sceneTree)
        {
            sceneTree.Root.AddChild(player);
            player.Play();
            lock (_activePlayersLock)
            {
                _activePlayers.Add(player);
            }
            player.Finished += () =>
            {
                // 检查对象是否仍然有效（Godot 对象可能已被释放）
                if (GodotObject.IsInstanceValid(player) && player.IsInsideTree())
                    player.QueueFree();
                lock (_activePlayersLock)
                {
                    _activePlayers.Remove(player);
                }
            };
        }
    }

    /// <summary>
    /// 清理所有活跃的音效播放器，防止资源泄漏。
    /// 由独立的 CombatRoomAudioCleanupPatch 在房间退出时调用。
    /// </summary>
    public static void CleanupActivePlayers()
    {
        lock (_activePlayersLock)
        {
            foreach (var player in _activePlayers)
            {
                if (GodotObject.IsInstanceValid(player))
                {
                    if (player.Playing) player.Stop();
                    if (player.IsInsideTree()) player.QueueFree();
                }
            }
            _activePlayers.Clear();
        }
    }

    private static string ToAbsolutePath(string path)
    {
        if (path.StartsWith("res://"))
        {
            var modRoot = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location)
                ?? AppContext.BaseDirectory;
            return Path.GetFullPath(Path.Combine(modRoot, path["res://".Length..]));
        }

        return Path.IsPathRooted(path) ? path : Path.GetFullPath(path);
    }

    private static string? ResolveRandomVariant(string prefixPath)
    {
        var lastSlash = prefixPath.LastIndexOf('/');
        if (lastSlash < 0) return null;
        var dir = prefixPath[..lastSlash];
        var filePrefix = prefixPath[(lastSlash + 1)..];
        if (string.IsNullOrEmpty(dir) || string.IsNullOrEmpty(filePrefix)) return null;

        // 缓存 key: "dir|prefix"
        var cacheKey = $"{dir}|{filePrefix}";
        lock (_variantCacheLock)
        {
            if (_variantCache.TryGetValue(cacheKey, out var cachedCandidates))
                return PickVariant(cachedCandidates, filePrefix);
        }

        var list = new List<string>();
        DirAccess? da = DirAccess.Open(dir);
        if (da != null)
        {
            da.ListDirBegin();
            var fileName = da.GetNext();
            while (fileName != string.Empty)
            {
                if (!da.CurrentIsDir())
                {
                    var actualName = fileName.EndsWith(".import") ? fileName[..^".import".Length] : fileName;
                    if (IsAudioFile(actualName) &&
                        actualName.StartsWith(filePrefix, StringComparison.OrdinalIgnoreCase))
                    {
                        var nameNoExt = actualName[..actualName.LastIndexOf('.')];
                        if (nameNoExt.Equals(filePrefix, StringComparison.OrdinalIgnoreCase)
                            || (nameNoExt.StartsWith(filePrefix + "-") && nameNoExt.Length > filePrefix.Length + 1 &&
                                char.IsDigit(nameNoExt[filePrefix.Length + 1])))
                            list.Add(dir + "/" + actualName);
                    }
                }

                fileName = da.GetNext();
            }

            da.ListDirEnd();
        }

        if (list.Count == 0)
        {
            var absDir = ToAbsolutePath(dir);
            if (Directory.Exists(absDir))
                foreach (var filePath in Directory.GetFiles(absDir))
                {
                    var nameNoExt = Path.GetFileNameWithoutExtension(filePath);
                    if ((nameNoExt.Equals(filePrefix, StringComparison.OrdinalIgnoreCase)
                         || (nameNoExt.StartsWith(filePrefix + "-") && nameNoExt.Length > filePrefix.Length + 1 &&
                             char.IsDigit(nameNoExt[filePrefix.Length + 1])))
                        && IsAudioFile(Path.GetExtension(filePath)))
                        list.Add(dir + "/" + Path.GetFileName(filePath));
                }
        }

        var candidates = list.ToArray();
        lock (_variantCacheLock)
        {
            _variantCache[cacheKey] = candidates;
        }

        return PickVariant(candidates, filePrefix);
    }

    private static string? PickVariant(string[] candidates, string filePrefix)
    {
        if (candidates == null || candidates.Length == 0) return null;
        var exact = Array.Find(candidates, c =>
        {
            var name = c[(c.LastIndexOf('/') + 1)..];
            var noExt = name[..name.LastIndexOf('.')];
            return noExt.Equals(filePrefix, StringComparison.OrdinalIgnoreCase);
        });
        if (exact != null) return exact;
        lock (_variantRngLock)
        {
            return candidates[_variantRng.RandiRange(0, candidates.Length - 1)];
        }
    }

    private static bool HasAudioExtension(string path)
    {
        var ext = Path.GetExtension(path).ToLowerInvariant();
        return ext == ".ogg" || ext == ".wav" || ext == ".mp3";
    }

    private static bool IsAudioFile(string fileName)
    {
        if (!fileName.Contains('.')) return false;
        var ext = fileName[fileName.LastIndexOf('.')..].ToLowerInvariant();
        return ext == ".ogg" || ext == ".wav" || ext == ".mp3";
    }
}
