using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;

namespace STS2_Things.Cards;

public sealed class ThingsSurrender : CardModel
{
    public ThingsSurrender() : base(0, CardType.Skill, CardRarity.Ancient, TargetType.AnyEnemy)
    {
    }

    public override IEnumerable<CardKeyword> CanonicalKeywords =>
        new[] { CardKeyword.Exhaust };

    protected override List<DynamicVar> CanonicalVars =>
    [
        new HealVar(3),
        new PowerVar<WeakPower>(1m)
    ];
    // 动态变量

    // 卡牌的构造函数，指定卡牌的相关属性

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        await CreatureCmd.TriggerAnim(Owner.Creature, "Cast", Owner.Character.CastAnimDelay);

        await CreatureCmd.Heal(Owner.Creature, DynamicVars.Heal.BaseValue); //回血

        var target = cardPlay.Target;
        var monster = target?.Monster;
        var cardOwner = Owner; // 用闭包捕获
        if (monster == null) return;
        var moveStateMachine = monster.MoveStateMachine;
        if (moveStateMachine == null) return;
        var stateLog = moveStateMachine.StateLog;
        if (stateLog.Count == 0) return;
        var originalStateId = stateLog.Last().Id;
        var applyWeak = new MoveState(
            "DEBUFF_WEAK",
            async targets =>
            {
                foreach (var t in targets)
                    await PowerCmd.Apply<WeakPower>(new ThrowingPlayerChoiceContext(), t, DynamicVars.Weak.BaseValue,
                        cardOwner.Creature, this);
            },
            new DebuffIntent()
        )
        {
            FollowUpStateId = originalStateId,
            MustPerformOnceBeforeTransitioning = true
        };
        monster.SetMoveImmediate(applyWeak, forceTransition: true);
    }

    protected override void OnUpgrade()
    {
        AddKeyword(CardKeyword.Retain);
    }
}
