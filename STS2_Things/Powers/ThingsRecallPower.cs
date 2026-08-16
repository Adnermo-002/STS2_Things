using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Things.Powers;

/// <summary>
/// 回溯 — 本回合内你的抽牌改为从弃牌堆抽牌
/// 回合结束时移除
/// </summary>
public sealed class ThingsRecallPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Single;

    public override Task AfterSideTurnEnd(PlayerChoiceContext choiceContext, CombatSide side,
        IEnumerable<Creature> participants)
    {
        // 玩家回合结束时移除
        if (side == CombatSide.Player)
        {
            return PowerCmd.Remove(this);
        }
        return Task.CompletedTask;
    }
}
