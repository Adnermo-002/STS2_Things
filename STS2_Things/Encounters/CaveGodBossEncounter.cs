using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

/// <summary>
/// Cave God boss encounter - Built against Kaiser Crab dual-monster architectural framework.
/// Uses 0.75x camera scaling, centered players, dual monster proxies (Left Hand & Right Hand),
/// and a full-screen dual-pass background Spine driver.
/// </summary>
public sealed class CaveGodBossEncounter : ModBossEncounter
{
    public const string LeftHandSlot = "left_hand";
    public const string RightHandSlot = "right_hand";
    public const string CaptiveHandSlot = "captive_hand";

    protected override string IconName => "cave_god";

    public override RoomType RoomType => RoomType.Boss;

    // 复用原版帝王蟹音乐（全套管弦乐+动态打击参数）
    public override string CustomBgm => "event:/music/act2_boss_kaiser_crab";

    public override bool HasScene => true;

    protected override bool HasCustomBackground => true;

    public override IEnumerable<string> ExtraAssetPaths =>
    [
        "res://images/ui/run_history/cave_god_boss_encounter.png",
        "res://images/ui/run_history/cave_god_boss_encounter_outline.png"
    ];

    public override bool FullyCenterPlayers => true;

    public override float GetCameraScaling() => 0.75f;

    public override Vector2 GetCameraOffset() => Vector2.Down * 35f;

    public override IReadOnlyList<string> Slots => [LeftHandSlot, RightHandSlot, CaptiveHandSlot];

    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
    [
        ModelDb.Monster<ThingsCaveGodLeftHand>(),
        ModelDb.Monster<ThingsCaveGodRightHand>(),
        ModelDb.Monster<ThingsCaveGodCaptiveClaw>()
    ];

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        return
        [
            (ModelDb.Monster<ThingsCaveGodLeftHand>().ToMutable(), LeftHandSlot),
            (ModelDb.Monster<ThingsCaveGodRightHand>().ToMutable(), RightHandSlot)
        ];
    }
}
