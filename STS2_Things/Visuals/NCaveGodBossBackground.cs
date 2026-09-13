using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;

namespace STS2_Things.Visuals;

/// <summary>
/// Dual-pass background controller for Cave God boss encounter.
/// Manages two lock-stepped SpineSprite rigs:
/// 1. CaveGodBody: Rendered behind the basalt platform foreground layer with all arm/fist slots masked transparent.
/// 2. CaveGodArms: Rendered in front of the platform foreground layer with all body/crystal/beard slots masked transparent.
/// This creates an authentic 3D sandwich occlusion depth where the boss's colossal body emerges from the lava behind
/// the circular platform, while its massive stone fists rest and strike on top of the front edge without occlusion.
/// </summary>
[GlobalClass]
public partial class NCaveGodBossBackground : Node2D
{
    private const int MainTrack = 0;
    private const int ReactionTrack = 1;

    private static readonly string[] ArmSlotNames =
    [
        "arm1_2_back", "arm1_2_back_red", "arm1_1", "arm2_1",
        "arm1_2", "arm1_2_red", "arm1_3", "arm2_2", "arm2_2_red", "arm2_3"
    ];

    private static readonly string[] BodySlotNames =
    [
        "body_bottom", "body", "body_red", "neck", "neck_red",
        "head", "head_red", "eyes", "eyes_red", "beard3", "beard3_red",
        "beard2", "beard2_red", "beard1", "beard1_red", "crastalls_roof",
        "crastalls_roof_red", "horn1", "horn1_red", "horn2", "horn2_red",
        "head_skale", "head_skale_red", "horizon"
    ];

    private static readonly string[] RedSlotNames =
    [
        "arm1_2_back_red", "arm1_2_red", "arm2_2_red",
        "beard1_red", "beard2_red", "beard3_red",
        "body_red", "crastalls_roof_red", "eyes_red",
        "head_red", "head_skale_red", "horn1_red", "horn2_red", "neck_red"
    ];

    private static readonly Color TransparentColor = new(1f, 1f, 1f, 0f);

    private MegaSprite? _bodyController;
    private MegaSprite? _armsController;
    private readonly List<GodotObject> _bodyMaskSlots = new();
    private readonly List<GodotObject> _armsMaskSlots = new();
    private readonly List<GodotObject> _bodyRedSlots = new();
    private readonly List<GodotObject> _armsRedSlots = new();

    private readonly List<(NCreature node, Vector2 origPos, float origRot, Vector2 origScale)> _capturedPlayers = new();
    private bool _isAngry;
    private CancellationTokenSource? _cts;

    public bool IsAngry => _isAngry;

    public override void _ExitTree()
    {
        RestoreCapturedPlayersInstantly();
        _cts?.Cancel();
        _cts?.Dispose();
        _cts = null;
    }

    public override void _Ready()
    {
        Node2D? bodyNode = GetNodeOrNull<Node2D>("%CaveGodBody") ?? GetNodeOrNull<Node2D>("CaveGodBody");
        Node2D? armsNode = GetNodeOrNull<Node2D>("%CaveGodArms") ?? GetParent()?.GetNodeOrNull<Node2D>("%CaveGodArms") ?? GetParent()?.GetNodeOrNull<Node2D>("CaveGodArms");

        if (bodyNode == null || armsNode == null)
        {
            Log.Error($"[CaveGodBackground] Setup failed: bodyNode={(bodyNode != null)}, armsNode={(armsNode != null)}");
            return;
        }

        _bodyController = new MegaSprite(bodyNode);
        _armsController = new MegaSprite(armsNode);

        SetupBodySprite(_bodyController);
        SetupArmsSprite(_armsController);

        Callable.From(AlignStageAndPlayers).CallDeferred();

        Log.Info("[CaveGodBackground] Dual-pass CaveGod Spine controllers initialized.");
    }

    /// <summary>
    /// Aligns the player battle formation onto the central basalt cliff stage.
    /// Shifts AllyContainer +60px down to perfectly meet Cave God's crushing fists.
    /// </summary>
    public void AlignStageAndPlayers()
    {
        Control? allyContainer = NCombatRoom.Instance?.GetNodeOrNull<Control>("%AllyContainer");
        if (allyContainer != null && !allyContainer.HasMeta("CaveGodStageAligned"))
        {
            allyContainer.SetMeta("CaveGodStageAligned", true);
            allyContainer.Position = new Vector2(allyContainer.Position.X, allyContainer.Position.Y + 60f);
            Log.Info($"[CaveGodBackground] AllyContainer aligned to central stage (Y + 60px -> {allyContainer.Position.Y}).");
        }
    }

