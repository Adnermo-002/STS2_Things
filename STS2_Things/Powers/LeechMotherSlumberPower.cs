using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Monsters;

namespace STS2_Things.Powers;

public sealed class LeechMotherSlumberPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public override async Task AfterDamageReceived(PlayerChoiceContext choiceContext, Creature target,
        DamageResult result, ValueProp props, Creature? dealer, CardModel? cardSource)
    {
        if (target == Owner && Owner.IsAlive && Owner.Monster is LeechMother mother &&
            (result.UnblockedDamage > 0 || (props.HasFlag(ValueProp.Move) && dealer?.Side == CombatSide.Player)))
            await mother.Wake();
    }
    public override async Task AfterAttack(PlayerChoiceContext choiceContext, AttackCommand command)
    {
        // An attack that hits for zero or is fully blocked still disturbs her.
        if (Owner.IsAlive && command.Attacker?.Side == CombatSide.Player &&
            command.Results.SelectMany(r => r).Any(r => r.Receiver == Owner) && Owner.Monster is LeechMother mother)
            await mother.Wake();
    }
    public override async Task AfterSideTurnEnd(PlayerChoiceContext choiceContext, CombatSide side,
        IEnumerable<Creature> participants)
    {
        if (side != CombatSide.Enemy || !participants.Contains(Owner) || !Owner.IsAlive ||
            Owner.Monster is not LeechMother mother || mother.IsAwake) return;
        if (Amount <= 1) await mother.LeaveUndisturbed();
        else await PowerCmd.Decrement(this);
    }
}
