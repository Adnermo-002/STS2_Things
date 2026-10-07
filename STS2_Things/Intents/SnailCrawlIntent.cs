using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;

namespace STS2_Things.Intents;

/// <summary>A real defensive intent with a crawl countdown; it is not an attack/status intent.</summary>
public sealed class SnailCrawlIntent(int remaining) : DefendIntent
{
    public override LocString GetIntentLabel(IEnumerable<Creature> targets, Creature owner)
    {
        var label = new LocString("monsters", "ROCK_SNAIL.crawlLabel");
        label.Add("Remaining", remaining);
        return label;
    }

    protected override LocString GetIntentDescription(IEnumerable<Creature> targets, Creature owner)
    {
        var description = new LocString("powers", "ROCK_CRAWL_STATE_POWER.intentDescription");
        description.Add("Remaining", remaining);
        return description;
    }
}
