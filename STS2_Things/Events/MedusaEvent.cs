using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Gold;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Enchantments;
using MegaCrit.Sts2.Core.Models.Potions;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Vfx;
using STS2_Things.Relics;

namespace STS2_Things.Events;

public sealed class Medusa : EventModel
{
    private Player EventOwner => Owner
        ?? throw new InvalidOperationException("Medusa event has not been initialized with an owner.");

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new GoldVar(75) // 献上钱财所需金币
    ];

    protected override IReadOnlyList<EventOption> GenerateInitialOptions()
    {
        var options = new List<EventOption>();

        // 选项1：物归原主 — 需要拥有石化蟾蜍
        var toad = EventOwner.GetRelic<PetrifiedToad>();
        if (toad != null)
        {
            var tips = HoverTipFactory.FromRelic<PetrifiedToad>()
                .Concat(HoverTipFactory.FromRelic<MedusaHair>());
            options.Add(new EventOption(this, ReturnToOwner,
                L10NLookup("MEDUSA.pages.INITIAL.options.RETURN_TO_OWNER.title"),
                L10NLookup("MEDUSA.pages.INITIAL.options.RETURN_TO_OWNER.description"),
                "MEDUSA.pages.INITIAL.options.RETURN_TO_OWNER",
                tips));
        }
        else
        {
            var lockedTips = HoverTipFactory.FromRelic<PetrifiedToad>();
            options.Add(new EventOption(this, null,
                L10NLookup("MEDUSA.pages.INITIAL.options.RETURN_TO_OWNER_LOCKED.title"),
                L10NLookup("MEDUSA.pages.INITIAL.options.RETURN_TO_OWNER_LOCKED.description"),
                "MEDUSA.pages.INITIAL.options.RETURN_TO_OWNER_LOCKED",
                lockedTips));
        }

        // 选项2：献上钱财 — 需要75金币
        if (EventOwner.Gold >= (int)DynamicVars["Gold"].BaseValue)
        {
            options.Add(new EventOption(this, OfferGold,
                L10NLookup("MEDUSA.pages.INITIAL.options.OFFER_GOLD.title"),
                L10NLookup("MEDUSA.pages.INITIAL.options.OFFER_GOLD.description"),
                "MEDUSA.pages.INITIAL.options.OFFER_GOLD",
                HoverTipFactory.FromEnchantment<Steady>()));
        }
        else
        {
            options.Add(new EventOption(this, null,
                L10NLookup("MEDUSA.pages.INITIAL.options.OFFER_GOLD_LOCKED.title"),
                L10NLookup("MEDUSA.pages.INITIAL.options.OFFER_GOLD_LOCKED.description"),
                "MEDUSA.pages.INITIAL.options.OFFER_GOLD_LOCKED",
                Array.Empty<IHoverTip>()));
        }

        // 选项3：礼貌问候
        options.Add(new EventOption(this, Greet,
            L10NLookup("MEDUSA.pages.INITIAL.options.GREET.title"),
            L10NLookup("MEDUSA.pages.INITIAL.options.GREET.description"),
            "MEDUSA.pages.INITIAL.options.GREET",
            Array.Empty<IHoverTip>()));

        return options;
    }

    /// <summary>
    /// 物归原主：失去石化蟾蜍，获得美杜莎之发
    /// </summary>
    private async Task ReturnToOwner()
    {
        var owner = EventOwner;
        var toad = owner.GetRelic<PetrifiedToad>();
        if (toad != null)
        {
            await RelicCmd.Remove(toad);
        }
        var hair = ModelDb.Relic<MedusaHair>().ToMutable();
        await RelicCmd.Obtain(hair, owner);
        SetEventFinished(L10NLookup("MEDUSA.pages.RETURN_TO_OWNER.description"));
    }

    /// <summary>
    /// 献上钱财：失去75金币，选择一张卡附魔保留
    /// </summary>
    private async Task OfferGold()
    {
        var owner = EventOwner;
        await PlayerCmd.LoseGold(DynamicVars["Gold"].BaseValue, owner, GoldLossType.Spent);
        var prefs = new CardSelectorPrefs(CardSelectorPrefs.EnchantSelectionPrompt, 1);
        var enchantment = ModelDb.Enchantment<Steady>();
        var selected = await CardSelectCmd.FromDeckForEnchantment(owner, enchantment, 1, prefs);
        foreach (var card in selected)
        {
            CardCmd.Enchant<Steady>(card, 1m);
            var vfx = NCardEnchantVfx.Create(card);
            if (vfx != null)
            {
                NRun.Instance?.GlobalUi.CardPreviewContainer.AddChildSafely(vfx);
            }
        }
        SetEventFinished(L10NLookup("MEDUSA.pages.OFFER_GOLD.description"));
    }

    /// <summary>
    /// 礼貌问候：获得1瓶药水形状的石头
    /// </summary>
    private async Task Greet()
    {
        await PotionCmd.TryToProcure<PotionShapedRock>(EventOwner);
        SetEventFinished(L10NLookup("MEDUSA.pages.GREET.description"));
    }
}
