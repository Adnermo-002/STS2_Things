using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Potions;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Powers;

/// <summary>
/// Tracks one player's loot stolen by <see cref="Monsters.QuirkyHopper"/>.
///
/// Full-combat multiplayer snapshots retain only a Power's model id and Amount.
/// The visible loot state and invisible potion recovery state therefore encode all
/// recovery data in Amount instead of relying on object references or unsaved fields.
/// The permanent deck card stays in the deck as a save-safe escrow while its combat
/// copy is absent; killing the Hopper releases that escrow, while escape removes it.
/// </summary>
public sealed class ThingsQuirkPower : PowerModel
{
    private const int PlayerRadix = 4;
    private const int DeckIndexRadix = 8193;
    private const int CardModelRadix = 8193;
    private const int PotionSlotRadix = 33;
    private const int PotionModelRadix = 8193;
    private const int PotionStateOffset = 500_000_000;

    private CardModel? _stolenDeckCard;
    private PotionModel? _stolenPotion;
    private bool _resolved;
    private int _configuredAmount;

    public override PowerType Type => PowerType.Buff;

    public override PowerStackType StackType => PowerStackType.Single;

    public override PowerInstanceType InstanceType => PowerInstanceType.Instanced;

    public override int DisplayAmount => 0;

    public bool IsPotionState => Amount >= PotionStateOffset;

    protected override bool IsVisibleInternal => !IsPotionState;

    protected override IEnumerable<IHoverTip> ExtraHoverTips
    {
        get
        {
            if (!IsMutable || IsPotionState)
            {
                return Array.Empty<IHoverTip>();
            }

            var tips = new List<IHoverTip>();
            CardModel? card = ResolveStolenDeckCard();
            if (card != null)
            {
                tips.Add(HoverTipFactory.FromCard(card));
            }

            PotionModel? potion = _stolenPotion
                ?? FindPotionStateForSamePlayer()?.ResolveStolenPotion();
            if (potion != null)
            {
                tips.Add(HoverTipFactory.FromPotion(potion));
            }

            return tips;
        }
    }

    public int ConfigureCardState(Player player, CardModel? deckCard, PotionModel? potion)
    {
        AssertMutable();
        Target = player.Creature;
        _stolenDeckCard = deckCard;
        // This immediate reference drives the first hover display. The hidden encoded
        // potion state remains the source of truth after a multiplayer rejoin.
        _stolenPotion = potion;

        int playerIndex = GetPlayerIndex(player);
        int deckIndexToken = 0;
        int cardModelToken = 0;
        if (deckCard != null)
        {
            deckIndexToken = GetDeckIndex(player, deckCard) + 1;
            cardModelToken = GetCardModelIndex(deckCard) + 1;
        }

        _configuredAmount = EncodeCardState(playerIndex, deckIndexToken, cardModelToken);
        return _configuredAmount;
    }

    public int ConfigurePotionState(Player player, PotionModel potion, int potionSlot)
    {
        AssertMutable();
        Target = player.Creature;
        _stolenPotion = potion;

        int playerIndex = GetPlayerIndex(player);
        _configuredAmount = EncodePotionState(
            playerIndex,
            potionSlot + 1,
            GetPotionModelIndex(potion) + 1);
        return _configuredAmount;
    }

    public override Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        // Power amount hooks are allowed to modify buffs. Restore the opaque state
        // payload after those hooks so the state remains valid for snapshots/rejoin.
        if (_configuredAmount > 0 && Amount != _configuredAmount)
        {
            SetAmount(_configuredAmount, silent: true);
        }

