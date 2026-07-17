using System.Collections.Generic;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Powers;

namespace STS2_Things.Powers;

/// <summary>
///     放缩巨甲虫的常驻buff：每当它对玩家造成未被抵挡的伤害时，该玩家获得5层缩小。
/// </summary>
public sealed class ScaleBeetlePower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Single;

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new IntVar("ScaleDownAmount", 5)
    ];

    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
    [
        HoverTipFactory.FromPower<ScaleDownPower>()
    ];

    public override async Task AfterDamageGiven(PlayerChoiceContext choiceContext, Creature? dealer,
        DamageResult result, ValueProp props, Creature target, CardModel? cardSource)
    {
        if (dealer == Owner && result.UnblockedDamage > 0 && target.Side != Owner.Side)
        {
            Flash();
            await PowerCmd.Apply<ScaleDownPower>(
                choiceContext,
                target,
                DynamicVars["ScaleDownAmount"].BaseValue,
                Owner,
                null
            );
        }
    }
}
