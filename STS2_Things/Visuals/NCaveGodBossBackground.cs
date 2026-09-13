using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Logging;
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
}
