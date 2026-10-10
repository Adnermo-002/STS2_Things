using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Rooms;

namespace STS2_Things.Encounters;

/// <summary>Event-only pair; preserves the native merchant models and reward budget.</summary>
public sealed class RobberyFakeMerchantEncounter : EncounterModel
{
    private bool _healthPrepared;
    public override RoomType RoomType => RoomType.Monster;
    public override bool HasScene => true;
    protected override bool HasCustomBackground => true;
    public override IReadOnlyList<string> Slots => ["merchant_left", "merchant_right"];
    public override IEnumerable<MonsterModel> AllPossibleMonsters => [ModelDb.Monster<FakeMerchantMonster>()];
    public override int MinGoldReward => 300;
    public override int MaxGoldReward => 300;

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters() =>
    [
        (ModelDb.Monster<FakeMerchantMonster>().ToMutable(), "merchant_left"),
        (ModelDb.Monster<FakeMerchantMonster>().ToMutable(), "merchant_right"),
    ];

    internal async Task PrepareForFight(ICombatState state)
    {
        AssertMutable();
        if (_healthPrepared) return;
        // Shared events execute one callback per player against the same arena.
        // Mark the mutable encounter before awaiting, so both merchants are
        // halved once after native multiplayer HP scaling, never once per voter.
        _healthPrepared = true;
        foreach (var merchant in state.Enemies.Where(c => c.Monster is FakeMerchantMonster))
            await CreatureCmd.SetMaxAndCurrentHp(merchant, Math.Max(1, merchant.MaxHp / 2));
    }
}
