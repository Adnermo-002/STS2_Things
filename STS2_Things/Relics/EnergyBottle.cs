using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Things.Relics;

public sealed class EnergyBottle : RelicModel
{
    public override RelicRarity Rarity => RelicRarity.Starter;

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new EnergyVar(2),
        new GoldVar(10)
    ];

    // v1.0.7: 新增 IReadOnlyList<Creature> participants, CombatState → ICombatState
    public override async Task AfterSideTurnStart(CombatSide side, IReadOnlyList<Creature> participants,
        ICombatState combatState)
    {
        if (side == Owner.Creature.Side && combatState.RoundNumber == 1)
        {
            Flash();
            await PlayerCmd.GainEnergy(DynamicVars.Energy.BaseValue, Owner);
            await PlayerCmd.LoseGold(DynamicVars.Gold.BaseValue, Owner);
        }
    }
}
