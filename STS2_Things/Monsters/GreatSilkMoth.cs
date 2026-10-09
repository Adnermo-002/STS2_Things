using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Helpers;

namespace STS2_Things.Monsters;

/// <summary>A sturdy silk caster: two upcoming player turns, one pair per turn.</summary>
public sealed class GreatSilkMoth : SilkMoth
{
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 66, 58);
    public override int MaxInitialHp => MinInitialHp + 6;
    public override float HpBarSizeReduction => 55f;
    protected override int WeaveLayers => 2;
    protected override int FlutterDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 5, 4);
}