    private void SetupBodySprite(MegaSprite sprite)
    {
        this.RunWhenSpineReady(sprite, state =>
        {
            state.SetAnimation("idle_front", loop: true, MainTrack);
            MegaSkeleton? skel = sprite.GetSkeleton();
            if (skel != null)
            {
                foreach (string name in ArmSlotNames)
                {
                    Variant slotVar = skel.BoundObject.Call("find_slot", name);
                    if (slotVar.AsGodotObject() is GodotObject slotObj)
                    {
                        _bodyMaskSlots.Add(slotObj);
                    }
                }
                foreach (string name in RedSlotNames)
                {
                    Variant slotVar = skel.BoundObject.Call("find_slot", name);
                    if (slotVar.AsGodotObject() is GodotObject slotObj)
                    {
                        _bodyRedSlots.Add(slotObj);
                    }
                }
            }

            sprite.ConnectBeforeWorldTransformsChange(Callable.From((Variant _) =>
            {
                for (int i = 0; i < _bodyMaskSlots.Count; i++)
                {
                    _bodyMaskSlots[i].Call("set_color", TransparentColor);
                }
                if (!_isAngry)
                {
                    for (int i = 0; i < _bodyRedSlots.Count; i++)
                    {
                        _bodyRedSlots[i].Call("set_color", TransparentColor);
                    }
                }
            }));
            Log.Info($"[CaveGodBackground] Body skeleton initialized: {_bodyMaskSlots.Count} arm slots masked transparent, {_bodyRedSlots.Count} red slots tracked.");
        });
    }

    private void SetupArmsSprite(MegaSprite sprite)
    {
        this.RunWhenSpineReady(sprite, state =>
        {
            state.SetAnimation("idle_front", loop: true, MainTrack);
            MegaSkeleton? skel = sprite.GetSkeleton();
            if (skel != null)
            {
                foreach (string name in BodySlotNames)
                {
                    Variant slotVar = skel.BoundObject.Call("find_slot", name);
                    if (slotVar.AsGodotObject() is GodotObject slotObj)
                    {
                        _armsMaskSlots.Add(slotObj);
                    }
                }
                foreach (string name in RedSlotNames)
                {
                    Variant slotVar = skel.BoundObject.Call("find_slot", name);
                    if (slotVar.AsGodotObject() is GodotObject slotObj)
                    {
                        _armsRedSlots.Add(slotObj);
                    }
                }
            }

            sprite.ConnectBeforeWorldTransformsChange(Callable.From((Variant _) =>
            {
                for (int i = 0; i < _armsMaskSlots.Count; i++)
                {
                    _armsMaskSlots[i].Call("set_color", TransparentColor);
                }
                if (!_isAngry)
                {
                    for (int i = 0; i < _armsRedSlots.Count; i++)
                    {
                        _armsRedSlots[i].Call("set_color", TransparentColor);
                    }
                }
            }));
            Log.Info($"[CaveGodBackground] Arms skeleton initialized: {_armsMaskSlots.Count} body slots masked transparent, {_armsRedSlots.Count} red slots tracked.");
        });
    }

    public void SetAngry(bool angry)
    {
        if (_isAngry == angry)
            return;

        _isAngry = angry;
        string targetIdle = _isAngry ? "idle_front_angry" : "idle_front";

        SetTrackAnimationBoth(targetIdle, loop: true, MainTrack);
        Log.Info($"[CaveGodBackground] CaveGod transitioned to {(angry ? "ANGRY" : "NORMAL")} idle ({targetIdle}).");
    }

    /// <summary>
    /// Starts attack animation without blocking. The monster move logic orchestrates
    /// precise impact frames (e.g. 1.88s for central_slam, 0.64s/1.34s/2.32s for jabs)
    /// and recovery phases directly.
    /// </summary>
    public void StartAttackAnim(string animBase)
    {
        _cts?.Cancel();
        _cts?.Dispose();
        _cts = new CancellationTokenSource();

        string anim = animBase;
        if (_isAngry)
        {
            string angryCandidate = animBase + "_angry";
            if (_bodyController != null && _bodyController.HasAnimation(angryCandidate))
            {
                anim = angryCandidate;
            }
        }
        else
        {
            if (anim.EndsWith("_angry"))
            {
                anim = anim.Substring(0, anim.Length - "_angry".Length);
            }
        }

        string idleAnim = _isAngry ? "idle_front_angry" : "idle_front";

        SetTrackAnimationBoth(anim, loop: false, MainTrack);
        AddTrackAnimationBoth(idleAnim, delay: 0f, loop: true, MainTrack);
        Log.Info($"[CaveGodBackground] Started attack animation: {anim} (isAngry={_isAngry})");
    }

