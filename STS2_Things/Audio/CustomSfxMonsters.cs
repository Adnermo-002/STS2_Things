using System.Collections.Generic;

namespace STS2_Things.Audio;

/// <summary>
///     使用 Godot 原生音效的自定义怪物注册表
///     加新怪物只需在这里加一行 Entry 名即可
/// </summary>
public static class CustomSfxMonsters
{
    /// <summary>怪物 Entry（ModelId.Entry 小写），路径自动拼接</summary>
    public static readonly HashSet<string> Entries = new()
    {
        "origin_fogmog",
        "gravetide_slug"
        // origin_eye_with_teeth 用原版 EyeWithTeeth 音效，不走自定义音频拦截
        // 加新怪物音效：在这里加一行，格式 "怪物entry小写",
    };
}
