using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.ValueProps;

namespace STS2_Things.Powers;

/// <summary>
///     死亡律动 — Boss 身上的 Buff，玩家每出一张牌 Boss 受到伤害
///     使用 Buff 类型以避免被人工制品抵消
///     注意：不使用 InternalData 存储卡牌映射，因为 InternalData 不会在多人游戏下同步，
///     会导致不同客户端伤害计算不一致。直接使用 Amount（自动同步）即可。
/// </summary>
public sealed class LegacyBeatOfDeathPower : PowerModel
{
    public override PowerType Type => PowerType.Buff;

    public override PowerStackType StackType => PowerStackType.Counter;

    public override async Task AfterCardPlayed(PlayerChoiceContext context, CardPlay cardPlay)
    {
        Flash();
        // 伤害目标: Owner = Boss 自己
        await CreatureCmd.Damage(context, Owner, Amount,
            ValueProp.Unblockable | ValueProp.Unpowered, null, null);
    }
}
