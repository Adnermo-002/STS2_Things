using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class LanternSpongeEncounter : EncounterModel
{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => false;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["fish", "sponge", "crystal"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
        [ModelDb.Monster<LanternFish>(), ModelDb.Monster<WaterSponge>(), ModelDb.Monster<CrystalSnail>()];
    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters() =>
        [(ModelDb.Monster<LanternFish>().ToMutable(), "fish"),
         (ModelDb.Monster<WaterSponge>().ToMutable(), "sponge"),
         (ModelDb.Monster<CrystalSnail>().ToMutable(), "crystal")];
}
