#if STS2_V111
using System;
using System.Collections.Generic;

namespace STS2_Things.Features.MerchantBargain;

public enum MerchantBargainAttemptDisposition
{
    PassThrough,
    Suppress,
    StartFight,
    PurchaseAtNegotiatedPrice
}

public sealed class MerchantBargainSession<TEntry> where TEntry : class
{
    private readonly Dictionary<TEntry, int> _eligibleAttemptCounts =
        new(ReferenceEqualityComparer.Instance);

    public bool Consumed { get; private set; }

    public bool FightInProgress { get; private set; }

    public TEntry? WinningEntry { get; private set; }

    public int? WinningPrice { get; private set; }

    public MerchantBargainAttemptDisposition RegisterAttempt(
        TEntry entry,
        bool isStocked,
        bool isEligible)
    {
        if (FightInProgress)
        {
            return MerchantBargainAttemptDisposition.Suppress;
        }

        if (WinningEntry is not null)
        {
            return isStocked && ReferenceEquals(WinningEntry, entry)
                ? MerchantBargainAttemptDisposition.PurchaseAtNegotiatedPrice
                : MerchantBargainAttemptDisposition.PassThrough;
        }

        if (Consumed || !isStocked || !isEligible)
        {
            return MerchantBargainAttemptDisposition.PassThrough;
        }

        _eligibleAttemptCounts.TryGetValue(entry, out int previousAttempts);
        int currentAttempt = Math.Min(
            previousAttempts + 1,
            MerchantBargainRules.TriggerAttempt);
        _eligibleAttemptCounts[entry] = currentAttempt;
        if (currentAttempt < MerchantBargainRules.TriggerAttempt)
        {
            return MerchantBargainAttemptDisposition.PassThrough;
        }

        FightInProgress = true;
        return MerchantBargainAttemptDisposition.StartFight;
    }

    public int GetEligibleAttemptCount(TEntry entry)
    {
        return _eligibleAttemptCounts.GetValueOrDefault(entry);
    }

    public void MarkFightWon(TEntry entry, int negotiatedPrice)
    {
        ArgumentOutOfRangeException.ThrowIfNegative(negotiatedPrice);
        WinningEntry = entry;
        WinningPrice = negotiatedPrice;
    }

    public void MarkFightLost()
    {
        Consumed = true;
        ClearWinningOffer();
    }

    public void MarkPurchaseSucceeded()
    {
        Consumed = true;
        ClearWinningOffer();
    }

    public void ResetFightAfterError(TEntry entry)
    {
        ClearWinningOffer();
        _eligibleAttemptCounts[entry] = MerchantBargainRules.TriggerAttempt - 1;
    }

    public void EndFight()
    {
        FightInProgress = false;
    }

    private void ClearWinningOffer()
    {
        WinningEntry = null;
        WinningPrice = null;
    }
}
#endif
