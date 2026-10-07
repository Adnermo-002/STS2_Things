using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class CaveMawEncounter : EncounterModel
{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => false;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["maw", "moth", "leech"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
        [ModelDb.Monster<CaveMaw>(), ModelDb.Monster<SilkMoth>(), ModelDb.Monster<SanguineLeech>()];
    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        var leech = (SanguineLeech)ModelDb.Monster<SanguineLeech>().ToMutable();
        leech.SetOpeningPhase(0);
        return [(ModelDb.Monster<CaveMaw>().ToMutable(), "maw"),
            (ModelDb.Monster<SilkMoth>().ToMutable(), "moth"), (leech, "leech")];
    }
}
