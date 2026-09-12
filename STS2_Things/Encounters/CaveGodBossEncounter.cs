using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

/// <summary>
/// Cave God boss encounter - Built against Kaiser Crab architectural framework.
/// Uses 0.75x camera scaling, centered players, and full-screen background Spine driver.
/// </summary>
public sealed class CaveGodBossEncounter : ModBossEncounter
{
    private const string SlotName = "cave_god";

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

    public override IReadOnlyList<string> Slots => [SlotName];

    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
    [
        ModelDb.Monster<ThingsCaveGod>()
    ];

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        return
        [
            (ModelDb.Monster<ThingsCaveGod>().ToMutable(), SlotName)
        ];
    }
}
