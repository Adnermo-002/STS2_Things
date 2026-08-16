using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Saves.Runs;
using STS2_Things.Powers;

namespace STS2_Things.Monsters;

/// <summary>
/// Destructible remains left by a Gravetide Corpse Slug. Its native Spine
/// body starts on the death animation and is revealed only once that animation
/// has reached its final pose.
/// </summary>
public sealed class GravetideSlugCorpse : MonsterModel
{
    private bool _delayDigestionUntilNextEnemyTurn;

    public override int MinInitialHp => 6;

    public override int MaxInitialHp => 6;

    public override bool ShouldShowInCompendium => false;

    public override bool HasDeathSfx => false;

    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Slime;

    [SavedProperty]
    public bool DelayDigestionUntilNextEnemyTurn
    {
        get => _delayDigestionUntilNextEnemyTurn;
        set
        {
            AssertMutable();
            _delayDigestionUntilNextEnemyTurn = value;
        }
    }

    protected override string VisualsPath =>
        SceneHelper.GetScenePath("creature_visuals/gravetide_slug_corpse");

    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        await PowerCmd.Apply<GravetideMinionPower>(
            new ThrowingPlayerChoiceContext(), Creature, 1m, Creature, null);
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var remains = new MoveState(
            "REMAINS_MOVE",
            (IReadOnlyList<Creature> _) => Task.CompletedTask,
            new HiddenIntent());
        remains.FollowUpState = remains;
        return new MonsterMoveStateMachine([remains], remains);
    }

    public override CreatureAnimator GenerateAnimator(MegaSprite controller)
    {
        var finalDeathPose = new AnimState("die");
        var animator = new CreatureAnimator(finalDeathPose, controller);
        animator.AddAnyState("Idle", finalDeathPose);
        animator.AddAnyState("Dead", finalDeathPose);
        return animator;
    }
}
