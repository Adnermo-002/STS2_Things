using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class SanguineLeechEncounter : EncounterModel
{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => false;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["first", "second", "third"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters => [ModelDb.Monster<SanguineLeech>()];
    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        var colony = new List<(MonsterModel, string?)>();
        int[] phases = [0, 1, 3];
        for (int i = 0; i < Slots.Count; i++)
        {
            var leech = (SanguineLeech)ModelDb.Monster<SanguineLeech>().ToMutable();
            leech.SetOpeningPhase(phases[i]);
            colony.Add((leech, Slots[i]));
        }
        return colony;
    }
}
