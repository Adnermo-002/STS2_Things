using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class LeechMotherEncounter : EncounterModel
{
    private bool _leftUndisturbed;
    public override RoomType RoomType => RoomType.Monster;
    public override bool IsWeak => false;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override bool ShouldGiveRewards => !_leftUndisturbed;
    public override IReadOnlyList<string> Slots => ["mother", "brood_front", "brood_rear"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
        [ModelDb.Monster<LeechMother>(), ModelDb.Monster<SanguineLeech>()];
    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters() =>
        [(ModelDb.Monster<LeechMother>().ToMutable(), "mother")];

    public void LeaveUndisturbed() { AssertMutable(); _leftUndisturbed = true; }
    public override Dictionary<string, string> SaveCustomState() =>
        new() { ["leftUndisturbed"] = _leftUndisturbed ? "1" : "0" };
    public override void LoadCustomState(Dictionary<string, string> state)
    {
        AssertMutable();
        _leftUndisturbed = state.GetValueOrDefault("leftUndisturbed") == "1";
    }
}
