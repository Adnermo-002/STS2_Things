using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Things.Events;

internal static class DepthsEventDefaults
{
    public const int SmallGold = 15;
    public static DynamicVar SmallGoldVar() => new IntVar("SmallGold", SmallGold);
    public static Task TakeSmallReward(Player player) => PlayerCmd.GainGold(SmallGold, player);
    public static IEnumerable<LocString> DescribeOptions(EventModel model, params string[] keys)
    {
        foreach (string key in keys)
            foreach (string part in new[] { "title", "description" })
            {
                var text = new LocString(model.LocTable, $"{model.Id.Entry}.pages.INITIAL.options.{key}.{part}");
                model.DynamicVars.AddTo(text);
                text.Add("IsMultiplayer", model.Owner?.RunState.Players.Count > 1);
                yield return text;
            }
    }
}
