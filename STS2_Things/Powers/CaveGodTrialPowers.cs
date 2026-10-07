using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;

namespace STS2_Things.Powers;

/// <summary>
/// 【断刃】(Broken Blade) — 受到岩之手强力禁锢，兵刃折断！本回合无法打出攻击牌！
/// </summary>
public sealed class CaveGodBrokenBladePower : PowerModel
{
    public override PowerType Type => PowerType.Debuff;
    public override PowerStackType StackType => PowerStackType.Counter;

    public override bool ShouldPlay(CardModel card, AutoPlayType autoPlayType)
    {
        if (card.Owner == Owner.Player)
        {
            return card.Type != CardType.Attack;
        }
        return true;
    }

    public override async Task AfterSideTurnEnd(PlayerChoiceContext choiceContext, CombatSide side, IEnumerable<Creature> participants)
    {
        if (participants.Contains(Owner))
        {
            Flash();
            await PowerCmd.Remove(this);
        }
    }
}

/// <summary>
/// 【碎盾】(Shattered Shield) — 受到岩之手强力禁锢，盾甲碎裂！本回合无法打出技能牌！
/// </summary>
public sealed class CaveGodShatteredShieldPower : PowerModel
{
    public override PowerType Type => PowerType.Debuff;
    public override PowerStackType StackType => PowerStackType.Counter;

    public override bool ShouldPlay(CardModel card, AutoPlayType autoPlayType)
    {
        if (card.Owner == Owner.Player)
        {
            return card.Type != CardType.Skill;
        }
        return true;
    }

    public override async Task AfterSideTurnEnd(PlayerChoiceContext choiceContext, CombatSide side, IEnumerable<Creature> participants)
    {
        if (participants.Contains(Owner))
        {
            Flash();
            await PowerCmd.Remove(this);
        }
    }
}

/// <summary>
/// 【刚猛试炼】(Trial of Force) — 受到石爪强力禁锢，本回合只能打出攻击牌！（兼容保留）
/// </summary>
public sealed class CaveGodMartialPower : PowerModel
{
    public override PowerType Type => PowerType.Debuff;
    public override PowerStackType StackType => PowerStackType.Counter;

    public override bool ShouldPlay(CardModel card, AutoPlayType autoPlayType)
    {
        if (card.Owner == Owner.Player)
        {
            return card.Type == CardType.Attack;
        }
        return true;
    }

    public override async Task AfterSideTurnEnd(PlayerChoiceContext choiceContext, CombatSide side, IEnumerable<Creature> participants)
    {
        if (participants.Contains(Owner))
        {
            Flash();
            await PowerCmd.Remove(this);
        }
    }
}

/// <summary>
/// 【坚韧试炼】(Trial of Skill) — 受到石爪强力禁锢，本回合只能打出技能牌！（兼容保留）
/// </summary>
public sealed class CaveGodArcanePower : PowerModel
{
    public override PowerType Type => PowerType.Debuff;
    public override PowerStackType StackType => PowerStackType.Counter;

    public override bool ShouldPlay(CardModel card, AutoPlayType autoPlayType)
    {
        if (card.Owner == Owner.Player)
        {
            return card.Type == CardType.Skill;
        }
        return true;
    }

    public override async Task AfterSideTurnEnd(PlayerChoiceContext choiceContext, CombatSide side, IEnumerable<Creature> participants)
    {
        if (participants.Contains(Owner))
        {
            Flash();
            await PowerCmd.Remove(this);
        }
    }
}
