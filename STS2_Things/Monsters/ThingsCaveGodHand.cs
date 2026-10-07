using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Enchantments;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Vfx.Utilities;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Cards;
using STS2_Things.Encounters;
using STS2_Things.Powers;
using STS2_Things.Visuals;

namespace STS2_Things.Monsters;

/// <summary>
/// A damageable arm and an intent/attack proxy for the body's single move cycle.
/// Both concrete models keep their shipped IDs and visuals; lifecycle rules live here.
/// </summary>
public abstract class ThingsCaveGodHand : MonsterModel
{
    public enum Action { Rest, Down, Sweep, Grab, Slam, WeakStun, WeakAttack, Recover, EscapeStun }

    /// <summary>
    /// Move-state id for an action. Ids double as localization keys
    /// (THINGS_CAVE_GOD_LEFT_HAND / _RIGHT_HAND .moves.&lt;id&gt;.title), so they follow the body's UPPER_SNAKE style.
    /// </summary>
    public static string MoveId(Action action) => action switch
    {
        Action.Rest => "REST",
        Action.Down => "DOWN_STATE",
        Action.Sweep => "FRONT_SWEEP",
        Action.Grab => "GRAB_PLAYER",
        Action.Slam => "AIR_SLAM",
        Action.WeakStun => "WEAK_STUN",
        Action.WeakAttack => "WEAK_ATTACK",
        Action.Recover => "RECOVER",
        Action.EscapeStun => "GRAB_STUNNED",
        _ => throw new ArgumentOutOfRangeException(nameof(action), action, null)
    };

    public abstract bool IsLeft { get; }
    public bool IsDown { get; private set; }
    public bool IsStunned { get; private set; }
    public bool IsGrabbing { get; private set; }
    private bool _needsRecovery;
    private bool _applyingGrowth;
    private List<CardModel> _stolenCards = [];
    public IReadOnlyList<CardModel> StolenCards => _stolenCards;

    // ToMutable() is a MemberwiseClone: without this every arm instance (and the canonical model)
    // would share one stolen-card list, leaking cards across combats and runs.
    protected override void DeepCloneFields()
    {
        base.DeepCloneFields();
        _stolenCards = [];
    }

    private static readonly Func<CardModel, bool>[] StealPriorities =
    [
        c => c.Enchantment is not Imbued && c.Rarity == CardRarity.Uncommon,
        c => c.Enchantment is not Imbued && c.Rarity is CardRarity.Common or CardRarity.Rare or CardRarity.Event,
        c => c.Enchantment is not Imbued && c.Rarity is CardRarity.Basic or CardRarity.Quest,
        c => c.Rarity == CardRarity.Ancient || c.Enchantment is Imbued
    ];

    public ThingsCaveGodBody? Body => CombatState?.Enemies.Select(c => c.Monster).OfType<ThingsCaveGodBody>().FirstOrDefault();
    private NCaveGodBossBackground? Background => Body?.Background;
    private bool CanAct => !IsDown && !IsStunned && Body is { IsPhaseTransitionPending: false, IsDefeated: false };

    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 55, 50);
    public override int MaxInitialHp => MinInitialHp;
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Stone;
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_knockout";
    public override bool ShouldFadeAfterDeath => false;
    public override bool ShouldDisappearFromDoom => false;
    public override float DeathAnimLengthOverride => 0f;
    public override bool IsHealthBarVisible => !IsDown && !IsGrabbing;
    public override bool ShouldAllowHitting(Creature creature) => creature != Creature || _applyingGrowth || (!IsDown && !IsStunned && !IsGrabbing);
    public override bool ShouldAllowTargeting(Creature target) => target != Creature || (!IsDown && !IsStunned && !IsGrabbing);

    // Direct poison/retaliation damage does not use target selection. A downed or
    // recovering arm must also be protected on the actual damage path.
#if STS2_V107_1
    public override decimal ModifyDamageMultiplicative(Creature? target, decimal amount, ValueProp props,
        Creature? dealer, CardModel? cardSource)
