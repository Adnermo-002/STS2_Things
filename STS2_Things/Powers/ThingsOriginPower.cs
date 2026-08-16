using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Monsters;

namespace STS2_Things.Powers;

public sealed class ThingsOriginPower : PowerModel
{
    public override PowerType Type => PowerType.Debuff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public override bool ShouldScaleInMultiplayer => true;

    // Amount 直接保存同步的半血阈值，而不是累计伤害。这样治疗不会导致提前转阶段，
    // 并且与玩家可见描述保持一致。

    public override async Task AfterDamageReceived(
        PlayerChoiceContext choiceContext, Creature target, DamageResult result, ValueProp props, Creature? dealer,
        CardModel? cardSource)
    {
        if (target != Owner || Owner.CurrentHp > Amount || result.UnblockedDamage <= 0)
            return;

        Flash();
        if (Owner.Monster is not OriginFogmog origin) return;

        // Stun replaces the currently scheduled move. If the threshold is crossed
        // before the opening ILLUSION_MOVE has executed, use a two-Eye callback so
        // the interrupted opening summon is not lost. Otherwise phase two adds the
        // normal single Eye.
        Func<IReadOnlyList<Creature>, Task> phaseSummon =
            origin.NextMove.StateId == OriginFogmog.IllusionMoveId
            ? origin.PerformInterruptedOpeningIllusionMove
            : origin.PerformIllusionMove;
        await CreatureCmd.Stun(Owner, phaseSummon, OriginFogmog.SwipeMoveId);

        // Never consume the one-shot threshold unless the forced phase state was
        // actually installed. This also makes the chain resilient to another mod
        // patching SetMoveImmediate with higher priority.
        if (origin.NextMove.StateId != MonsterModel.stunnedMoveId
            || origin.NextMove.FollowUpStateId != OriginFogmog.SwipeMoveId)
            return;

        origin.OnPhaseTransition();
        await PowerCmd.Remove(this);
    }
}
