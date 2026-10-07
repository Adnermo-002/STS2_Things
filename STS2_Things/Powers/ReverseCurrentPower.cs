using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using STS2_Things.Afflictions;
using STS2_Things.Monsters;

namespace STS2_Things.Powers;

/// <summary>Native history supplies the real card; native afflictions carry the visible offer.</summary>
public sealed class ReverseCurrentPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.None;
    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        [new HoverTip(new LocString("powers", "REVERSE_CURRENT_POWER.refluxTitle"),
            new LocString("powers", "REVERSE_CURRENT_POWER.refluxDescription")),
         HoverTipFactory.FromPower<StrengthPower>()];
    private bool IsReturnSource => Owner.IsAlive && CombatState.Enemies
        .FirstOrDefault(c=>c.IsAlive&&c.GetPower<ReverseCurrentPower>()!=null)==Owner;

    public override async Task AfterPlayerTurnStartLate(PlayerChoiceContext choiceContext,Player player)
    {
        if(!IsReturnSource||!player.Creature.IsAlive||player.PlayerCombatState==null)return;
        ClearFor(player);
        // Same history predicate as vanilla HistoryCourse. Drawing/autoplay at
        // the start of this turn cannot overwrite the previous turn's history.
        var card=CombatManager.Instance.History.CardPlaysFinished.LastOrDefault(e=>
            e.Actor==player.Creature&&e.CardPlay.Card.Owner==player&&e.HappenedLastPlayerTurn(player)&&!e.CardPlay.Card.IsDupe&&
            IsAvailable(e.CardPlay.Card))?.CardPlay.Card;
        if(card==null)return;
        if(card.Pile?.Type!=PileType.Hand&&player.PlayerCombatState.Hand.Cards.Count>=CardPile.MaxCardsInHand)return;
        Flash();
        if(Owner.Monster is ReverseSalamander monster)await monster.RecallPose();
        if(!Owner.IsAlive||!IsAvailable(card))return;
        if(card.Pile?.Type!=PileType.Hand)await CardPileCmd.Add(card,PileType.Hand);
        if(card.Pile?.Type!=PileType.Hand||!Owner.IsAlive)return;
        await CardCmd.AfflictAndPreview<UpstreamRecall>([card],Amount,CardPreviewStyle.None);
        if(card.Affliction is not UpstreamRecall)return;
        // Native "this turn" convention: expires on use or at turn end.
        card.EnergyCost.AddThisTurnOrUntilPlayed(-1,reduceOnly:true);
        card.InvokeEnergyCostChanged();
    }

    private static bool IsAvailable(CardModel card) =>
        card.Pile?.Type is PileType.Hand or PileType.Draw or PileType.Discard &&
        ModelDb.Affliction<UpstreamRecall>().CanAfflict(card);

    public override async Task AfterCardPlayed(PlayerChoiceContext choiceContext,CardPlay cardPlay)
    {
        if(!IsReturnSource||cardPlay.Card.IsDupe||cardPlay.Card.Affliction is not UpstreamRecall)return;
        // Clearing all copies of the offer also limits the growth to once per
        // owning player per turn, without unsynchronized card-reference caches.
        ClearFor(cardPlay.Card.Owner);
        foreach(var enemy in CombatState.Enemies.Where(c=>c.IsAlive&&c.GetPower<ReverseCurrentPower>()!=null).ToArray())
        {
            var current=enemy.GetPower<ReverseCurrentPower>()!;current.Flash();
            await PowerCmd.Apply<StrengthPower>(choiceContext,enemy,current.Amount,enemy,null);
            if(enemy.IsAlive)await CreatureCmd.TriggerAnim(enemy,"PowerUp",.18f);
        }
    }

    public override Task AfterCardChangedPiles(CardModel card,PileType oldPileType,AbstractModel? clonedBy)
    {
        if(IsReturnSource&&card.Pile?.Type==PileType.Exhaust&&card.Affliction is UpstreamRecall)CardCmd.ClearAffliction(card);
        return Task.CompletedTask;
    }

    public override Task BeforeSideTurnEnd(PlayerChoiceContext choiceContext,CombatSide side,IEnumerable<Creature> participants)
    {
        if(IsReturnSource&&side==CombatSide.Player)
            foreach(var creature in participants)if(creature.Player is { } player)ClearFor(player);
        return Task.CompletedTask;
    }

    public override Task AfterRemoved(Creature oldOwner)
    {
        var state=oldOwner.CombatState;
        if(state!=null&&!state.Enemies.Any(c=>c.IsAlive&&c.GetPower<ReverseCurrentPower>()!=null))
            foreach(var player in state.Players)ClearFor(player);
        return Task.CompletedTask;
    }

    private static void ClearFor(Player player)
    {
        foreach(var card in player.PlayerCombatState?.AllCards.ToArray()??[])
            if(card.Affliction is UpstreamRecall)CardCmd.ClearAffliction(card);
    }
}
