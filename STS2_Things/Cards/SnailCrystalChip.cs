using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.CardPools;
using MegaCrit.Sts2.Core.ValueProps;

namespace STS2_Things.Cards;

public sealed class SnailCrystalChip : CardModel
{
    public SnailCrystalChip() : base(0, CardType.Attack, CardRarity.Token, TargetType.AnyEnemy) { }
    public override int MaxUpgradeLevel => 0;
    public override bool CanBeGeneratedInCombat => false;
    public override CardPoolModel Pool => ModelDb.CardPool<TokenCardPool>();
    public override string PortraitPath => "res://images/packed/card_portraits/token/snail_crystal_chip.png";
#if !STS2_V107_1
    protected override string PortraitPngPath => PortraitPath;
#endif
    protected override IEnumerable<DynamicVar> CanonicalVars => [new DamageVar(5m, ValueProp.Move)];
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];

    protected override async Task OnPlay(PlayerChoiceContext context, CardPlay play)
    {
        var attack = DamageCmd.Attack(DynamicVars.Damage.BaseValue);
#if STS2_V107_1
        attack.FromCard(this);
#else
        attack.FromCard(this, play);
#endif
        await attack.Targeting(play.Target!).WithHitFx("vfx/vfx_attack_slash").Execute(context);
    }
}
