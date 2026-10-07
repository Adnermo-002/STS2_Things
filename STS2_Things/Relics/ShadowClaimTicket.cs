using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Saves.Runs;

namespace STS2_Things.Relics;

/// <summary>Uses the same saved card representation as Pael's Tooth.</summary>
public sealed class ShadowClaimTicket : RelicModel
{
    private SerializableCard? _storedCard;
    private bool _returned;
    private bool _returning;

    public override RelicRarity Rarity => RelicRarity.Event;
    public override bool IsUsedUp => Returned;

    [SavedProperty]
    public SerializableCard? StoredCard
    {
        get => _storedCard;
        private set
        {
            AssertMutable();
            _storedCard = value;
        }
    }

    [SavedProperty]
    public int DepositActIndex { get; private set; }

    [SavedProperty]
    public bool Returned
    {
        get => _returned;
        private set
        {
            AssertMutable();
            _returned = value;
            Status = value ? RelicStatus.Disabled : RelicStatus.Normal;
        }
    }

    protected override IEnumerable<IHoverTip> ExtraHoverTips
    {
        get
        {
            if (StoredCard == null) yield break;
            CardModel card = CardModel.FromSerializable(StoredCard);
            yield return HoverTipFactory.FromCard(card);
            foreach (IHoverTip tip in card.HoverTips) yield return tip;
        }
    }

    protected override void AfterCloned()
    {
        base.AfterCloned();
        _returning = false;
    }

    internal void Store(CardModel card, int actIndex)
    {
        AssertMutable();
        if (StoredCard != null) throw new InvalidOperationException("This claim ticket already has a deposit.");
        StoredCard = card.ToSerializable();
        DepositActIndex = actIndex;
        Returned = false;
    }

    public override Task BeforeRoomEntered(AbstractRoom room)
    {
        // This hook runs before CombatRoom.Enter/SetUpCombat copies and shuffles
        // the deck. BeforeCombatStart would already be too late for that copy.
        bool isDue = Owner.RunState.CurrentActIndex > DepositActIndex ||
            (Owner.RunState.CurrentActIndex == DepositActIndex && room.RoomType == RoomType.Boss);
        return isDue ? ReturnCard(upgrade: true) : Task.CompletedTask;
    }

    public override Task AfterActEntered() => Owner.RunState.CurrentActIndex > DepositActIndex
        ? ReturnCard(upgrade: true) : Task.CompletedTask;

    // Event-rarity relics cannot be traded by the native relic trader. If another
    // mod removes the receipt, release the deposit without the maturation bonus.
    public override Task AfterRemoved() => ReturnCard(upgrade: false);

    private async Task ReturnCard(bool upgrade)
    {
        if (_returning || Returned || StoredCard == null || Owner.Creature.IsDead) return;
        _returning = true;
        try
        {
            SerializableCard saved = StoredCard;
            CardModel card = CardModel.FromSerializable(saved);
            Owner.RunState.AddCard(card, Owner);
            if (upgrade && card.IsUpgradable) CardCmd.Upgrade(card, CardPreviewStyle.None);
            CardPileAddResult result = await CardPileCmd.Add(card, PileType.Deck, skipVisuals: true);
            if (!result.success)
            {
                // A failed acquisition must not consume the saved deposit.
                card.RemoveFromState();
                return;
            }

            result.cardAdded.FloorAddedToDeck = saved.FloorAddedToDeck;
            StoredCard = result.cardAdded.ToSerializable();
            Returned = true;
            Flash();
            CardCmd.PreviewCardPileAdd(result);
        }
        finally
        {
            _returning = false;
        }
    }
}
