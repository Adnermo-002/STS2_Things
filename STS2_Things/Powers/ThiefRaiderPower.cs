using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;

namespace STS2_Things.Powers;

/// <summary>
/// 劫掠者窃贼被动 — 死亡掉落金币 + 每回合给队友虚弱
/// </summary>
public sealed class ThiefRaiderPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Single;

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new GoldVar(50)
    ];

    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        new IHoverTip[] { HoverTipFactory.FromPower<WeakPower>() };

    public override Task BeforeDeath(Creature target)
    {
        if (target != Owner)
            return Task.CompletedTask;

        if (base.CombatState.RunState.CurrentRoom is CombatRoom combatRoom)
        {
            foreach (var player in CombatState.Players)
                combatRoom.AddExtraReward(player, new GoldReward(DynamicVars.Gold.IntValue, player));
        }
        return Task.CompletedTask;
    }

    public override async Task AfterSideTurnStart(CombatSide side,
        IReadOnlyList<Creature> participants, ICombatState combatState)
    {
        if (side != CombatSide.Enemy || !Owner.IsAlive) return;

        foreach (var enemy in CombatState.Enemies)
        {
            if (enemy != Owner && enemy.IsAlive)
                await PowerCmd.Apply<WeakPower>(new ThrowingPlayerChoiceContext(),
                    new[] { enemy }, 1m, Owner, null);
        }
    }
}
