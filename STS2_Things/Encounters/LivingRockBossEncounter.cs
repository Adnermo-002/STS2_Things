using System.Collections.Generic;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class LivingRockBossEncounter : ModBossEncounter
{
    public const string BossSlot = "living_rock";

    protected override string IconName => "living_rock";

    public override RoomType RoomType => RoomType.Boss;

    public override bool HasScene => true;

    public override IReadOnlyList<string> Slots => [BossSlot];

    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
    [
        ModelDb.Monster<ThingsLivingRock>()
    ];

    public override IEnumerable<string> ExtraAssetPaths =>
    [
        "res://images/map/living_rock_boss_icon.png",
        "res://images/map/living_rock_boss_icon_outline.png"
    ];

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        return [(ModelDb.Monster<ThingsLivingRock>().ToMutable(), BossSlot)];
    }
}
