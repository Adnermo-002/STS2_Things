using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Potions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using STS2_Things.Powers;

namespace STS2_Things.Monsters;

/// <summary>
/// A Thieving Hopper variant that targets Curses, then starter Strikes/Defends,
/// then Common, Uncommon, and Rare cards before stealing one potion. It returns
/// the exact loot when killed and keeps it when it escapes.
/// </summary>
public sealed class QuirkyHopper : MonsterModel
{
    public const string StunTrigger = "StunTrigger";
    public const string HoverLoop = "event:/sfx/enemy/enemy_attacks/thieving_hopper/thieving_hopper_hover_loop";

    private const string FleeTrigger = "Flee";
    private const string HoverTrigger = "Hover";
    private const string StealTrigger = "Steal";
    private const string EscapeMoveId = "ESCAPE_MOVE";
    private const string StealSfx = "event:/sfx/enemy/enemy_attacks/thieving_hopper/thieving_hopper_steal";
    private const string TakeOffSfx = "event:/sfx/enemy/enemy_attacks/thieving_hopper/thieving_hopper_take_off";

    private static readonly Func<CardModel, bool>[] CardTheftPriority =
    [
        card => card.Type == CardType.Curse,
        IsStarterStrikeOrDefend,
        card => card.Rarity == CardRarity.Common,
        card => card.Rarity == CardRarity.Uncommon,
        card => card.Rarity == CardRarity.Rare
    ];

