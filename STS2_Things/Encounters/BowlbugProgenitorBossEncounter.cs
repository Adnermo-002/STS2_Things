using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class BowlbugProgenitorBossEncounter : ModBossEncounter
{
    protected override string IconName => "bowlbug_progenitor";

    public override RoomType RoomType => RoomType.Boss;

    // Keep the BGM in Hive's native act2 bank. EncounterModel has no cross-Act
    // bank declaration, so cross-bank music needs an invasive loader patch.
    public override string CustomBgm => "event:/music/act2_boss_kaiser_crab";

    public override bool HasScene => true;

    protected override bool HasCustomBackground => true;

    public override IEnumerable<string> ExtraAssetPaths => new[]
    {
        "res://images/ui/run_history/bowlbug_progenitor_boss_encounter.png",
        "res://images/ui/run_history/bowlbug_progenitor_boss_encounter_outline.png"
    };

    public override IReadOnlyList<string> Slots =>
        new[] { "bowlbug_progenitor" }
            .Concat(Enumerable.Range(1, 16).Select(i => $"bowlbug_{i}"))
            .ToArray();

    public override IEnumerable<MonsterModel> AllPossibleMonsters => new MonsterModel[]
    {
        ModelDb.Monster<BowlbugProgenitor>(),
        ModelDb.Monster<BowlbugSilk>(),
        ModelDb.Monster<BowlbugRock>(),
        ModelDb.Monster<BowlbugNectar>(),
        ModelDb.Monster<BowlbugEgg>()
    };

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        return new (MonsterModel, string?)[]
        {
            (ModelDb.Monster<BowlbugProgenitor>().ToMutable(),
                "bowlbug_progenitor")
        };
    }
}
