using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;

namespace STS2_Things.Cards;

/// <summary>
/// Ironclad Uncommon Attack. The damage resolves before the equal Strength loss
/// so the player gets the advertised hit even when the loss would reach zero.
/// Exhaust keeps its permanent symmetrical Strength loss from becoming a
/// repeatable boss-locking effect.
/// </summary>
public sealed class ThingsCollision : CardModel
{
    private const string StrengthLossKey = "StrengthLoss";

    public override IEnumerable<CardKeyword> CanonicalKeywords =>
        [CardKeyword.Exhaust];

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new DamageVar(10m, ValueProp.Move),
        new DynamicVar(StrengthLossKey, 2m)
    ];

    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        [HoverTipFactory.FromPower<StrengthPower>()];

    public ThingsCollision()
        : base(1, CardType.Attack, CardRarity.Uncommon, TargetType.AnyEnemy)
    {
    }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        ArgumentNullException.ThrowIfNull(cardPlay.Target);

#if STS2_V107_1
        var attack = DamageCmd.Attack(DynamicVars.Damage.BaseValue).FromCard(this);
#else
        // V110 damage hooks consume the CardPlay reference for multiplayer-safe context.
        var attack = DamageCmd.Attack(DynamicVars.Damage.BaseValue).FromCard(this, cardPlay);
#endif
        await attack.Targeting(cardPlay.Target)
            .WithAttackerAnim(
                Ironclad.GetHeavyAnimIfApplicable(Owner.Character),
                Ironclad.GetHeavyAttackDelayIfApplicable(Owner.Character))
            .WithHitFx("vfx/vfx_heavy_blunt", null, "heavy_attack.mp3")
            .WithHitVfxSpawnedAtBase()
            .Execute(choiceContext);

        decimal strengthLoss = DynamicVars[StrengthLossKey].BaseValue;
        await PowerCmd.Apply<StrengthPower>(
            choiceContext, Owner.Creature, -strengthLoss, Owner.Creature, this);
        await PowerCmd.Apply<StrengthPower>(
            choiceContext, cardPlay.Target, -strengthLoss, Owner.Creature, this);
    }

    protected override void OnUpgrade()
    {
        DynamicVars.Damage.UpgradeValueBy(4m);
    }
}
