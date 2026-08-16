using System.Reflection;
using Godot;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.TreasureRelicPicking;
using STS2_Things.Features.MerchantBargain;

public partial class MerchantBargainProbeNode : Node
{
    public override void _Ready()
    {
        if (OS.GetCmdlineUserArgs().FirstOrDefault() == "visual")
        {
            AddChild(new MerchantBargainVisualProbeNode());
            return;
        }

        try
        {
            VerifyShortfallBoundary();
            VerifyRoundTable();
            VerifySessionState();
            VerifyAssetContract();
            VerifyOverlaySurface();
            VerifyPatchTargets();
            GD.Print("Merchant bargain behavior probe: PASS");
            GetTree().Quit(0);
        }
        catch (Exception exception)
        {
            GD.PushError(exception.ToString());
            GetTree().Quit(1);
        }
    }

    private static void VerifyShortfallBoundary()
    {
        Assert(MerchantBargainRules.MaximumGoldShortfall == 20,
            "Maximum shortfall is not 20 gold.");
        Assert(MerchantBargainRules.TriggerAttempt == 5,
            "The bargain does not trigger on attempt five.");
        Assert(MerchantBargainRules.IsEligibleShortfall(101, 81),
            "A 20-gold shortfall was rejected.");
        Assert(!MerchantBargainRules.IsEligibleShortfall(101, 80),
            "A 21-gold shortfall was accepted.");
        Assert(!MerchantBargainRules.IsEligibleShortfall(100, 100),
            "An affordable item was treated as a shortfall.");
    }

    private static void VerifyRoundTable()
    {
        RelicPickingFightMove[] moves = Enum.GetValues<RelicPickingFightMove>();
        foreach (RelicPickingFightMove move in moves)
        {
            Assert(MerchantBargainRules.EvaluateRound(move, move) ==
                   MerchantBargainRoundResult.Tie,
                $"{move} versus itself did not tie.");
        }

        AssertWinner(RelicPickingFightMove.Paper, RelicPickingFightMove.Rock);
        AssertWinner(RelicPickingFightMove.Scissors, RelicPickingFightMove.Paper);
        AssertWinner(RelicPickingFightMove.Rock, RelicPickingFightMove.Scissors);
    }

    private static void AssertWinner(
        RelicPickingFightMove winningMove,
        RelicPickingFightMove losingMove)
    {
        Assert(MerchantBargainRules.EvaluateRound(winningMove, losingMove) ==
               MerchantBargainRoundResult.PlayerWon,
            $"{winningMove} did not beat {losingMove} for the player.");
        Assert(MerchantBargainRules.EvaluateRound(losingMove, winningMove) ==
               MerchantBargainRoundResult.MerchantWon,
            $"{losingMove} did not lose to {winningMove} for the player.");
    }

