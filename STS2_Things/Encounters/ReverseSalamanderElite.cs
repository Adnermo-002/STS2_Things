using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class ReverseSalamanderElite : EncounterModel
{
    public override RoomType RoomType => RoomType.Elite;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["salamander"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters => [ModelDb.Monster<ReverseSalamander>()];
    protected override IReadOnlyList<(MonsterModel,string?)> GenerateMonsters() =>
        [(ModelDb.Monster<ReverseSalamander>().ToMutable(),"salamander")];
}
