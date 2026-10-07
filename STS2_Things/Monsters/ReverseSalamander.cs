using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Vfx;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Afflictions;
using STS2_Things.Powers;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Monsters;

public sealed class ReverseSalamander : ThingsSpineMonster
{
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies,190,170);
    public override int MaxInitialHp => MinInitialHp;
    public override float HpBarSizeReduction => 10f;
    public int GrowthAmount => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies,2,1);
    private int TideDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies,15,13);
    private int TailDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies,19,16);
    private int RollDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies,7,6);
    private int GatherDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies,13,11);
    private int GatherBlock => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies,16,12);
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Magic;
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/gravetide_slug/gravetide_slug_attack_light";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/gravetide_slug/gravetide_slug_die";
    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat([
        ModelDb.Power<ReverseCurrentPower>().ResolvedBigIconPath,
        ModelDb.Affliction<UpstreamRecall>().OverlayPath,NSplashVfx.scenePath]);

    public override async Task BeforeCombatStart()
    {
        await PowerCmd.Apply<ReverseCurrentPower>(new ThrowingPlayerChoiceContext(),Creature,GrowthAmount,Creature,null);
    }

    protected override void AddExtraAnimationStates(CreatureAnimator animator,AnimState idle)
    {
        foreach(var(trigger,name) in new[]{("Tide","tide"),("Roll","roll"),("Gather","gather"),("Recall","recall")})
            animator.AddAnyState(trigger,new AnimState(name){NextState=idle});
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var opening=new MoveState("UPSTREAM_MOVE",_=>Strike(TideDamage,"Tide","tide",[.56f],1.55f),new SingleAttackIntent(TideDamage));
        var tail=new MoveState("TAIL_WAVE_MOVE",_=>Strike(TailDamage,"Attack","attack",[.50f],1.40f),new SingleAttackIntent(TailDamage));
        var roll=new MoveState("BACKWASH_MOVE",_=>Strike(RollDamage,"Roll","roll",[.46f,.74f,1.02f],1.65f),new MultiAttackIntent(RollDamage,3));
        var gather=new MoveState("GATHER_MOVE",Gather,new SingleAttackIntent(GatherDamage),new DefendIntent());
        opening.FollowUpState=tail;tail.FollowUpState=roll;roll.FollowUpState=gather;gather.FollowUpState=tail;
        return new MonsterMoveStateMachine([opening,tail,roll,gather],opening);
    }

    private async Task Strike(int damage,string trigger,string animation,float[] contacts,float duration)
    {
        int hit=0;
        await DamageCmd.Attack(damage).WithHitCount(contacts.Length).FromMonster(this)
            .WithNoAttackerAnim().AfterAttackerAnim(async()=>
            {
                if(hit==0)await CreatureCmd.TriggerAnim(Creature,trigger,0);
                float moment=contacts[Math.Min(hit,contacts.Length-1)];
                await WaitForPose(animation,moment,hit==0?moment:.28f);hit++;
            })
            .WithAttackerFx(null,AttackSfx)
            .WithHitVfxNode(target=>target.GetCreatureNode() is { } node
                ? NSplashVfx.Create(node.VfxSpawnPosition,new Godot.Color("a1d2ce")):null)
            .Execute(null);
        await WaitForPose(animation,duration,0);
    }

    private async Task Gather(IReadOnlyList<Creature> targets)
    {
        await Strike(GatherDamage,"Gather","gather",[.56f],1.20f);
        await CreatureCmd.GainBlock(Creature,GatherBlock,ValueProp.Move,null);
        await WaitForPose("gather",1.55f,0);
    }

    public async Task RecallPose()
    {
        if(!Creature.IsAlive)return;
        await CreatureCmd.TriggerAnim(Creature,"Recall",0);
        await WaitForPose("recall",.54f,.54f);
    }

    private async Task WaitForPose(string animation,float moment,float fallback)
    {
        var sprite=Creature.GetCreatureNode()?.Visuals?.SpineBody;float wait=fallback;
        using(TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0),out MegaTrackEntry? track))
            if(track!=null&&track.GetAnimationName()==animation)wait=Math.Max(0,moment-track.GetTrackTime());
        await Cmd.Wait(wait);
        using var scope=TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0),out MegaTrackEntry? current);
        if(current!=null&&current.GetAnimationName()==animation&&current.GetTrackTime()<moment)
        {current.SetMixDuration(0);current.SetTrackTime(moment);sprite!.BoundObject.Call("update_skeleton",0f);}
    }
}
