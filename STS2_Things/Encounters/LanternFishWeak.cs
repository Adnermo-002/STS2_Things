using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

/// <summary>The two-fish opening encounter; identical creature rules with staggered moves.</summary>
public sealed class LanternFishWeak : EncounterModel
{
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => true;
    public override bool HasScene => true;
    public override IReadOnlyList<string> Slots => ["first", "second"];
    protected override bool HasCustomBackground => true;
    public override IEnumerable<MonsterModel> AllPossibleMonsters => [ModelDb.Monster<LanternFish>()];
    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        var fish = new List<(MonsterModel, string?)>();
        for (int phase = 0; phase < 2; phase++)
        {
            var monster = (LanternFish)ModelDb.Monster<LanternFish>().ToMutable();
            monster.SetOpeningPhase(phase);
            fish.Add((monster, Slots[phase]));
        }
        return fish;
    }
}
