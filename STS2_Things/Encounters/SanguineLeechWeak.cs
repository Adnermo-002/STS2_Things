using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class SanguineLeechWeak : EncounterModel
{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => true;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["first", "second"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters => [ModelDb.Monster<SanguineLeech>()];
    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        var pair = new List<(MonsterModel, string?)>();
        int[] phases = [0, 3];
        for (int i = 0; i < Slots.Count; i++)
        {
            var leech = (SanguineLeech)ModelDb.Monster<SanguineLeech>().ToMutable();
            leech.SetOpeningPhase(phases[i]);
            pair.Add((leech, Slots[i]));
        }
        return pair;
    }
}
