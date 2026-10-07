using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using STS2_Things.Monsters;

namespace STS2_Things.Powers;

public sealed class SpongeReservoirPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        [new HoverTip(new LocString("powers", "SPONGE_RESERVOIR_POWER.sprayTitle"),
            new LocString("powers", "SPONGE_RESERVOIR_POWER.sprayDescription")),
         HoverTipFactory.FromPower<SpongeRinsePower>()];

    public override Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        Refresh();
        return Task.CompletedTask;
    }

    public override Task AfterPowerAmountChanged(PlayerChoiceContext choiceContext, PowerModel power,
        decimal amount, Creature? applier, CardModel? cardSource)
    {
        if (ReferenceEquals(power, this)) Refresh();
        return Task.CompletedTask;
    }

    private void Refresh()
    {
        if (Amount > WaterSponge.WaterCapacity) SetAmount(WaterSponge.WaterCapacity);
        if (Amount >= WaterSponge.WaterCapacity)
            Owner.GetPower<SpongeDamageProgressPower>()?.Reset();
        if (Owner.Monster is WaterSponge sponge) sponge.PrepareSpray();
    }

    public override Task AfterRemoved(Creature oldOwner)
    {
        oldOwner.GetPower<SpongeDamageProgressPower>()?.Reset();
        return Task.CompletedTask;
    }
}
