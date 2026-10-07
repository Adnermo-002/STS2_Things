using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using STS2_Things.Afflictions;
using STS2_Things.Powers;

namespace STS2_Things.Monsters;

public sealed class SilkMoth : ThingsSpineMonster
{
    public const float WeaveContact = .62f;
    public const float SwoopContact = .48f;
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 48, 44);
    public override int MaxInitialHp => MinInitialHp + 4;
    public override float HpBarSizeReduction => 130f;
    private int SwoopDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 14, 12);
    private int FlutterDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 7, 6);
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/thieving_hopper/thieving_hopper_attack_hover";
    protected override string CastSfx => "event:/sfx/enemy/enemy_attacks/workbug_silk/workbug_silk_spit";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/workbug_silk/workbug_silk_die";
    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat([
        ModelDb.Power<SilkThreadPower>().ResolvedBigIconPath,
        ModelDb.Affliction<SilkLead>().OverlayPath, ModelDb.Affliction<SilkBound>().OverlayPath,
        Visuals.NSilkCardOverlay.EffectScenePath]);

    protected override void AddExtraAnimationStates(CreatureAnimator animator, AnimState idle) =>
        animator.AddAnyState("Flutter", new AnimState("flutter") { NextState = idle });

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var weave = new MoveState("WEAVE_MOVE", Weave, new CardDebuffIntent());
        var swoop = new MoveState("SWOOP_MOVE", Swoop, new SingleAttackIntent(SwoopDamage));
        var flutter = new MoveState("FLUTTER_MOVE", Flutter, new MultiAttackIntent(FlutterDamage, 2));
        weave.FollowUpState = swoop;
        swoop.FollowUpState = flutter;
        flutter.FollowUpState = weave;
        return new MonsterMoveStateMachine([weave, swoop, flutter], weave);
    }

    private async Task Weave(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await CreatureCmd.TriggerAnim(Creature, "Cast", WeaveContact);
        foreach (var target in targets.Where(target => target.IsAlive && target.GetPower<SilkThreadPower>() == null))
            await PowerCmd.Apply<SilkThreadPower>(new ThrowingPlayerChoiceContext(), target, 1, Creature, null);
        await Cmd.Wait(.73f);
    }

    private async Task Swoop(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(SwoopDamage).FromMonster(this)
            .WithAttackerAnim("Attack", SwoopContact).WithAttackerFx(null, AttackSfx)
            .WithHitFx("vfx/vfx_attack_slash").Execute(null);
        await Cmd.Wait(.48f);
    }

    private async Task Flutter(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(FlutterDamage).WithHitCount(2).FromMonster(this)
            .WithAttackerAnim("Flutter", .42f).OnlyPlayAnimOnce().WithAttackerFx(null, AttackSfx)
            .WithHitFx("vfx/vfx_attack_blunt").Execute(null);
        await Cmd.Wait(.48f);
    }
}
