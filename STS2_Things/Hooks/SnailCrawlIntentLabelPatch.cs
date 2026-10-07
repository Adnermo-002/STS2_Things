using HarmonyLib;
using MegaCrit.Sts2.addons.mega_text;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.Nodes.Combat;
using STS2_Things.Intents;

namespace STS2_Things.Hooks;

// NIntent only fills its native value label for attacks/statuses. Opt this one
// defensive countdown into that existing label without changing intent types,
// icon/animation registries, input handling, or any other monster's intent.
[HarmonyPatch(typeof(NIntent), "UpdateVisuals")]
internal static class SnailCrawlIntentLabelPatch
{
    [HarmonyPostfix]
    private static void Postfix(AbstractIntent ____intent, MegaRichTextLabel ____valueLabel,
        IEnumerable<Creature> ____targets, Creature ____owner)
    {
        if (____intent is SnailCrawlIntent crawl)
            ____valueLabel.Text = crawl.GetIntentLabel(____targets, ____owner).GetFormattedText();
    }
}
