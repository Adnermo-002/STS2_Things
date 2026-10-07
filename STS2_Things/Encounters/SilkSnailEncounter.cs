using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class SilkSnailEncounter : EncounterModel
{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => false;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["moth", "rock", "slime"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
        [ModelDb.Monster<SilkMoth>(), ModelDb.Monster<RockSnail>(), ModelDb.Monster<SlimeSnail>()];
    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters() =>
        [(ModelDb.Monster<SilkMoth>().ToMutable(), "moth"),
         (ModelDb.Monster<RockSnail>().ToMutable(), "rock"),
         (ModelDb.Monster<SlimeSnail>().ToMutable(), "slime")];
}
