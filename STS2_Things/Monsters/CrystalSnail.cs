using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using STS2_Things.Cards;

namespace STS2_Things.Monsters;

public sealed class CrystalSnail : DepthsSnail
{
    private MoveState? _bareBump;
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 31, 28);
    public override int MaxInitialHp => MinInitialHp + 3;
    private int BumpDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 9, 8);
    private int OpeningShell => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 8, 6);
    private int RetreatShell => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 8, 6);
    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat([ModelDb.Card<SnailCrystalChip>().PortraitPath]);

    public override Task BeforeCombatStart() => GrowShell(new ThrowingPlayerChoiceContext(), OpeningShell, initial: true);

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var bump = new MoveState("BUMP_MOVE", _ => Hit(BumpDamage), new SingleAttackIntent(BumpDamage));
        var retreat = new MoveState("RETREAT_MOVE", Retreat, new DefendIntent());
        var bare = new MoveState("BARE_BUMP_MOVE", _ => Hit(BumpDamage), new SingleAttackIntent(BumpDamage))
            { MustPerformOnceBeforeTransitioning = true };
        var afterBump = new ConditionalBranchState("AFTER_BUMP");
        afterBump.AddState(retreat, () => HasShell);
        afterBump.AddState(bare, () => true);
        bump.FollowUpState = afterBump;
        retreat.FollowUpState = bump;
        bare.FollowUpState = bare;
        _bareBump = bare;
        return new MonsterMoveStateMachine([bump, retreat, bare, afterBump], bump);
    }

    private async Task Retreat(IReadOnlyList<Creature> targets)
    {
        if (!CanAct || !HasShell) return;
        await BeginPose("Retreat", "retreat", .55f);
        if (CanAct && HasShell)
            await GrowShell(new ThrowingPlayerChoiceContext(), RetreatShell);
        await WaitForPose("retreat", 1.35f, 0);
    }

    public override async Task OnShellBroken(PlayerChoiceContext context)
    {
        if (Creature.IsAlive && _bareBump != null)
        {
            if (NextMove.Id == MonsterModel.stunnedMoveId) NextMove.FollowUpState = _bareBump;
            else if (!IsPerformingMove) SetMoveImmediate(_bareBump, forceTransition: true);
        }
        // Shell breaking, including a lethal hit, rewards each living player once.
        foreach (var player in CombatState.Players.Where(p => p.Creature.IsAlive))
        {
            var card = CombatState.CreateCard<SnailCrystalChip>(player);
            var result = await CardPileCmd.AddGeneratedCardToCombat(card, PileType.Discard, player);
            if (LocalContext.IsMe(player))
            {
                CardCmd.PreviewCardPileAdd(result);
            }
        }
    }
}