#else
    public override decimal ModifyDamageMultiplicative(Creature? target, decimal amount, ValueProp props,
        Creature? dealer, CardModel? cardSource, CardPlay? cardPlay)
#endif
        => target == Creature && (IsDown || IsStunned) ? 0m : 1m;

    private int SweepDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 15, 14);
    private int GrabDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 8, 7);
    private int SlamDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 26, 24);
    private int WeakDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 20, 18);

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        MoveState rest = new(MoveId(Action.Rest), Rest);
        MoveState down = new(MoveId(Action.Down), Rest);
        MoveState sweep = new(MoveId(Action.Sweep), Sweep, new SingleAttackIntent(SweepDamage), new CardDebuffIntent());
        MoveState grab = new(MoveId(Action.Grab), Grab, new SingleAttackIntent(GrabDamage), new DebuffIntent());
        MoveState slam = new(MoveId(Action.Slam), Slam, new SingleAttackIntent(SlamDamage));
        MoveState weakStun = new(MoveId(Action.WeakStun), Stun, new StunIntent());
        MoveState weakAttack = new(MoveId(Action.WeakAttack), WeakAttack, new SingleAttackIntent(WeakDamage));
        MoveState recover = new(MoveId(Action.Recover), Recover, new StunIntent(), new HealIntent());
        MoveState escapeStun = new(MoveId(Action.EscapeStun), Stun, new StunIntent());

        rest.FollowUpState = rest;
        down.FollowUpState = down;
        sweep.FollowUpState = rest;
        grab.FollowUpState = rest;
        slam.FollowUpState = rest;
        weakStun.FollowUpState = weakAttack;
        weakAttack.FollowUpState = weakAttack;
        recover.FollowUpState = weakAttack;
        escapeStun.FollowUpState = rest;

        return new MonsterMoveStateMachine([rest, down, sweep, grab, slam, weakStun, weakAttack, recover, escapeStun], rest);
    }

    public void Plan(Action action)
    {
        // Preserve a native CreatureCmd.Stun until it has actually consumed its enemy action.
        if (!IsDown && !_needsRecovery && NextMove.Id == "STUNNED" && !NextMove.CanTransitionAway)
        {
            IsStunned = true;
            return;
        }
        if (IsDown) action = Action.Down;
        else if (_needsRecovery) action = Action.Recover;
        IsStunned = action is Action.WeakStun or Action.Recover or Action.EscapeStun or Action.Down;
        SetMoveImmediate((MoveState)MoveStateMachine!.States[MoveId(action)], forceTransition: true);
        // NCreature couples this switch to HP-bar visibility. The model's targeting hook
        // rejects stunned targets while still showing their health and healing intent.
        NCombatRoom.Instance?.GetCreatureNode(Creature)?.ToggleIsInteractable(IsHealthBarVisible);
        ConfigureCreatureNode();
    }

    internal void Disable()
    {
        IsDown = true;
        IsGrabbing = false;
        _needsRecovery = false;
        Plan(Action.Down);
    }

    internal async Task Restore()
    {
        IsDown = false;
        IsStunned = false;
        IsGrabbing = false;
        _needsRecovery = false;
        if (Creature.CurrentHp < Creature.MaxHp)
            await CreatureCmd.Heal(Creature, Creature.MaxHp - Creature.CurrentHp, playAnim: true);
        Plan(Action.Rest);
        ConfigureCreatureNode();
    }

    private void ConfigureCreatureNode()
    {
        NCreature? creatureNode = NCombatRoom.Instance?.GetCreatureNode(Creature);
        if (creatureNode != null && GodotObject.IsInstanceValid(creatureNode))
        {
            creatureNode.ZIndex = 5;
            creatureNode.ZAsRelative = false;

            // Elevate StateDisplay / HealthBar (health bar, power container, nameplate)
            Node? healthBar = creatureNode.GetNodeOrNull("%HealthBar")
                ?? creatureNode.GetNodeOrNull("HealthBar")
                ?? creatureNode.GetNodeOrNull("StateDisplay")
                ?? creatureNode.FindChild("HealthBar", recursive: true, owned: false)
                ?? creatureNode.FindChild("StateDisplay", recursive: true, owned: false);
            if (healthBar is CanvasItem hpCanvas)
            {
                hpCanvas.ZIndex = 5;
                hpCanvas.ZAsRelative = false;
            }

            // Elevate Intents (node in NCreature is %Intents)
            Node? intents = creatureNode.GetNodeOrNull("%Intents")
                ?? creatureNode.GetNodeOrNull("Intents")
                ?? creatureNode.GetNodeOrNull("%IntentContainer")
                ?? creatureNode.GetNodeOrNull("IntentContainer")
                ?? creatureNode.FindChild("Intents", recursive: true, owned: false)
                ?? creatureNode.FindChild("IntentContainer", recursive: true, owned: false);
            if (intents is CanvasItem intentCanvas)
            {
                intentCanvas.ZIndex = 5;
                intentCanvas.ZAsRelative = false;
            }
        }
    }

    public override async Task AfterAddedToRoom()
    {
        await base.AfterAddedToRoom();
        ConfigureCreatureNode();
        await EnsureAgingPower();
    }

    public override async Task BeforeSideTurnStart(PlayerChoiceContext choiceContext, CombatSide side, IReadOnlyList<Creature> participants, ICombatState combatState)
    {
        await base.BeforeSideTurnStart(choiceContext, side, participants, combatState);
        await EnsureAgingPower();
    }

    public async Task EnsureAgingPower()
    {
        if (Creature != null && !Creature.HasPower<ThingsCaveGodAgingPower>())
        {
            int remaining = Body?.AgingCountdown ?? ThingsCaveGodAgingPower.ResetAmount;
            _applyingGrowth = true;
            try
            {
                await PowerCmd.Apply<ThingsCaveGodAgingPower>(new ThrowingPlayerChoiceContext(), Creature,
                    remaining, Creature, null);
            }
            finally { _applyingGrowth = false; }
        }
    }

    public override bool ShouldDie(Creature creature) =>
        creature != Creature || Body is not { IsDefeated: false };

    public override async Task AfterPreventingDeath(Creature creature)
    {
        if (creature != Creature || Body is not { } body) return;
        if (body.IsPhaseTransitionPending)
        {
            await CreatureCmd.Heal(Creature, 1m, playAnim: false);
            await ClearDebuffs(Creature);
            await ReleaseStolenCards();
            return;
        }
        // Freeze the defeated arm before any awaited hooks; poison/Doom must not re-enter defeat.
        bool wasExposed = body.IsWeakPhase;
        if (wasExposed)
        {
            _needsRecovery = true;
            Plan(Action.Recover);
        }
        else Disable();
        await CreatureCmd.Heal(Creature, 1m, playAnim: false);
        await ClearDebuffs(Creature);
        if (Creature.GetPower<ThingsCaveGodAgingPower>() is { } aging)
        {
            await aging.OnArmDowned();
        }
        await ReleaseStolenCards();
        if (!wasExposed) await body.ExposeCore(this);
    }

    public override async Task AfterDeath(PlayerChoiceContext choiceContext, Creature creature, bool wasRemovalPrevented, float deathAnimLength)
    {
        await base.AfterDeath(choiceContext, creature, wasRemovalPrevented, deathAnimLength);
        if (creature == Creature)
        {
            await ReleaseStolenCards();
        }
    }

    public override void BeforeRemovedFromRoom()
    {
        base.BeforeRemovedFromRoom();
        ClearStolenCardVisual();
    }

    internal static async Task ClearDebuffs(Creature creature)
    {
        // StrengthPower.Type is Buff even at -5. Use the same effective classification as Artifact.
        foreach (PowerModel power in creature.Powers.Where(p => p.TypeForCurrentAmount == PowerType.Debuff).ToList())
        {
            // Native turn hooks snapshot listeners before the first Doom kills
            // and cleanses both arms. Removed Doom retains its old Amount, so
            // the second queued listener can still consider its owner doomed
            // and call First() on the now-empty list. Retire that instance too.
            if (power is DoomPower) power.SetAmount(0, silent: true);
            await PowerCmd.Remove(power);
        }
    }

    internal async Task GainStrength(int amount, Creature source)
    {
        // Native stuns may cover the cycle's growth turn. Receive the encounter's
        // self-buff without reopening targeting or damage on the recovering arm.
        _applyingGrowth = true;
        try
        {
            await PowerCmd.Apply<StrengthPower>(new ThrowingPlayerChoiceContext(), Creature, amount, source, null);
        }
        finally { _applyingGrowth = false; }
    }

    /// <summary>
    /// Mirrors the body's Crystal Vein on this arm. The buried core hides its power row,
    /// so the arms carry the visible countdown (cf. Kaiser Crab showing Crab Rage on both claws).
    /// </summary>
    internal async Task MirrorCrystalVein(int stacks, Creature source)
    {
        int delta = stacks - (Creature.GetPower<ThingsCaveGodCrystalVeinPower>()?.Amount ?? 0);
        if (delta == 0) return;
        _applyingGrowth = true;
        try
        {
            if (stacks <= 0 && Creature.GetPower<ThingsCaveGodCrystalVeinPower>() is { } vein)
                await PowerCmd.Remove(vein);
            else
                await PowerCmd.Apply<ThingsCaveGodCrystalVeinPower>(new ThrowingPlayerChoiceContext(), Creature, delta, source, null);
        }
        finally { _applyingGrowth = false; }
    }

    public override Task AfterCurrentHpChanged(Creature creature, decimal delta)
    {
        if (creature == Creature && delta < 0 && Body?.IsDefeated != true)
            Background?.PlayHurtAnim(forceGroan: true, hitPos: creature.GetCreatureNode()?.VfxSpawnPosition);
        return Task.CompletedTask;
    }

    internal void CancelGrab(bool stun)
    {
        IsGrabbing = false;
        if (stun && !IsDown) Plan(Action.EscapeStun);
    }

    private static Task Rest(IReadOnlyList<Creature> _) => Task.CompletedTask;
    private Task Stun(IReadOnlyList<Creature> _) => Task.CompletedTask;

    private async Task Recover(IReadOnlyList<Creature> _)
    {
        if (!_needsRecovery || IsDown) return;
        // A healing turn has native green healing feedback only, never hurt/rock-shatter feedback.
        if (Creature.CurrentHp < Creature.MaxHp)
            await CreatureCmd.Heal(Creature, Creature.MaxHp - Creature.CurrentHp, playAnim: true);
        _needsRecovery = false;
        // Keep the stun guard until the next player turn, after poison/other turn-end effects settle.
    }

    private async Task Sweep(IReadOnlyList<Creature> targets)
    {
        if (!CanAct || Body?.IsWeakPhase != false) return;
        Background?.StartCardSnatchAnim(IsLeft, targets);
        try
        {
            if (Background is { } background)
                await background.WaitForAttackFrame("card_snatch", CaveGodAnimTiming.CardSnatchTouch, CaveGodAnimTiming.CardSnatchTouch);
            else
                await Cmd.Wait(CaveGodAnimTiming.CardSnatchTouch);
            if (!CanAct || Body?.IsWeakPhase != false) return;
            await DamageCmd.Attack(SweepDamage).FromMonster(this)
                .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_kick").Execute(null);

            if (Background is { } closingBackground)
                await closingBackground.WaitForAttackFrame("card_snatch", CaveGodAnimTiming.CardSnatchClose,
                    CaveGodAnimTiming.CardSnatchClose - CaveGodAnimTiming.CardSnatchTouch);
            else
                await Cmd.Wait(CaveGodAnimTiming.CardSnatchClose - CaveGodAnimTiming.CardSnatchTouch);

            // The palm touches first; cards enter the fist on the closing frame.
            if (CanAct && Body?.IsWeakPhase == false)
            {
                await StealCards(targets);
            }
            if (Background is { } recoveringBackground)
                await recoveringBackground.WaitForAttackFrame("card_snatch", CaveGodAnimTiming.CardSnatchLength,
                    CaveGodAnimTiming.CardSnatchLength - CaveGodAnimTiming.CardSnatchClose);
            else
                await Cmd.Wait(CaveGodAnimTiming.CardSnatchLength - CaveGodAnimTiming.CardSnatchClose);
        }
        finally { Background?.ResetArmScale(); }
    }

    private async Task StealCards(IReadOnlyList<Creature>? targets)
    {
        IReadOnlyList<Creature> playerTargets = targets != null && targets.Count > 0
            ? targets.Where(c => c.IsAlive && c.Player != null).ToList()
            : CombatState?.PlayerCreatures.Where(c => c.IsAlive).ToList() ?? [];

        if (playerTargets.Count == 0) return;

        List<CardModel> stolenInThisSweep = [];
        foreach (Creature target in playerTargets)
        {
            if (target.Player == null) continue;
            CardModel? card = SelectCardToSteal(target.Player);
            if (card != null)
                stolenInThisSweep.Add(card);
        }
        if (stolenInThisSweep.Count == 0) return;
        // Remove the whole multiplayer selection together. Native removal updates
        // every pile before its visual await, so cards enter the grip on one frame
        // even when one player's hand needs a longer native removal animation.
        Task removal = CardPileCmd.RemoveFromCombat(stolenInThisSweep);
        if (removal.IsFaulted) await removal;
        _stolenCards.AddRange(stolenInThisSweep);
        foreach (CardModel card in stolenInThisSweep) AttachStolenCardVisual(card);
        SfxCmd.Play("event:/sfx/enemy/enemy_attacks/thieving_hopper/thieving_hopper_steal");
        await removal;
    }

    internal CardModel? SelectCardToSteal(Player player)
    {
        // 1. Search Draw and Discard with DeckVersion != null (identical to ThievingHopper)
        List<CardModel> list = CardPile.GetCards(player, PileType.Draw, PileType.Discard)
            .Where(c => c.DeckVersion != null)
            .ToList();

        // 2. Fallback: Hand with DeckVersion != null (if Draw/Discard empty e.g. player hand full)
        if (list.Count == 0)
        {
            list = CardPile.GetCards(player, PileType.Hand)
                .Where(c => c.DeckVersion != null)
                .ToList();
        }

        // 3. Fallback: Any combat cards in Draw, Discard, or Hand (for test environments without DeckVersion)
        if (list.Count == 0)
        {
            list = CardPile.GetCards(player, PileType.Draw, PileType.Discard, PileType.Hand)
                .ToList();
        }

        if (list.Count == 0) return null;

        IEnumerable<CardModel> candidates = list;
        foreach (Func<CardModel, bool> predicate in StealPriorities)
        {
            List<CardModel> matches = list.Where(predicate).ToList();
            if (matches.Count > 0)
            {
                candidates = matches;
                break;
            }
        }

        List<CardModel> candidateList = candidates.ToList();
        return (RunRng?.CombatCardGeneration != null)
            ? RunRng.CombatCardGeneration.NextItem(candidateList)
            : candidateList[0];
    }

    public async Task ReleaseStolenCards()
    {
        if (_stolenCards.Count == 0) return;
        List<CardModel> cardsToReturn = [.. _stolenCards];
        _stolenCards.Clear();
        ClearStolenCardVisual();

        foreach (CardModel card in cardsToReturn)
        {
            if (card.Owner?.Creature is { IsAlive: true })
            {
                card.HasBeenRemovedFromState = false;
                try
                {
                    await CardPileCmd.Add(card, PileType.Hand);
                }
                catch (Exception ex)
                {
                    Log.Warn($"[CaveGodHand] Failed to return stolen card {card.Id} to Hand ({ex.Message}), falling back to Discard pile.");
                    try
                    {
                        card.HasBeenRemovedFromState = false;
                        await CardPileCmd.Add(card, PileType.Discard);
                    }
                    catch (Exception ex2)
                    {
                        Log.Error($"[CaveGodHand] Failed to return stolen card {card.Id} to Discard pile ({ex2.Message}).");
                    }
                }
            }
            else
            {
                card.HasBeenRemovedFromState = false;
            }
        }
    }

    private void AttachStolenCardVisual(CardModel card)
    {
        if (Background != null)
        {
            Background.AttachStolenCard(IsLeft, card);
        }
        else
        {
            NCreature? creatureNode = NCombatRoom.Instance?.GetCreatureNode(Creature);
            Marker2D? marker = creatureNode?.GetSpecialNode<Marker2D>("%StolenCardPos");
            if (marker != null && GodotObject.IsInstanceValid(marker))
            {
                NCard? nCard = null;
                bool wasTestMode = TestMode.IsOn;
                if (wasTestMode) TestMode.IsOn = false;
                try
                {
                    nCard = NCard.Create(card);
                }
                catch
                {
                    // Fall back
                }
                finally
                {
                    if (wasTestMode) TestMode.IsOn = true;
                }

                if (nCard == null)
                {
                    var cardScene = GD.Load<PackedScene>("res://scenes/cards/card.tscn");
                    if (cardScene != null)
                    {
                        nCard = cardScene.Instantiate<NCard>();
                    }
                }
                if (nCard != null)
                {
                    marker.AddChildSafely(nCard);
                    try
                    {
                        nCard.Model = card;
                    }
                    catch
                    {
                    }
                    int childCount = marker.GetChildCount();
                    float xOffset = (childCount - 1) * 12f;
                    float yOffset = (childCount - 1) * 8f;
                    nCard.Position = new Vector2(xOffset, -yOffset);
                    try
                    {
                        nCard.UpdateVisuals(PileType.Deck, CardPreviewMode.Normal);
                    }
                    catch
                    {
                    }
                    marker.Visible = true;
                }
            }
        }
    }

    private void ClearStolenCardVisual()
    {
        if (Background != null)
        {
            Background.ClearStolenCard(IsLeft);
        }
        else
        {
            NCreature? creatureNode = NCombatRoom.Instance?.GetCreatureNode(Creature);
            Marker2D? marker = creatureNode?.GetSpecialNode<Marker2D>("%StolenCardPos");
            if (marker != null && GodotObject.IsInstanceValid(marker))
            {
                foreach (Node child in marker.GetChildren())
                {
                    child.QueueFreeSafely();
                }
                marker.Visible = false;
            }
        }
    }

    private async Task WeakAttack(IReadOnlyList<Creature> _)
    {
        if (!CanAct || Body?.IsWeakPhase != true) return;
        Background?.StartWeakAttackAnim(isLeftArmBroken: !IsLeft);
        if (Background is { } background)
            await background.WaitForAttackFrame("weak_attack", 1.20f, 1.20f);
        else await Cmd.Wait(1.20f);
        if (!CanAct || Body?.IsWeakPhase != true) return;
        await DamageCmd.Attack(WeakDamage).FromMonster(this)
            .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_stomp").Execute(null);
        await Cmd.Wait(1.40f);
    }

    private async Task Grab(IReadOnlyList<Creature> targets)
    {
        if (!CanAct || Body is not { IsWeakPhase: false } body) return;
        bool completed = false;
        try
        {
            Background?.StartAttackAnim(IsLeft ? "grab_player" : "grab_player_right", isFlipped: !IsLeft);
            if (Background is { } background)
                await background.WaitForAttackFrame("grab_player", 1.15f, 1.15f);
            else await Cmd.Wait(1.15f);
            await DamageCmd.Attack(GrabDamage).FromMonster(this)
                .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_kick").Execute(null);
            // Thorns/retaliation can break this arm during the grab's initial hit.
            if (!CanAct || body.IsWeakPhase) return;
            Creature[] captives = targets.Where(c => c.IsAlive && c.Player != null).ToArray();
            if (captives.Length == 0) return;
            IsGrabbing = true;
            NCombatRoom.Instance?.GetCreatureNode(Creature)?.ToggleIsInteractable(false);
            await PowerCmd.Apply<VulnerablePower>(new ThrowingPlayerChoiceContext(), captives, 1m, Creature, null);
            // Native Cmd waits determine gameplay timing equally on rendered/headless peers.
            Background?.StartGrabTracking(captives, isFlipped: !IsLeft);
            await Cmd.Wait(0.70f);
            Background?.HoldGrabAnim();
            await CreatureCmd.Add<ThingsCaveGodCaptiveClaw>(CombatState!, CaveGodBossEncounter.CaptiveHandSlot);
            if (!CanAct || !IsGrabbing || body.IsWeakPhase) return;
            // Queue one native state power on each captive. Their own turn-start
            // hook presents the choice after the opening draw has completed.
            await PowerCmd.Apply<CaveGodPendingTrialPower>(new ThrowingPlayerChoiceContext(),
                captives.Where(c => c.IsAlive), 1m, Creature, null);
            completed = true;
        }
        finally
        {
            if (!completed) await body.ReleaseCaptives(stun: false);
        }
    }

    internal async Task ChooseTrialAfterDraw(PlayerChoiceContext choiceContext, Creature target)
    {
        if (target.IsDead || target.Player == null || CombatState == null || !IsGrabbing ||
            Body is not { IsWeakPhase: false, IsPhaseTransitionPending: false, IsDefeated: false }) return;
        // Remote choices use the native context but must not acquire or restore
        // the local overlay's Z order while the local player is still choosing.
        NOverlayStack? overlay = LocalContext.IsMe(target.Player) ? NOverlayStack.Instance : null;
        int originalZ = overlay?.ZIndex ?? 0;
        bool originalRelative = overlay?.ZAsRelative ?? true;
        try
        {
            if (overlay != null) { overlay.ZAsRelative = false; overlay.ZIndex = 100; }
            List<CardModel> choices =
            [
                CombatState.CreateCard(ModelDb.Card<CaveGodBrokenBladeTrial>(), target.Player),
                CombatState.CreateCard(ModelDb.Card<CaveGodShatteredShieldTrial>(), target.Player)
            ];
            CardModel? chosen = await CardSelectCmd.FromChooseACardScreen(choiceContext, choices, target.Player, canSkip: false);
            if (IsGrabbing && Body is { IsWeakPhase: false, IsPhaseTransitionPending: false, IsDefeated: false }
                && target.IsAlive && chosen is KnowledgeDemon.IChoosable trial)
                await trial.OnChosen();
        }
        finally
        {
            if (overlay != null && GodotObject.IsInstanceValid(overlay))
            {
                overlay.ZAsRelative = originalRelative;
                overlay.ZIndex = originalZ;
            }
        }
    }

    private async Task Slam(IReadOnlyList<Creature> _)
    {
        if (!CanAct || !IsGrabbing || Body is not { IsWeakPhase: false } body) return;
        bool impacted = false;
        try
        {
            Background?.ResumeSlamAnim();
            if (Background is { } background)
                await background.WaitForAttackFrame("grab_slam", 0.75f, 0.75f);
            else await Cmd.Wait(0.75f);
            if (!CanAct || !IsGrabbing || body.IsWeakPhase) return;
            NGame.Instance?.ScreenShake(ShakeStrength.Strong, ShakeDuration.Normal);
            await DamageCmd.Attack(SlamDamage).FromMonster(this)
                .WithHitFx("vfx/vfx_attack_blunt", "event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_stomp").Execute(null);
            impacted = !body.IsWeakPhase && !body.IsDefeated;
        }
        finally { await body.ReleaseCaptives(stun: false, slam: impacted); }
    }
}
