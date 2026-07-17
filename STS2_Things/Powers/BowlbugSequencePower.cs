using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Things.Powers;

/// <summary>
///     隐藏的盛碗虫召唤序列状态。Amount 使用 1-4 表示下一只召唤物，
///     从而让该跨动作状态进入多人 checksum/full-state。
/// </summary>
public sealed class BowlbugSequencePower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public override bool ShouldPlayVfx => false;

    protected override bool IsVisibleInternal => false;

    public int NextIndex => Math.Clamp(Amount - 1, 0, 3);

    public void Advance()
    {
        SetAmount(NextIndex == 3 ? 1 : NextIndex + 2, silent: true);
    }
}
