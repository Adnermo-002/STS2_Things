using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Things.Afflictions;

/// <summary>The native card affliction supplies text, hover tips and its overlay.</summary>
public sealed class SilkLead : AfflictionModel
{
    public override bool HasExtraCardText => true;
    public override bool CanAfflictUnplayableCards => false;
    public override bool CanAfflictCardType(CardType type) => type is CardType.Attack or CardType.Skill or CardType.Power;
    public override bool CanAfflict(CardModel card) => base.CanAfflict(card) && !card.EnergyCost.CostsX;
}
