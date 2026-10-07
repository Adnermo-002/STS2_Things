using System.Collections.Generic;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;

namespace STS2_Things.Powers;

/// <summary>
/// 崩落裂痕：核心暴露时出现，层数 = 仍需造成的伤害（核心最大生命的25%，向上取整）。
/// 归零时裂痕贯通：本次苏醒不获得力量，并清空晶脉。由 ThingsCaveGodBody 负责计数与移除。
/// </summary>
public sealed class ThingsCaveGodFissurePower : PowerModel
{
    public override PowerType Type => PowerType.Debuff;
    public override PowerStackType StackType => PowerStackType.Counter;

    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        [HoverTipFactory.FromPower<StrengthPower>(), HoverTipFactory.FromPower<ThingsCaveGodCrystalVeinPower>()];
}
