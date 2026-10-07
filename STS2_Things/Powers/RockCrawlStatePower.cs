using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Things.Powers;

/// <summary>Stores remaining crawl actions plus one, preserving ready-at-zero in native state.</summary>
public sealed class RockCrawlStatePower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    protected override bool IsVisibleInternal => false;
    public override bool ShouldPlayVfx => false;
    public int Remaining => Math.Clamp(Amount - 1, 0, 3);
    public void SetRemaining(int remaining) => SetAmount(Math.Clamp(remaining, 0, 3) + 1, silent: true);
}
