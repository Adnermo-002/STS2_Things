using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;

namespace STS2_Things.Cards;

/// <summary>
/// 整理 — Silent Uncommon Skill
/// 1费，抽1张牌，选择牌库中1张牌丢弃（可触发奇巧），消耗
/// 强化：去掉消耗
/// </summary>
public sealed class ThingsPackUp : CardModel
{
    public override IEnumerable<CardKeyword> CanonicalKeywords => IsUpgraded
        ? System.Array.Empty<CardKeyword>()
        : new[] { CardKeyword.Exhaust };

    public ThingsPackUp()
        : base(1, CardType.Skill, CardRarity.Uncommon, TargetType.Self)
    {
    }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        // 抽1张牌
        await CardPileCmd.Draw(choiceContext, 1m, Owner);

        // 从抽牌堆选择1张牌丢弃
        var drawPile = PileType.Draw.GetPile(Owner);
        if (drawPile.Cards.Count > 0)
        {
            var selected = (await CardSelectCmd.FromCombatPile(
                prefs: new CardSelectorPrefs(SelectionScreenPrompt, 1),
                context: choiceContext,
                pile: drawPile,
                player: Owner)).FirstOrDefault();

            if (selected != null)
            {
                await CardCmd.Discard(choiceContext, selected);
            }
        }
    }

    protected override void OnUpgrade()
    {
        RemoveKeyword(CardKeyword.Exhaust);
    }
}