    private bool _isHovering;

    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 72, 68);

    public override int MaxInitialHp => MinInitialHp;

    protected override string VisualsPath => SceneHelper.GetScenePath("creature_visuals/quirky_hopper");

    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat(
    [
        ModelDb.Power<ThingsQuirkPower>().ResolvedBigIconPath,
        ModelDb.Power<QuirkyFlutterPower>().ResolvedBigIconPath,
        ModelDb.Power<EscapeArtistPower>().ResolvedBigIconPath
    ]).Distinct();

    public bool IsHovering
    {
        get => _isHovering;
        set
        {
            AssertMutable();
            _isHovering = value;
        }
    }

    protected override string AttackSfx => IsHovering
        ? "event:/sfx/enemy/enemy_attacks/thieving_hopper/thieving_hopper_attack_hover"
        : "event:/sfx/enemy/enemy_attacks/thieving_hopper/thieving_hopper_attack";

    private string FleeSfx => IsHovering
        ? "event:/sfx/enemy/enemy_attacks/thieving_hopper/thieving_hopper_flee_hover"
        : "event:/sfx/enemy/enemy_attacks/thieving_hopper/thieving_hopper_flee";

    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/thieving_hopper/thieving_hopper_die";

    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Insect;

    public override string TakeDamageSfx => IsHovering
        ? "event:/sfx/enemy/enemy_attacks/thieving_hopper/thieving_hopper_hurt_hover"
        : base.TakeDamageSfx;

    private int TheftDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 22, 20);

    private int HatTrickDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 27, 25);

    private int NabDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 20, 18);

    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        await PowerCmd.Apply<EscapeArtistPower>(
            new ThrowingPlayerChoiceContext(),
            Creature,
            5m,
            Creature,
            null);
    }

    public override void BeforeRemovedFromRoom()
    {
        SfxCmd.StopLoop(Creature, HoverLoop);
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        var thievery = new MoveState(
            "THIEVERY_MOVE",
            ThieveryMove,
            new SingleAttackIntent(TheftDamage),
            new CardDebuffIntent());
        var nab = new MoveState("NAB_MOVE", NabMove, new SingleAttackIntent(NabDamage));
        var hatTrick = new MoveState("HAT_TRICK_MOVE", HatTrickMove, new SingleAttackIntent(HatTrickDamage));
        var flutter = new MoveState("FLUTTER_MOVE", FlutterMove, new BuffIntent());
        var escape = new MoveState(EscapeMoveId, EscapeMove, new EscapeIntent());

        thievery.FollowUpState = flutter;
        flutter.FollowUpState = hatTrick;
        hatTrick.FollowUpState = nab;
        nab.FollowUpState = escape;
        escape.FollowUpState = escape;
        return new MonsterMoveStateMachine([thievery, nab, hatTrick, flutter, escape], thievery);
    }

    private async Task ThieveryMove(IReadOnlyList<Creature> targets)
    {
        NCreature? creatureNode = NCombatRoom.Instance?.GetCreatureNode(Creature);
        if (creatureNode != null && targets.Count > 0)
        {
            Creature target = LocalContext.GetMe(targets) ?? targets[0];
            NCreature? targetNode = target.GetCreatureNode();
            Node2D? spineBone = creatureNode.GetSpecialNode<Node2D>("Visuals/SpineBoneNode");
            if (spineBone != null && targetNode != null)
            {
#if STS2_V107_1
                spineBone.Position = Vector2.Right * (targetNode.GlobalPosition.X - creatureNode.GlobalPosition.X);
#else
                float targetOffset = 900f * creatureNode.Visuals.Scale.X;
                spineBone.GlobalPosition = new Vector2(targetNode.GlobalPosition.X + targetOffset, spineBone.GlobalPosition.Y);
#endif
            }
        }

        await CreatureCmd.TriggerAnim(Creature, StealTrigger, 0.25f);
        SfxCmd.Play(StealSfx);

        var stolenLoot = new List<StolenLoot>();
        foreach (Creature target in targets)
        {
            if (target.IsDead)
            {
                continue;
            }

            Player? player = target.Player ?? target.PetOwner;
            if (player == null)
            {
                continue;
            }

            CardModel? card = SelectCardToSteal(player);
            PotionModel? potion = SelectPotionToSteal(player);
            int potionSlot = potion == null ? -1 : GetPotionSlot(player, potion);

            if (card != null)
            {
                await CardPileCmd.RemoveFromCombat(card);
            }

            if (potion != null)
            {
                // Do not use PotionCmd.Discard: this is temporary theft, not a player discard.
                player.DiscardPotionInternal(potion);
            }

            if (card != null || potion != null)
            {
                stolenLoot.Add(new StolenLoot(player, card, potion, potionSlot));
            }
        }

        await Cmd.Wait(0.6f);
        foreach (StolenLoot loot in stolenLoot)
        {
            if (loot.Card != null && creatureNode != null && LocalContext.IsMine(loot.Card))
            {
                Marker2D? stolenCardPos = creatureNode.GetSpecialNode<Marker2D>("%StolenCardPos");
                if (stolenCardPos != null)
                {
                    NCard? cardNode = NCard.Create(loot.Card);
                    if (cardNode != null)
                    {
                        stolenCardPos.AddChildSafely(cardNode);
                        cardNode.Position += cardNode.Size * 0.5f;
                        cardNode.UpdateVisuals(PileType.Deck, CardPreviewMode.Normal);
                    }
                }
            }

            if (loot.Potion != null)
            {
                var potionState = (ThingsQuirkPower)ModelDb.Power<ThingsQuirkPower>().ToMutable();
                int potionStateAmount = potionState.ConfigurePotionState(
                    loot.Player,
                    loot.Potion,
                    loot.PotionSlot);
                await PowerCmd.Apply(
                    new ThrowingPlayerChoiceContext(),
                    potionState,
                    Creature,
                    potionStateAmount,
                    Creature,
                    null);
                potionState.RecordTheft();
            }

            var cardState = (ThingsQuirkPower)ModelDb.Power<ThingsQuirkPower>().ToMutable();
            int cardStateAmount = cardState.ConfigureCardState(
                loot.Player,
                loot.Card?.DeckVersion,
                loot.Potion);
            await PowerCmd.Apply(
                new ThrowingPlayerChoiceContext(),
                cardState,
                Creature,
                cardStateAmount,
                Creature,
                null);
            cardState.RecordTheft();

        }

        await DamageCmd.Attack(TheftDamage)
            .FromMonster(this)
            .WithNoAttackerAnim()
            .WithHitFx("vfx/vfx_attack_blunt")
            .Execute(null);
    }

    private CardModel? SelectCardToSteal(Player player)
    {
        List<CardModel> candidates = CardPile
            .GetCards(player, PileType.Draw, PileType.Discard)
            .Where(card => card.DeckVersion != null)
            .ToList();
        if (candidates.Count == 0)
        {
            return null;
        }

        foreach (Func<CardModel, bool> isPriority in CardTheftPriority)
        {
            List<CardModel> tier = candidates.Where(isPriority).ToList();
            if (tier.Count > 0)
            {
                return RunRng.CombatCardGeneration.NextItem(tier);
            }
        }

        return RunRng.CombatCardGeneration.NextItem(candidates);
    }

    private PotionModel? SelectPotionToSteal(Player player)
    {
        List<PotionModel> potions = player.Potions.ToList();
        return potions.Count == 0 ? null : RunRng.CombatPotionGeneration.NextItem(potions);
    }

    private static bool IsStarterStrikeOrDefend(CardModel card)
    {
        string entry = card.Id.Entry;
        return entry.StartsWith("STRIKE_", StringComparison.Ordinal) ||
               entry.StartsWith("DEFEND_", StringComparison.Ordinal);
    }

    private static int GetPotionSlot(Player player, PotionModel potion)
    {
        for (int index = 0; index < player.PotionSlots.Count; index++)
        {
            if (ReferenceEquals(player.PotionSlots[index], potion))
            {
                return index;
            }
        }

        throw new InvalidOperationException("The stolen potion is not in the player's potion bar.");
    }

    private async Task NabMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(NabDamage)
            .FromMonster(this)
            .WithAttackerAnim("Attack", 0.3f)
            .WithAttackerFx(null, AttackSfx)
            .WithHitFx("vfx/vfx_attack_slash")
            .Execute(null);
    }

    private async Task HatTrickMove(IReadOnlyList<Creature> targets)
    {
        await DamageCmd.Attack(HatTrickDamage)
            .FromMonster(this)
            .WithAttackerAnim("Attack", 0.3f)
            .WithAttackerFx(null, AttackSfx)
            .WithHitFx("vfx/vfx_attack_slash")
            .Execute(null);
    }

    private async Task FlutterMove(IReadOnlyList<Creature> targets)
    {
        IsHovering = true;
        SfxCmd.Play(TakeOffSfx);
        SfxCmd.PlayLoop(Creature, HoverLoop);
        await CreatureCmd.TriggerAnim(Creature, HoverTrigger, 0f);
        await Cmd.Wait(1.25f);
        await PowerCmd.Apply<QuirkyFlutterPower>(
            new ThrowingPlayerChoiceContext(),
            Creature,
            3m,
            Creature,
            null);
    }

    private async Task EscapeMove(IReadOnlyList<Creature> targets)
    {
        NCombatRoom.Instance?.GetCreatureNode(Creature)?.ToggleIsInteractable(on: false);
        SfxCmd.Play(FleeSfx);
        await CreatureCmd.TriggerAnim(Creature, FleeTrigger, 0.85f);
        if (IsHovering)
        {
            SfxCmd.StopLoop(Creature, HoverLoop);
            IsHovering = false;
        }

        await Cmd.Wait(1.5f);
        List<ThingsQuirkPower> quirks = Creature.GetPowerInstances<ThingsQuirkPower>().ToList();
        foreach (ThingsQuirkPower quirk in quirks)
        {
            await quirk.ResolveEscape();
        }

        await CreatureCmd.Escape(Creature);
    }

    public override CreatureAnimator GenerateAnimator(MegaSprite controller)
    {
        var groundedIdle = new AnimState("idle_loop", isLooping: true)
        {
            BoundsContainer = "GroundedBounds"
        };
        var flee = new AnimState("flee");
        var hoverFlee = new AnimState("flee_hover");
        var groundedHurt = new AnimState("hurt");
        var hoverHurt = new AnimState("hurt_hover");
        var groundedAttack = new AnimState("attack");
        var hoverAttack = new AnimState("attack_hover");
        var death = new AnimState("die");
        var takeOff = new AnimState("take_off");
        var hoverIdle = new AnimState("hover_loop", isLooping: true)
        {
            BoundsContainer = "FlyingBounds"
        };
        var steal = new AnimState("steal");

        takeOff.NextState = hoverIdle;
        steal.NextState = groundedIdle;
        groundedHurt.NextState = groundedIdle;
        hoverHurt.NextState = hoverIdle;
        groundedAttack.NextState = groundedIdle;
        hoverAttack.NextState = hoverIdle;

        var animator = new CreatureAnimator(groundedIdle, controller);
        animator.AddAnyState(StunTrigger, groundedIdle);
        animator.AddAnyState(HoverTrigger, takeOff);
        animator.AddAnyState(StealTrigger, steal);
        animator.AddAnyState("Dead", death);
        animator.AddAnyState("Hit", hoverHurt, () => IsHovering);
        animator.AddAnyState("Hit", groundedHurt, () => !IsHovering);
        animator.AddAnyState("Attack", hoverAttack, () => IsHovering);
        animator.AddAnyState("Attack", groundedAttack, () => !IsHovering);
        animator.AddAnyState(FleeTrigger, hoverFlee, () => IsHovering);
        animator.AddAnyState(FleeTrigger, flee, () => !IsHovering);
        return animator;
    }

    private readonly record struct StolenLoot(
        Player Player,
        CardModel? Card,
        PotionModel? Potion,
        int PotionSlot);

}
