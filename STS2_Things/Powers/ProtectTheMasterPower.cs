using System.Linq;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;

namespace STS2_Things.Powers;

/// <summary>
/// 护主 — 盛碗虫族母的常驻Buff。
/// 当场上有任意盛碗虫存活时，玩家对族母造成的伤害减半。
/// 此减半效果不叠加（Power只在族母身上有一份）。
/// </summary>
public sealed class ProtectTheMasterPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Single;

    /// <summary>
    /// 当目标为族母自身、伤害来源为玩家方、且场上有盛碗虫存活时，伤害×0.5
    /// </summary>
#if STS2_V107_1
    public override decimal ModifyDamageMultiplicative(Creature? target, decimal amount,
        ValueProp props, Creature? dealer, CardModel? cardSource)
#else
    public override decimal ModifyDamageMultiplicative(Creature? target, decimal amount,
        ValueProp props, Creature? dealer, CardModel? cardSource, CardPlay? cardPlay)
#endif
    {
        if (target != Owner) return 1m;
        if (!props.IsPoweredAttack()) return 1m;
        if (dealer == null || dealer.Side == CombatSide.Enemy) return 1m;

        var combatState = Owner.CombatState;
        if (combatState == null) return 1m;
        bool hasBowlbug = combatState.Enemies.Any(e =>
            e.IsAlive && e != Owner &&
            (e.Monster is BowlbugSilk || e.Monster is BowlbugRock ||
             e.Monster is BowlbugNectar || e.Monster is BowlbugEgg));

        return hasBowlbug ? 0.5m : 1m;
    }
}
