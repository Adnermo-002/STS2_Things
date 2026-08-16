using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Nodes.Combat;

namespace STS2_Things.Visuals;

public enum LivingRockIdleDirection
{
    LeftToRight,
    RightToLeft
}

public enum LivingRockPunch
{
    Left,
    Right
}

public enum LivingRockTransitionMode
{
    NaturalComplete,
    ManualRewind
}

public readonly record struct LivingRockPunchPlan(
    LivingRockTransitionMode Mode,
    LivingRockIdleDirection ResultIdle);

public static class LivingRockAnimationPlan
{
    public static LivingRockPunchPlan Resolve(
        LivingRockIdleDirection currentIdle,
        LivingRockPunch punch)
    {
        bool sameDirection = punch == LivingRockPunch.Left
            ? currentIdle == LivingRockIdleDirection.LeftToRight
            : currentIdle == LivingRockIdleDirection.RightToLeft;
        var mode = sameDirection
            ? LivingRockTransitionMode.ManualRewind
            : LivingRockTransitionMode.NaturalComplete;
        var resultIdle = punch == LivingRockPunch.Left
            ? LivingRockIdleDirection.LeftToRight
            : LivingRockIdleDirection.RightToLeft;
        return new LivingRockPunchPlan(mode, resultIdle);
    }

    public static float RewindTrackTime(float currentTime, double delta, float rewindRate)
    {
        return Mathf.Max(0f, currentTime - (float)(delta * rewindRate));
    }
}

[GlobalClass]
public partial class NCaveGodVisuals : NCreatureVisuals
{
    public const string LeftPunchTrigger = "LivingRockLeftPunch";
    public const string RightPunchTrigger = "LivingRockRightPunch";
    public const string LeftToRightAnimation = "main_01_left_to_right";
    public const string RightToLeftAnimation = "main_01_right_to_left";
    public const string LeftPunchAnimation = "leftpunch";
    public const string RightPunchAnimation = "rightpunch";

    private const float RewindRate = 8f;
    private const float EndEpsilon = 0.002f;

    private enum Phase
    {
        WaitingForSpine,
        Idle,
        AwaitingNaturalCompletion,
        Rewinding,
        Punching,
        Dead
    }

    private MegaAnimationState? _animationState;
    private MegaSkeleton? _skeleton;
    private Phase _phase = Phase.WaitingForSpine;
    private LivingRockIdleDirection _idleDirection = LivingRockIdleDirection.LeftToRight;
    private LivingRockPunch? _pendingPunch;
    private LivingRockPunch? _queuedPunch;
    private LivingRockPunch? _activePunch;

    public LivingRockIdleDirection IdleDirection => _idleDirection;
    public bool IsRewinding => _phase == Phase.Rewinding;
    public string CurrentPhase => _phase.ToString();

    public override void _Ready()
    {
        base._Ready();
        SetProcess(true);
    }

    public override void _Process(double delta)
    {
        if (IsCreatureDead())
        {
            _phase = Phase.Dead;
            SetProcess(false);
            return;
        }
        if (!EnsureSpineReady())
            return;

        switch (_phase)
        {
            case Phase.WaitingForSpine:
                StartIdle(LivingRockIdleDirection.LeftToRight);
                break;
            case Phase.Idle:
                if (TrackComplete())
                {
                    StartIdle(_idleDirection == LivingRockIdleDirection.LeftToRight
                        ? LivingRockIdleDirection.RightToLeft
                        : LivingRockIdleDirection.LeftToRight);
                }
                break;
            case Phase.AwaitingNaturalCompletion:
                if (TrackComplete())
                {
                    SnapCurrentTrackToEnd();
                    StartPunch(_pendingPunch!.Value);
                }
                break;
            case Phase.Rewinding:
                RewindTrack(delta);
                break;
            case Phase.Punching:
                if (TrackComplete())
                {
                    SnapCurrentTrackToEnd();
                    LivingRockPunch punch = _activePunch!.Value;
                    _activePunch = null;
                    StartIdle(punch == LivingRockPunch.Left
                        ? LivingRockIdleDirection.LeftToRight
                        : LivingRockIdleDirection.RightToLeft);
                }
                break;
        }
    }

    public override void _ExitTree()
    {
#if !STS2_V107_1
        _animationState?.Dispose();
        _skeleton?.Dispose();
#endif
        _animationState = null;
        _skeleton = null;
        base._ExitTree();
    }

    public void TriggerPunch(string trigger)
    {
        LivingRockPunch? punch = trigger switch
        {
            LeftPunchTrigger => LivingRockPunch.Left,
            RightPunchTrigger => LivingRockPunch.Right,
            _ => null
        };
        if (!punch.HasValue)
            return;
        if (_phase is Phase.Punching or Phase.AwaitingNaturalCompletion or Phase.Rewinding)
        {
            _queuedPunch = punch;
            return;
        }
        if (!EnsureSpineReady())
        {
            _queuedPunch = punch;
            return;
        }
        BeginPunchRequest(punch.Value);
    }

    private bool EnsureSpineReady()
    {
        if (_animationState != null && _skeleton != null)
            return true;
        if (SpineBody == null || !SpineBody.IsAnimationStateReady())
            return false;
        _animationState = SpineBody.TryGetAnimationState();
        _skeleton = SpineBody.GetSkeleton();
        if (_animationState == null || _skeleton == null)
        {
#if !STS2_V107_1
            _animationState?.Dispose();
            _skeleton?.Dispose();
#endif
            _animationState = null;
            _skeleton = null;
            return false;
        }
        if (_phase == Phase.WaitingForSpine)
            StartIdle(LivingRockIdleDirection.LeftToRight);
        if (_queuedPunch.HasValue && _phase == Phase.Idle)
        {
            LivingRockPunch queued = _queuedPunch.Value;
            _queuedPunch = null;
            BeginPunchRequest(queued);
        }
        return true;
    }

