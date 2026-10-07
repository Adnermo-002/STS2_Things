using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Monsters;

namespace STS2_Things.Powers;

/// <summary>One native counter displays shared layers and height-dependent protection.</summary>
public sealed class HumanFaceColumnPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public override bool ShouldPlayVfx => false;
    public void RefreshHeightDisplay() => InvokeDisplayAmountChanged();
    private int Level => Owner.Monster is HumanFaceColumn column ? column.Level : 0;
    protected override string SmartDescriptionLocKey => !IsMutable ? base.SmartDescriptionLocKey :
        Level switch
        {
            2 => "HUMAN_FACE_COLUMN_POWER.topDescription",
            1 => "HUMAN_FACE_COLUMN_POWER.middleDescription",
            _ => "HUMAN_FACE_COLUMN_POWER.bottomDescription",
        };

#if STS2_V107_1
    public override decimal ModifyDamageMultiplicative(Creature? target, decimal amount, ValueProp props,
        Creature? dealer, CardModel? cardSource) =>
#else
    public override decimal ModifyDamageMultiplicative(Creature? target, decimal amount, ValueProp props,
        Creature? dealer, CardModel? cardSource, CardPlay? cardPlay) =>
#endif
        target != Owner ? 1m : Level >= 2 ? 0m : Level == 1 ? .5m : 1m;

#if STS2_V107_1
    public override decimal ModifyDamageCap(Creature? target, ValueProp props,
        Creature? dealer, CardModel? cardSource) =>
#else
    public override decimal ModifyDamageCap(Creature? target, ValueProp props,
        Creature? dealer, CardModel? cardSource, CardPlay? cardPlay) =>
#endif
        target == Owner && Level >= 2 ? 0m : decimal.MaxValue;

    public override decimal ModifyHpLostAfterOsty(Creature target, decimal amount, ValueProp props,
        Creature? dealer, CardModel? cardSource) => target == Owner && Level >= 2 ? 0m : amount;
}
