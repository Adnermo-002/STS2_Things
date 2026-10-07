using System.Reflection;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Models;
using STS2_Things.Audio;
using STS2_Things.Hooks;
using STS2_Things.Monsters;
using STS2_Things.Visuals;

public partial class DepthsProbeNode
{
    private static readonly List<(string Path, bool AllowEnding)> DeathAudioCalls = [];
    private static bool AllowDeathAudioInFixture(ref bool __result) { __result = true; return false; }
    private static bool CaptureDeathAudio(string resPath, bool allowCombatEnding)
    {
        DeathAudioCalls.Add((resPath, allowCombatEnding));
        return false;
    }
    private static void VerifyBorrowedDeathAudio()
    {
        var host = new Harmony("DepthsProbe.BorrowedDeathAudio");
        host.Patch(AccessTools.Method(typeof(SfxHooks), "CanPlayDeathAudio"),
            prefix: new HarmonyMethod(typeof(DepthsProbeNode), nameof(AllowDeathAudioInFixture)));
        host.Patch(AccessTools.Method(typeof(NativeSfxPlayer), nameof(NativeSfxPlayer.Play)),
            prefix: new HarmonyMethod(typeof(DepthsProbeNode), nameof(CaptureDeathAudio)));
        try
        {
            foreach (var monster in new MonsterModel[] { ModelDb.Monster<WaterSponge>(), ModelDb.Monster<CaveMaw>(),
                         ModelDb.Monster<SanguineLeech>(), ModelDb.Monster<ReverseSalamander>(), ModelDb.Monster<GravetideSlug>() })
            {
                DeathAudioCalls.Clear();
                Assert(!SfxHooks.SfxCmdPlayDeathPatch.Prefix(monster), "Bundled death sound must bypass FMOD: " + monster.Id);
                Assert(DeathAudioCalls.SequenceEqual(new[] { ("res://sfx/gravetide_slug/gravetide_slug_die", true) }),
                    "Exactly one native death sound, including final-enemy death: " + monster.Id);
            }
            DeathAudioCalls.Clear();
            Assert(SfxHooks.SfxCmdPlayDeathPatch.Prefix(ModelDb.Monster<LanternFish>()) && DeathAudioCalls.Count == 0,
                "Borrowed vanilla FMOD sounds still use their original playback.");
        }
        finally { host.UnpatchAll(host.Id); }
        GD.Print("PASS shared native death audio routing and ordinary FMOD fallback.");
    }

    private async Task VerifySpongeSprayRendering()
    {
        // Exercise the production _Draw, including the sub-frame launch and tail.
        // The runner treats any renderer error on stderr as a failure.
        var view = new SubViewport { Size = new Vector2I(600, 400), Disable3D = true,
            RenderTargetUpdateMode = SubViewport.UpdateMode.Always };
        AddChild(view);
        var jets = new List<SpongeJetRegressionNode>();
        foreach (float pixel in new[] { .25f, 1f, 4f })
        foreach (Vector2 target in new[] { new Vector2(-200, 0), new Vector2(-800, 120),
                     new Vector2(-2200, 120), new Vector2(-1500, -600) })
        {
            var jet = new SpongeJetRegressionNode { Position = new Vector2(560, 200), Scale = new Vector2(.2f, .2f) };
            jet.SetPose(WaterSponge.SprayContact - .14f, target, pixel);
            view.AddChild(jet);
            jets.Add(jet);
        }
        float launch = WaterSponge.SprayContact - .14f;
        var times = new[] { launch + .00001f, launch + .0001f, launch + .0005f,
            launch + .001f, launch + .002f, launch + .004f, launch + .008f,
            launch + .016f, launch + .025f, launch + .04f, launch + .08f, launch + .14f,
            .85f, .95f, 1.05f, 1.15f, 1.159f, 1.1599f, 1.16f, 1.2f, 1.23f };
        foreach (float time in times)
        {
            foreach (var jet in jets) jet.SetTime(time);
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            RenderingServer.ForceDraw();
        }
        view.Free();
        await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
        GD.Print($"PASS {jets.Count * times.Length} production sponge jet draw poses (launch/tail, target direction, scale).");
        Assert(true, "Production water-jet render sweep completes; stderr must be clean.");
    }
}

// Bypass only Spine timing/target discovery; retain production drawing unchanged.
public partial class SpongeJetRegressionNode : NSpongeWaterJet
{
    private const BindingFlags Flags = BindingFlags.NonPublic | BindingFlags.Instance;
    private static readonly FieldInfo TimeField = typeof(NSpongeWaterJet).GetField("_time", Flags)!;
    public override void _Ready() { }
    public override void _Process(double delta) { }
    public void SetPose(float time, Vector2 target, float pixel)
    {
        typeof(NSpongeWaterJet).GetField("_pixel", Flags)!.SetValue(this, pixel);
        var targets = (List<Vector2>)typeof(NSpongeWaterJet).GetField("_targets", Flags)!.GetValue(this)!;
        targets.Add(target);
        SetTime(time);
    }
    public void SetTime(float time) { TimeField.SetValue(this, time); QueueRedraw(); }
}
