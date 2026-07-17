using System.Collections.Generic;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class TheLegacyBossEncounter : ModBossEncounter
{
    protected override string IconName => "the_legacy";

    public override RoomType RoomType => RoomType.Boss;

    // Keep the BGM in Underdocks' native act1_b bank. EncounterModel has no
    // cross-Act bank declaration, so cross-bank music needs an invasive loader patch.
    public override string CustomBgm => "event:/music/act1_b_boss_waterfall_giant";

    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;

    public override IEnumerable<string> ExtraAssetPaths => new[]
    {
        "res://images/ui/run_history/the_legacy_boss_encounter.png",
        "res://images/ui/run_history/the_legacy_boss_encounter_outline.png"
    };

    public override IReadOnlyList<string> Slots => ["the_legacy"];

    public override IEnumerable<MonsterModel> AllPossibleMonsters => new MonsterModel[]
    {
        ModelDb.Monster<TheLegacy>()
    };

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        return new (MonsterModel, string?)[]
        {
            (ModelDb.Monster<TheLegacy>().ToMutable(), "the_legacy")
        };
    }
}
