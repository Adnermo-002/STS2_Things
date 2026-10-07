using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Powers;
using STS2_Things.Visuals;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Monsters;

/// <summary>A low-damage tank: retained native Debris offers the next meal.</summary>
public sealed class CaveMaw : ThingsSpineMonster
{
    public const int DebrisCount = 2;
    public const int BlockPerCard = 3;
    public const int StrengthPerMeal = 3;
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 122, 112);
    public override int MaxInitialHp => MinInitialHp + 6;
    public override float HpBarSizeReduction => 60f;
    private int InitialPlating => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 14, 12);
    private int BiteDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 12, 10);
    private int PressDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 7, 6);
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Magic;
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/gravetide_slug/gravetide_slug_attack_light";
    protected override string CastSfx => "event:/sfx/enemy/enemy_attacks/gravetide_slug/gravetide_slug_devour";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/gravetide_slug/gravetide_slug_die";
    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat([
        ModelDb.Card<Debris>().PortraitPath,
        ModelDb.Power<CaveMawAppetitePower>().ResolvedBigIconPath,
        ModelDb.Power<PlatingPower>().ResolvedBigIconPath,
        ModelDb.Power<StrengthPower>().ResolvedBigIconPath]);

    public override async Task BeforeCombatStart()
    {
        var context = new ThrowingPlayerChoiceContext();
        await PowerCmd.Apply<PlatingPower>(context, Creature, InitialPlating, Creature, null);
        await PowerCmd.Apply<CaveMawAppetitePower>(context, Creature, 1, Creature, null);
    }

    protected override void AddExtraAnimationStates(CreatureAnimator animator, AnimState idle)
    {
        foreach (var (trigger, clip) in new[] { ("Devour", "devour"), ("Press", "press"), ("Empty", "empty") })
            animator.AddAnyState(trigger, new AnimState(clip) { NextState = idle });
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var feed = new MoveState("OFFER_MOVE", Offer, new StatusIntent(DebrisCount));
        var devour = new MoveState("DEVOUR_MOVE", Devour, new BuffIntent(), new DefendIntent());
        var bite = new MoveState("BITE_MOVE", _ => Strike(BiteDamage, "Attack", "attack", [.48f], 1.35f),
            new SingleAttackIntent(BiteDamage));
        var press = new MoveState("PRESS_MOVE", _ => Strike(PressDamage, "Press", "press", [.44f, .80f], 1.5f),
            new MultiAttackIntent(PressDamage, 2));
        feed.FollowUpState = devour;
        devour.FollowUpState = bite;
        bite.FollowUpState = press;
        press.FollowUpState = feed;
        return new MonsterMoveStateMachine([feed, devour, bite, press], feed);
    }

    private async Task Offer(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await CreatureCmd.TriggerAnim(Creature, "Cast", 0);
        await WaitForPose("cast", .54f, .54f);
        foreach (var target in targets.Where(c => c.IsAlive && c.Player != null))
        {
            if (!Creature.IsAlive || CombatManager.Instance.IsOverOrEnding) return;
            var cards = new List<CardModel>();
            for (int i = 0; i < DebrisCount; i++)
            {
                var debris = CombatState.CreateCard<Debris>(target.Player!);
                debris.AddKeyword(CardKeyword.Retain);
                cards.Add(debris);
            }
            // Native creation/overflow/keyword display. Never mutate canonical
            // Debris or a permanent-deck card, and never replace its Exhaust.
            await CardPileCmd.AddGeneratedCardsToCombat(cards, PileType.Hand, null);
        }
        await WaitForPose("cast", 1.6f, 0);
    }

    private async Task Devour(IReadOnlyList<Creature> targets)
    {
        // End-of-turn discard has already happened. Retained Debris is in Hand;
        // ordinary Status cards (including Parasitism) are in Discard.
        // Snapshot once: Exhaust hooks must not recursively feed new cards.
        var meal = targets.Where(c => c.IsAlive && c.Player?.PlayerCombatState != null)
            .SelectMany(c => CardPile.GetCards(c.Player!, PileType.Hand)
                .Concat(CardPile.GetCards(c.Player!, PileType.Discard)))
            .Where(card => card.Type == CardType.Status).ToArray();
        if (meal.Length == 0)
        {
            await CreatureCmd.TriggerAnim(Creature, "Empty", 0);
            await WaitForPose("empty", 1.15f, 1.15f);
            return;
        }
        SfxCmd.Play(CastSfx);
        await CreatureCmd.TriggerAnim(Creature, "Devour", 0);
        await WaitForPose("devour", .50f, .50f);
        var context = new ThrowingPlayerChoiceContext();
        int consumed = 0;
        foreach (var card in meal)
        {
            if (!Creature.IsAlive || CombatManager.Instance.IsOverOrEnding) return;
            if (card.CombatState != CombatState || card.Pile?.Type is not (PileType.Hand or PileType.Discard)) continue;
            var from = NCaveMawMealVfx.GetCardOrigin(card);
            // Keep native pile notifications and card-view cleanup. Skipping
            // visuals leaves consumed hand holders alive; the meal VFX owns
            // only its separate decorative card, not the original hand view.
            // V107 returns Task, V111 returns a pile result. The final pile is
            // authoritative on both versions, including redirected moves.
            await CardCmd.Exhaust(context, card);
            if (card.Pile?.Type != PileType.Exhaust) continue;
            consumed++;
            NCaveMawMealVfx.Play(card, Creature, from, Math.Min(consumed - 1, 5) * .045f);
        }
        await WaitForPose("devour", 1.40f, .90f);
        if (!Creature.IsAlive || CombatManager.Instance.IsOverOrEnding) return;
        if (consumed > 0)
        {
            Creature.GetPower<CaveMawAppetitePower>()?.ShowMeal();
            await CreatureCmd.GainBlock(Creature, consumed * BlockPerCard, ValueProp.Move, null);
            await PowerCmd.Apply<StrengthPower>(context, Creature, Math.Min(consumed, StrengthPerMeal), Creature, null);
        }
        await WaitForPose("devour", 2.10f, 0);
    }

    private async Task Strike(int damage, string trigger, string animation, float[] contacts, float duration)
    {
        int hit = 0;
        await DamageCmd.Attack(damage).WithHitCount(contacts.Length).FromMonster(this).WithNoAttackerAnim()
            .AfterAttackerAnim(async () =>
            {
                if (hit == 0) await CreatureCmd.TriggerAnim(Creature, trigger, 0);
                float contact = contacts[Math.Min(hit, contacts.Length - 1)];
                await WaitForPose(animation, contact, hit == 0 ? contact : contacts[hit] - contacts[hit - 1]);
                hit++;
            }).WithAttackerFx(null, AttackSfx).WithHitFx("vfx/vfx_bite").Execute(null);
        await WaitForPose(animation, duration, 0);
    }

    private async Task WaitForPose(string animation, float moment, float fallback)
    {
        var sprite = Creature.GetCreatureNode()?.Visuals?.SpineBody;
        float wait = fallback;
        using (TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? track))
            if (track != null && track.GetAnimationName() == animation) wait = Math.Max(0, moment - track.GetTrackTime());
        await Cmd.Wait(wait);
        using var scope = TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? current);
        if (current != null && current.GetAnimationName() == animation && current.GetTrackTime() < moment)
        {
            current.SetMixDuration(0);
            current.SetTrackTime(moment);
            sprite!.BoundObject.Call("update_skeleton", 0f);
        }
    }
}
