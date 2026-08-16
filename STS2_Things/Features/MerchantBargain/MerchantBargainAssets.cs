#if STS2_V111
using Godot;

namespace STS2_Things.Features.MerchantBargain;

public readonly record struct MerchantBargainHandLayout(
    Vector2 HandSize,
    Vector2 MerchantRestPosition,
    Vector2 PlayerRestPosition,
    Vector2 MerchantHiddenPosition,
    Vector2 PlayerHiddenPosition);

public static class MerchantBargainAssets
{
    private const float HandHeightViewportRatio = 1.03f;
    private const float HandAspectRatio = 422f / 1200f;
    private const float MerchantReachViewportRatio = 0.51f;
    private const float PlayerReachViewportRatio = 0.53f;
    private const float HiddenMarginViewportRatio = 0.06f;

    public const string MerchantRockPath =
        "res://images/ui/merchant_bargain/merchant_rock.png";
    public const string MerchantPaperPath =
        "res://images/ui/merchant_bargain/merchant_paper.png";
    public const string MerchantScissorsPath =
        "res://images/ui/merchant_bargain/merchant_scissors.png";

    public static IReadOnlyList<string> MerchantHandPaths { get; } =
    [
        MerchantRockPath,
        MerchantPaperPath,
        MerchantScissorsPath
    ];

    public static IReadOnlyList<string> PlayerHandPaths { get; } =
    [
        "res://images/ui/hands/multiplayer_hand_ironclad_rock.png",
        "res://images/ui/hands/multiplayer_hand_ironclad_paper.png",
        "res://images/ui/hands/multiplayer_hand_ironclad_scissors.png",
        "res://images/ui/hands/multiplayer_hand_silent_rock.png",
        "res://images/ui/hands/multiplayer_hand_silent_paper.png",
        "res://images/ui/hands/multiplayer_hand_silent_scissors.png",
        "res://images/ui/hands/multiplayer_hand_defect_rock.png",
        "res://images/ui/hands/multiplayer_hand_defect_paper.png",
        "res://images/ui/hands/multiplayer_hand_defect_scissors.png",
        "res://images/ui/hands/multiplayer_hand_necrobinder_rock.png",
        "res://images/ui/hands/multiplayer_hand_necrobinder_paper.png",
        "res://images/ui/hands/multiplayer_hand_necrobinder_scissors.png",
        "res://images/ui/hands/multiplayer_hand_regent_rock.png",
        "res://images/ui/hands/multiplayer_hand_regent_paper.png",
        "res://images/ui/hands/multiplayer_hand_regent_scissors.png"
    ];

    public static IReadOnlyList<string> PreloadPaths { get; } =
    [
        .. MerchantHandPaths,
        .. PlayerHandPaths
    ];

    public static MerchantBargainHandLayout CalculateLayout(Vector2 viewportSize)
    {
        float handHeight = viewportSize.Y * HandHeightViewportRatio;
        Vector2 handSize = new(handHeight * HandAspectRatio, handHeight);
        float centerX = viewportSize.X * 0.5f - handSize.X * 0.5f;
        float hiddenMargin = viewportSize.Y * HiddenMarginViewportRatio;
        Vector2 merchantRest = new(
            centerX,
            viewportSize.Y * MerchantReachViewportRatio - handHeight);
        Vector2 playerRest = new(
            centerX,
            viewportSize.Y * PlayerReachViewportRatio);
        return new MerchantBargainHandLayout(
            handSize,
            merchantRest,
            playerRest,
            new Vector2(centerX, -handHeight - hiddenMargin),
            new Vector2(centerX, viewportSize.Y + hiddenMargin));
    }
}
#endif
