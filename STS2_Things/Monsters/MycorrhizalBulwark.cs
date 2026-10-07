using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.ValueProps;

namespace STS2_Things.Monsters;

public sealed class MycorrhizalBulwark : MycorrhizalTwin
{
    public override bool IsVanguard => false;
    private async Task Bash(bool furious)
    {
        await Strike(furious ? Damage(14,16) : Damage(11,13));
        await CreatureCmd.GainBlock(Creature, Guard, ValueProp.Move, null);
    }
    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var shelter = new MoveState("SHELTER_MOVE", _ => Shelter(), new DefendIntent());
        var armor = new MoveState("ARMOR_MOVE", _ => Armor(), new BuffIntent());
        var bash = new MoveState("BASH_MOVE", _ => Bash(false), new SingleAttackIntent(Damage(11,13)), new DefendIntent());
        var fury = new MoveState("RAMPART_MOVE", _ => Bash(true), new SingleAttackIntent(Damage(14,16)), new DefendIntent());
        var fortify = new MoveState("FORTIFY_MOVE", _ => Armor(true), new DefendIntent(), new BuffIntent());
        fury.FollowUpState = fortify; fortify.FollowUpState = fury;
        var a = After("AFTER_SHELTER", armor, fury, () => IsFurious);
        var b = After("AFTER_ARMOR", bash, fury, () => IsFurious);
        var c = After("AFTER_BASH", shelter, fury, () => IsFurious);
        shelter.FollowUpState = a; armor.FollowUpState = b; bash.FollowUpState = c;
        return new MonsterMoveStateMachine([shelter,armor,bash,fury,fortify,a,b,c], shelter);
    }
}
