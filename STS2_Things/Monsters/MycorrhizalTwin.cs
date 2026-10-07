using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Powers;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Monsters;

/// <summary>Two equal HP pools, complementary roles, and native move transitions.</summary>
public abstract class MycorrhizalTwin : ThingsSpineMonster
{
    public abstract bool IsVanguard { get; }
    public bool IsFurious => Creature.GetPower<MycorrhizalFuryPower>() != null;
    public bool IsRobust => IsFurious || Creature.GetPower<MycorrhizalBondPower>()?.IsRobust == true;
    public int StrengthGift => IsRobust ? 3 : 1;
    public int ArmorGift => IsRobust ? 3 : 2;
    public int ScaleProtection(int value) => (int)Math.Round(value * (IsRobust ? 1.25m : .75m), MidpointRounding.AwayFromZero);
    public MycorrhizalTwin? Partner => CombatState.Enemies.Select(c => c.Monster)
        .OfType<MycorrhizalTwin>().FirstOrDefault(m => m != this && m.IsVanguard != IsVanguard && m.Creature.IsAlive);
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 98, 88);
    public override int MaxInitialHp => MinInitialHp;
    public override float HpBarSizeReduction => 75f;
    protected int Damage(int normal, int hard) => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, hard, normal);
    protected int Guard => ScaleProtection(AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 13, 11));
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/fogmog/fogmog_attack";
    public override string DeathSfx => ModelDb.Monster<Fogmog>().DeathSfx;
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Plant;
    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat([
        ModelDb.Power<MycorrhizalBondPower>().ResolvedBigIconPath,
        ModelDb.Power<MycorrhizalFuryPower>().ResolvedBigIconPath, Visuals.NMycorrhizalLink.TexturePath]);

    public override async Task BeforeCombatStart()
    {
        await PowerCmd.Apply<MycorrhizalBondPower>(new ThrowingPlayerChoiceContext(), Creature, 1, Creature, null);
    }

    protected override void AddExtraAnimationStates(CreatureAnimator animator, AnimState idle)
    {
        foreach (var (trigger, name) in new[] { ("Double", "double_attack"), ("Guard", "guard"), ("Exchange", "exchange"), ("Enrage", "enrage") })
            animator.AddAnyState(trigger, new AnimState(name) { NextState = idle });
    }

    protected static ConditionalBranchState After(string name, MoveState next, MoveState fury, Func<bool> furious)
    {
        var branch = new ConditionalBranchState(name);
        branch.AddState(fury, furious);
        branch.AddState(next, () => true);
        return branch;
    }

    protected async Task Strike(int amount, int count = 1)
    {
        string animation=count==1?"attack":"double_attack";
        int hit=0;
        await DamageCmd.Attack(amount).WithHitCount(count).FromMonster(this)
            .WithNoAttackerAnim().AfterAttackerAnim(async () =>
            {
                // Native damage waits differ between fast and standard mode.
                // Advance the existing clip to each contact without restarting it.
                if(hit++==0)await BeginPose(count==1?"Attack":"Double",animation,.48f);
                else await FinishPose(animation,.73f,.25f);
            })
            .WithAttackerFx(null, AttackSfx).WithHitFx("vfx/vfx_attack_blunt").Execute(null);
        await FinishPose(animation,count==1?1.28f:1.52f,0);
    }

    private async Task BeginPose(string trigger,string animation,float contact)
    {
        await CreatureCmd.TriggerAnim(Creature,trigger,0);
        await FinishPose(animation,contact,contact);
    }

    public async Task FinishPose(string animation,float moment,float fallback)
    {
        var sprite=Creature.GetCreatureNode()?.Visuals?.SpineBody;
        float wait=fallback;
        using(TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0),out MegaTrackEntry? track))
            if(track!=null&&track.GetAnimationName()==animation)wait=Math.Max(0,moment-track.GetTrackTime());
        await Cmd.Wait(wait);
        using var scope=TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0),out MegaTrackEntry? current);
        if(current!=null&&current.GetAnimationName()==animation&&current.GetTrackTime()<moment)
        {
            current.SetMixDuration(0);current.SetTrackTime(moment);sprite!.BoundObject.Call("update_skeleton",0f);
        }
    }

    protected IEnumerable<Creature> LivingTwins => CombatState.Enemies
        .Where(c => c.IsAlive && (c == Creature || c.Monster == Partner)).ToArray();

    protected async Task Strengthen()
    {
        SfxCmd.Play("event:/sfx/enemy/enemy_attacks/fogmog/fogmog_summon");
        await BeginPose("Cast","cast",.60f);
        foreach (var ally in LivingTwins)
            await PowerCmd.Apply<StrengthPower>(new ThrowingPlayerChoiceContext(), ally, StrengthGift, Creature, null);
        await FinishPose("cast",1.5f,0);
    }

    protected async Task Armor(bool solo = false)
    {
        await BeginPose("Guard","guard",.56f);
        foreach (var ally in solo ? new[] { Creature } : LivingTwins)
        {
            await PowerCmd.Apply<PlatingPower>(new ThrowingPlayerChoiceContext(), ally, ArmorGift, Creature, null);
            if (solo) await CreatureCmd.GainBlock(ally, Guard + ScaleProtection(6), ValueProp.Move, null);
        }
        await FinishPose("guard",1.5f,0);
    }

    protected async Task Shelter()
    {
        await BeginPose("Guard","guard",.56f);
        foreach (var ally in LivingTwins) await CreatureCmd.GainBlock(ally, Guard, ValueProp.Move, null);
        await FinishPose("guard",1.5f,0);
    }
}
