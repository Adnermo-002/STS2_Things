#if STS2_V111
using System;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.TreasureRelicPicking;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Shops;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Rooms;

namespace STS2_Things.Features.MerchantBargain;

internal static class MerchantBargainManager
{
    private sealed class InventoryState
    {
        public MerchantBargainSession<MerchantEntry> Session { get; } = new();
    }

    private sealed class PriceOverride
    {
        public required int Price { get; init; }
    }

    private static readonly ConditionalWeakTable<MerchantInventory, InventoryState> InventoryStates = new();
    private static readonly ConditionalWeakTable<MerchantEntry, PriceOverride> PriceOverrides = new();

    internal static bool TryIntercept(
        MerchantEntry entry,
        MerchantInventory? inventory,
        bool ignoreCost,
        out Task<bool> result)
    {
        result = Task.FromResult(false);
        if (ignoreCost || inventory is null || entry is MerchantCardRemovalEntry ||
            TryGetPriceOverride(entry, out _))
        {
            return false;
        }

        Player player = inventory.Player;
        NMerchantInventory? merchantUi = NMerchantRoom.Instance?.Inventory;
        if (player.RunState.CurrentRoom is not MerchantRoom ||
            merchantUi is null || !merchantUi.IsOpen || merchantUi.Inventory != inventory)
        {
            return false;
        }

        InventoryState state = InventoryStates.GetValue(inventory, static _ => new InventoryState());
        int price = entry.Cost;
        MerchantBargainAttemptDisposition disposition = state.Session.RegisterAttempt(
            entry,
            entry.IsStocked,
            MerchantBargainRules.IsEligibleShortfall(price, player.Gold));
        switch (disposition)
        {
            case MerchantBargainAttemptDisposition.PassThrough:
                return false;
            case MerchantBargainAttemptDisposition.Suppress:
                return true;
            case MerchantBargainAttemptDisposition.PurchaseAtNegotiatedPrice:
                int negotiatedPrice = state.Session.WinningPrice
                    ?? throw new InvalidOperationException(
                        "A merchant bargain winning entry has no negotiated price.");
                result = PurchaseAtNegotiatedPriceAsync(
                    entry,
                    inventory,
                    state,
                    negotiatedPrice);
                return true;
            case MerchantBargainAttemptDisposition.StartFight:
                result = ResolveFightAndPurchaseAsync(entry, inventory, merchantUi, state);
                return true;
            default:
                throw new ArgumentOutOfRangeException(nameof(disposition), disposition, null);
        }
    }

    internal static bool TryGetPriceOverride(MerchantEntry entry, out int price)
    {
        if (PriceOverrides.TryGetValue(entry, out PriceOverride? priceOverride))
        {
            price = priceOverride.Price;
            return true;
        }

        price = 0;
        return false;
    }

    private static async Task<bool> ResolveFightAndPurchaseAsync(
        MerchantEntry entry,
        MerchantInventory inventory,
        NMerchantInventory merchantUi,
        InventoryState state)
    {
        NMerchantBargainRps? overlay = null;
        merchantUi.BlockInput();
        try
        {
            Player player = inventory.Player;
            merchantUi.MerchantHand.StopPointing(0f);
            await merchantUi.GetTree()
                .CreateTimer(0.7)
                .AwaitSignal(SceneTreeTimer.SignalName.Timeout, merchantUi);

            overlay = NMerchantBargainRps.Create(player, merchantUi.GetViewportRect().Size);
            merchantUi.AddChild(overlay);
            await overlay.PlayEntrance();

            Rng rng = CreateFightRng(player);
            MerchantBargainRoundResult roundResult;
            do
            {
                RelicPickingFightMove playerMove = (RelicPickingFightMove)rng.NextInt(3);
                RelicPickingFightMove merchantMove = (RelicPickingFightMove)rng.NextInt(3);
                await overlay.PlayRound(playerMove, merchantMove);
                roundResult = MerchantBargainRules.EvaluateRound(playerMove, merchantMove);
                if (roundResult == MerchantBargainRoundResult.Tie)
                {
                    await overlay.PlayTie();
                }
            }
            while (roundResult == MerchantBargainRoundResult.Tie);

            bool playerWon = roundResult == MerchantBargainRoundResult.PlayerWon;
            await overlay.PlayOutcome(playerWon);
            await overlay.PlayExit();
            if (!playerWon)
            {
                state.Session.MarkFightLost();
                entry.InvokePurchaseFailed(PurchaseStatus.FailureGold);
                return false;
            }

            int negotiatedPrice = player.Gold;
            state.Session.MarkFightWon(entry, negotiatedPrice);
            return await PurchaseAtNegotiatedPriceAsync(
                entry,
                inventory,
                state,
                negotiatedPrice);
        }
        catch (Exception exception)
        {
            state.Session.ResetFightAfterError(entry);
            Log.Error($"[STS2_Things] Merchant bargain fight failed: {exception}");
            entry.InvokePurchaseFailed(PurchaseStatus.FailureGold);
            return false;
        }
        finally
        {
            state.Session.EndFight();
            overlay?.QueueFree();
            if (GodotObject.IsInstanceValid(merchantUi) && merchantUi.IsInsideTree())
            {
                merchantUi.UnblockInput();
            }
        }
    }

    private static async Task<bool> PurchaseAtNegotiatedPriceAsync(
        MerchantEntry entry,
        MerchantInventory inventory,
        InventoryState state,
        int negotiatedPrice)
    {
        SetPriceOverride(entry, negotiatedPrice);
        bool success = false;
        try
        {
            success = await entry.OnTryPurchaseWrapper(inventory);
            if (success)
            {
                state.Session.MarkPurchaseSucceeded();
            }

            return success;
        }
        finally
        {
            PriceOverrides.Remove(entry);
            entry.OnMerchantInventoryUpdated();
        }
    }

    private static void SetPriceOverride(MerchantEntry entry, int price)
    {
        PriceOverrides.Remove(entry);
        PriceOverrides.Add(entry, new PriceOverride { Price = price });
    }

    private static Rng CreateFightRng(Player player)
    {
        ulong floor = (ulong)Math.Max(0, player.RunState.TotalFloor);
        ulong playerSlot = (ulong)Math.Max(0, player.RunState.GetPlayerSlotIndex(player));
        ulong seed = unchecked(
            player.PlayerRng.Seed ^
            ((floor + 1UL) * 0x9E3779B97F4A7C15UL) ^
            ((playerSlot + 1UL) * 0xBF58476D1CE4E5B9UL));
        return new Rng(seed, "sts2_things_merchant_bargain");
    }
}
#endif
