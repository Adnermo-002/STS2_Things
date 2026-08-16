using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Rooms;

namespace STS2_Things.Relics;

public sealed class ThingsAlmondWater : RelicModel
{
    public override RelicRarity Rarity => RelicRarity.Event;

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new IntVar("NormalRegen", 1),
        new IntVar("EliteRegen", 2),
        new IntVar("BossRegen", 3)
    ];

    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
    [
        HoverTipFactory.FromPower<RegenPower>()
    ];

    public override async Task AfterSideTurnStart(CombatSide side, IReadOnlyList<Creature> participants,
        ICombatState combatState)
    {
        if (side == Owner.Creature.Side && combatState.RoundNumber == 1)
        {
            Flash();
            int regenAmount = combatState.Encounter?.RoomType switch
            {
                RoomType.Boss => (int)DynamicVars["BossRegen"].BaseValue,
                RoomType.Elite => (int)DynamicVars["EliteRegen"].BaseValue,
                _ => (int)DynamicVars["NormalRegen"].BaseValue
            };
            await PowerCmd.Apply<RegenPower>(
                new ThrowingPlayerChoiceContext(),
                Owner.Creature,
                regenAmount,
                Owner.Creature,
                null
            );
        }
    }
}
