using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class SpongeLeechWeak : EncounterModel
{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => true;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["sponge", "leech_1"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
        [ModelDb.Monster<WaterSponge>(), ModelDb.Monster<SanguineLeech>()];

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        var leech = (SanguineLeech)ModelDb.Monster<SanguineLeech>().ToMutable();
        leech.SetOpeningPhase(0);
        return [(ModelDb.Monster<WaterSponge>().ToMutable(), "sponge"), (leech, "leech_1")];
    }
}
