using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using STS2_Things.Monsters;

namespace STS2_Things.Powers;

/// <summary>
/// Both arms mirror one native countdown, coordinated by their shared body.
/// </summary>
public sealed class ThingsCaveGodAgingPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public const int ResetAmount = 2;
    public override PowerStackType StackType => PowerStackType.Counter;

    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        ModelDb.Card<StoneArmor>().HoverTips;

    public Task OnArmDowned() => Owner.Monster is ThingsCaveGodHand { Body: { } body }
        ? body.AdvanceAgingCountdown(this) : Task.CompletedTask;

    internal void SetCountdown(int remaining)
    {
        SetAmount(remaining);
        Flash();
    }

    internal async Task GiveStoneArmor()
    {
        if (Owner?.CombatState is not { } combatState) return;

        foreach (Player player in combatState.Players)
        {
            if (player.Creature.IsDead) continue;

            CardModel stoneArmor = combatState.CreateCard<StoneArmor>(player);
            stoneArmor.SetToFreeThisCombat();
            await CardPileCmd.AddGeneratedCardToCombat(stoneArmor, PileType.Hand, player);
        }
    }
}
