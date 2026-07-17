using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Things.Powers;

/// <summary>
///     死亡时给予所有玩家1点能量
/// </summary>
public sealed class OriginGainEnergyPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;

    protected override IEnumerable<DynamicVar> CanonicalVars =>
        new[] { new DynamicVar("Energy", 1m) };

    public override async Task AfterDeath(PlayerChoiceContext choiceContext, Creature creature,
        bool wasRemovalPrevented, float deathAnimLength)
    {
        if (creature != Owner)
            return;

        var combatState = Owner.CombatState;
        if (combatState == null)
            return;

        Flash();
        foreach (var player in combatState.Players)
            await PlayerCmd.GainEnergy(DynamicVars["Energy"].BaseValue, player);
    }
}
