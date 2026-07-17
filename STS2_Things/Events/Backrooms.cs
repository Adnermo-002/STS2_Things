using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Vfx;
using STS2_Things.Enchantments;
using STS2_Things.Relics;

namespace STS2_Things.Events;

public sealed class Backrooms : EventModel
{
    private Player EventOwner => Owner
        ?? throw new InvalidOperationException("Backrooms event has not been initialized with an owner.");

    // 搜索伤害/概率统一以 DynamicVars 为唯一数据源，避免与实例字段不同步
    private int SearchDamage => (int)DynamicVars.HpLoss.BaseValue;
    private int SearchChance => (int)DynamicVars["SearchChance"].BaseValue;

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new HpLossVar(2m),       // 寻找出口初始扣血
        new IntVar("SearchChance", 10), // 初始概率10%
        new IntVar("MaxHpLoss", 5),     // 原地休息失去最大生命
        new HealVar(25),         // 原地休息恢复生命
        new CardsVar(2)          // 附魔消散选择牌数
    ];

    protected override IReadOnlyList<EventOption> GenerateInitialOptions()
    {
        return
        [
            new EventOption(this, SearchExit, "BACKROOMS.pages.INITIAL.options.SEARCH_EXIT"),
            new EventOption(this, Rest, "BACKROOMS.pages.INITIAL.options.REST")
        ];
    }

    private async Task SearchExit()
    {
        var damage = SearchDamage;
        var chance = SearchChance;

        // 扣除生命值
        await CreatureCmd.Damage(
            new ThrowingPlayerChoiceContext(),
            EventOwner.Creature,
            damage,
            ValueProp.Unblockable | ValueProp.Unpowered,
            null, null
        );

        // 判断是否找到出口
        if (Rng.NextInt(100) < chance)
        {
            // 找到出口！切换到出口页面
            ShowExitPage();
        }
        else
        {
            // 没找到出口，增加扣血和概率（唯一数据源：DynamicVars）
            DynamicVars.HpLoss.BaseValue = damage + 2;
            DynamicVars["SearchChance"].BaseValue = chance + 20;

            // 显示未找到出口的页面，可以继续寻找
            SetEventState(
                L10NLookup("BACKROOMS.pages.SEARCH_FAIL.description"),
                [
                    new EventOption(this, SearchExit, "BACKROOMS.pages.SEARCH_FAIL.options.SEARCH_EXIT"),
                    new EventOption(this, Rest, "BACKROOMS.pages.SEARCH_FAIL.options.REST")
                ]
            );
        }
    }

    private void ShowExitPage()
    {
        SetEventState(
            L10NLookup("BACKROOMS.pages.EXIT.description"),
            [
                new EventOption(this, EnchantDissolve, "BACKROOMS.pages.EXIT.options.ENCHANT_DISSOLVE"),
                new EventOption(this, TakeAlmondWater, "BACKROOMS.pages.EXIT.options.TAKE_ALMOND_WATER"),
                new EventOption(this, Leave, "BACKROOMS.pages.EXIT.options.LEAVE")
            ]
        );
    }

    private async Task EnchantDissolve()
    {
        var selected = (await CardSelectCmd.FromDeckForEnchantment(
            EventOwner, ModelDb.Enchantment<Disperse>(), 1,
            new CardSelectorPrefs(CardSelectorPrefs.EnchantSelectionPrompt,
                (int)DynamicVars["Cards"].BaseValue))).ToList();

        foreach (var card in selected)
        {
            CardCmd.Enchant<Disperse>(card, 1m);
            var vfx = NCardEnchantVfx.Create(card);
            if (vfx != null)
            {
                NRun.Instance?.GlobalUi.CardPreviewContainer.AddChildSafely(vfx);
            }
        }

        SetEventFinished(L10NLookup("BACKROOMS.pages.ENCHANT_DISSOLVE.description"));
    }

    private async Task TakeAlmondWater()
    {
        var relic = ModelDb.Relic<AlmondWater>().ToMutable();
        await RelicCmd.Obtain(relic, EventOwner);
        SetEventFinished(L10NLookup("BACKROOMS.pages.TAKE_ALMOND_WATER.description"));
    }

    private async Task Rest()
    {
        await CreatureCmd.LoseMaxHp(
            new ThrowingPlayerChoiceContext(),
            EventOwner.Creature,
            DynamicVars["MaxHpLoss"].BaseValue,
            false
        );
        await CreatureCmd.Heal(EventOwner.Creature, DynamicVars.Heal.BaseValue);
        SetEventFinished(L10NLookup("BACKROOMS.pages.REST.description"));
    }

    private Task Leave()
    {
        SetEventFinished(L10NLookup("BACKROOMS.pages.LEAVE.description"));
        return Task.CompletedTask;
    }
}
