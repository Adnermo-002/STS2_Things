#if STS2_V111
using MegaCrit.Sts2.Core.Entities.TreasureRelicPicking;

namespace STS2_Things.Features.MerchantBargain;

public enum MerchantBargainRoundResult
{
    Tie,
    PlayerWon,
    MerchantWon
}

public static class MerchantBargainRules
{
    public const int MaximumGoldShortfall = 20;
    public const int TriggerAttempt = 5;

    public static bool IsEligibleShortfall(int price, int gold)
    {
        return price > gold && price - gold <= MaximumGoldShortfall;
    }

    public static MerchantBargainRoundResult EvaluateRound(
        RelicPickingFightMove playerMove,
        RelicPickingFightMove merchantMove)
    {
        if (playerMove == merchantMove)
        {
            return MerchantBargainRoundResult.Tie;
        }

        return ((int)merchantMove + 1) % 3 == (int)playerMove
            ? MerchantBargainRoundResult.PlayerWon
            : MerchantBargainRoundResult.MerchantWon;
    }
}
#endif
