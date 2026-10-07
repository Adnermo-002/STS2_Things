using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using STS2_Things.Visuals;

namespace STS2_Things.Monsters;

public sealed class SlimeSnail : DepthsSnail
{
    private MoveState? _repair;
    private MoveState? _bite;
    private ConditionalBranchState? _repairChoice;
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 27, 24);
    public override int MaxInitialHp => MinInitialHp + 3;
    private int BiteDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 9, 8);
    private int RepairShell => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 9, 7);
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/workbug_goop/workbug_goop_spit";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/workbug_goop/workbug_goop_die";

    private DepthsSnail? RepairTarget => CombatState.Enemies.Select(c => c.Monster).OfType<DepthsSnail>()
        .Where(s => s != this && s.Creature.IsAlive && s.HasShell)
        .OrderBy(s => s.Creature.Block).ThenBy(s => s.Id.Entry, StringComparer.Ordinal).FirstOrDefault();

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var spit = new MoveState("SPIT_MOVE", Spit, new DebuffIntent());
        var repair = new MoveState("REPAIR_MOVE", Repair, new DefendIntent());
        var bite = new MoveState("BITE_MOVE", _ => Hit(BiteDamage), new SingleAttackIntent(BiteDamage));
        var choice = new ConditionalBranchState("REPAIR_OR_BITE");
        choice.AddState(repair, () => RepairTarget != null);
        choice.AddState(bite, () => true);
        spit.FollowUpState = choice;
        repair.FollowUpState = spit;
        bite.FollowUpState = spit;
        _repair = repair; _bite = bite; _repairChoice = choice;
        return new MonsterMoveStateMachine([spit, repair, bite, choice], spit);
    }

    public void RefreshRepairIntent()
    {
        if (!CanAct || IsPerformingMove || _repair == null || _bite == null ||
            CombatState.CurrentSide != CombatSide.Player) return;
        if (NextMove.Id == MonsterModel.stunnedMoveId)
        {
            string? resume = NextMove.FollowUpState?.Id ?? NextMove.FollowUpStateId;
            if (resume is "REPAIR_MOVE" or "BITE_MOVE" or "REPAIR_OR_BITE") NextMove.FollowUpState = _repairChoice;
            return;
        }
        if (NextMove.Id is not ("REPAIR_MOVE" or "BITE_MOVE")) return;
        var desired = RepairTarget == null ? _bite : _repair;
        if (!ReferenceEquals(NextMove, desired)) SetMoveImmediate(desired);
    }

    public override Task AfterSideTurnStart(CombatSide side, IReadOnlyList<Creature> participants, ICombatState state)
    {
        if (side == CombatSide.Player) RefreshRepairIntent();
        return Task.CompletedTask;
    }

    private async Task Spit(IReadOnlyList<Creature> targets)
    {
        await BeginPose("Cast", "cast", .58f);
        if (!CanAct) return;
        SfxCmd.Play("event:/sfx/enemy/enemy_attacks/workbug_silk/workbug_silk_spit");
        foreach (var target in targets.Where(c => c.IsAlive)) NSnailSupportVfx.Play(Creature, target, repair: false);
        await PowerCmd.Apply<WeakPower>(new ThrowingPlayerChoiceContext(), targets.Where(c => c.IsAlive), 1, Creature, null);
        await WaitForPose("cast", 1.35f, 0);
    }

    private async Task Repair(IReadOnlyList<Creature> targets)
    {
        await BeginPose("Cast", "cast", .58f);
        var target = RepairTarget;
        // If a target disappeared during enemy resolution, do not replace a
        // displayed defensive move with an unadvertised attack.
        if (!CanAct || target == null) return;
        SfxCmd.Play(CastSfx);
        NSnailSupportVfx.Play(Creature, target.Creature, repair: true);
        await target.GrowShell(new ThrowingPlayerChoiceContext(), RepairShell);
        await WaitForPose("cast", 1.35f, 0);
    }
}
