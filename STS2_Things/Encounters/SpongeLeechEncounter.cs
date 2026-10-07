using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class SpongeLeechEncounter : EncounterModel
{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => false;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["sponge", "leech_1", "leech_2"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
        [ModelDb.Monster<WaterSponge>(), ModelDb.Monster<SanguineLeech>()];

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        var first = (SanguineLeech)ModelDb.Monster<SanguineLeech>().ToMutable();
        var second = (SanguineLeech)ModelDb.Monster<SanguineLeech>().ToMutable();
        first.SetOpeningPhase(0);
        second.SetOpeningPhase(2);
        return [(ModelDb.Monster<WaterSponge>().ToMutable(), "sponge"), (first, "leech_1"), (second, "leech_2")];
    }
}
