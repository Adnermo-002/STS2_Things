using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using STS2_Things.Intents;
using STS2_Things.Powers;

namespace STS2_Things.Monsters;

public sealed class RockSnail : DepthsSnail
{
    private Dictionary<int, MoveState>? _moves;
    private ConditionalBranchState? _choose;
    public int CrawlsRemaining => Creature.GetPower<RockCrawlStatePower>()?.Remaining ?? 2;
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 34, 30);
    public override int MaxInitialHp => MinInitialHp + 3;
    private int OpeningShell => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 6, 5);
    private int CrawlShell => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 4, 3);
    private int CrushDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 25, 22);

    public override async Task BeforeCombatStart()
    {
        await PowerCmd.Apply<RockCrawlStatePower>(new ThrowingPlayerChoiceContext(), Creature, 3, Creature, null);
        await GrowShell(new ThrowingPlayerChoiceContext(), OpeningShell, initial: true);
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var choose = new ConditionalBranchState("CHOOSE_PROGRESS");
        var moves = new Dictionary<int, MoveState>
        {
            [2] = new("CRAWL_2_MOVE", Crawl, new SnailCrawlIntent(2)),
            [1] = new("CRAWL_1_MOVE", Crawl, new SnailCrawlIntent(1)),
            [0] = new("CRUSH_MOVE", Crush, new SingleAttackIntent(CrushDamage)),
            [3] = new("RECOIL_MOVE", Recoil, new StunIntent()),
        };
        foreach (var (remaining, move) in moves)
        {
            move.FollowUpState = choose;
            move.MustPerformOnceBeforeTransitioning = true;
            int captured = remaining;
            choose.AddState(move, () => CrawlsRemaining == captured);
        }
        _moves = moves; _choose = choose;
        return new MonsterMoveStateMachine([.. moves.Values, choose], moves[2]);
    }

    private void SetProgress(int remaining) => Creature.GetPower<RockCrawlStatePower>()?.SetRemaining(remaining);

    public override Task OnShellBroken(PlayerChoiceContext context)
    {
        if (!Creature.IsAlive) return Task.CompletedTask;
        SetProgress(CrawlsRemaining + 1);
        if (_moves == null) return Task.CompletedTask;
        if (NextMove.Id == MonsterModel.stunnedMoveId) NextMove.FollowUpState = _choose;
        else if (!IsPerformingMove) SetMoveImmediate(_moves[CrawlsRemaining], forceTransition: true);
        return Task.CompletedTask;
    }

    private async Task Crawl(IReadOnlyList<Creature> targets)
    {
        await BeginPose("Crawl", "crawl", .62f);
        if (!CanAct) return;
        // Advance first, so a shell broken by a reaction to the gain below can
        // push this same step back without being overwritten afterwards.
        SetProgress(Math.Max(0, CrawlsRemaining - 1));
        await GrowShell(new ThrowingPlayerChoiceContext(), CrawlShell);
        await WaitForPose("crawl", 1.45f, 0);
    }

    private async Task Recoil(IReadOnlyList<Creature> targets)
    {
        await BeginPose("Retreat", "retreat", .55f);
        if (CanAct) SetProgress(2);
        await WaitForPose("retreat", 1.35f, 0);
    }

    private async Task Crush(IReadOnlyList<Creature> targets)
    {
        await Hit(CrushDamage, .62f);
        if (!CanAct) return;
        // Retaliation can break the shell during impact. The completed hit is
        // not undone; an extra recoil turn delays the next charge instead.
        SetProgress(CrawlsRemaining > 0 ? 3 : 2);
    }
}
