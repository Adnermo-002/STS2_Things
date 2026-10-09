using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Afflictions;
using STS2_Things.Monsters;

namespace STS2_Things.Powers;

/// <summary>One ordered pair per player, owned by native power/card lifecycles.</summary>
public sealed class SilkThreadPower : PowerModel
{
    private sealed class Data
    {
        public bool Pending = true;
        public bool ConsumedThisTurn;
        public CardModel? First;
        public CardModel? Second;
    }

    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;
    public const int MaxLayers = 2;
    public override Task AfterApplied(Creature? applier, CardModel? cardSource)
    {
        ClampLayers();
        return Task.CompletedTask;
    }
    public override Task AfterPowerAmountChanged(PlayerChoiceContext choiceContext, PowerModel power,
        decimal amount, Creature? applier, CardModel? cardSource)
    {
        if (ReferenceEquals(power, this)) ClampLayers();
        return Task.CompletedTask;
    }
    private void ClampLayers() { if (Amount > MaxLayers) SetAmount(MaxLayers); }
    protected override object InitInternalData() => new Data();
    protected override string SmartDescriptionLocKey => IsMutable && !IsPending
        ? HasLivePair ? "SILK_THREAD_POWER.activeDescription" : "SILK_THREAD_POWER.unboundDescription"
        : base.SmartDescriptionLocKey;
    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        HoverTipFactory.FromAffliction<SilkLead>().Concat(HoverTipFactory.FromAffliction<SilkBound>());

    public CardModel? FirstCard => GetInternalData<Data>().First;
    public CardModel? SecondCard => GetInternalData<Data>().Second;
    public bool IsPending => GetInternalData<Data>().Pending;
    public bool HasLivePair => FirstCard is { Affliction: SilkLead } first &&
        SecondCard is { Affliction: SilkBound } second && first.Owner.Creature == Owner &&
        second.Owner.Creature == Owner && first.Pile?.Type is PileType.Hand or PileType.Play &&
        second.Pile?.Type == PileType.Hand;

    public override async Task AfterPlayerTurnStartLate(PlayerChoiceContext choiceContext, Player player)
    {
        if (player.Creature != Owner || !IsPending) return;
        GetInternalData<Data>().Pending = false;
        GetInternalData<Data>().ConsumedThisTurn = false;
        // Run after the native opening draw and other start-of-turn effects. Never
        // overwrite another affliction, or require playing a Status/Curse/X card.
        var candidates = player.PlayerCombatState!.Hand.Cards
            .Where(card => ModelDb.Affliction<SilkLead>().CanAfflict(card) && IsEligible(card)).ToList();
        var starters = candidates.Where(card => card.CanPlay()).ToList();
        if (candidates.Count < 2 || starters.Count == 0)
        {
            await FinishCurrentPair(choiceContext);
            return;
        }
        var rng = player.RunState.Rng.CombatCardSelection;
        CardModel first = starters[rng.NextInt(starters.Count)];
        candidates.Remove(first);
        CardModel second = candidates[rng.NextInt(candidates.Count)];
        var data = GetInternalData<Data>();
        data.First = first;
        data.Second = second;
        await CardCmd.AfflictAndPreview<SilkLead>([first], 1, CardPreviewStyle.None);
        await CardCmd.AfflictAndPreview<SilkBound>([second], 1, CardPreviewStyle.None);
        if (!HasLivePair) await FinishCurrentPair(choiceContext);
        else Flash();
    }

    public override bool ShouldPlay(CardModel card, AutoPlayType autoPlayType) =>
        !ReferenceEquals(card, SecondCard) || !HasLivePair;

    private static bool IsEligible(CardModel card)
    {
        card.CanPlay(out var reason, out _);
        return (reason & (UnplayableReason.BlockedByCardLogic | UnplayableReason.HasUnplayableKeyword |
                          UnplayableReason.NoLivingAllies | UnplayableReason.BlockedByHook)) == 0;
    }

    public override async Task BeforeCardPlayed(CardPlay cardPlay)
    {
        // Manual and automatic play both pass through this native hook, after
        // moving the actual card to Play. Duplicate plays cannot unlock twice.
        if (ReferenceEquals(cardPlay.Card, FirstCard) && !cardPlay.Card.IsDupe)
        {
            Flash();
            await FinishCurrentPair(new ThrowingPlayerChoiceContext());
        }
        else if (!IsPending && !HasLivePair) await FinishCurrentPair(new ThrowingPlayerChoiceContext());
    }

    public override async Task AfterCardChangedPiles(CardModel card, PileType oldPileType, AbstractModel? clonedBy)
    {
        if (IsPending) return;
        if (ReferenceEquals(card, FirstCard) && card.Pile?.Type == PileType.Play) return;
        if (ReferenceEquals(card, FirstCard) || ReferenceEquals(card, SecondCard))
            await FinishCurrentPair(new ThrowingPlayerChoiceContext());
        else ClearOrphanMark(card);
    }

    public override Task AfterCardEnteredCombat(CardModel card)
    {
        ClearOrphanMark(card);
        return Task.CompletedTask;
    }

    private void ClearOrphanMark(CardModel card)
    {
        if (card.Owner.Creature == Owner && !ReferenceEquals(card, FirstCard) &&
            !ReferenceEquals(card, SecondCard) && card.Affliction is SilkLead or SilkBound)
            CardCmd.ClearAffliction(card);
    }

    public override async Task BeforeSideTurnEnd(PlayerChoiceContext choiceContext, CombatSide side,
        IEnumerable<Creature> participants)
    {
        if (IsPending || side != Owner.Side || !participants.Contains(Owner)) return;
        await FinishCurrentPair(choiceContext);
        if (Amount > 0)
        {
            var data = GetInternalData<Data>();
            data.Pending = true;
            data.ConsumedThisTurn = false;
            InvokeDisplayAmountChanged();
        }
    }

    private async Task FinishCurrentPair(PlayerChoiceContext context)
    {
        var data = GetInternalData<Data>();
        if (data.ConsumedThisTurn) return;
        data.ConsumedThisTurn = true;
        ClearMarks();
        await PowerCmd.ModifyAmount(context, this, -1, null, null);
    }

    public override async Task AfterDeath(PlayerChoiceContext choiceContext, Creature creature,
        bool wasRemovalPrevented, float deathAnimLength)
    {
        if (!wasRemovalPrevented && (creature == Owner || creature.Monster is SilkMoth &&
            !CombatState.Enemies.Any(enemy => enemy.IsAlive && enemy.Monster is SilkMoth)))
            await PowerCmd.Remove(this);
    }

    public override Task AfterRemoved(Creature oldOwner)
    {
        ClearMarks();
        return Task.CompletedTask;
    }

    public override Task AfterCombatEnd(CombatRoom room)
    {
        ClearMarks();
        return Task.CompletedTask;
    }

    private void ClearMarks()
    {
        var data = GetInternalData<Data>();
        var first = data.First;
        var second = data.Second;
        if (second?.Pile?.Type == PileType.Hand) Visuals.NSilkCardOverlay.Release(second);
        data.First = data.Second = null;
        data.Pending = false;
        if (first?.Affliction is SilkLead) CardCmd.ClearAffliction(first);
        if (second?.Affliction is SilkBound) CardCmd.ClearAffliction(second);
        foreach (var card in Owner.Player?.PlayerCombatState?.AllCards.ToArray() ?? [])
            if (card.Affliction is SilkLead or SilkBound) CardCmd.ClearAffliction(card);
    }
}