        return Task.CompletedTask;
    }

    public void RecordTheft()
    {
        if (!IsMutable || !HasTrackedItem())
        {
            return;
        }

        // Configure* always targets the affected player's creature. Use that direct
        // reference here so history recording remains valid even if another hook
        // prevents the power from being attached to the monster.
        Player? player = Target?.Player;
        var history = player?.RunState.CurrentMapPointHistoryEntry?.GetEntry(player.NetId);
        history?.MarkLootStolen();
    }

    public override Task BeforeDeath(Creature target)
    {
        // Run-hook subscriptions are global and receive canonical models too.
        // Prove mutability before touching Owner so a misplaced listener never
        // interrupts CreatureCmd's native death-animation and removal sequence.
        if (!IsMutable || _resolved)
        {
            return Task.CompletedTask;
        }

        if (Owner != target)
        {
            return Task.CompletedTask;
        }

        _resolved = true;
        bool restored = IsPotionState
            ? RestoreStolenPotion()
            : ResolveStolenDeckCard()?.Pile?.Type == PileType.Deck;
        if (restored)
        {
            MarkLootReturned();
        }

        return Task.CompletedTask;
    }

    public async Task ResolveEscape()
    {
        if (_resolved)
        {
            return;
        }

        _resolved = true;
        if (IsPotionState)
        {
            // The potion was removed from the belt during Thievery. Escaping keeps it.
            return;
        }

        // The permanent card was deliberately held in the deck as save/rejoin-safe
        // escrow. Commit the theft only when the Hopper actually escapes.
        CardModel? stolenCard = ResolveStolenDeckCard();
        if (stolenCard?.Pile?.Type == PileType.Deck)
        {
            await CardPileCmd.RemoveFromDeck(stolenCard, showPreview: false);
        }
    }

    private bool RestoreStolenPotion()
    {
        PotionState state = DecodePotionState();
        Player? player = GetPlayer(state.PlayerIndex);
        PotionModel? potion = ResolveStolenPotion();
        if (player == null || potion == null)
        {
            return false;
        }

        bool restored = false;
        if (state.PotionSlotIndex >= 0 &&
            state.PotionSlotIndex < player.PotionSlots.Count &&
            player.PotionSlots[state.PotionSlotIndex] == null)
        {
            restored = player.AddPotionInternal(potion, state.PotionSlotIndex).success;
        }
        else if (player.HasOpenPotionSlots)
        {
            restored = player.AddPotionInternal(potion).success;
        }

        if (!restored && CombatState.RunState.CurrentRoom is CombatRoom room)
        {
            room.AddExtraReward(player, new PotionReward(potion, player));
            restored = true;
        }

        return restored;
    }

    private ThingsQuirkPower? FindPotionStateForSamePlayer()
    {
        CardState cardState = DecodeCardState();
        return Owner.GetPowerInstances<ThingsQuirkPower>()
            .FirstOrDefault(power =>
                power.IsPotionState &&
                power.DecodePotionState().PlayerIndex == cardState.PlayerIndex);
    }

    private CardModel? ResolveStolenDeckCard()
    {
        if (IsPotionState || _stolenDeckCard != null)
        {
            return _stolenDeckCard;
        }

        CardState state = DecodeCardState();
        if (state.DeckIndex < 0 || state.CardModelIndex < 0)
        {
            return null;
        }

        Player? player = GetPlayer(state.PlayerIndex);
        IReadOnlyList<CardModel> models = GetCardModels();
        if (player == null || state.CardModelIndex >= models.Count)
        {
            return null;
        }

        ModelId expectedId = models[state.CardModelIndex].Id;
        IReadOnlyList<CardModel> deckCards = player.Deck.Cards;
        if (state.DeckIndex < deckCards.Count && deckCards[state.DeckIndex].Id == expectedId)
        {
            return _stolenDeckCard = deckCards[state.DeckIndex];
        }

        return _stolenDeckCard = deckCards
            .Select((card, index) => (card, index))
            .Where(entry => entry.card.Id == expectedId)
            .OrderBy(entry => Math.Abs(entry.index - state.DeckIndex))
            .Select(entry => entry.card)
            .FirstOrDefault();
    }

    private PotionModel? ResolveStolenPotion()
    {
        if (!IsPotionState || _stolenPotion != null)
        {
            return _stolenPotion;
        }

        PotionState state = DecodePotionState();
        IReadOnlyList<PotionModel> models = GetPotionModels();
        if (state.PotionModelIndex < 0 || state.PotionModelIndex >= models.Count)
        {
            return null;
        }

        return _stolenPotion = models[state.PotionModelIndex].ToMutable();
    }

    private Player? GetPlayer(int playerIndex)
    {
        IReadOnlyList<Player> players = CombatState.Players;
        return playerIndex >= 0 && playerIndex < players.Count ? players[playerIndex] : null;
    }

    private Player? ResolveStolenPlayer()
    {
        int playerIndex = IsPotionState
            ? DecodePotionState().PlayerIndex
            : DecodeCardState().PlayerIndex;
        return GetPlayer(playerIndex);
    }

    private bool HasTrackedItem()
    {
        return IsPotionState
            ? DecodePotionState().PotionModelIndex >= 0
            : DecodeCardState().CardModelIndex >= 0;
    }

    private void MarkLootReturned()
    {
        Player? player = ResolveStolenPlayer();
        var history = player?.RunState.CurrentMapPointHistoryEntry?.GetEntry(player.NetId);
        if (history is { StolenLoot: > 0 })
        {
            // One state represents exactly one stolen item. Never erase theft caused
            // by another monster or another Quirky Hopper in the same combat.
            history.MarkLootReturned();
        }
    }

    private static int GetPlayerIndex(Player player)
    {
        IReadOnlyList<Player> players = player.Creature.CombatState?.Players
            ?? throw new InvalidOperationException("The stolen player's combat state is unavailable.");
        for (int index = 0; index < players.Count; index++)
        {
            if (ReferenceEquals(players[index], player))
            {
                if (index >= PlayerRadix)
                {
                    throw new InvalidOperationException("Quirk Power supports at most four players.");
                }

                return index;
            }
        }

        throw new InvalidOperationException("The stolen player is not part of the current combat.");
    }

    private static int GetDeckIndex(Player player, CardModel deckCard)
    {
        for (int index = 0; index < player.Deck.Cards.Count; index++)
        {
            if (ReferenceEquals(player.Deck.Cards[index], deckCard))
            {
                if (index >= DeckIndexRadix - 1)
                {
                    throw new InvalidOperationException("Deck is too large for Quirk Power's synchronized state.");
                }

                return index;
            }
        }

        throw new InvalidOperationException("The stolen card is not in the player's deck.");
    }

    private static int GetCardModelIndex(CardModel card)
    {
        int index = GetCardModels().ToList().FindIndex(model => model.Id == card.Id);
        if (index is < 0 or >= CardModelRadix - 1)
        {
            throw new InvalidOperationException("Card model is unavailable for Quirk Power's synchronized state.");
        }

        return index;
    }

    private static int GetPotionModelIndex(PotionModel potion)
    {
        int index = GetPotionModels().ToList().FindIndex(model => model.Id == potion.Id);
        if (index is < 0 or >= PotionModelRadix - 1)
        {
            throw new InvalidOperationException("Potion model is unavailable for Quirk Power's synchronized state.");
        }

        return index;
    }

    private static IReadOnlyList<CardModel> GetCardModels()
    {
        return ModelDb.AllCards.OrderBy(model => model.Id.Entry, StringComparer.Ordinal).ToList();
    }

    private static IReadOnlyList<PotionModel> GetPotionModels()
    {
        return ModelDb.AllPotions.OrderBy(model => model.Id.Entry, StringComparer.Ordinal).ToList();
    }

    private static int EncodeCardState(int playerIndex, int deckIndexToken, int cardModelToken)
    {
        ValidateToken(playerIndex, PlayerRadix, nameof(playerIndex));
        ValidateToken(deckIndexToken, DeckIndexRadix, nameof(deckIndexToken));
        ValidateToken(cardModelToken, CardModelRadix, nameof(cardModelToken));
        return checked(((playerIndex * DeckIndexRadix + deckIndexToken) * CardModelRadix) + cardModelToken + 1);
    }

    private static int EncodePotionState(int playerIndex, int potionSlotToken, int potionModelToken)
    {
        ValidateToken(playerIndex, PlayerRadix, nameof(playerIndex));
        ValidateToken(potionSlotToken, PotionSlotRadix, nameof(potionSlotToken));
        ValidateToken(potionModelToken, PotionModelRadix, nameof(potionModelToken));
        return checked(PotionStateOffset + ((playerIndex * PotionSlotRadix + potionSlotToken) * PotionModelRadix) + potionModelToken + 1);
    }

    private CardState DecodeCardState()
    {
        if (IsPotionState || Amount <= 0)
        {
            return new CardState(-1, -1, -1);
        }

        int payload = Amount - 1;
        int cardModelToken = payload % CardModelRadix;
        payload /= CardModelRadix;
        int deckIndexToken = payload % DeckIndexRadix;
        int playerIndex = payload / DeckIndexRadix;
        return playerIndex is < 0 or >= PlayerRadix
            ? new CardState(-1, -1, -1)
            : new CardState(playerIndex, deckIndexToken - 1, cardModelToken - 1);
    }

    private PotionState DecodePotionState()
    {
        if (!IsPotionState)
        {
            return new PotionState(-1, -1, -1);
        }

        int payload = Amount - PotionStateOffset - 1;
        int potionModelToken = payload % PotionModelRadix;
        payload /= PotionModelRadix;
        int potionSlotToken = payload % PotionSlotRadix;
        int playerIndex = payload / PotionSlotRadix;
        return playerIndex is < 0 or >= PlayerRadix
            ? new PotionState(-1, -1, -1)
            : new PotionState(playerIndex, potionSlotToken - 1, potionModelToken - 1);
    }

    private static void ValidateToken(int token, int radix, string name)
    {
        if (token < 0 || token >= radix)
        {
            throw new ArgumentOutOfRangeException(name);
        }
    }

    private readonly record struct CardState(int PlayerIndex, int DeckIndex, int CardModelIndex);

    private readonly record struct PotionState(int PlayerIndex, int PotionSlotIndex, int PotionModelIndex);
}
