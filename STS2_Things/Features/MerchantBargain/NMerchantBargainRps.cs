#if STS2_V110
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.TreasureRelicPicking;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;

namespace STS2_Things.Features.MerchantBargain;

internal partial class NMerchantBargainRps : Control
{
    private const float FightDuration = 1.5f;
    private const float EntranceDuration = 0.45f;
    private const float ExitDuration = 0.35f;

    private TextureRect _playerHand = null!;
    private TextureRect _merchantHand = null!;
    private Vector2 _playerRestPosition;
    private Vector2 _merchantRestPosition;
    private Vector2 _playerHiddenPosition;
    private Vector2 _merchantHiddenPosition;
    private Texture2D _playerRock = null!;
    private Texture2D _playerPaper = null!;
    private Texture2D _playerScissors = null!;
    private Texture2D _merchantRock = null!;
    private Texture2D _merchantPaper = null!;
    private Texture2D _merchantScissors = null!;

    public static NMerchantBargainRps Create(Player player, Vector2 viewportSize)
    {
        var overlay = new NMerchantBargainRps
        {
            Name = "STS2ThingsMerchantBargainRps",
            MouseFilter = MouseFilterEnum.Stop,
            FocusMode = FocusModeEnum.None,
            ZIndex = 100,
            Size = viewportSize
        };
        overlay.LoadTextures(player);
        overlay.BuildVisuals(viewportSize);
        return overlay;
    }

    public async Task PlayEntrance()
    {
        _playerHand.Modulate = Colors.White;
        _merchantHand.Modulate = Colors.White;
        Tween tween = CreateTween().SetParallel();
        tween.TweenProperty(
                _playerHand,
                "position",
                _playerRestPosition,
                EntranceDuration)
            .SetTrans(Tween.TransitionType.Cubic)
            .SetEase(Tween.EaseType.Out);
        tween.TweenProperty(
                _merchantHand,
                "position",
                _merchantRestPosition,
                EntranceDuration)
            .SetTrans(Tween.TransitionType.Cubic)
            .SetEase(Tween.EaseType.Out);
        await tween.AwaitFinished(this);
    }

    public async Task PlayRound(
        RelicPickingFightMove playerMove,
        RelicPickingFightMove merchantMove)
    {
        _playerHand.Modulate = Colors.White;
        _merchantHand.Modulate = Colors.White;
        _playerHand.Texture = _playerRock;
        _merchantHand.Texture = _merchantRock;

        Tween playerTween = AnimateThrow(
            _playerHand,
            0f,
            -1f,
            GetPlayerTexture(playerMove));
        Tween merchantTween = AnimateThrow(
            _merchantHand,
            Mathf.Pi,
            1f,
            GetMerchantTexture(merchantMove));
        await Task.WhenAll(
            playerTween.AwaitFinished(this),
            merchantTween.AwaitFinished(this));
    }

    public async Task PlayTie()
    {
        Color dimmed = new Color(0.7f, 0.7f, 0.7f, 0.75f);
        Tween dimTween = CreateTween().SetParallel();
        dimTween.TweenProperty(_playerHand, "modulate", dimmed, 0.15f);
        dimTween.TweenProperty(_merchantHand, "modulate", dimmed, 0.15f);
        await dimTween.AwaitFinished(this);

        Tween restoreTween = CreateTween().SetParallel();
        restoreTween.TweenProperty(_playerHand, "modulate", Colors.White, 0.2f);
        restoreTween.TweenProperty(_merchantHand, "modulate", Colors.White, 0.2f);
        await restoreTween.AwaitFinished(this);
    }

    public async Task PlayOutcome(bool playerWon)
    {
        TextureRect loser = playerWon ? _merchantHand : _playerHand;
        Vector2 restingPosition = loser.Position;

        Tween fadeTween = CreateTween();
        fadeTween.TweenProperty(loser, "modulate", new Color(0.45f, 0.45f, 0.45f, 0.45f), 0.45f);

        Tween shakeTween = CreateTween();
        for (int i = 0; i < 6; i++)
        {
            float offset = i % 2 == 0 ? 12f : -12f;
            shakeTween.TweenProperty(loser, "position", restingPosition + Vector2.Right * offset, 0.055f);
        }
        shakeTween.TweenProperty(loser, "position", restingPosition, 0.055f);

        await Task.WhenAll(
            fadeTween.AwaitFinished(this),
            shakeTween.AwaitFinished(this));
        await GetTree().CreateTimer(0.3).AwaitSignal(SceneTreeTimer.SignalName.Timeout, this);
    }

