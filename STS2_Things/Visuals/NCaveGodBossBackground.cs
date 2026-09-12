using System;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Logging;

namespace STS2_Things.Visuals;

/// <summary>
/// Background controller for CaveGod boss encounter.
/// Manages the full-screen SpineSprite animation tracks in the background layer,
/// coordinating combat actions (slams, sweeps, jabs, hit recoils, angry phase)
/// with ThingsCaveGod monster model.
/// </summary>
[GlobalClass]
public partial class NCaveGodBossBackground : Node2D
{
    private const int MainTrack = 0;
    private const int ReactionTrack = 1;

    private MegaSprite? _animController;
    private bool _isAngry;
    private CancellationTokenSource? _cts;

    public bool IsAngry => _isAngry;

    public override void _ExitTree()
    {
        _cts?.Cancel();
        _cts?.Dispose();
        _cts = null;
    }

    public override void _Ready()
    {
        Node2D? visualsNode = GetNodeOrNull<Node2D>("%Visuals");
        if (visualsNode == null)
        {
            Log.Error("[CaveGodBackground] Failed to find '%Visuals' node in hierarchy.");
            return;
        }

        _animController = new MegaSprite(visualsNode);
        this.RunWhenSpineReady(_animController, state =>
        {
            state.SetAnimation("idle_loop", loop: true, MainTrack);
            Log.Info("[CaveGodBackground] CaveGod Spine animation state initialized to 'idle_loop'.");
        });
    }

    public void SetAngry(bool angry)
    {
        if (_isAngry == angry || _animController == null)
            return;

        _isAngry = angry;
        MegaAnimationState? state = _animController.TryGetAnimationState();
        if (state == null)
            return;

        string targetIdle = _isAngry ? "angry_idle_loop" : "idle_loop";
        if (_animController.HasAnimation(targetIdle))
        {
            state.SetAnimation(targetIdle, loop: true, MainTrack);
            Log.Info($"[CaveGodBackground] CaveGod transitioned to {(angry ? "ANGRY" : "NORMAL")} idle.");
        }
    }

    public void PlayCentralSlam()
    {
        string anim = _isAngry ? "central_slam_angry" : "central_slam";
        PlayMainAnimation(anim);
    }

    public void PlayFrontSweep()
    {
        string anim = _isAngry ? "front_sweep_angry" : "front_sweep";
        PlayMainAnimation(anim);
    }

    public void PlayAlternatingJabs()
    {
        PlayMainAnimation("alternating_jabs");
    }

    public void PlayDoubleFistCrush()
    {
        PlayMainAnimation("double_fist_crush");
    }

    public void PlayGrabPlayer()
    {
        PlayMainAnimation("grab_player");
    }

    public void PlayHitRecoil()
    {
        if (_animController == null)
            return;

        MegaAnimationState? state = _animController.TryGetAnimationState();
        if (state == null)
            return;

        string hurtAnim = _isAngry ? "hit_recoil_angry" : "hit_recoil";
        if (_animController.HasAnimation(hurtAnim))
        {
            state.SetAnimation(hurtAnim, loop: false, ReactionTrack);
        }
    }

    public void PlayDie()
    {
        if (_animController == null)
            return;

        MegaAnimationState? state = _animController.TryGetAnimationState();
        if (state == null)
            return;

        if (_animController.HasAnimation("die"))
        {
            state.SetAnimation("die", loop: false, MainTrack);
        }
    }

    private void PlayMainAnimation(string animName)
    {
        if (_animController == null)
            return;

        MegaAnimationState? state = _animController.TryGetAnimationState();
        if (state == null)
            return;

        if (_animController.HasAnimation(animName))
        {
            state.SetAnimation(animName, loop: false, MainTrack);
            string idle = _isAngry ? "angry_idle_loop" : "idle_loop";
            state.AddAnimation(idle, delay: 0f, loop: true, MainTrack);
            Log.Info($"[CaveGodBackground] Playing action animation: {animName}");
        }
        else
        {
            Log.Warn($"[CaveGodBackground] Animation '{animName}' not found in skeleton, keeping idle.");
        }
    }
}
