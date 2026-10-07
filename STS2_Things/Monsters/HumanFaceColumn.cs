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
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Powers;
using STS2_Things.Visuals;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Monsters;

/// <summary>One independently targetable stone disc of a finite, shared column.</summary>
public sealed class HumanFaceColumn : ThingsSpineMonster
{
    public const int InitialLayers = 6;
    public const float LayerSpacing = 190f;
    public static readonly string[] LayerSlots = ["column_bottom", "column_middle", "column_top"];
    private HumanFaceColumnGroup? _group;
    private int _opening;
    private bool _deathHandled;
    public int Level { get; private set; }
    public int RemainingLayers => _group?.Remaining ?? InitialLayers;
    public int ReserveLayers => _group?.Reserve ?? 0;
    public bool IsTopVisible => _group?.Living.LastOrDefault() == this;
    public bool IsDizzy => NextMove?.Id == stunnedMoveId;
    public bool IsReplacement { get; private set; }

    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 46, 40);
    public override int MaxInitialHp => MinInitialHp + 6;
    public override float HpBarSizeReduction => 24f;
    // Budget for the complete column: at most three ten-damage attacks per turn.
    private int KnockDamage => 10;
    private int RattleDamage => 5;
    private int SealBlock => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 18, 14);
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/workbug_rock/workbug_rock_attack";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/workbug_rock/workbug_rock_die";
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Stone;
    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat([
        ModelDb.Power<HumanFaceColumnPower>().ResolvedBigIconPath]);

    internal void Configure(HumanFaceColumnGroup group, int level, int opening, bool replacement = false)
    {
        AssertMutable();
        _group = group;
        Level = level;
        _opening = opening;
        IsReplacement = replacement;
    }

    internal void LowerTo(int level)
    {
        int distance = Level - level;
        Level = level;
        Creature.SlotName = LayerSlots[level];
        if (distance > 0) NHumanFaceColumnVisuals.Drop(Creature, distance);
    }

    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        // A console-spawned disc has no guaranteed column encounter slots.
        if (_group == null) _group = HumanFaceColumnGroup.ForStandalone(this);
        if (!Creature.HasPower<HumanFaceColumnPower>())
            await PowerCmd.Apply<HumanFaceColumnPower>(new ThrowingPlayerChoiceContext(),
                Creature, RemainingLayers, Creature, null);
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        MoveState[] moves =
        [
            new("KNOCK_MOVE", Knock, new SingleAttackIntent(KnockDamage)),
            new("REBUKE_MOVE", Rebuke, new DebuffIntent()),
            new("SEAL_MOVE", Seal, new DefendIntent()),
            new("RATTLE_MOVE", Rattle, new MultiAttackIntent(RattleDamage, 2)),
        ];
        for (int i = 0; i < moves.Length; i++) moves[i].FollowUpState = moves[(i + 1) % moves.Length];
        return new MonsterMoveStateMachine(moves, moves[_opening % moves.Length]);
    }

    protected override void AddExtraAnimationStates(CreatureAnimator animator, AnimState idle)
    {
        animator.AddAnyState("Seal", new AnimState("seal") { NextState = idle });
        animator.AddAnyState("Rattle", new AnimState("rattle") { NextState = idle });
        var dizzy = new AnimState("stunned_loop", isLooping: true);
        var fall = new AnimState("fall") { NextState = dizzy };
        var stunnedHurt = new AnimState("hurt") { NextState = dizzy };
        dizzy.AddBranch(CreatureAnimator.hitTrigger, stunnedHurt);
        fall.AddBranch(CreatureAnimator.hitTrigger, stunnedHurt);
        stunnedHurt.AddBranch(CreatureAnimator.hitTrigger, stunnedHurt);
        animator.AddAnyState("Fall", fall);
        animator.AddAnyState("Dizzy", dizzy);
        animator.AddAnyState("Recover", new AnimState("recover") { NextState = idle });
    }

    internal async Task StunForCollapse()
    {
        if (!Creature.IsAlive) return;
        if (!IsDizzy)
        {
            // Enemy-turn summons are not rolled by the native Add command yet.
            if (NextMove == null) RollMove(CombatState.Players.Select(player => player.Creature));
            await CreatureCmd.Stun(Creature, Recover, NextMove?.Id ?? "KNOCK_MOVE");
        }
        await CreatureCmd.TriggerAnim(Creature, "Fall", 0);
    }

    private async Task Recover(IReadOnlyList<Creature> _) =>
        await CreatureCmd.TriggerAnim(Creature, "Recover", .35f);

    private async Task Knock(IReadOnlyList<Creature> _)
    {
        await DamageCmd.Attack(KnockDamage).FromMonster(this).WithAttackerAnim("Attack", .38f)
            .WithAttackerFx(null, AttackSfx).WithHitFx("vfx/vfx_attack_blunt").Execute(null);
    }

    private async Task Rebuke(IReadOnlyList<Creature> targets)
    {
        await CreatureCmd.TriggerAnim(Creature, "Cast", .5f);
        await PowerCmd.Apply<WeakPower>(new ThrowingPlayerChoiceContext(),
            targets.Where(target => target.IsAlive).ToArray(), 2, Creature, null);
    }

    private async Task Seal(IReadOnlyList<Creature> _)
    {
        await CreatureCmd.TriggerAnim(Creature, "Seal", .42f);
        await CreatureCmd.GainBlock(Creature, SealBlock, ValueProp.Move, null);
    }

    private async Task Rattle(IReadOnlyList<Creature> _)
    {
        int hit = 0;
        await DamageCmd.Attack(RattleDamage).WithHitCount(2).FromMonster(this).WithNoAttackerAnim()
            .AfterAttackerAnim(async () =>
            {
                float contact = hit++ == 0 ? .34f : .62f;
                if (hit == 1) await CreatureCmd.TriggerAnim(Creature, "Rattle", 0);
                var sprite = Creature.GetCreatureNode()?.Visuals?.SpineBody;
                float time = 0;
                using (TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? track))
                    if (track?.GetAnimationName() == "rattle") time = track.GetTrackTime();
                await Cmd.Wait(Math.Max(0, contact - time));
                using (TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? current))
                    if (current?.GetAnimationName() == "rattle" && current.GetTrackTime() < contact)
                    {
                        current.SetMixDuration(0);
                        current.SetTrackTime(contact);
                        sprite!.BoundObject.Call("update_skeleton", 0f);
                    }
            }).WithAttackerFx(null, AttackSfx)
            .WithHitFx("vfx/vfx_attack_blunt").Execute(null);
    }

    public override async Task AfterDeath(PlayerChoiceContext context, Creature creature,
        bool wasRemovalPrevented, float deathAnimLength)
    {
        if (creature != Creature) return;
        if (wasRemovalPrevented || creature.IsAlive)
        {
            if (_group != null) await _group.ResolvePending(context, creature.CombatState);
            return;
        }
        if (_deathHandled) return;
        _deathHandled = true;
        if (_group != null) await _group.BreakLayer(this, context);
    }

    public override async Task AfterCurrentHpChanged(Creature creature, decimal delta)
    {
        // Native death preventers may heal only after AfterDeath has run.
        // Resume a queued collapse once that layer is alive again.
        if (creature == Creature && delta > 0 && creature.IsAlive && _group != null)
            await _group.ResolvePending(new ThrowingPlayerChoiceContext(), creature.CombatState);
    }
}
