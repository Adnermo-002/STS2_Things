using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class HumanFaceColumnEncounter : EncounterModel
{
    // One encounter entry with native seeded variants, as in BowlbugsNormal.
    // This expands the matchups without increasing the column's pool weight.
    private static IReadOnlyList<(MonsterModel Monster, string Slot)> Companions =>
    [
        (ModelDb.Monster<RockSnail>(), "rock"),
        (ModelDb.Monster<CrystalSnail>(), "crystal"),
        (ModelDb.Monster<SanguineLeech>(), "leech"),
        (ModelDb.Monster<LanternFish>(), "fish"),
        (ModelDb.Monster<SilkMoth>(), "moth"),
        (ModelDb.Monster<WaterSponge>(), "sponge"),
    ];

    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => false;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots =>
        ["column_top", "column_middle", "column_bottom", .. Companions.Select(entry => entry.Slot)];
    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
        [ModelDb.Monster<HumanFaceColumn>(), .. Companions.Select(entry => entry.Monster)];

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        var companion = Rng.NextItem(Companions);
        return [.. HumanFaceColumnGroup.CreateInitial(), (companion.Monster.ToMutable(), companion.Slot)];
    }
}
