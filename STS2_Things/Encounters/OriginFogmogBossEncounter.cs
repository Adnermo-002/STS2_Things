using System.Collections.Generic;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class OriginFogmogBossEncounter : ModBossEncounter
{
    protected override string IconName => "origin_fogmog";

    public override IEnumerable<string> ExtraAssetPaths => new[]
    {
        "res://images/ui/run_history/origin_fogmog_boss_encounter.png",
        "res://images/ui/run_history/origin_fogmog_boss_encounter_outline.png"
    };

    public override RoomType RoomType => RoomType.Boss;

    // 复用TheKin(Queen)的专属Boss音乐（多阶段+随从，与Fogmog机制相似）
    public override string CustomBgm => "event:/music/act1_boss_the_kin";

    public override bool HasScene => true;

    protected override bool HasCustomBackground => true;

    public override IReadOnlyList<string> Slots => new[] { "fogmog", "illusion1", "illusion2" };

    public override IEnumerable<MonsterModel> AllPossibleMonsters => new MonsterModel[]
    {
        ModelDb.Monster<OriginFogmog>(),
        ModelDb.Monster<OriginEyeWithTeeth>()
    };

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        return new (MonsterModel, string?)[1]
        {
            (ModelDb.Monster<OriginFogmog>().ToMutable(), "fogmog")
        };
    }
}
