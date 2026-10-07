using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class LanternMothEncounter : EncounterModel
{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => false;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["fish", "moth", "crystal"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
        [ModelDb.Monster<LanternFish>(), ModelDb.Monster<SilkMoth>(), ModelDb.Monster<CrystalSnail>()];
    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters() =>
        [(ModelDb.Monster<LanternFish>().ToMutable(), "fish"),
         (ModelDb.Monster<SilkMoth>().ToMutable(), "moth"),
         (ModelDb.Monster<CrystalSnail>().ToMutable(), "crystal")];
}