    private static void VerifySessionState()
    {
        var entry = new object();
        var otherEntry = new object();
        var session = new MerchantBargainSession<object>();

        Assert(session.RegisterAttempt(entry, isStocked: true, isEligible: false) ==
               MerchantBargainAttemptDisposition.PassThrough,
            "An ineligible click did not pass through.");
        Assert(session.RegisterAttempt(entry, isStocked: false, isEligible: true) ==
               MerchantBargainAttemptDisposition.PassThrough,
            "An out-of-stock click did not pass through.");
        Assert(session.GetEligibleAttemptCount(entry) == 0,
            "Ineligible clicks changed the attempt counter.");

        for (int attempt = 1; attempt < MerchantBargainRules.TriggerAttempt; attempt++)
        {
            Assert(session.RegisterAttempt(entry, isStocked: true, isEligible: true) ==
                   MerchantBargainAttemptDisposition.PassThrough,
                $"Eligible attempt {attempt} triggered early.");
            Assert(session.GetEligibleAttemptCount(entry) == attempt,
                $"Eligible attempt {attempt} was not recorded.");
        }

        Assert(session.RegisterAttempt(entry, isStocked: true, isEligible: true) ==
               MerchantBargainAttemptDisposition.StartFight,
            "The fifth eligible attempt did not start the fight.");
        Assert(session.FightInProgress,
            "The session did not enter the fight-in-progress state.");
        Assert(session.RegisterAttempt(entry, isStocked: true, isEligible: true) ==
               MerchantBargainAttemptDisposition.Suppress,
            "A duplicate click during the fight was not suppressed.");

        session.MarkFightWon(entry, negotiatedPrice: 81);
        session.EndFight();
        Assert(session.WinningPrice == 81,
            "The winning price was not captured at fight resolution.");
        Assert(session.RegisterAttempt(entry, isStocked: true, isEligible: false) ==
               MerchantBargainAttemptDisposition.PurchaseAtNegotiatedPrice,
            "The winning entry did not retain its negotiated purchase offer.");
        Assert(session.RegisterAttempt(otherEntry, isStocked: true, isEligible: true) ==
               MerchantBargainAttemptDisposition.PassThrough,
            "A different entry reused the winning offer.");

        session.MarkPurchaseSucceeded();
        Assert(session.Consumed && session.WinningEntry is null && session.WinningPrice is null,
            "A successful bargain purchase did not consume and clear the offer.");
        Assert(session.RegisterAttempt(entry, isStocked: true, isEligible: true) ==
               MerchantBargainAttemptDisposition.PassThrough,
            "A consumed shop started another bargain.");

        var losingSession = AdvanceToFight(entry);
        losingSession.MarkFightLost();
        losingSession.EndFight();
        Assert(losingSession.Consumed,
            "A lost fight did not consume the shop bargain.");
        Assert(losingSession.RegisterAttempt(entry, isStocked: true, isEligible: true) ==
               MerchantBargainAttemptDisposition.PassThrough,
            "A lost fight allowed another bargain in the same shop.");

        var retrySession = AdvanceToFight(entry);
        retrySession.MarkFightWon(entry, negotiatedPrice: 81);
        retrySession.ResetFightAfterError(entry);
        retrySession.EndFight();
        Assert(retrySession.WinningEntry is null && retrySession.WinningPrice is null,
            "An exception left a stale winning offer behind.");
        Assert(retrySession.GetEligibleAttemptCount(entry) ==
               MerchantBargainRules.TriggerAttempt - 1,
            "An exception did not reset the entry to one click before retry.");
        Assert(retrySession.RegisterAttempt(entry, isStocked: true, isEligible: true) ==
               MerchantBargainAttemptDisposition.StartFight,
            "The post-exception retry did not restart on the next eligible click.");
    }

    private static MerchantBargainSession<object> AdvanceToFight(object entry)
    {
        var session = new MerchantBargainSession<object>();
        for (int attempt = 1; attempt <= MerchantBargainRules.TriggerAttempt; attempt++)
        {
            MerchantBargainAttemptDisposition disposition = session.RegisterAttempt(
                entry,
                isStocked: true,
                isEligible: true);
            MerchantBargainAttemptDisposition expected =
                attempt == MerchantBargainRules.TriggerAttempt
                    ? MerchantBargainAttemptDisposition.StartFight
                    : MerchantBargainAttemptDisposition.PassThrough;
            Assert(disposition == expected,
                $"Unexpected disposition while advancing attempt {attempt}: {disposition}.");
        }
        return session;
    }

