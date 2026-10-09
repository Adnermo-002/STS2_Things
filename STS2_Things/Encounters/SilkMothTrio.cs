using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class SilkMothTrio : EncounterModel
{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => false;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["moth_left", "great_moth", "moth_right"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters => [ModelDb.Monster<SilkMoth>(), ModelDb.Monster<GreatSilkMoth>()];
    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        var left = (SilkMoth)ModelDb.Monster<SilkMoth>().ToMutable();
        var center = (GreatSilkMoth)ModelDb.Monster<GreatSilkMoth>().ToMutable();
        var right = (SilkMoth)ModelDb.Monster<SilkMoth>().ToMutable();
        left.SetOpeningPhase(1);
        center.SetOpeningPhase(0);
        right.SetOpeningPhase(2);
        return [(left, "moth_left"), (center, "great_moth"), (right, "moth_right")];
    }
}
