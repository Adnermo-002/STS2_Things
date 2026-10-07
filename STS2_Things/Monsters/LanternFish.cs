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
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Powers;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Monsters;

public sealed class LanternFish : ThingsSpineMonster
{
    public const float BiteContact = 0.48f;
    public const float FlashRelease = 0.72f;
    public const float GuardRelease = 0.42f;
    public const int BlindCharges = 2;
    public const int GuardBlock = 9;
    private int _openingPhase;
    public int OpeningPhase => _openingPhase;
    public void SetOpeningPhase(int phase) { AssertMutable(); _openingPhase = Math.Clamp(phase, 0, 3); }

    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 44, 40);
    public override int MaxInitialHp => MinInitialHp + 4;
    public override float HpBarSizeReduction => 145f;
    private int BiteDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 9, 8);
    private int TailDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 6, 5);
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/thieving_hopper/thieving_hopper_attack";
    protected override string CastSfx => "event:/sfx/enemy/enemy_attacks/soul_fysh/soul_fysh_beckon";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/soul_fysh/soul_fysh_intangible";
    public override string HurtSfx => "event:/sfx/enemy/enemy_attacks/soul_fysh/soul_fysh_hurt";
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Magic;
    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat([
        ModelDb.Power<LanternBlindnessPower>().ResolvedBigIconPath,
        "res://shaders/cards/lantern_blindness.gdshader"]);

    protected override void AddExtraAnimationStates(CreatureAnimator animator, AnimState idle)
    {
        animator.AddAnyState("Guard", new AnimState("guard") { NextState = idle });
        animator.AddAnyState("TailSwipe", new AnimState("tail_swipe") { NextState = idle });
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        MoveState[] moves = [
            new("BITE_MOVE", Bite, new SingleAttackIntent(BiteDamage)),
            new("FLASH_MOVE", FlashLantern, new DebuffIntent()),
            new("TAIL_MOVE", TailSwipe, new MultiAttackIntent(TailDamage, 2)),
            new("GUARD_MOVE", Guard, new DefendIntent())];
        for (int i = 0; i < moves.Length; i++) moves[i].FollowUpState = moves[(i + 1) % moves.Length];
        return new MonsterMoveStateMachine(moves, moves[_openingPhase]);
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

    private async Task Begin(string trigger, string animation, float moment)
    {
        await CreatureCmd.TriggerAnim(Creature, trigger, 0f);
        await WaitForPose(animation, moment, moment);
    }

    private async Task Finish(string animation, float duration) => await WaitForPose(animation, duration, 0);

    private async Task Bite(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(BiteDamage).FromMonster(this).WithNoAttackerAnim()
            .AfterAttackerAnim(() => Begin("Attack", "attack", BiteContact))
            .WithAttackerFx(null, AttackSfx).Execute(null);
        await Finish("attack", 1.25f);
    }

    private async Task TailSwipe(IReadOnlyList<Creature> targets)
    {
        // Each hit has its own windup/contact/recovery: slow hooks cannot outrun the next tail swipe.
        await DamageCmd.Attack(TailDamage).FromMonster(this).WithHitCount(2).WithNoAttackerAnim()
            .AfterAttackerAnim(async () => {
                await Finish("tail_swipe", 0.95f);
                await Begin("TailSwipe", "tail_swipe", 0.36f);
            }).WithAttackerFx(null, AttackSfx).Execute(null);
        await Finish("tail_swipe", 0.95f);
    }

    private async Task FlashLantern(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await Begin("Cast", "cast", FlashRelease);
        await PowerCmd.Apply<LanternBlindnessPower>(new ThrowingPlayerChoiceContext(),
            CombatState.Players.Select(player => player.Creature).Where(creature => creature.IsAlive),
            BlindCharges, Creature, null);
        await Finish("cast", 1.8f);
    }

    private async Task Guard(IReadOnlyList<Creature> targets)
    {
        await Begin("Guard", "guard", GuardRelease);
        await CreatureCmd.GainBlock(Creature, GuardBlock, ValueProp.Move, null);
        await Finish("guard", 1.25f);
    }
}
