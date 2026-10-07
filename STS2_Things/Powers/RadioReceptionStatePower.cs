using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Things.Powers;

/// <summary>Native checksum-visible state, following BowlbugSequencePower's pattern.</summary>
public sealed class RadioReceptionStatePower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public override bool ShouldPlayVfx => false;
    protected override bool IsVisibleInternal => false;

    public void Synchronize(IEnumerable<int> playerCodes, RadioProgram program)
    {
        // Roster order is already part of the native full state. Do not embed
        // platform IDs or localized labels: anonymous replays can remap IDs.
        uint stamp = 2166136261;
        unchecked
        {
            foreach (int code in playerCodes) stamp = (stamp ^ (uint)code) * 16777619;
            foreach (int count in new[] { program.First.Attacks, program.First.Skills,
                         program.Second.Attacks, program.Second.Skills })
                stamp = (stamp ^ (uint)count) * 16777619;
        }
        SetAmount(1 + (int)(stamp % 999999998u), silent: true);
    }

    public void Clear() => SetAmount(1, silent: true);
}
