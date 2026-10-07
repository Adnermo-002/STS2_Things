using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using STS2_Things.Cards;
using STS2_Things.Monsters;
using STS2_Things.Visuals;

namespace STS2_Things.Powers;

/// <summary>Persistent native Block is the shell; native block breaking resolves it once.</summary>
public sealed class SnailShellPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Single;
    protected override IEnumerable<IHoverTip> ExtraHoverTips
    {
        get
        {
            yield return HoverTipFactory.Static(StaticHoverTip.Block);
            if (!IsMutable) yield break;
            string kind = Owner.Monster is CrystalSnail ? "crystalBreak" : "rockBreak";
            yield return new HoverTip(new LocString("powers", "SNAIL_SHELL_POWER.breakTitle"),
                new LocString("powers", $"SNAIL_SHELL_POWER.{kind}"));
            if (Owner.Monster is CrystalSnail)
                foreach (var tip in HoverTipFactory.FromCardWithCardHoverTips<SnailCrystalChip>()) yield return tip;
        }
    }

    public override bool ShouldClearBlock(Creature creature) => creature != Owner;

#if STS2_V107_1
    public override Task AfterBlockBroken(Creature creature) =>
        Break(new ThrowingPlayerChoiceContext(), creature);
#else
    public override Task AfterBlockBroken(PlayerChoiceContext context, Creature target, Creature? breaker) =>
        Break(context, target);
#endif

    private async Task Break(PlayerChoiceContext context, Creature target)
    {
        if (target != Owner || target.Block > 0 || !ReferenceEquals(target.GetPower<SnailShellPower>(), this)) return;
        // Remove before reward/retreat hooks, including simultaneous AoE breaks.
        await PowerCmd.Remove(this);
        NSnailShellBreakVfx.Play(target);
        if (target.Monster is DepthsSnail snail)
        {
            if (target.IsAlive && !snail.IsPerformingMove)
                await CreatureCmd.TriggerAnim(target, "ShellBreak", 0);
            await snail.OnShellBroken(context);
            snail.NotifyMenders();
        }
    }
}
