using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Combat.History.Entries;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using STS2_Things.Cards;

namespace STS2_Things.Powers;

public sealed class ThingsReusePower : PowerModel
{
    public override PowerType Type => PowerType.Buff;

    public override PowerStackType StackType => PowerStackType.Counter;

    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        HoverTipFactory.FromCardWithCardHoverTips<Fuel>()
            .Concat(HoverTipFactory.FromCardWithCardHoverTips<Soot>());

    public override async Task AfterCardDrawn(
        PlayerChoiceContext choiceContext,
        CardModel card,
        bool fromHandDraw)
    {
        // 触发条件：
        // 1. 抽到的牌属于这个能力的拥有者（不是队友的牌）
        // 2. 抽到的是状态牌（Status）
        if (card.Owner.Creature == Owner && card.Type == CardType.Status)
        {
            var player = Owner.Player;
            if (player == null) return;
            // 检查：本回合这张 Power 触发了多少次
            var num = CombatManager.Instance.History.Entries
                .OfType<CardDrawnEntry>()
                .Count(e =>
                    e.HappenedThisTurn(CombatState) && // 本回合
                    e.Actor == Owner && // 玩家抽的
                    e.Card.Type == CardType.Status); // 状态牌
            // 只在第一次触发时抽牌（防止重复触发）
            if (num <= Amount)
            {
                Flash();
                await CardPileCmd.RemoveFromCombat(card);
                var fuelCard = CombatState.CreateCard<Fuel>(player);
                var sootCard = CombatState.CreateCard<Soot>(player);
                await CardPileCmd.AddGeneratedCardToCombat(fuelCard, PileType.Hand, player);
                await CardPileCmd.AddGeneratedCardToCombat(sootCard, PileType.Discard, player);
            }
        }
    }
}
