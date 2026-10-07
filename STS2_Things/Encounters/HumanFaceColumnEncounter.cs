using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class HumanFaceColumnEncounter : EncounterModel
{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => false;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["column_top", "column_middle", "column_bottom"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters => [ModelDb.Monster<HumanFaceColumn>()];
    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters() => HumanFaceColumnGroup.CreateInitial();
}
