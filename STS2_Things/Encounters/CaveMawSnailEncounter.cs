using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class CaveMawSnailEncounter : EncounterModel
{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => false;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["maw", "crystal", "slime"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
        [ModelDb.Monster<CaveMaw>(), ModelDb.Monster<CrystalSnail>(), ModelDb.Monster<SlimeSnail>()];
    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters() =>
        [(ModelDb.Monster<CaveMaw>().ToMutable(), "maw"),
         (ModelDb.Monster<CrystalSnail>().ToMutable(), "crystal"),
         (ModelDb.Monster<SlimeSnail>().ToMutable(), "slime")];
}
