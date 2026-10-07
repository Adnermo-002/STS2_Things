using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Powers;
using STS2_Things.Visuals;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Monsters;

public abstract class DepthsSnail : ThingsSpineMonster
{
    public bool HasShell => Creature.HasPower<SnailShellPower>() && Creature.Block > 0;
    protected bool CanAct => Creature.IsAlive && !CombatManager.Instance.IsOverOrEnding;
    public override float HpBarSizeReduction => 115f;
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Insect;
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/workbug_rock/workbug_rock_attack";
    protected override string CastSfx => "event:/sfx/enemy/enemy_attacks/workbug_goop/workbug_goop_spit";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/workbug_rock/workbug_rock_die";
    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat([
        ModelDb.Power<SnailShellPower>().ResolvedBigIconPath]);

    protected override void AddExtraAnimationStates(CreatureAnimator animator, AnimState idle)
    {
        foreach (var (trigger, clip) in new[] { ("Retreat", "retreat"), ("Crawl", "crawl"), ("ShellBreak", "shell_break") })
            animator.AddAnyState(trigger, new AnimState(clip) { NextState = idle });
    }

    public async Task GrowShell(PlayerChoiceContext context, int amount, bool initial = false)
    {
        if (!CanAct || (!initial && this is CrystalSnail && !HasShell)) return;
        if (!Creature.HasPower<SnailShellPower>())
            await PowerCmd.Apply<SnailShellPower>(context, Creature, 1, Creature, null);
        await CreatureCmd.GainBlock(Creature, amount, ValueProp.Move, null);
        NotifyMenders();
    }

    public virtual Task OnShellBroken(PlayerChoiceContext context) => Task.CompletedTask;

    public void NotifyMenders()
    {
        if (CombatState?.CurrentSide != CombatSide.Player) return;
        foreach (var mender in CombatState.Enemies.Select(c => c.Monster).OfType<SlimeSnail>())
            mender.RefreshRepairIntent();
    }

    public override Task AfterDeath(PlayerChoiceContext context, Creature creature, bool prevented, float deathAnimLength)
    {
        if (creature == Creature && !prevented) NotifyMenders();
        return Task.CompletedTask;
    }

    protected async Task BeginPose(string trigger, string animation, float contact)
    {
        await CreatureCmd.TriggerAnim(Creature, trigger, 0);
        await WaitForPose(animation, contact, contact);
    }

    protected async Task WaitForPose(string animation, float moment, float fallback)
    {
        var sprite = Creature.GetCreatureNode()?.Visuals?.SpineBody;
        float wait = fallback;
        using (TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? track))
            if (track?.GetAnimationName() == animation) wait = Math.Max(0, moment - track.GetTrackTime());
        await Cmd.Wait(wait);
        using var scope = TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? current);
        if (current?.GetAnimationName() == animation && current.GetTrackTime() < moment)
        {
            current.SetMixDuration(0);
            current.SetTrackTime(moment);
            sprite!.BoundObject.Call("update_skeleton", 0f);
        }
    }

    protected async Task Hit(int damage, float contact = .48f)
    {
        await DamageCmd.Attack(damage).FromMonster(this).WithNoAttackerAnim()
            .AfterAttackerAnim(() => BeginPose("Attack", "attack", contact))
            .WithAttackerFx(null, AttackSfx).WithHitFx("vfx/vfx_attack_blunt").Execute(null);
        await WaitForPose("attack", 1.25f, 0);
    }
}
