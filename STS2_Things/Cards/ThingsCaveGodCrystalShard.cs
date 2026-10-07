using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.CardPools;
using MegaCrit.Sts2.Core.ValueProps;

namespace STS2_Things.Cards;

/// <summary>
/// 【碎晶】(Crystal Shard)：活体巨岩「晶簇崩发」塞入弃牌堆的状态牌。
/// Debris-style removal cost (1 energy, Exhaust) with a Burn-style end-of-turn bite,
/// so the player chooses between spending energy and eating 2 damage.
/// </summary>
public sealed class ThingsCaveGodCrystalShard : CardModel
{
    public override int MaxUpgradeLevel => 0;
    public override CardPoolModel Pool => ModelDb.CardPool<TokenCardPool>();
    public override string PortraitPath => "res://images/packed/card_portraits/token/things_cave_god_crystal_shard.png";
#if !STS2_V107_1
    protected override string PortraitPngPath => PortraitPath;
#endif

    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(2m, ValueProp.Unpowered | ValueProp.Move)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    public override bool HasTurnEndInHandEffect => true;

    public ThingsCaveGodCrystalShard()
        : base(1, CardType.Status, CardRarity.Status, TargetType.None)
    {
    }

    protected override Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay) => Task.CompletedTask;

    protected override async Task OnTurnEndInHand(PlayerChoiceContext choiceContext)
    {
#if STS2_V107_1
        await CreatureCmd.Damage(choiceContext, Owner.Creature, DynamicVars.Damage, this);
#else
        await CreatureCmd.Damage(choiceContext, Owner.Creature, DynamicVars.Damage, this, null);
#endif
    }
}