    private static void VerifyAssetContract()
    {
        Assert(MerchantBargainAssets.MerchantHandPaths.Count == 3,
            "The merchant hand set is incomplete.");
        Assert(MerchantBargainAssets.PlayerHandPaths.Count == 15,
            "The five-character hand set is incomplete.");
        Assert(MerchantBargainAssets.PreloadPaths.Count == 18 &&
               MerchantBargainAssets.PreloadPaths.Distinct(StringComparer.Ordinal).Count() == 18,
            "The merchant bargain preload set is incomplete or duplicated.");

        string[] characters = ["ironclad", "silent", "defect", "necrobinder", "regent"];
        string[] moves = ["rock", "paper", "scissors"];
        foreach (string character in characters)
        {
            foreach (string move in moves)
            {
                string expected =
                    $"res://images/ui/hands/multiplayer_hand_{character}_{move}.png";
                Assert(MerchantBargainAssets.PlayerHandPaths.Contains(expected),
                    $"Missing preloaded player hand: {expected}");
            }
        }

        MerchantBargainHandLayout layout = MerchantBargainAssets.CalculateLayout(
            new Vector2(2048f, 1152f));
        Assert(layout.HandSize.Y > 1180f && layout.HandSize.X > 415f,
            $"The 2048x1152 bargain hands are still undersized: {layout.HandSize}.");
        Assert(layout.MerchantHiddenPosition.Y + layout.HandSize.Y < 0f,
            "The merchant hand does not begin fully above the viewport.");
        Assert(layout.PlayerHiddenPosition.Y > 1152f,
            "The player hand does not begin fully below the viewport.");
        Assert(layout.MerchantRestPosition.Y + layout.HandSize.Y <
               layout.PlayerRestPosition.Y,
            "The resting hand rectangles overlap at the reveal line.");
    }

    private static void VerifyOverlaySurface()
    {
        Type overlayType = typeof(STS2_ThingsInit).Assembly.GetType(
            "STS2_Things.Features.MerchantBargain.NMerchantBargainRps",
            throwOnError: true)!;
        var overlay = (Control)(Activator.CreateInstance(overlayType, nonPublic: true)
            ?? throw new InvalidOperationException("Could not construct the bargain overlay."));
        try
        {
            MethodInfo buildVisuals = overlayType.GetMethod(
                    "BuildVisuals",
                    BindingFlags.Instance | BindingFlags.NonPublic)
                ?? throw new MissingMethodException(overlayType.FullName, "BuildVisuals");
            buildVisuals.Invoke(overlay, [new Vector2(2048f, 1152f)]);

            Assert(overlay.GetChildCount() == 2,
                $"The bargain overlay exposes {overlay.GetChildCount()} children instead of two hands.");
            Assert(overlay.GetChildren().All(child => child is TextureRect),
                "The bargain overlay still contains a drawable background node.");
            Assert(overlayType.GetMethod("PlayEntrance", BindingFlags.Instance | BindingFlags.Public) != null,
                "The bargain overlay has no entrance animation.");
            Assert(overlayType.GetMethod("PlayExit", BindingFlags.Instance | BindingFlags.Public) != null,
                "The bargain overlay has no exit animation.");
        }
        finally
        {
            overlay.Free();
        }
    }

    private static void VerifyPatchTargets()
    {
        Assembly assembly = typeof(STS2_ThingsInit).Assembly;
        MethodBase purchaseTarget = InvokeTargetMethod(
            assembly,
            "STS2_Things.Features.MerchantBargain.MerchantEntryOnTryPurchaseWrapperPatch");
        Assert(purchaseTarget.DeclaringType == typeof(MerchantEntry) &&
               purchaseTarget.Name == nameof(MerchantEntry.OnTryPurchaseWrapper),
            "Purchase patch resolved to the wrong member.");
        ParameterInfo[] purchaseParameters = purchaseTarget.GetParameters();
        Assert(purchaseParameters.Length == 2 &&
               purchaseParameters[0].ParameterType == typeof(MerchantInventory) &&
               purchaseParameters[1].ParameterType == typeof(bool),
            "Purchase patch resolved to the wrong overload.");

        MethodBase costTarget = InvokeTargetMethod(
            assembly,
            "STS2_Things.Features.MerchantBargain.MerchantEntryCostPatch");
        Assert(costTarget.DeclaringType == typeof(MerchantEntry) &&
               costTarget.Name == "get_Cost",
            "Cost patch did not resolve MerchantEntry.get_Cost.");
    }

    private static MethodBase InvokeTargetMethod(Assembly assembly, string typeName)
    {
        Type patchType = assembly.GetType(typeName, throwOnError: true)!;
        MethodInfo targetMethod = patchType.GetMethod(
            "TargetMethod",
            BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new MissingMethodException(typeName, "TargetMethod");
        return (MethodBase)(targetMethod.Invoke(null, null)
            ?? throw new InvalidOperationException($"{typeName}.TargetMethod returned null."));
    }

    private static void Assert(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }
}
