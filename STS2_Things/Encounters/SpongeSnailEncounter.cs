using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class SpongeSnailEncounter : EncounterModel
{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => false;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["sponge", "rock", "crystal"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
        [ModelDb.Monster<WaterSponge>(), ModelDb.Monster<RockSnail>(), ModelDb.Monster<CrystalSnail>()];
    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters() =>
        [(ModelDb.Monster<WaterSponge>().ToMutable(), "sponge"),
         (ModelDb.Monster<RockSnail>().ToMutable(), "rock"),
         (ModelDb.Monster<CrystalSnail>().ToMutable(), "crystal")];
}
