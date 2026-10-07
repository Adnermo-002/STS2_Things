using System.Collections.Generic;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Models;
using STS2_Things.Cards;

namespace STS2_Things.Powers;

/// <summary>
/// 晶脉：活体巨岩每完成一个招式获得1层；满4层时下一招变为「晶簇崩发」。
/// 手臂被击倒时失去2层。真实层数由 ThingsCaveGodBody.CrystalVein 持有，
/// 双臂上的本能力只是镜像显示（核心埋在岩浆中时能力栏不可见）。
/// </summary>
public sealed class ThingsCaveGodCrystalVeinPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;
    public override PowerStackType StackType => PowerStackType.Counter;

    // Crystal Burst seeds shards; show the card so players can plan around it.
    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        HoverTipFactory.FromCardWithCardHoverTips<ThingsCaveGodCrystalShard>();
}
