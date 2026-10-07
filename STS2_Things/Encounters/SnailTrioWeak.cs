using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class SnailTrioWeak : EncounterModel
{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => true;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["crystal", "slime", "rock"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
        [ModelDb.Monster<CrystalSnail>(), ModelDb.Monster<SlimeSnail>(), ModelDb.Monster<RockSnail>()];
    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters() =>
        [(ModelDb.Monster<CrystalSnail>().ToMutable(), "crystal"),
         (ModelDb.Monster<SlimeSnail>().ToMutable(), "slime"),
         (ModelDb.Monster<RockSnail>().ToMutable(), "rock")];
}
