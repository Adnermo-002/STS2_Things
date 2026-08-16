using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using HarmonyLib;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.DevConsole;
using MegaCrit.Sts2.Core.DevConsole.ConsoleCommands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens.Capstones;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.TestSupport;
using STS2_Things.Enchantments;

namespace STS2_Things.Events;

public sealed class CuttingItClose : EventModel
{
    private Player EventOwner => Owner
        ?? throw new InvalidOperationException("Cutting It Close has not been initialized with an owner.");

    protected override IEnumerable<DynamicVar> CanonicalVars =>
    [
        new StringVar("Enchantment", ModelDb.Enchantment<ThingsSplit>().Title.GetFormattedText())
    ];

    public override bool IsAllowed(IRunState runState)
    {
        var split = ModelDb.Enchantment<ThingsSplit>();
        return runState.Players.All(player => player.Deck.Cards.Any(card => IsSplitCandidate(split, card)));
    }

    protected override IReadOnlyList<EventOption> GenerateInitialOptions()
    {
        return
        [
            new EventOption(
                this,
                Improvise,
                InitialOptionKey("IMPROVISE"),
                HoverTipFactory.FromEnchantment<ThingsSplit>()),
            new EventOption(this, Throw, InitialOptionKey("THROW"))
        ];
    }

    private async Task Improvise()
    {
        var split = ModelDb.Enchantment<ThingsSplit>();
        var selected = (await CardSelectCmd.FromDeckForEnchantment(
            EventOwner,
            split,
            1,
            card => card is not null && IsSplitCandidate(split, card),
            new CardSelectorPrefs(
                L10NLookup("CUTTING_IT_CLOSE.pages.IMPROVISE.selectionScreenPrompt"),
                1))).FirstOrDefault();

        if (selected is null)
        {
            FinishWithoutCard();
            return;
        }

        CardModel[] copies =
        [
            EventOwner.RunState.CloneCard(selected),
            EventOwner.RunState.CloneCard(selected)
        ];

        foreach (var copy in copies)
        {
            CardCmd.Enchant<ThingsSplit>(copy, 1m);
        }

        await CardPileCmd.RemoveFromDeck(selected);
        var addResults = await CardPileCmd.Add(copies, PileType.Deck);
        CardCmd.PreviewCardPileAdd(addResults, 1.6f, CardPreviewStyle.EventLayout);
        SetEventFinished(L10NLookup("CUTTING_IT_CLOSE.pages.IMPROVISE.description"));
    }

    private async Task Throw()
    {
        var selected = (await CardSelectCmd.FromDeckForRemoval(
            EventOwner,
            new CardSelectorPrefs(
                L10NLookup("CUTTING_IT_CLOSE.pages.THROW.selectionScreenPrompt"),
                1))).FirstOrDefault();

        if (selected is null)
        {
            FinishWithoutCard();
            return;
        }

        await CardPileCmd.RemoveFromDeck(selected);
        SetEventFinished(L10NLookup("CUTTING_IT_CLOSE.pages.THROW.description"));
    }

    private static bool IsSplitCandidate(ThingsSplit split, CardModel card)
    {
        return card.Type is CardType.Attack or CardType.Skill &&
               card.IsRemovable &&
               split.CanEnchant(card);
    }

    private void FinishWithoutCard()
    {
        // Selection is normally mandatory. Still close the event cleanly if a
        // replay, disconnect, death, or future cancelable selector returns no
        // card; EventOption has already recorded the click at this point.
        SetEventFinished(L10NLookup("CUTTING_IT_CLOSE.pages.ABORTED.description"));
    }
}

/// <summary>
/// EventConsoleCmd enters rooms without RunManager's debug transition helper,
/// so a reward overlay from the previous combat can remain above the new event
/// and intercept all input. Clear the same three screen layers as
/// RunManager.ClearScreens before the first debug jump. A second jump while this
/// event is active is rejected before cleanup so it cannot replace the mutable
/// event instance underneath a pending option callback.
/// </summary>
[HarmonyPatch(typeof(EventConsoleCmd), nameof(EventConsoleCmd.Process))]
internal static class CuttingItCloseConsoleReentryPatch
{
    private static bool Prefix(Player? issuingPlayer, string[] args, ref CmdResult __result)
    {
        bool duplicateActive = issuingPlayer is not null &&
                               issuingPlayer.RunState.CurrentRoom is EventRoom currentRoom &&
                               ShouldBlockDuplicate(
                                   args,
                                   currentRoom.CanonicalEvent,
                                   RunManager.Instance.EventSynchronizer.Events);

        if (duplicateActive)
        {
            __result = new CmdResult(
                success: false,
                "CUTTING_IT_CLOSE is already active; finish its current option before jumping again.");
            return false;
        }

        if (ShouldPrepareScreens(
                args,
                issuingPlayer is not null,
                RunManager.Instance.IsInProgress,
                duplicateActive))
        {
            ClearBlockingScreens();
        }

        return true;
    }

    internal static bool ShouldPrepareScreens(
        string[] args,
        bool hasIssuingPlayer,
        bool runInProgress,
        bool duplicateActive)
    {
        return args.Length > 0 &&
               string.Equals(args[0], "CUTTING_IT_CLOSE", StringComparison.OrdinalIgnoreCase) &&
               hasIssuingPlayer &&
               runInProgress &&
               !duplicateActive;
    }

    private static void ClearBlockingScreens()
    {
        if (TestMode.IsOn)
        {
            return;
        }

        NOverlayStack.Instance?.Clear();
        NCapstoneContainer.Instance?.Close();
        NMapScreen.Instance?.Close(animateOut: false);
    }

    internal static bool ShouldBlockDuplicate(
        string[] args,
        EventModel canonicalEvent,
        IEnumerable<EventModel> mutableEvents)
    {
        return args.Length > 0 &&
               string.Equals(args[0], "CUTTING_IT_CLOSE", StringComparison.OrdinalIgnoreCase) &&
               canonicalEvent is CuttingItClose &&
               mutableEvents.Any(mutableEvent =>
                   mutableEvent is CuttingItClose && !mutableEvent.IsFinished);
    }
}
