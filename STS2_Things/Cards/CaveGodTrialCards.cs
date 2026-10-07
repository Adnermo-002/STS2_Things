using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.CardPools;
using MegaCrit.Sts2.Core.Models.Monsters;
using STS2_Things.Powers;

namespace STS2_Things.Cards;

/// <summary>
/// 【断刃】(Broken Blade) 状态卡（二选一）：选择后本回合无法打出攻击牌
/// </summary>
public sealed class CaveGodBrokenBladeTrial : CardModel, KnowledgeDemon.IChoosable
{
    public override int MaxUpgradeLevel => 0;
    public override bool CanBeGeneratedInCombat => false;
    public override CardPoolModel Pool => ModelDb.CardPool<TokenCardPool>();
    public override string PortraitPath => "res://images/packed/card_portraits/token/cave_god_broken_blade_trial.png";
#if !STS2_V107_1
    protected override string PortraitPngPath => PortraitPath;
#endif

    public CaveGodBrokenBladeTrial()
        : base(-1, CardType.Status, CardRarity.Status, TargetType.None)
    {
    }

    public async Task OnChosen()
    {
        await PowerCmd.Apply<CaveGodBrokenBladePower>(new ThrowingPlayerChoiceContext(), Owner.Creature, 1m, Owner.Creature, this);
    }
}

/// <summary>
/// 【碎盾】(Shattered Shield) 状态卡（二选一）：选择后本回合无法打出技能牌
/// </summary>
public sealed class CaveGodShatteredShieldTrial : CardModel, KnowledgeDemon.IChoosable
{
    public override int MaxUpgradeLevel => 0;
    public override bool CanBeGeneratedInCombat => false;
    public override CardPoolModel Pool => ModelDb.CardPool<TokenCardPool>();
    public override string PortraitPath => "res://images/packed/card_portraits/token/cave_god_shattered_shield_trial.png";
#if !STS2_V107_1
    protected override string PortraitPngPath => PortraitPath;
#endif

    public CaveGodShatteredShieldTrial()
        : base(-1, CardType.Status, CardRarity.Status, TargetType.None)
    {
    }

    public async Task OnChosen()
    {
        await PowerCmd.Apply<CaveGodShatteredShieldPower>(new ThrowingPlayerChoiceContext(), Owner.Creature, 1m, Owner.Creature, this);
    }
}

/// <summary>
/// 【刚猛试炼】(Trial of Force) 状态卡（兼容保留）
/// </summary>
public sealed class CaveGodMartialTrial : CardModel, KnowledgeDemon.IChoosable
{
    public override int MaxUpgradeLevel => 0;
    public override bool CanBeGeneratedInCombat => false;
    public override CardPoolModel Pool => ModelDb.CardPool<TokenCardPool>();
    public override string PortraitPath => "res://images/packed/card_portraits/token/cave_god_martial_trial.png";
#if !STS2_V107_1
    protected override string PortraitPngPath => PortraitPath;
#endif

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
/// 【坚韧试炼】(Trial of Skill) 状态卡（兼容保留）
/// </summary>
public sealed class CaveGodArcaneTrial : CardModel, KnowledgeDemon.IChoosable
{
    public override int MaxUpgradeLevel => 0;
    public override bool CanBeGeneratedInCombat => false;
    public override CardPoolModel Pool => ModelDb.CardPool<TokenCardPool>();
    public override string PortraitPath => "res://images/packed/card_portraits/token/cave_god_arcane_trial.png";
#if !STS2_V107_1
    protected override string PortraitPngPath => PortraitPath;
#endif

    public CaveGodArcaneTrial()
        : base(-1, CardType.Status, CardRarity.Status, TargetType.None)
    {
    }

    public async Task OnChosen()
    {
        await PowerCmd.Apply<CaveGodArcanePower>(new ThrowingPlayerChoiceContext(), Owner.Creature, 1m, Owner.Creature, this);
    }
}
