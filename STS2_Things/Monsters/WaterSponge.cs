using Godot;
using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
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
using MegaCrit.Sts2.Core.Nodes.Vfx;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Powers;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Monsters;

public sealed class WaterSponge : ThingsSpineMonster
{
    public const int WaterCapacity = 3;
    public const string SprayMoveId = "SPRAY_MOVE";
    public const float SlapContact = .48f;
    public const float SoakContact = .56f;
    public const float SprayContact = .64f;
    private MoveState? _spray;

    public int Water => Creature.GetPower<SpongeReservoirPower>()?.Amount ?? 0;
    public int DamagePerWater => Math.Max(1, (int)Math.Ceiling(Creature.MaxHp * .10m));
    public int StoredDamage => Creature.GetPower<SpongeDamageProgressPower>()?.Damage ?? 0;
    public float VisibleWater => Math.Min(WaterCapacity, Water + StoredDamage / (float)DamagePerWater);
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 55, 50);
    public override int MaxInitialHp => MinInitialHp + 4;
    public override float HpBarSizeReduction => 130f;
    private int AttackDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 12, 11);
    private int SprayDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 20, 18);
    private int SprayHealing => Math.Max(1, (int)Math.Ceiling(Creature.MaxHp * .10m));
    private int SoakBlock => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 12, 10);
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/gravetide_slug/gravetide_slug_attack_light";
    protected override string CastSfx => "event:/sfx/enemy/enemy_attacks/gravetide_slug/gravetide_slug_devour";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/gravetide_slug/gravetide_slug_die";
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Magic;
    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat([
        ModelDb.Power<AbsorbentSpongePower>().ResolvedBigIconPath,
        ModelDb.Power<SpongeReservoirPower>().ResolvedBigIconPath,
        ModelDb.Power<SpongeRinsePower>().ResolvedBigIconPath,
        NSplashVfx.scenePath]);

    public override async Task BeforeCombatStart()
    {
        if (Creature.IsAlive)
        {
            await PowerCmd.Apply<SpongeDamageProgressPower>(new ThrowingPlayerChoiceContext(), Creature, 1, Creature, null);
            await PowerCmd.Apply<AbsorbentSpongePower>(new ThrowingPlayerChoiceContext(), Creature, 1, Creature, null);
        }
    }

    protected override void AddExtraAnimationStates(CreatureAnimator animator, AnimState idle) =>
        animator.AddAnyState("Soak", new AnimState("soak") { NextState = idle });

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var soak = new MoveState("SOAK_MOVE", Soak, new DefendIntent(), new BuffIntent());
        var slap = new MoveState("SLAP_MOVE", Slap, new SingleAttackIntent(AttackDamage));
        _spray = new MoveState(SprayMoveId, Spray, new SingleAttackIntent(SprayDamage), new BuffIntent(), new HealIntent())
        {
            // Filling during our own Soak must not let the following RollMove skip
            // the newly selected spray before it has actually been performed.
            MustPerformOnceBeforeTransitioning = true,
            FollowUpState = soak,
        };
        var afterSoak = new ConditionalBranchState("AFTER_SOAK");
        afterSoak.AddState(_spray, () => Water >= WaterCapacity);
        afterSoak.AddState(slap, () => true);
        var afterSlap = new ConditionalBranchState("AFTER_SLAP");
        afterSlap.AddState(_spray, () => Water >= WaterCapacity);
        afterSlap.AddState(soak, () => true);
        soak.FollowUpState = afterSoak;
        slap.FollowUpState = afterSlap;
        return new MonsterMoveStateMachine([soak, slap, _spray, afterSoak, afterSlap], soak);
    }

    public async Task AbsorbWater(PlayerChoiceContext choiceContext, int stacks = 1)
    {
        if (!Creature.IsAlive || Water >= WaterCapacity || stacks <= 0) return;
        await PowerCmd.Apply<SpongeReservoirPower>(choiceContext, Creature,
            Math.Min(stacks, WaterCapacity - Water), Creature, null);
    }

    public void PrepareSpray()
    {
        if (Creature.IsAlive && Water >= WaterCapacity && _spray != null && NextMove != _spray)
            SetMoveImmediate(_spray);
    }

    private async Task BeginPose(string trigger, string animation, float contact)
    {
        await CreatureCmd.TriggerAnim(Creature, trigger, 0f);
        await WaitForPose(animation, contact, contact);
    }

    private async Task WaitForPose(string animation, float moment, float fallback)
    {
        var sprite = Creature.GetCreatureNode()?.Visuals?.SpineBody;
        float wait = fallback;
        using (TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? track))
            if (track != null && track.GetAnimationName() == animation)
                wait = Math.Max(0, moment - track.GetTrackTime());
        await Cmd.Wait(wait);
        using var scope = TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? current);
        if (current != null && current.GetAnimationName() == animation && current.GetTrackTime() < moment)
        {
            current.SetMixDuration(0);
            current.SetTrackTime(moment);
            sprite!.BoundObject.Call("update_skeleton", 0f);
        }
    }

    private async Task Soak(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await BeginPose("Soak", "soak", SoakContact);
        await CreatureCmd.GainBlock(Creature, SoakBlock, ValueProp.Move, null);
        if (Water < WaterCapacity)
            await PowerCmd.Apply<SpongeReservoirPower>(new ThrowingPlayerChoiceContext(), Creature, 1, Creature, null);
        await WaitForPose("soak", 1.35f, 0);
    }

    private async Task Slap(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(AttackDamage).FromMonster(this).WithNoAttackerAnim()
            .AfterAttackerAnim(() => BeginPose("Attack", "attack", SlapContact))
            .WithAttackerFx(null, AttackSfx).WithHitFx("vfx/vfx_attack_blunt").Execute(null);
        await WaitForPose("attack", 1.15f, 0);
    }

    private async Task Spray(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(SprayDamage).FromMonster(this).WithNoAttackerAnim()
            .AfterAttackerAnim(() => BeginPose("Cast", "cast", SprayContact))
            .WithAttackerFx(null, CastSfx)
            .WithHitVfxNode(target => target.GetCreatureNode() is { } node
                ? NSplashVfx.Create(node.VfxSpawnPosition, new Color("8ec7d8")) : null)
            .Execute(null);
        // The rinse follows damage: Vulnerable still applies to this spray.
        foreach (var target in targets.Where(creature => creature.IsAlive))
        {
            foreach (var power in target.Powers.Where(power => power.Amount > 0 &&
                         power is WeakPower or VulnerablePower or FrailPower or LanternBlindnessPower).ToArray())
                await PowerCmd.Decrement(power);
            await PowerCmd.Apply<SpongeRinsePower>(new ThrowingPlayerChoiceContext(), target, 1, Creature, null);
        }
        if (Creature.GetPower<SpongeReservoirPower>() is { } reservoir)
            await PowerCmd.Remove(reservoir);
        Creature.GetPower<SpongeDamageProgressPower>()?.Reset();
        await WaitForPose("cast", 1.5f, 0);
        // Native Heal can revive creatures, so guard survival after retaliation.
        if (Creature.IsAlive && !CombatManager.Instance.IsOverOrEnding)
        {
            int healing = Math.Min(SprayHealing, Creature.MaxHp - Creature.CurrentHp);
            if (healing > 0) await CreatureCmd.Heal(Creature, healing);
        }
    }
}
