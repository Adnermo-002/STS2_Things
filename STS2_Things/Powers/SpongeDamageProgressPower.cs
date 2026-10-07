using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Things.Powers;

/// <summary>Native, checksum-visible storage for the damage left toward the next water stack.</summary>
public sealed class SpongeDamageProgressPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public override bool ShouldPlayVfx => false;
    protected override bool IsVisibleInternal => false;

    // Keep the state power present at zero progress; Amount participates in the
    // native multiplayer combat snapshot just like the reservoir's stack count.
    public int Damage => Math.Max(0, Amount - 1);
    public void SetDamage(int damage) => SetAmount(Math.Max(0, damage) + 1, silent: true);
    public void Reset() => SetDamage(0);
}
