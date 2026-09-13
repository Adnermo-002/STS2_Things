using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using STS2_Things.Powers;

namespace STS2_Things.Cards;

/// <summary>
/// 【唯攻是图】状态卡（二选一）：选择后本回合只能打出攻击牌
/// </summary>
public sealed class CaveGodMartialTrial : CardModel, KnowledgeDemon.IChoosable
{
    public override int MaxUpgradeLevel => 0;
    public override bool CanBeGeneratedInCombat => false;

    public CaveGodMartialTrial()
        : base(-1, CardType.Status, CardRarity.Status, TargetType.None)
    {
    }

    public async Task OnChosen()
    {
        await PowerCmd.Apply<CaveGodMartialPower>(new ThrowingPlayerChoiceContext(), Owner.Creature, 1m, Owner.Creature, this);
    }
}

/// <summary>
/// 【唯守是图】状态卡（二选一）：选择后本回合只能打出技能牌
/// </summary>
public sealed class CaveGodArcaneTrial : CardModel, KnowledgeDemon.IChoosable
{
    public override int MaxUpgradeLevel => 0;
    public override bool CanBeGeneratedInCombat => false;

    public CaveGodArcaneTrial()
        : base(-1, CardType.Status, CardRarity.Status, TargetType.None)
    {
    }

    public async Task OnChosen()
    {
        await PowerCmd.Apply<CaveGodArcanePower>(new ThrowingPlayerChoiceContext(), Owner.Creature, 1m, Owner.Creature, this);
    }
}
