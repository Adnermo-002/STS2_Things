using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Extensions;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Rewards;

namespace STS2_Things.Events;

public sealed class RobberyFakeMerchant : EventModel
{
    private Player EventOwner => Owner
        ?? throw new InvalidOperationException("Robbery Fake Merchant event has not been initialized with an owner.");

    // 改为懒加载，避免类首次访问时 ModelDb 尚未初始化
    private static RelicModel[]? _fakeRelicPool;
    private static RelicModel[] FakeRelicPool => _fakeRelicPool ??= new RelicModel[] //所有假遗物
    {
        ModelDb.Relic<FakeAnchor>(),
        ModelDb.Relic<FakeBloodVial>(),
        ModelDb.Relic<FakeHappyFlower>(),
        ModelDb.Relic<FakeLeesWaffle>(),
        ModelDb.Relic<FakeMango>(),
        ModelDb.Relic<FakeOrichalcum>(),
        ModelDb.Relic<FakeSneckoEye>(),
        ModelDb.Relic<FakeStrikeDummy>(),
        ModelDb.Relic<FakeVenerableTeaSet>()
    };

    private static RelicModel[]? _trueRelicPool;
    private static RelicModel[] TrueRelicPool => _trueRelicPool ??= new RelicModel[] //所有真遗物
    {
        ModelDb.Relic<Anchor>(),
        ModelDb.Relic<BloodVial>(),
        ModelDb.Relic<HappyFlower>(),
        ModelDb.Relic<LeesWaffle>(),
        ModelDb.Relic<Mango>(),
        ModelDb.Relic<Orichalcum>(),
        ModelDb.Relic<SneckoEye>(),
        ModelDb.Relic<StrikeDummy>(),
        ModelDb.Relic<VenerableTeaSet>()
    };

    public override EventLayoutType LayoutType => EventLayoutType.Combat;

    public override EncounterModel CanonicalEncounter => ModelDb.Encounter<FakeMerchantEventEncounter>();

    public override bool IsShared => true;

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new IntVar("GoldsCount", 67),
        new IntVar("FakeRelicsCount", 2),
        new IntVar("TrueRelicsCount", 2)
    ];

    protected override IReadOnlyList<EventOption> GenerateInitialOptions()
    {
        return new EventOption[3]
        {
            new(this, TakeRelics, "ROBBERY_FAKE_MERCHANT.pages.INITIAL.options.TAKERELICS"),
            new(this, TakeGolds, "ROBBERY_FAKE_MERCHANT.pages.INITIAL.options.TAKEGOLDS"),
            new(this, BeginFight, "ROBBERY_FAKE_MERCHANT.pages.INITIAL.options.BEGINFIGHT")
        };
    }

    private async Task TakeGolds()
    {
        await PlayerCmd.GainGold((int)DynamicVars["GoldsCount"].BaseValue, EventOwner);
        SetEventFinished(L10NLookup("ROBBERY_FAKE_MERCHANT.pages.INITIAL.options.TAKEGOLDS.description"));
    }

    private async Task TakeRelics()
    {
        var relics = FakeRelicPool
            .ToList()
            .UnstableShuffle(Rng)
            .Take((int)DynamicVars["FakeRelicsCount"].BaseValue)
            .ToList();

        foreach (var relic in relics)
            await RelicCmd.Obtain(relic.ToMutable(), EventOwner);

        SetEventFinished(L10NLookup("ROBBERY_FAKE_MERCHANT.pages.TAKERELICS.description"));
    }

    private Task BeginFight()
    {
        SetEventState(L10NLookup("ROBBERY_FAKE_MERCHANT.pages.BEGINFIGHT.description"),
            [new EventOption(this, Fight, "THE_LANTERN_KEY.pages.KEEP_THE_KEY.options.FIGHT")]); //别动这个 用自带的文本会卡住
        return Task.CompletedTask;
    }

    private async Task Fight()
    {
        // 假商人血量改为原版一半
#if STS2_V107_1
        var combatState = _combatStateForCombatLayout
            ?? throw new InvalidOperationException("Robbery Fake Merchant combat layout state is not initialized.");
#else
        var combatSynchronizer = _combatSynchronizer
            ?? throw new InvalidOperationException("Robbery Fake Merchant combat synchronizer is not initialized.");
        var combatState = combatSynchronizer.CombatStateForLayout
            ?? throw new InvalidOperationException("Robbery Fake Merchant combat layout state is not initialized.");
#endif
        var merchant = combatState.Enemies.FirstOrDefault();
        if (merchant != null)
        {
            int halfHp = merchant.MaxHp / 2;
            await CreatureCmd.SetMaxAndCurrentHp(merchant, halfHp);
        }

        var extraRewards = TrueRelicPool
            .ToList()
            .UnstableShuffle(Rng)
            .Take((int)DynamicVars["TrueRelicsCount"].BaseValue)
            .Select(relic => (Reward)new RelicReward(relic.ToMutable(), EventOwner))
            .ToList();
        EnterCombatWithoutExitingEvent<FakeMerchantEventEncounter>(extraRewards, false);
    }
}
