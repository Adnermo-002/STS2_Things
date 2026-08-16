using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.ValueProps;

namespace STS2_Things.Powers;

/// <summary>
///     缩小 — 玩家 Debuff，每层缩 1%，伤害减 1%
///     模仿 ShrinkPower，支持层数叠加
/// </summary>
public sealed class ThingsScaleDownPower : PowerModel
{
    public override PowerType Type => PowerType.Debuff;
    public override PowerStackType StackType => PowerStackType.Counter;

    protected override IEnumerable<DynamicVar> CanonicalVars =>
        new[] { new DynamicVar("PercentPerStack", 1m) };

    private float ScaleFactor =>
        (float)Math.Pow(1.0 - (double)DynamicVars["PercentPerStack"].BaseValue / 100.0, Amount);

    public override Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        ApplyScale();
        return Task.CompletedTask;
    }

    public override Task AfterPowerAmountChanged(PlayerChoiceContext choiceContext, PowerModel power, decimal amount,
        Creature? applier, CardModel? cardSource)
    {
        if (power == this) ApplyScale();
        return Task.CompletedTask;
    }

    public override Task AfterSideTurnStart(CombatSide side, IReadOnlyList<Creature> participants, ICombatState combatState)
    {
        // 每回合开始时重新应用缩放，确保视觉与层数同步
        ApplyScale();
        return Task.CompletedTask;
    }

    public override Task AfterRemoved(Creature oldOwner)
    {
        SafeScale(oldOwner, 1f);
        return Task.CompletedTask;
    }

    private void ApplyScale()
    {
        SafeScale(Owner, ScaleFactor);
    }

    private static void SafeScale(Creature creature, float target)
    {
        try
        {
            var combatRoom = NCombatRoom.Instance;
            combatRoom?.GetCreatureNode(creature)?.ScaleTo(target, 0.75);
        }
        catch (ObjectDisposedException)
        {
            Log.Warn("[ThingsScaleDownPower] 尝试缩放已释放的战斗节点，忽略。");
        }
        catch (NullReferenceException)
        {
            // NCombatRoom 或节点可能已被释放，忽略。
        }
    }

#if STS2_V107_1
    public override decimal ModifyDamageMultiplicative(Creature? target, decimal amount, ValueProp props,
        Creature? dealer, CardModel? cardSource)
#else
    public override decimal ModifyDamageMultiplicative(Creature? target, decimal amount, ValueProp props,
        Creature? dealer, CardModel? cardSource, CardPlay? cardPlay)
#endif
    {
        if (Owner != dealer || !props.IsPoweredAttack())
            return 1m;
        return Math.Max(0m,
            (100m - DynamicVars["PercentPerStack"].BaseValue * Amount) / 100m);
    }
}
