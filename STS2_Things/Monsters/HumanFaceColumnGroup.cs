using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using STS2_Things.Powers;
using STS2_Things.Visuals;

namespace STS2_Things.Monsters;

/// <summary>Encounter-local shared state; no static cross-combat or local-UI state.</summary>
internal sealed class HumanFaceColumnGroup
{
    private readonly List<HumanFaceColumn> _members = [];
    private readonly HashSet<HumanFaceColumn> _broken = [];
    private readonly HashSet<HumanFaceColumn> _pendingStuns = [];
    private int _pendingLosses;
    private bool _resolving;
    public int Remaining { get; private set; } = HumanFaceColumn.InitialLayers;
    public int Reserve { get; private set; } = HumanFaceColumn.InitialLayers - 3;
    public HumanFaceColumn[] Living => _members.Where(member => member.Creature.IsAlive)
        .OrderBy(member => member.Level).ToArray();

    public static IReadOnlyList<(MonsterModel, string?)> CreateInitial()
    {
        var group = new HumanFaceColumnGroup();
        var result = new List<(MonsterModel, string?)>();
        for (int level = 2; level >= 0; level--)
        {
            var member = (HumanFaceColumn)ModelDb.Monster<HumanFaceColumn>().ToMutable();
            member.Configure(group, level, 2 - level);
            group._members.Add(member);
            result.Add((member, HumanFaceColumn.LayerSlots[level]));
        }
        return result;
    }

    public static HumanFaceColumnGroup ForStandalone(HumanFaceColumn member)
    {
        var group = new HumanFaceColumnGroup { Remaining = 1, Reserve = 0 };
        group._members.Add(member);
        return group;
    }

    public async Task BreakLayer(HumanFaceColumn broken, PlayerChoiceContext context)
    {
        if (!_broken.Add(broken)) return;
        // Capture identity before compacting the stack. In a simultaneous
        // bottom/middle kill this reference can die too; neither the old top
        // nor a new replacement should inherit its stun.
        var originalMiddle = broken.Level == 0
            ? _members.FirstOrDefault(member => member.Level == 1) : null;
        if (!_members.Remove(broken)) return;
        if (originalMiddle != null) _pendingStuns.Add(originalMiddle);
        Remaining = Math.Max(0, Remaining - 1);
        _pendingLosses++;
        await ResolvePending(context, broken.Creature.CombatState);
    }

    public async Task ResolvePending(PlayerChoiceContext context, ICombatState? combat)
    {
        // Native AoE applies all HP loss before resolving each death. Wait for
        // those confirmations, including possible death prevention, so a living
        // disc never falls through a zero-HP layer still awaiting its death hook.
        if (_resolving || _pendingLosses == 0 || combat == null || CombatManager.Instance.IsOverOrEnding ||
            _members.Any(member => member.Creature.IsDead)) return;
        _resolving = true;
        try
        {
            int losses = _pendingLosses;
            _pendingLosses = 0;
            var stunTargets = _pendingStuns.ToArray();
            _pendingStuns.Clear();
            var survivors = Living;
            int replacements = Math.Min(Reserve, losses);
            var poses = Enumerable.Range(0, Reserve)
                .Select(index => NHumanFaceColumnVisuals.IncomingPose(survivors.LastOrDefault()?.Creature, index)).ToArray();
            Reserve -= replacements;
            for (int level = 0; level < survivors.Length; level++) survivors[level].LowerTo(level);
            for (int i = 0; i < replacements; i++)
            {
                int level = Living.Length;
                var replacement = (HumanFaceColumn)ModelDb.Monster<HumanFaceColumn>().ToMutable();
                replacement.Configure(this, level, 0, replacement: true);
                _members.Add(replacement);
                await CreatureCmd.Add(replacement, combat, CombatSide.Enemy, HumanFaceColumn.LayerSlots[level]);
                NHumanFaceColumnVisuals.DropIn(replacement.Creature, poses[i], losses, i);
            }
            NHumanFaceColumnVisuals.RestoreReservePoses(Living.LastOrDefault()?.Creature,
                poses.Skip(replacements).ToArray());
            foreach (var member in Living)
            {
                if (member.Creature.GetPower<HumanFaceColumnPower>() is { } power)
                {
                    int difference = Remaining - power.Amount;
                    if (difference != 0)
                        await PowerCmd.ModifyAmount(context, power, difference, member.Creature, null, silent: true);
                    power.RefreshHeightDisplay();
                }
                if (stunTargets.Contains(member)) await member.StunForCollapse();
            }
            await Cmd.Wait(.32f * MathF.Sqrt(losses) + .23f);
        }
        finally { _resolving = false; }
        // Reactions to spawning or changing a power can produce another death.
        // Its confirmed loss is queued above and resolved after this pass.
        if (_pendingLosses > 0) await ResolvePending(context, combat);
    }
}
