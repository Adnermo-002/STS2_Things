using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Encounters;

namespace STS2_Things.Modifiers;

/// <summary>
/// Keeps the Quirky Hopper's stolen-potion resolution unambiguous.
///
/// An ordinary room PotionReward is unrelated to the stolen potion, but presenting
/// it beside an exact returned-potion reward makes the random reward look like a
/// randomized return. Normally the stolen potion goes straight back to its old belt
/// slot; only a full belt creates an exact ExtraReward and activates this policy.
/// </summary>
public sealed class QuirkyHopperRewardPolicy : ModifierModel
{
    public override bool TryModifyRewardsLate(
        Player player,
        List<Reward> rewards,
        AbstractRoom? room)
    {
        if (room is not CombatRoom combatRoom ||
            combatRoom.Encounter is not QuirkyHopperWeak)
        {
            return false;
        }

        IReadOnlyList<Reward> extraRewards = combatRoom.ExtraRewards.TryGetValue(
            player,
            out List<Reward>? playerExtraRewards)
            ? playerExtraRewards
            : [];
        List<PotionReward> returnedPotionRewards = extraRewards
            .OfType<PotionReward>()
            .ToList();
        if (returnedPotionRewards.Count == 0)
        {
            return false;
        }

        List<PotionReward> ordinaryPotionRewards = rewards
            .OfType<PotionReward>()
            .Where(reward => !returnedPotionRewards.Any(returned => ReferenceEquals(returned, reward)))
            .ToList();

        foreach (PotionReward reward in ordinaryPotionRewards)
        {
            rewards.Remove(reward);
        }

        return ordinaryPotionRewards.Count > 0;
    }
}
