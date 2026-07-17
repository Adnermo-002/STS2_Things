using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Things.Powers;

/// <summary>
///     隐藏的腐化之遗强化阶段。Amount 表示下一次强化阶段，确保进度进入
///     多人 checksum/full-state，而不是停留在 MonsterModel 实例字段中。
/// </summary>
public sealed class LegacyProgressPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public override bool ShouldPlayVfx => false;

    protected override bool IsVisibleInternal => false;

    public int NextStage => Math.Max(1, Amount);

    public void Advance()
    {
        SetAmount(NextStage + 1, silent: true);
    }
}
