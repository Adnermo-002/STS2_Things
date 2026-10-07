using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

/// <summary>
/// 活体巨岩 (Living Megalith) boss encounter - Built against Kaiser Crab dual-monster architectural framework.
/// Uses 0.75x camera scaling, centered players, dual monster proxies (Left Hand & Right Hand),
/// and a full-screen dual-pass background Spine driver.
/// </summary>
public sealed class CaveGodBossEncounter : ModBossEncounter
{
    public const string LeftHandSlot = "left_hand";
    public const string RightHandSlot = "right_hand";
    public const string CaptiveHandSlot = "captive_hand";
    public const string BodySlot = "body";

    protected override string IconName => "cave_god";

    public override RoomType RoomType => RoomType.Boss;

    // 复用原版帝王蟹音乐（全套管弦乐+动态打击参数）
    public override string CustomBgm => ConfiguredBgm("event:/music/act2_boss_kaiser_crab");

    public override bool HasScene => true;

    protected override bool HasCustomBackground => true;

    public override IEnumerable<string> ExtraAssetPaths =>
    [
        "res://images/map/cave_god_boss_icon.png",
        "res://images/map/cave_god_boss_icon_outline.png",
        "res://images/ui/run_history/cave_god_boss_encounter.png",
        "res://images/ui/run_history/cave_god_boss_encounter_outline.png",
        "res://images/ui/run_history/cave_god_boss.png",
        "res://images/ui/run_history/cave_god_boss_outline.png",
        "res://images/packed/card_portraits/token/cave_god_broken_blade_trial.png",
        "res://images/packed/card_portraits/token/cave_god_shattered_shield_trial.png",
        "res://images/packed/card_portraits/token/things_cave_god_crystal_shard.png",
        "res://images/packed/card_portraits/token/cave_god_martial_trial.png",
        "res://images/packed/card_portraits/token/cave_god_arcane_trial.png",
        "res://images/rooms/cave_god_boss/cavegod_bg_far_blue.png",
        "res://images/rooms/cave_god_boss/cavegod_bg_far.png",
        "res://images/rooms/cave_god_boss/cavegod_fg_platform.png",
        ..ModelDb.Monster<ThingsCaveGodCaptiveClaw>().AssetPaths,
        ..ModelDb.Monster<ThingsCaveGodBody>().AssetPaths
    ];

    public override bool FullyCenterPlayers => true;

    public override float GetCameraScaling() => 0.75f;

    public override Vector2 GetCameraOffset() => Vector2.Down * 35f;

    public override IReadOnlyList<string> Slots => [LeftHandSlot, RightHandSlot, CaptiveHandSlot, BodySlot];

    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
    [
        ModelDb.Monster<ThingsCaveGodBody>(),
        ModelDb.Monster<ThingsCaveGodLeftHand>(),
        ModelDb.Monster<ThingsCaveGodRightHand>(),
        ModelDb.Monster<ThingsCaveGodCaptiveClaw>()
    ];

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        return
        [
            (ModelDb.Monster<ThingsCaveGodLeftHand>().ToMutable(), LeftHandSlot),
            (ModelDb.Monster<ThingsCaveGodRightHand>().ToMutable(), RightHandSlot),
            (ModelDb.Monster<ThingsCaveGodBody>().ToMutable(), BodySlot)
        ];
    }
}
