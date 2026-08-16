using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.Audio.Debug;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Random;
using STS2_Things.Powers;

namespace STS2_Things.Cards;

/// <summary>
/// 当玩家拥有 DrawFromDiscardPower 时，优先从弃牌堆抽牌，弃牌堆为空时回退到抽牌堆
/// </summary>
[HarmonyPatch]
public static class DrawFromDiscardPatch
{
    [HarmonyTargetMethod]
    public static MethodBase Target(HarmonyPatchType _, Harmony __)
    {
        return typeof(CardPileCmd).GetMethod("Draw",
            BindingFlags.Public | BindingFlags.Static,
            null,
            new[]
            {
                typeof(PlayerChoiceContext),
                typeof(decimal),
                typeof(Player),
                typeof(bool)
            },
            null) ?? throw new MissingMethodException(typeof(CardPileCmd).FullName, "Draw");
    }

    /// <summary>
    /// 当玩家拥有 DrawFromDiscardPower 时，优先从弃牌堆抽牌；
    /// 弃牌堆为空时回退到原始抽牌逻辑
    /// </summary>
    private static bool Prefix(PlayerChoiceContext choiceContext, decimal count, Player player,
        bool fromHandDraw, ref Task<IEnumerable<CardModel>> __result)
    {
        if (player.Creature.GetPower<ThingsRecallPower>() == null)
            return true; // 正常抽牌

        var discardPile = PileType.Discard.GetPile(player);
        if (discardPile.Cards.Count == 0)
            return true; // 弃牌堆为空，回退到正常抽牌

        __result = DrawFromDiscardThenFallback(choiceContext, count, player, fromHandDraw);
        return false;
    }

    private static async Task<IEnumerable<CardModel>> DrawFromDiscardThenFallback(
        PlayerChoiceContext choiceContext, decimal count, Player player, bool fromHandDraw)
    {
        if (CombatManager.Instance.IsOverOrEnding)
            return Array.Empty<CardModel>();

        var combatState = player.Creature.CombatState;
        if (combatState == null)
            return Array.Empty<CardModel>();
        if (!Hook.ShouldDraw(combatState, player, fromHandDraw, out var modifier))
        {
            if (modifier != null)
                await Hook.AfterPreventingDraw(combatState, modifier);
            return Array.Empty<CardModel>();
        }

        CardPile hand = PileType.Hand.GetPile(player);
        CardPile discardPile = PileType.Discard.GetPile(player);
        CardPile drawPile = PileType.Draw.GetPile(player);
        int drawsRequested = count > 0m ? (int)Math.Ceiling(count) : 0;
        var result = new List<CardModel>();

        for (int i = 0; i < drawsRequested; i++)
        {
            if (CombatManager.Instance.IsOverOrEnding ||
                hand.Cards.Count >= CardPile.MaxCardsInHand)
                break;

            CardModel? card;
            if (discardPile.Cards.Count > 0)
            {
                // 优先从弃牌堆随机抽一张
                card = player.RunState.Rng.CombatCardSelection.NextItem(discardPile.Cards);
            }
            else
            {
                // 本次调用已经通过 ShouldDraw；直接继续从抽牌堆顶部抽取，
                // 避免递归调用原方法导致 ShouldDraw/AfterPreventingDraw 重复触发。
                card = drawPile.Cards.FirstOrDefault();
            }

            if (card == null)
                break;

            result.Add(card);
            await CardPileCmd.Add(card, hand);
            CombatManager.Instance.History.CardDrawn(combatState, card, fromHandDraw);
            await Hook.AfterCardDrawn(combatState, choiceContext, card, fromHandDraw);
            card.InvokeDrawn();
            NDebugAudioManager.Instance?.Play("card_deal.mp3", 0.25f, PitchVariance.Small);
        }

        return result;
    }
}