    public async Task PlayExit()
    {
        Tween tween = CreateTween().SetParallel();
        tween.TweenProperty(
                _playerHand,
                "position",
                _playerHiddenPosition,
                ExitDuration)
            .SetTrans(Tween.TransitionType.Cubic)
            .SetEase(Tween.EaseType.In);
        tween.TweenProperty(
                _merchantHand,
                "position",
                _merchantHiddenPosition,
                ExitDuration)
            .SetTrans(Tween.TransitionType.Cubic)
            .SetEase(Tween.EaseType.In);
        tween.TweenProperty(_playerHand, "modulate:a", 0f, ExitDuration);
        tween.TweenProperty(_merchantHand, "modulate:a", 0f, ExitDuration);
        await tween.AwaitFinished(this);
    }

    private void LoadTextures(Player player)
    {
        _playerRock = player.Character.ArmRockTexture;
        _playerPaper = player.Character.ArmPaperTexture;
        _playerScissors = player.Character.ArmScissorsTexture;
        _merchantRock = LoadTexture(MerchantBargainAssets.MerchantRockPath);
        _merchantPaper = LoadTexture(MerchantBargainAssets.MerchantPaperPath);
        _merchantScissors = LoadTexture(MerchantBargainAssets.MerchantScissorsPath);
    }

    private void BuildVisuals(Vector2 viewportSize)
    {
        MerchantBargainHandLayout layout = MerchantBargainAssets.CalculateLayout(viewportSize);
        _merchantRestPosition = layout.MerchantRestPosition;
        _playerRestPosition = layout.PlayerRestPosition;
        _merchantHiddenPosition = layout.MerchantHiddenPosition;
        _playerHiddenPosition = layout.PlayerHiddenPosition;

        _merchantHand = CreateHand(_merchantRock, layout.HandSize);
        _merchantHand.Name = "MerchantHand";
        _merchantHand.Position = _merchantHiddenPosition;
        _merchantHand.Rotation = Mathf.Pi;
        AddChild(_merchantHand);

        _playerHand = CreateHand(_playerRock, layout.HandSize);
        _playerHand.Name = "PlayerHand";
        _playerHand.Position = _playerHiddenPosition;
        AddChild(_playerHand);
    }

    private Tween AnimateThrow(
        TextureRect hand,
        float restingRotation,
        float direction,
        Texture2D finalTexture)
    {
        hand.Rotation = restingRotation;
        float windUpDuration = 0.666f * FightDuration / 3f;
        float returnDuration = 0.333f * FightDuration / 3f;
        float throwAngle = Mathf.Pi / 10f;
        Tween tween = CreateTween();
        for (int i = 0; i < 3; i++)
        {
            tween.TweenProperty(
                    hand,
                    "rotation",
                    restingRotation + direction * throwAngle,
                    windUpDuration)
                .SetTrans(Tween.TransitionType.Linear)
                .SetEase(Tween.EaseType.In);
            tween.TweenProperty(hand, "rotation", restingRotation, returnDuration)
                .SetTrans(Tween.TransitionType.Expo)
                .SetEase(Tween.EaseType.In);
        }
        tween.TweenCallback(Callable.From(() => hand.Texture = finalTexture));
        return tween;
    }

    private Texture2D GetPlayerTexture(RelicPickingFightMove move)
    {
        return move switch
        {
            RelicPickingFightMove.Rock => _playerRock,
            RelicPickingFightMove.Paper => _playerPaper,
            RelicPickingFightMove.Scissors => _playerScissors,
            _ => throw new ArgumentOutOfRangeException(nameof(move), move, null)
        };
    }

    private Texture2D GetMerchantTexture(RelicPickingFightMove move)
    {
        return move switch
        {
            RelicPickingFightMove.Rock => _merchantRock,
            RelicPickingFightMove.Paper => _merchantPaper,
            RelicPickingFightMove.Scissors => _merchantScissors,
            _ => throw new ArgumentOutOfRangeException(nameof(move), move, null)
        };
    }

    private static TextureRect CreateHand(Texture2D texture, Vector2 size)
    {
        return new TextureRect
        {
            Texture = texture,
            ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
            StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered,
            MouseFilter = MouseFilterEnum.Ignore,
            FocusMode = FocusModeEnum.None,
            Size = size,
            PivotOffset = size * 0.5f
        };
    }

    private static Texture2D LoadTexture(string path)
    {
        return ResourceLoader.Load<Texture2D>(path, null, ResourceLoader.CacheMode.Reuse)
            ?? throw new InvalidOperationException($"Merchant bargain texture was not found: {path}");
    }
}
#endif
