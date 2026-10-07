using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Saves.Runs;

namespace STS2_Things.Relics;

public sealed class BottledEcho : RelicModel
{
    private SerializableCard? _storedCard;
    private int _remainingCombats = 3;
    private ICombatState? _lastEchoCombat;

    public override RelicRarity Rarity => RelicRarity.Event;
    public override bool ShowCounter => true;
    public override int DisplayAmount => RemainingCombats;
    public override bool IsUsedUp => RemainingCombats <= 0;
    protected override IEnumerable<DynamicVar> CanonicalVars => [new IntVar("Combats", 3)];

    [SavedProperty]
    public SerializableCard? StoredCard
    {
        get => _storedCard;
        private set { AssertMutable(); _storedCard = value; }
    }

    [SavedProperty]
    public int RemainingCombats
    {
        get => _remainingCombats;
        private set
        {
            AssertMutable();
            _remainingCombats = Math.Max(0, value);
            DynamicVars["Combats"].BaseValue = _remainingCombats;
            Status = IsUsedUp ? RelicStatus.Disabled : RelicStatus.Normal;
            InvokeDisplayAmountChanged();
        }
    }

    protected override IEnumerable<IHoverTip> ExtraHoverTips
    {
        get
        {
            if (StoredCard != null)
            {
                CardModel card = CardModel.FromSerializable(StoredCard);
                yield return HoverTipFactory.FromCard(card);
                foreach (IHoverTip tip in card.HoverTips) yield return tip;
            }
            yield return HoverTipFactory.FromKeyword(CardKeyword.Exhaust);
            yield return HoverTipFactory.FromKeyword(CardKeyword.Ethereal);
        }
    }

    protected override void AfterCloned()
    {
        base.AfterCloned();
        _lastEchoCombat = null;
    }

    internal void Record(CardModel card)
    {
        AssertMutable();
        if (StoredCard != null) throw new InvalidOperationException("This bottle already contains an echo.");
        StoredCard = card.ToSerializable();
        RemainingCombats = 3;
    }

    public override Task AfterCombatEnd(CombatRoom room)
    {
        _lastEchoCombat = null;
        return Task.CompletedTask;
    }

    public override async Task AfterPlayerTurnStart(PlayerChoiceContext choiceContext, Player player)
    {
        // Same opening-hand hook as native Vexing Puzzlebox. References identify
        // combats correctly even when an event starts several on the same floor.
        ICombatState? combat = player.Creature.CombatState;
        if (player != Owner || player.Creature.IsDead || player.PlayerCombatState?.TurnNumber != 1 ||
            IsUsedUp || StoredCard == null || combat == null || ReferenceEquals(combat, _lastEchoCombat)) return;
        _lastEchoCombat = combat;
        CardModel copy = CardModel.FromSerializable(StoredCard);
        combat.AddCard(copy, Owner);
        copy.SetToFreeThisCombat();
        copy.AddKeyword(CardKeyword.Exhaust);
        copy.AddKeyword(CardKeyword.Ethereal);
        await CardPileCmd.AddGeneratedCardToCombat(copy, PileType.Hand, Owner);
        if (copy.Pile?.IsCombatPile == true)
        {
            RemainingCombats--;
            Flash();
        }
    }
}
