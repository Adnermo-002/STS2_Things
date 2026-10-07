using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.CardPools;
using MegaCrit.Sts2.Core.Models.Powers;
using STS2_Things.Monsters;

namespace STS2_Things.Cards;

/// <summary>A removable status that feeds only living leeches if left in hand.</summary>
public sealed class LeechParasite : CardModel
{
    public const int FeedAmount = 2;
    public LeechParasite() : base(1, CardType.Status, CardRarity.Status, TargetType.None) { }
    public override int MaxUpgradeLevel => 0;
    public override CardPoolModel Pool => ModelDb.CardPool<TokenCardPool>();
    public override string PortraitPath => "res://images/cards/leech_parasite.png";
#if !STS2_V107_1
    protected override string PortraitPngPath => PortraitPath;
#endif
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];
    protected override IEnumerable<DynamicVar> CanonicalVars =>
        [new PowerVar<RegenPower>(FeedAmount), new PowerVar<StrengthPower>(FeedAmount)];
    protected override IEnumerable<IHoverTip> ExtraHoverTips =>
        [HoverTipFactory.FromPower<RegenPower>(), HoverTipFactory.FromPower<StrengthPower>()];
    public override bool HasTurnEndInHandEffect => true;
    protected override Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay) => Task.CompletedTask;

    protected override async Task OnTurnEndInHand(PlayerChoiceContext choiceContext)
    {
        // CombatManager selects cards that were in hand, then moves them to Play
        // before invoking this callback (inside the wrapper on v107.1). Checking
        // Hand here would suppress the effect in an actual turn-end sequence.
        if (Owner.Creature.IsDead || CombatState == null)
            return;
        foreach (var leech in CombatState.Enemies.Where(c => c.IsAlive && c.Monster is SanguineLeech).ToArray())
        {
            decimal regeneration = DynamicVars["RegenPower"].BaseValue;
            // Native Regen multiplies its first application in multiplayer, while subsequent
            // stacks are unscaled. Each parasite already resolves per player: grant exactly
            // the displayed two stacks without multiplying that first application again.
            if (leech.GetPower<RegenPower>() == null && CombatState.Players.Count > 1)
            {
                decimal multiplier = ModelDb.Power<RegenPower>().GetScaledAmountForMultiplayer(
                    CombatState, Owner.Creature, 1m, leech, this);
                // ApplyInternal truncates to an integer. Round the inverse upward so a
                // repeating decimal cannot become 1.999... and silently lose a stack.
                if (multiplier > 0) regeneration = decimal.Ceiling(regeneration / multiplier * 1_000_000m) / 1_000_000m;
            }
            await PowerCmd.Apply<RegenPower>(choiceContext, leech, regeneration, Owner.Creature, this);
            if (leech.IsAlive)
                await PowerCmd.Apply<StrengthPower>(choiceContext, leech,
                    DynamicVars["StrengthPower"].BaseValue, Owner.Creature, this);
        }
    }
}