    public async Task PlayAttackAnim(string animBase, float duration)
    {
        StartAttackAnim(animBase);
        if (duration > 0f)
        {
            await Cmd.Wait(duration, _cts?.Token ?? CancellationToken.None);
        }
    }

    public void PlayHurtAnim()
    {
        string hurtAnim = _isAngry ? "hit_recoil_angry" : "hit_recoil";
        SetTrackAnimationBoth(hurtAnim, loop: false, ReactionTrack);
        AddEmptyReactionAnimation();
    }

    public void PlayBodyDeathAnim()
    {
        string deathAnim = _isAngry ? "hide_angry" : "hide";
        SetTrackAnimationBoth(deathAnim, loop: false, MainTrack);
        Log.Info($"[CaveGodBackground] Playing CaveGod body retreat/death animation: {deathAnim}");
    }

    private void SetTrackAnimationBoth(string animName, bool loop, int track)
    {
        MegaAnimationState? bodyState = _bodyController?.TryGetAnimationState();
        MegaAnimationState? armsState = _armsController?.TryGetAnimationState();

        if (bodyState != null && (_bodyController?.HasAnimation(animName) ?? false))
        {
            bodyState.SetAnimation(animName, loop, track);
        }
        if (armsState != null && (_armsController?.HasAnimation(animName) ?? false))
        {
            armsState.SetAnimation(animName, loop, track);
        }
    }

    private void AddTrackAnimationBoth(string animName, float delay, bool loop, int track)
    {
        MegaAnimationState? bodyState = _bodyController?.TryGetAnimationState();
        MegaAnimationState? armsState = _armsController?.TryGetAnimationState();

        if (bodyState != null && (_bodyController?.HasAnimation(animName) ?? false))
        {
            bodyState.AddAnimation(animName, delay, loop, track);
        }
        if (armsState != null && (_armsController?.HasAnimation(animName) ?? false))
        {
            armsState.AddAnimation(animName, delay, loop, track);
        }
    }

    private void AddEmptyReactionAnimation()
    {
        _bodyController?.TryGetAnimationState()?.AddEmptyAnimation(ReactionTrack);
        _armsController?.TryGetAnimationState()?.AddEmptyAnimation(ReactionTrack);
    }

    /// <summary>
    /// Lifts players up into the air during Cave God's grab move.
    /// Arranges multiple players tightly clustered so they do not overlap.
    /// </summary>
    public async Task LiftPlayersToAir(IReadOnlyList<Creature> targets, float duration = 0.70f)
    {
        _capturedPlayers.Clear();
        NCombatRoom? combatRoom = NCombatRoom.Instance;
        if (combatRoom == null) return;

        foreach (Creature target in targets)
        {
            NCreature? node = combatRoom.GetCreatureNode(target);
            if (node != null && GodotObject.IsInstanceValid(node))
            {
                _capturedPlayers.Add((node, node.Position, node.Rotation, node.Scale));
            }
        }

        if (_capturedPlayers.Count == 0) return;

        Tween tween = combatRoom.CreateTween().SetParallel().SetEase(Tween.EaseType.Out).SetTrans(Tween.TransitionType.Quad);
        for (int i = 0; i < _capturedPlayers.Count; i++)
        {
            (NCreature node, Vector2 origPos, _, _) = _capturedPlayers[i];
            node.AnimDisableUi();

            Vector2 clusterOffset = GetClusterOffset(i, _capturedPlayers.Count);
            // Converge X towards center while lifting Y up into Cave God's raised fist
            Vector2 targetPos = new Vector2(origPos.X * 0.35f, origPos.Y - 420f) + clusterOffset;
            float tilt = GetClusterTilt(i, _capturedPlayers.Count);

            tween.TweenProperty(node, "position", targetPos, duration);
            tween.TweenProperty(node, "rotation", tilt, duration);

            node.SetAnimationTrigger("Hit");
        }

        await Cmd.Wait(duration);
    }

