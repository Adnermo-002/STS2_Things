using System.Collections.Generic;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class ScaleBeetleBossEncounter : ModBossEncounter
{
    protected override string IconName => "scale_beetle";

    public override RoomType RoomType => RoomType.Boss;

    // 复用Vantom的专属Boss音乐（有完整progress参数+升调自动化）
    public override string CustomBgm => "event:/music/act1_boss_vantom";
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;

    public override IEnumerable<string> ExtraAssetPaths => new[]
    {
        "res://images/ui/run_history/scale_beetle_boss_encounter.png",
        "res://images/ui/run_history/scale_beetle_boss_encounter_outline.png"
    };

    public override IReadOnlyList<string> Slots => ["scale_beetle"];

    public override IEnumerable<MonsterModel> AllPossibleMonsters => new MonsterModel[]
    {
        ModelDb.Monster<ThingsScaleBeetle>()
    };

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        return new (MonsterModel, string?)[]
        {
            (ModelDb.Monster<ThingsScaleBeetle>().ToMutable(), "scale_beetle")
        };
    }
}