    private void BeginPunchRequest(LivingRockPunch punch)
    {
        if (_phase != Phase.Idle)
        {
            _queuedPunch = punch;
            return;
        }
        _idleDirection = ResolveCurrentIdleDirection();
        LivingRockPunchPlan plan = LivingRockAnimationPlan.Resolve(_idleDirection, punch);
        _pendingPunch = punch;
        if (plan.Mode == LivingRockTransitionMode.ManualRewind)
        {
            SetTrackTimeScale(0f);
            _phase = Phase.Rewinding;
        }
        else
        {
            SetTrackTimeScale(1f);
            _phase = Phase.AwaitingNaturalCompletion;
        }
    }

    private void StartIdle(LivingRockIdleDirection direction)
    {
        string animation = direction == LivingRockIdleDirection.LeftToRight
            ? LeftToRightAnimation
            : RightToLeftAnimation;
        SetAnimation(animation);
        _idleDirection = direction;
        _pendingPunch = null;
        _phase = Phase.Idle;
        if (_queuedPunch.HasValue)
        {
            LivingRockPunch queued = _queuedPunch.Value;
            _queuedPunch = null;
            BeginPunchRequest(queued);
        }
    }

    private void StartPunch(LivingRockPunch punch)
    {
        string animation = punch == LivingRockPunch.Left
            ? LeftPunchAnimation
            : RightPunchAnimation;
        SetAnimation(animation);
        _pendingPunch = null;
        _activePunch = punch;
        _phase = Phase.Punching;
    }

    private void SetAnimation(string animation)
    {
        if (_animationState == null || SpineBody == null || !SpineBody.HasAnimation(animation))
            return;
        _animationState.SetAnimation(animation, false, 0);
        SetCurrentTrackMixDuration(0f);
        SetTrackTimeScale(1f);
        ApplyPose();
    }

    private bool TrackComplete()
    {
        if (_animationState == null)
            return false;
        MegaTrackEntry? track = _animationState.GetCurrent(0);
        if (track == null)
            return false;
#if !STS2_V107_1
        using (track)
        {
            return track.IsComplete() ||
                   track.GetTrackTime() >= track.GetAnimationEnd() - EndEpsilon;
        }
#else
        return track.IsComplete() ||
               track.GetTrackTime() >= track.GetAnimationEnd() - EndEpsilon;
#endif
    }

    private void SetTrackTimeScale(float scale)
    {
        if (_animationState == null)
            return;
        MegaTrackEntry? track = _animationState.GetCurrent(0);
        if (track == null)
            return;
#if !STS2_V107_1
        using (track)
            track.SetTimeScale(scale);
#else
        track.SetTimeScale(scale);
#endif
    }

    private void RewindTrack(double delta)
    {
        if (_animationState == null || _skeleton == null || _pendingPunch == null)
            return;
        MegaTrackEntry? track = _animationState.GetCurrent(0);
        if (track == null)
            return;
        bool reachedStart;
#if !STS2_V107_1
        using (track)
        {
            float nextTime = LivingRockAnimationPlan.RewindTrackTime(
                track.GetTrackTime(), delta, RewindRate);
            track.SetTrackTime(nextTime);
            reachedStart = nextTime <= EndEpsilon;
        }
#else
        float nextTime = LivingRockAnimationPlan.RewindTrackTime(
            track.GetTrackTime(), delta, RewindRate);
        track.SetTrackTime(nextTime);
        reachedStart = nextTime <= EndEpsilon;
#endif
        _animationState.Update(0f);
        _animationState.Apply(_skeleton);
        if (reachedStart)
        {
            SnapCurrentTrackToStart();
            StartPunch(_pendingPunch.Value);
        }
    }

    private void SnapCurrentTrackToStart()
    {
        SetCurrentTrackTime(0f);
    }

    private void SnapCurrentTrackToEnd()
    {
        if (_animationState == null)
            return;
        MegaTrackEntry? track = _animationState.GetCurrent(0);
        if (track == null)
            return;
#if !STS2_V107_1
        using (track)
            SetCurrentTrackTime(track.GetAnimationEnd());
#else
        SetCurrentTrackTime(track.GetAnimationEnd());
#endif
    }

    private void SetCurrentTrackTime(float time)
    {
        if (_animationState == null || _skeleton == null)
            return;
        MegaTrackEntry? track = _animationState.GetCurrent(0);
        if (track == null)
            return;
#if !STS2_V107_1
        using (track)
            track.SetTrackTime(time);
#else
        track.SetTrackTime(time);
#endif
        ApplyPose();
    }

    private void SetCurrentTrackMixDuration(float duration)
    {
        if (_animationState == null)
            return;
        MegaTrackEntry? track = _animationState.GetCurrent(0);
        if (track == null)
            return;
#if !STS2_V107_1
        using (track)
            track.SetMixDuration(duration);
#else
        track.SetMixDuration(duration);
#endif
    }

    private void ApplyPose()
    {
        if (_animationState != null && _skeleton != null)
        {
            _animationState.Update(0f);
            _animationState.Apply(_skeleton);
        }
    }

    private LivingRockIdleDirection ResolveCurrentIdleDirection()
    {
        if (_animationState?.GetCurrentAnimationName(0) == RightToLeftAnimation)
            return LivingRockIdleDirection.RightToLeft;
        return LivingRockIdleDirection.LeftToRight;
    }

    private bool IsCreatureDead()
    {
        return GetParent() is NCreature creature && creature.Entity.IsDead;
    }
}