    /// <summary>
    /// Drops players back to their original stage positions.
    /// If isSlam is true, slams down violently with expo ease and damage impact.
    /// If isSlam is false, drops back safely with bounce ease.
    /// </summary>
    public async Task DropPlayersToGround(bool isSlam)
    {
        if (_capturedPlayers.Count == 0) return;
        NCombatRoom? combatRoom = NCombatRoom.Instance;
        if (combatRoom == null)
        {
            RestoreCapturedPlayersInstantly();
            return;
        }

        float duration = isSlam ? 0.15f : 0.35f;
        Tween.TransitionType trans = isSlam ? Tween.TransitionType.Expo : Tween.TransitionType.Bounce;
        Tween.EaseType ease = isSlam ? Tween.EaseType.In : Tween.EaseType.Out;

        Tween tween = combatRoom.CreateTween().SetParallel().SetEase(ease).SetTrans(trans);
        foreach ((NCreature node, Vector2 origPos, float origRot, Vector2 origScale) in _capturedPlayers)
        {
            if (GodotObject.IsInstanceValid(node))
            {
                tween.TweenProperty(node, "position", origPos, duration);
                tween.TweenProperty(node, "rotation", origRot, duration);
                tween.TweenProperty(node, "scale", origScale, duration);
            }
        }

        await Cmd.Wait(duration);

        RestoreCapturedPlayersInstantly();
    }

    /// <summary>
    /// Instantly restores all captured players to their original positions and state.
    /// Guaranteed to be called on room exit, death, or error to prevent permanent coordinate drift.
    /// </summary>
    public void RestoreCapturedPlayersInstantly()
    {
        foreach ((NCreature node, Vector2 origPos, float origRot, Vector2 origScale) in _capturedPlayers)
        {
            if (GodotObject.IsInstanceValid(node))
            {
                node.Position = origPos;
                node.Rotation = origRot;
                node.Scale = origScale;
                node.AnimEnableUi();
                node.SetAnimationTrigger("Idle");
            }
        }
        _capturedPlayers.Clear();
    }

    private static Vector2 GetClusterOffset(int index, int total)
    {
        if (total <= 1) return Vector2.Zero;
        if (total == 2)
        {
            return index == 0 ? new Vector2(-40f, -10f) : new Vector2(40f, 10f);
        }
        if (total == 3)
        {
            return index switch
            {
                0 => new Vector2(0f, -35f),
                1 => new Vector2(-45f, 15f),
                _ => new Vector2(45f, 15f)
            };
        }
        return index switch
        {
            0 => new Vector2(-35f, -30f),
            1 => new Vector2(35f, -30f),
            2 => new Vector2(-50f, 20f),
            _ => new Vector2(50f, 20f)
        };
    }

    private static float GetClusterTilt(int index, int total)
    {
        if (total <= 1) return 0f;
        if (total == 2) return index == 0 ? 0.15f : -0.15f;
        if (total == 3) return index == 0 ? 0f : (index == 1 ? 0.18f : -0.18f);
        return (index % 2 == 0) ? 0.12f : -0.12f;
    }

    /// <summary>
    /// Pauses Cave God's grab animation at apex (t = 2.20s) so the giant fist remains
    /// suspended in the air holding the players while they choose cards and attack the claw.
    /// </summary>
    public void HoldGrabAnim()
    {
        using MegaTrackEntry? trackBody = _bodyController?.TryGetAnimationState()?.GetCurrent(MainTrack);
        trackBody?.SetTimeScale(0f);
        using MegaTrackEntry? trackArms = _armsController?.TryGetAnimationState()?.GetCurrent(MainTrack);
        trackArms?.SetTimeScale(0f);
        Log.Info("[CaveGodBackground] Grab animation held at apex.");
    }

    /// <summary>
    /// Resumes Cave God's slam animation from t = 2.90s at full speed, delivering the downward slam.
    /// </summary>
    public void ResumeSlamAnim()
    {
        using (MegaTrackEntry? trackBody = _bodyController?.TryGetAnimationState()?.GetCurrent(MainTrack))
        {
            if (trackBody != null)
            {
                trackBody.SetTrackTime(2.90f);
                trackBody.SetTimeScale(1f);
            }
        }
        using (MegaTrackEntry? trackArms = _armsController?.TryGetAnimationState()?.GetCurrent(MainTrack))
        {
            if (trackArms != null)
            {
                trackArms.SetTrackTime(2.90f);
                trackArms.SetTimeScale(1f);
            }
        }
        Log.Info("[CaveGodBackground] Resumed slam animation from apex down to ground.");
    }
}

