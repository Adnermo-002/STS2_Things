using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Vfx.Utilities;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Audio;
using STS2_Things.Compatibility;
using STS2_Things.Monsters;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Visuals;

/// <summary>
/// Dual-pass background controller for the 活体巨岩 (Living Megalith) boss encounter.
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

    private ulong _lastHurtAnimTicks;
    private const ulong HurtAnimCooldownMs = 150;

    private ulong _lastGroanTicks;
    private const ulong GroanCooldownMs = 450;
    private const float GroanChance = 0.70f;

    private static readonly string[] ArmForegroundSlotNames =
    [
        "arm1_2", "arm1_2_red", "arm1_2_back", "arm1_2_back_red", "arm1_3", "arm2_2", "arm2_2_red", "arm2_3"
    ];

    private static readonly string[] BodySlotNames =
    [
        "body_bottom", "body", "body_red",
        "arm1_1", "arm2_1", "neck", "neck_red",
        "head", "head_red", "eyes", "eyes_red", "beard3", "beard3_red",
        "beard2", "beard2_red", "beard1", "beard1_red", "crastalls_roof",
        "crastalls_roof_red", "horn1", "horn1_red", "horn2", "horn2_red",
        "head_skale", "head_skale_red", "horizon"
    ];

    private static readonly string[] BodyRedSlotNames =
    [
        "beard1_red", "beard2_red", "beard3_red",
        "body_red", "crastalls_roof_red", "eyes_red",
        "head_red", "head_skale_red", "horn1_red", "horn2_red", "neck_red"
    ];

    private static readonly string[] BodyBlueSlotNames =
    [
        "beard1", "beard2", "beard3",
        "body", "crastalls_roof", "eyes",
        "head", "head_skale", "horn1", "horn2", "neck"
    ];

    private static readonly string[] ArmRedSlotNames =
    [
        "arm1_2_red", "arm1_2_back_red", "arm2_2_red"
    ];

    private static readonly string[] ArmBlueSlotNames =
    [
        "arm1_2", "arm1_2_back", "arm2_2"
    ];

    private static readonly Color TransparentColor = new(1f, 1f, 1f, 0f);

    private static readonly Vector2[] HurtScatterOffsets =
    [
        new(0f, 0f),
        new(-28f, 16f),
        new(32f, -12f),
        new(-18f, -22f),
        new(22f, 24f),
        new(35f, 6f),
        new(-32f, -10f),
        new(14f, -18f)
    ];
    private int _hurtScatterIndex;

    private MegaSprite? _bodyController;
    private MegaSprite? _armsController;
    private Node2D? _bodyNode;
    private Node2D? _armsNode;
    private Tween? _weakHurtTween;
    private Tween? _weakFlashTween;
    private TextureRect? _cachedRedBgNode;
    private Tween? _bgTransitionTween;
    private Tween? _crystalTween;
    private Tween? _releaseTween;
    private bool _presentationEnded;

    // Z-order is owned by code, not the scene: native background scenes must rely on tree order
    // (scripts/verify_project.py rejects z_index in *_background.tscn).
    private const int BackgroundZIndex = -20;
    private const int ArmsZIndex = 2;
    private const int StolenCardZIndex = BackgroundZIndex + 1;
    private static readonly Color CrystalCharge = new(0.80f, 1.15f, 1.45f, 1f);
    private static readonly Color CrystalChargeAngry = new(1.45f, 0.95f, 0.70f, 1f);

    private readonly List<GodotObject> _bodyMaskArmSlots = new();
    private readonly List<GodotObject> _bodyRedSlots = new();
    private readonly List<GodotObject> _bodyBlueSlots = new();

    private readonly List<GodotObject> _armsMaskBodySlots = new();
    private readonly List<GodotObject> _armsRedSlots = new();
    private readonly List<GodotObject> _armsBlueSlots = new();

    private readonly List<(NCreature node, Vector2 origPos, float origRot, Vector2 origScale)> _capturedPlayers = new();
    private bool _isGrabTracking;
    private bool _isRightGrab;

    /// <summary>
    /// True from the moment the unbroken fist starts hauling the captives down (ResumeSlamAnim)
    /// until the impact frame. While set, captured players are stretched along the fall axis so
    /// the plunge reads as being dragged through the air rather than gently lowered.
    /// </summary>
    private bool _isSlamDescending;
    private bool _isAngry;
    private bool _isTransforming;
    private bool _isWeakIdle;
    private bool _isRetreating;
    private CancellationTokenSource? _cts;

    public bool IsAngry => _isAngry;
    public bool IsWeakIdle => _isWeakIdle;
    public bool IsRetreating => _isRetreating;
    public bool HasCapturedPlayers => _capturedPlayers.Count > 0;

    /// <summary>
    /// Vertical world-space offset applied to the captive claw creature node during grab tracking,
    /// relative to the 'player_grab' bone origin. Lowering the node places the claw's health bar and
    /// nameplate at the lower edge of the giant stone fist instead of floating above the knuckles.
    /// The Bounds / CenterPos markers in things_cave_god_captive_claw.tscn are pre-offset by the
    /// same amount so the hitbox and hit-VFX anchor stay locked to the fist itself.
    /// </summary>
    private const float CaptiveClawNodeOffsetY = 50f;

    /// <summary>How long the crushed impact pose is held before the recovery bounce begins.</summary>
    private const float SlamImpactHoldDuration = 0.08f;

    /// <summary>Duration of the back-eased bounce that returns slammed players to their formation slots.</summary>
    private const float SlamRecoverDuration = 0.42f;

    private Marker2D? _stolenCardPosLeft;
    private Marker2D? _stolenCardPosRight;

    private NCreature? _cachedClawNode;

    private NCreature? GetCaptiveClawNode()
    {
        if (_cachedClawNode != null && GodotObject.IsInstanceValid(_cachedClawNode) && _cachedClawNode.IsInsideTree())
        {
            return _cachedClawNode;
        }

        NCombatRoom? room = NCombatRoom.Instance;
        if (room == null) return null;

        _cachedClawNode = room.CreatureNodes.FirstOrDefault(c => c.Entity?.Monster is ThingsCaveGodCaptiveClaw && c.Entity.IsAlive);
        return _cachedClawNode;
    }

    public static void ElevateHandsUi(NCombatRoom? combatRoom)
    {
        if (combatRoom == null) return;
        foreach (NCreature enemyNode in combatRoom.CreatureNodes)
        {
            if (enemyNode != null && GodotObject.IsInstanceValid(enemyNode) && enemyNode.Entity?.IsEnemy == true)
            {
                if (enemyNode.Entity.Monster is ThingsCaveGodLeftHand or ThingsCaveGodRightHand or ThingsCaveGodCaptiveClaw)
                {
                    enemyNode.ZAsRelative = false;
                    enemyNode.ZIndex = NCaveGodHandCreatureVisuals.CreatureUiZIndex;
                }
            }
        }
    }

    public static void ResetHandsUi(NCombatRoom? combatRoom)
    {
        if (combatRoom == null) return;
        foreach (NCreature enemyNode in combatRoom.CreatureNodes)
        {
            if (enemyNode != null && GodotObject.IsInstanceValid(enemyNode) && enemyNode.Entity?.IsEnemy == true)
            {
                if (enemyNode.Entity.Monster is ThingsCaveGodLeftHand or ThingsCaveGodRightHand or ThingsCaveGodCaptiveClaw)
                {
                    enemyNode.ZAsRelative = false;
                    enemyNode.ZIndex = NCaveGodHandCreatureVisuals.CreatureUiZIndex;
                }
            }
        }
    }

    public void ResetVisualState()
    {
        ResetHandsUi(NCombatRoom.Instance);

        if (_isRetreating)
        {
            return;
        }

        _weakHurtTween?.Kill();
        _weakHurtTween = null;
        _weakFlashTween?.Kill();
        _weakFlashTween = null;
        _bgTransitionTween?.Kill();
        _bgTransitionTween = null;
        _crystalTween?.Kill();
        _crystalTween = null;
        UpdateBackgroundPhaseImmediate(_isAngry);

        if (_bodyNode != null)
        {
            _bodyNode.Modulate = Colors.White;
            _bodyNode.Position = new Vector2(0f, 15f);
            _bodyNode.ZAsRelative = true;
            _bodyNode.ZIndex = 0;
        }
        if (_armsNode != null)
        {
            _armsNode.Modulate = Colors.White;
            _armsNode.Position = new Vector2(0f, 15f);
            _armsNode.Scale = new Vector2(1.3f, 1.3f);
            _armsNode.ZAsRelative = true;
            _armsNode.ZIndex = ArmsZIndex;
        }

        Control? foreground = GetNodeOrNull<Control>("%Foreground")
            ?? GetParent()?.GetNodeOrNull<Control>("%Foreground")
            ?? GetParent()?.GetNodeOrNull<Control>("Foreground");
        if (foreground != null)
        {
            foreground.ZAsRelative = true;
            foreground.ZIndex = 0;
            if (foreground.GetChildCount() > 0 && foreground.GetChild(0) is CanvasItem fgChild)
            {
                fgChild.ZAsRelative = true;
                fgChild.ZIndex = 0;
            }
        }
        if (_armsNode != null && foreground != null)
        {
            // In normal combat, position _armsNode AFTER Foreground in tree order so hands strike in front of the platform
            if (_armsNode.GetIndex() < foreground.GetIndex())
            {
                _armsNode.GetParent()?.MoveChild(_armsNode, foreground.GetIndex() + 1);
            }
        }
    }

    public void ResetArmScale()
    {
        if (_isRetreating)
        {
            return;
        }

        if (_armsNode != null)
        {
            _armsNode.Scale = new Vector2(1.3f, 1.3f);
        }

        Control? foreground = GetNodeOrNull<Control>("%Foreground")
            ?? GetParent()?.GetNodeOrNull<Control>("%Foreground")
            ?? GetParent()?.GetNodeOrNull<Control>("Foreground");
        if (_armsNode != null && foreground != null)
        {
            if (_armsNode.GetIndex() < foreground.GetIndex())
            {
                _armsNode.GetParent()?.MoveChild(_armsNode, foreground.GetIndex() + 1);
            }
        }
    }

    public override void _Process(double delta)
    {
        base._Process(delta);
        if (_presentationEnded) return;

        if (CombatManager.Instance.IsInProgress && NCombatRoom.Instance is { } room)
            UpdateHandAnchors(room.CreatureNodes);

        if (_isGrabTracking && _capturedPlayers.Count > 0)
        {
            Transform2D? boneTransform = _armsController?.GetGlobalBoneTransform("player_grab");
            Vector2 grabWorldPos = boneTransform?.Origin ?? new Vector2(983f, 400f);

            // Dynamic plunge stretch based on slam animation phase:
            // 0.00s ~ 0.52s: Upward windup into high sky (firm grip)
            // 0.52s ~ 0.78s: Explosive downward plunge (plunge stretch)
            if (_armsController != null)
            {
                using var mainTrackScope = TrackEntryScope(_armsController.TryGetAnimationState()?.GetCurrent(MainTrack), out MegaTrackEntry? mainTrack);
                if (mainTrack != null)
                {
                    string animName = mainTrack.GetAnimationName();
                    if (animName is "grab_slam" or "grab_slam_angry" or "grab_slam_right" or "grab_slam_right_angry")
                    {
                        float trackTime = mainTrack.GetTrackTime();
                        _isSlamDescending = trackTime >= 0.52f && trackTime < 0.78f;
                    }
                }
            }

            for (int i = 0; i < _capturedPlayers.Count; i++)
            {
                (NCreature node, _, _, Vector2 origScale) = _capturedPlayers[i];
                if (GodotObject.IsInstanceValid(node))
                {
                    Vector2 clusterOffset = GetClusterOffset(i, _capturedPlayers.Count);
                    node.GlobalPosition = grabWorldPos + clusterOffset;
                    node.Rotation = GetClusterTilt(i, _capturedPlayers.Count);

                    // Grip pose: captives are held slightly shrunk inside the fist.
                    Vector2 gripScale = origScale * 0.88f;
                    if (_isSlamDescending)
                    {
                        // Plunge pose: narrow + tall stretch, and the cluster tilt is damped so the
                        // bodies hang straight as they are driven down into the stage.
                        gripScale = new Vector2(gripScale.X * 0.86f, gripScale.Y * 1.22f);
                        node.Rotation = GetClusterTilt(i, _capturedPlayers.Count) * 0.55f;
                    }
                    node.Scale = gripScale;
                }
            }

            // Lock the captive claw monster node onto the giant stone fist so its health bar,
            // nameplate and hitbox all track the palm as it lifts and holds the players.
            NCreature? clawNode = GetCaptiveClawNode();
            if (clawNode != null && GodotObject.IsInstanceValid(clawNode))
            {
                if (clawNode.ZIndex != NCaveGodHandCreatureVisuals.CreatureUiZIndex || clawNode.ZAsRelative)
                {
                    clawNode.ZAsRelative = false;
                    clawNode.ZIndex = NCaveGodHandCreatureVisuals.CreatureUiZIndex;
                }
                clawNode.GlobalPosition = new Vector2(grabWorldPos.X, grabWorldPos.Y + CaptiveClawNodeOffsetY);
            }

            // Ensure idle hand creature nodes remain elevated above CaveGodArms (ZIndex = 5)
            if (NCombatRoom.Instance != null)
            {
                foreach (NCreature enemyNode in NCombatRoom.Instance.CreatureNodes)
                {
                    if (enemyNode != null && GodotObject.IsInstanceValid(enemyNode) && enemyNode.Entity?.IsEnemy == true)
                    {
                        if (enemyNode.Entity.Monster is ThingsCaveGodLeftHand or ThingsCaveGodRightHand)
                        {
                            if (enemyNode.ZIndex != NCaveGodHandCreatureVisuals.CreatureUiZIndex || enemyNode.ZAsRelative)
                            {
                                enemyNode.ZAsRelative = false;
                                enemyNode.ZIndex = NCaveGodHandCreatureVisuals.CreatureUiZIndex;
                            }
                        }
                    }
                }
            }
        }

        UpdateStolenCardPositions();
    }

    /// <summary>Keep targeting, impact effects and health bars attached to the enlarged Spine fists.</summary>
    public void UpdateHandAnchors(IEnumerable<NCreature> creatures)
    {
        if (_presentationEnded || _isRetreating || _armsController is null || _armsNode is null) return;
        foreach (NCreature node in creatures)
        {
            if (!GodotObject.IsInstanceValid(node) || node.Entity?.Monster is not ThingsCaveGodHand hand) continue;
            Transform2D? fist = _armsController.GetGlobalBoneTransform(hand.IsLeft ? "arm1_3" : "arm2_3");
            if (fist is not { } transform) continue;
            // Stay horizontal while the fist rotates. Use world scale so camera
            // zoom and the rig's 1.3x enlargement cannot displace the UI.
            Vector2 offset = new(hand.IsLeft ? -10f : 10f, 135f);
            node.GlobalPosition = transform.Origin + offset * _armsNode.GlobalScale.Abs();
        }
    }

    public override void _ExitTree()
    {
        CombatManager.Instance.CombatEnded -= OnCombatEnded;
        _presentationEnded = true;
        ClearMainEntries();
        ClearAllStolenCards();
        RestoreCapturedPlayersInstantly();
        ResetVisualState();
        _cts?.Cancel();
        _cts?.Dispose();
        _cts = null;
    }

    public override void _Ready()
    {
        CombatManager.Instance.CombatEnded += OnCombatEnded;
        // Keep the whole world composition below native cards, menus and the
        // game-over backstop. Child arm tracks use relative Z inside this range.
        if (GetParent() is CanvasItem background)
        {
            background.ZAsRelative = false;
            background.ZIndex = BackgroundZIndex;
        }
        _bodyNode = GetNodeOrNull<Node2D>("%CaveGodBody") ?? GetNodeOrNull<Node2D>("CaveGodBody");
        _armsNode = GetNodeOrNull<Node2D>("%CaveGodArms") ?? GetParent()?.GetNodeOrNull<Node2D>("%CaveGodArms") ?? GetParent()?.GetNodeOrNull<Node2D>("CaveGodArms");

        if (_bodyNode == null || _armsNode == null)
        {
            Log.Error($"[CaveGodBackground] Setup failed: bodyNode={(_bodyNode != null)}, armsNode={(_armsNode != null)}");
            return;
        }

        ResetVisualState();

        _stolenCardPosLeft = GetNodeOrNull<Marker2D>("%StolenCardPosLeft")
            ?? GetParent()?.GetNodeOrNull<Marker2D>("%StolenCardPosLeft")
            ?? GetParent()?.GetNodeOrNull<Marker2D>("StolenCardPosLeft");
        _stolenCardPosRight = GetNodeOrNull<Marker2D>("%StolenCardPosRight")
            ?? GetParent()?.GetNodeOrNull<Marker2D>("%StolenCardPosRight")
            ?? GetParent()?.GetNodeOrNull<Marker2D>("StolenCardPosRight");
        foreach (Marker2D? marker in new[] { _stolenCardPosLeft, _stolenCardPosRight })
        {
            if (marker == null) continue;
            marker.ZAsRelative = false;
            marker.ZIndex = StolenCardZIndex;
        }

        _bodyController = new MegaSprite(_bodyNode);
        _armsController = new MegaSprite(_armsNode);

        SetupBodySprite(_bodyController);
        SetupArmsSprite(_armsController);

        Callable.From(AlignStageAndPlayers).CallDeferred();

        // Preload Living Megalith hurt audio variants for zero-latency combat feedback
        for (int i = 1; i <= 5; i++)
        {
            NativeSfxPlayer.Preload($"res://sfx/cave_god/cave_god_hurt-{i:D2}.wav");
        }

        Log.Info("[CaveGodBackground] Dual-pass CaveGod Spine controllers initialized.");
    }

    private void OnCombatEnded(CombatRoom room)
    {
        if (room.Encounter is not STS2_Things.Encounters.CaveGodBossEncounter) return;
        _presentationEnded = true;
        ClearMainEntries();
        _cts?.Cancel();
        RestoreCapturedPlayersInstantly();
        ClearAllStolenCards();
        _weakHurtTween?.Kill();
        _weakFlashTween?.Kill();
        _crystalTween?.Kill();
    }

    /// <summary>
    /// Aligns the player battle formation onto the central basalt cliff stage.
    /// Moves the entire native formation, including other players and their pets.
    /// </summary>
    public void AlignStageAndPlayers()
    {
        Control? allyContainer = NCombatRoom.Instance?.GetNodeOrNull<Control>("%AllyContainer");
        if (allyContainer != null && !allyContainer.HasMeta("CaveGodStageAligned"))
        {
            allyContainer.SetMeta("CaveGodStageAligned", true);
            allyContainer.Position += Vector2.Down * PlayerStageOffsetY;
            Log.Info($"[CaveGodBackground] AllyContainer aligned to central stage (Y + {PlayerStageOffsetY}px -> {allyContainer.Position.Y}).");
        }
    }

    private void SetupBodySprite(MegaSprite sprite)
    {
        this.RunWhenSpineReady(sprite, state =>
        {
            ObserveMainAnimation(sprite, foreground: false);
            state.SetAnimation("idle_front", loop: true, MainTrack);
            MegaSkeleton? skel = sprite.GetSkeleton();
            if (skel != null)
            {
                foreach (string name in ArmForegroundSlotNames)
                {
                    Variant slotVar = skel.BoundObject.Call("find_slot", name);
                    if (slotVar.AsGodotObject() is GodotObject slotObj)
                    {
                        _bodyMaskArmSlots.Add(slotObj);
                    }
                }
                foreach (string name in BodyRedSlotNames)
                {
                    Variant slotVar = skel.BoundObject.Call("find_slot", name);
                    if (slotVar.AsGodotObject() is GodotObject slotObj)
                    {
                        _bodyRedSlots.Add(slotObj);
                    }
                }
                foreach (string name in BodyBlueSlotNames)
                {
                    Variant slotVar = skel.BoundObject.Call("find_slot", name);
                    if (slotVar.AsGodotObject() is GodotObject slotObj)
                    {
                        _bodyBlueSlots.Add(slotObj);
                    }
                }
            }

            sprite.ConnectBeforeWorldTransformsChange(Callable.From((Variant _) =>
            {
                ApplyAnimatedHandPose(sprite, foreground: false);
                // 1. Permanently mask ALL arm/hand/shoulder slots on background body pass
                // Under NO circumstances should _bodyNode EVER render any arm geometry!
                for (int i = 0; i < _bodyMaskArmSlots.Count; i++)
                {
                    _bodyMaskArmSlots[i].Call("set_attachment", default(Variant));
                    _bodyMaskArmSlots[i].Call("set_color", TransparentColor);
                }

                // 2. Strict phase slot isolation (when not dynamically cross-fading during transformation)
                if (!_isTransforming)
                {
                    if (_isAngry)
                    {
                        for (int i = 0; i < _bodyBlueSlots.Count; i++)
                        {
                            _bodyBlueSlots[i].Call("set_attachment", default(Variant));
                            _bodyBlueSlots[i].Call("set_color", TransparentColor);
                        }
                    }
                    else
                    {
                        for (int i = 0; i < _bodyRedSlots.Count; i++)
                        {
                            _bodyRedSlots[i].Call("set_attachment", default(Variant));
                            _bodyRedSlots[i].Call("set_color", TransparentColor);
                        }
                    }
                }
            }));
            Log.Info($"[CaveGodBackground] Body skeleton initialized: {_bodyMaskArmSlots.Count} arm slots masked transparent, {_bodyRedSlots.Count} red slots tracked.");
        });
    }

    private void SetupArmsSprite(MegaSprite sprite)
    {
        this.RunWhenSpineReady(sprite, state =>
        {
            ObserveMainAnimation(sprite, foreground: true);
            state.SetAnimation("idle_front", loop: true, MainTrack);
            MegaSkeleton? skel = sprite.GetSkeleton();
            if (skel != null)
            {
                foreach (string name in BodySlotNames)
                {
                    Variant slotVar = skel.BoundObject.Call("find_slot", name);
                    if (slotVar.AsGodotObject() is GodotObject slotObj)
                    {
                        _armsMaskBodySlots.Add(slotObj);
                    }
                }
                foreach (string name in ArmRedSlotNames)
                {
                    Variant slotVar = skel.BoundObject.Call("find_slot", name);
                    if (slotVar.AsGodotObject() is GodotObject slotObj)
                    {
                        _armsRedSlots.Add(slotObj);
                    }
                }
                foreach (string name in ArmBlueSlotNames)
                {
                    Variant slotVar = skel.BoundObject.Call("find_slot", name);
                    if (slotVar.AsGodotObject() is GodotObject slotObj)
                    {
                        _armsBlueSlots.Add(slotObj);
                    }
                }
            }

            sprite.ConnectBeforeWorldTransformsChange(Callable.From((Variant _) =>
            {
                ApplyAnimatedHandPose(sprite, foreground: true);
                // 1. Permanently mask ALL body/head/neck/horns/chest slots on foreground arms pass
                // Under NO circumstances should _armsNode EVER render any body geometry!
                for (int i = 0; i < _armsMaskBodySlots.Count; i++)
                {
                    _armsMaskBodySlots[i].Call("set_attachment", default(Variant));
                    _armsMaskBodySlots[i].Call("set_color", TransparentColor);
                }

                // 2. Strict phase slot isolation (when not dynamically cross-fading during transformation)
                if (!_isTransforming)
                {
                    if (_isAngry)
                    {
                        for (int i = 0; i < _armsBlueSlots.Count; i++)
                        {
                            _armsBlueSlots[i].Call("set_attachment", default(Variant));
                            _armsBlueSlots[i].Call("set_color", TransparentColor);
                        }
                    }
                    else
                    {
                        for (int i = 0; i < _armsRedSlots.Count; i++)
                        {
                            _armsRedSlots[i].Call("set_attachment", default(Variant));
                            _armsRedSlots[i].Call("set_color", TransparentColor);
                        }
                    }
                }
            }));
            sprite.ConnectWorldTransformsChanged(Callable.From((Variant _) => UpdateStolenCardPositions()));
            Log.Info($"[CaveGodBackground] Arms skeleton initialized: {_armsMaskBodySlots.Count} body slots masked transparent, {_armsRedSlots.Count} red slots tracked, {_armsBlueSlots.Count} blue slots tracked.");
        });
    }

    private TextureRect? GetRedBgNode()
    {
        if (_cachedRedBgNode != null && GodotObject.IsInstanceValid(_cachedRedBgNode))
        {
            return _cachedRedBgNode;
        }

        var layer00 = GetParent()?.GetNodeOrNull<Control>("Layer_00");
        _cachedRedBgNode = layer00?.GetNodeOrNull<TextureRect>("A/RedBg")
            ?? layer00?.FindChild("RedBg", recursive: true, owned: false) as TextureRect;
        return _cachedRedBgNode;
    }

    public void UpdateBackgroundPhaseImmediate(bool angry)
    {
        _bgTransitionTween?.Kill();
        _bgTransitionTween = null;
        var redBg = GetRedBgNode();
        if (redBg != null)
        {
            redBg.Modulate = new Color(1f, 1f, 1f, angry ? 1f : 0f);
        }
    }

    public void StartBackgroundCrossfade(float durationSeconds)
    {
        var redBg = GetRedBgNode();
        if (redBg == null) return;

        _bgTransitionTween?.Kill();
        _bgTransitionTween = CreateTween();
        _bgTransitionTween.TweenProperty(redBg, "modulate:a", 1.0f, durationSeconds)
            .SetTrans(Tween.TransitionType.Cubic)
            .SetEase(Tween.EaseType.InOut);
        Log.Info($"[CaveGodBackground] Started background crossfade to RED ({durationSeconds}s).");
    }

    public void SetAngry(bool angry)
    {
        if (_isAngry == angry)
            return;

        _isAngry = angry;
        string targetIdle = _isAngry ? "idle_front_angry" : "idle_front";

        SetTrackAnimationBoth(targetIdle, loop: true, MainTrack);
        UpdateBackgroundPhaseImmediate(angry);
        Log.Info($"[CaveGodBackground] CaveGod transitioned to {(angry ? "ANGRY" : "NORMAL")} idle ({targetIdle}).");
    }

    /// <summary>
    /// Plays the authentic Phase 2 transformation sequence using the Spine cutscene animation 'main_angry':
    /// 1. Drops any captured players safely and resets visual states;
    /// 2. Plays 'main_angry' (11.2s native, accelerated 1.5x to ~7.46s) in perfect lock-step across dual rigs;
    /// 3. Phase 1 (0.0s - 3.07s): Granite body channels subterranean magma with low rumble;
    /// 4. Phase 2 (3.07s): Molten red veins ignite across eyes and horns; background begins seamless 2.0s crossfade from blue to red;
    /// 5. Phase 3 (3.55s): Enraged roar upward, magma eruption with rock shatter particle;
    /// 6. Phase 4 (4.67s): Colossal body slam and ground shockwave;
    /// 7. Phase 5 (7.46s): Smooth settling into idle_front_angry with fully active red slots and red magma background.
    /// </summary>
    public async Task PlayPhaseTransitionAnim()
    {
        _cts?.Cancel();
        _cts?.Dispose();
        _cts = new CancellationTokenSource();

        if (HasCapturedPlayers)
        {
            await DropPlayersToGround(isSlam: false);
        }

        ResetVisualState();

        const float AnimSpeed = 1.5f;

        try
        {
            _isTransforming = true;
            _isAngry = false; // Spine 'main_angry' starts from normal blue palette and cross-fades internally
            UpdateBackgroundPhaseImmediate(false);

            SetTimeScaleBoth(AnimSpeed);
            SetTrackAnimationBoth("main_angry", loop: false, MainTrack);
            Log.Info($"[CaveGodBackground] Started authentic transformation animation 'main_angry' (speed={AnimSpeed}x, duration={11.2f / AnimSpeed:F2}s).");

            // Segment 1 (0.0s -> 3.07s real time): Boss shifts and channels magma core
            SfxCmd.Play("event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_stomp");
            NGame.Instance?.ScreenShake(ShakeStrength.Weak, ShakeDuration.Long);
            await Cmd.Wait(4.60f / AnimSpeed, _cts.Token);

            // Segment 2 (t = 4.60s Spine = 3.07s real): Eyes ignite with blazing molten glow
            // Start background crossfade from icy blue to fiery red over 2.0s
            StartBackgroundCrossfade(durationSeconds: 2.0f);
            SfxCmd.Play("event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_kick");
            NGame.Instance?.ScreenShake(ShakeStrength.Medium, ShakeDuration.Short);
            await Cmd.Wait((5.33f - 4.60f) / AnimSpeed, _cts.Token);

            // Segment 3 (t = 5.33s Spine = 3.55s real): Colossal roar upwards! Magma veins burst forth!
            SfxCmd.Play("event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_eruption");
            NGame.Instance?.ScreenShake(ShakeStrength.Strong, ShakeDuration.Long);
            Control? vfxContainer = NCombatRoom.Instance?.CombatVfxContainer;
            if (vfxContainer != null)
            {
                VfxCmd.PlayVfx(new Vector2(983f, 450f), VfxCmd.rockShatterPath, vfxContainer);
            }
            await Cmd.Wait((7.00f - 5.33f) / AnimSpeed, _cts.Token);

            // Segment 4 (t = 7.00s Spine = 4.67s real): Brutal body slam / shockwave thrashes across basalt floor
            SfxCmd.Play("event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_stomp");
            NGame.Instance?.ScreenShake(ShakeStrength.Strong, ShakeDuration.Normal);
            await Cmd.Wait((11.20f - 7.00f) / AnimSpeed, _cts.Token);

            // Transformation sequence concluded: seamlessly settle into idle_front_angry
            _isTransforming = false;
            _isAngry = true;
            UpdateBackgroundPhaseImmediate(true);
            SetTimeScaleBoth(1.0f);
            SetTrackAnimationBoth("idle_front_angry", loop: true, MainTrack);
            Log.Info("[CaveGodBackground] Transformation sequence completed successfully into idle_front_angry.");
        }
        catch (OperationCanceledException)
        {
            _isTransforming = false;
            _isAngry = true;
            UpdateBackgroundPhaseImmediate(true);
            SetTimeScaleBoth(1.0f);
            SetTrackAnimationBoth("idle_front_angry", loop: true, MainTrack);
            Log.Info("[CaveGodBackground] Phase transition animation was cancelled.");
        }
    }

    private void SetTimeScaleBoth(float scale)
    {
        _bodyController?.GetAnimationState()?.SetTimeScale(scale);
        _armsController?.GetAnimationState()?.SetTimeScale(scale);
    }

    /// <summary>
    /// Starts attack animation without blocking. The monster move logic orchestrates
    /// precise impact frames (e.g. 1.88s for central_slam, 0.64s/1.34s/2.32s for jabs)
    /// and recovery phases directly.
    /// </summary>
    public void StartAttackAnim(string animBase, bool isFlipped = false)
    {
        _cts?.Cancel();
        _cts?.Dispose();
        _cts = new CancellationTokenSource();

        if (!animBase.StartsWith("grab_player") && (HasCapturedPlayers || _isGrabTracking))
        {
            RestoreCapturedPlayersInstantly();
        }

        if (_armsNode != null)
        {
            _armsNode.Scale = new Vector2(1.3f, 1.3f);
        }

        if (animBase.StartsWith("grab_player") || animBase.StartsWith("grab_slam"))
        {
            _isRightGrab = isFlipped || animBase.Contains("right");
        }

        if (isFlipped)
        {
            if (animBase == "front_sweep") animBase = "front_sweep_right";
            else if (animBase == "front_sweep_angry") animBase = "front_sweep_right_angry";
            else if (animBase == "grab_player") animBase = "grab_player_right";
            else if (animBase == "grab_player_angry") animBase = "grab_player_right_angry";
            else if (animBase == "grab_slam") animBase = "grab_slam_right";
            else if (animBase == "grab_slam_angry") animBase = "grab_slam_right_angry";
            else if (animBase == "leftpunch") animBase = "rightpunch";
            else if (animBase == "weak_attack") animBase = "weak_attack_right";
            else if (animBase == "weak_enter") animBase = "weak_enter_right";
            else if (animBase == "weak_idle") animBase = "weak_idle_right";
            else if (animBase == "weak_recover") animBase = "weak_recover_right";
        }

        string anim = animBase;
        if (_isAngry)
        {
            if (!anim.EndsWith("_angry"))
            {
                string angryCandidate = animBase + "_angry";
                if (_bodyController != null && HasBossAnimation(_bodyController, angryCandidate))
                {
                    anim = angryCandidate;
                }
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

        PrepareContactAim(anim);
        SetTrackAnimationBoth(anim, loop: false, MainTrack);
        if (!animBase.StartsWith("grab_player"))
        {
            AddTrackAnimationBoth(idleAnim, delay: 0f, loop: true, MainTrack);
        }
        Log.Info($"[CaveGodBackground] Started attack animation: {anim} (isAngry={_isAngry}, isFlipped={isFlipped})");
    }

    public async Task PlayAttackAnim(string animBase, float duration, bool isFlipped = false)
    {
        StartAttackAnim(animBase, isFlipped);
        if (duration > 0f)
        {
            await Cmd.Wait(duration, _cts?.Token ?? CancellationToken.None);
        }
    }

    /// <summary>Wait for an absolute animation frame, including time spent inside native damage commands.</summary>
    public async Task WaitForAttackFrame(string animBase, float frameTime, float fallbackDelay)
    {
        float remaining = fallbackDelay;
        using (TrackEntryScope(_armsController?.TryGetAnimationState()?.GetCurrent(MainTrack), out MegaTrackEntry? current))
        {
            if (current != null && current.GetAnimationName().StartsWith(animBase, StringComparison.Ordinal))
                remaining = Math.Max(0f, frameTime - current.GetTrackTime());
        }
        await Cmd.Wait(remaining);
        // Instant/skip-wait modes may resolve without advancing the rendered
        // timeline. Show the contact pose before spawning that hit's effects.
        foreach (var (sprite, controller) in new[] { (_bodyNode, _bodyController), (_armsNode, _armsController) })
        {
            using var scope = TrackEntryScope(controller?.TryGetAnimationState()?.GetCurrent(MainTrack), out MegaTrackEntry? entry);
            if (sprite != null && entry != null && entry.GetAnimationName().StartsWith(animBase, StringComparison.Ordinal) &&
                entry.GetTrackTime() < frameTime)
            {
                // A seek without elapsed time also has to finish the incoming
                // blend; otherwise instant mode keeps the previous idle pose.
                entry.SetMixDuration(0f);
                entry.SetTrackTime(frameTime);
                sprite.Call("update_skeleton", 0f);
            }
        }
    }

    public async Task PlayWeakEnterAnim(bool isLeftArmBroken)
    {
        _cts?.Cancel();
        _cts?.Dispose();
        _cts = new CancellationTokenSource();

        if (HasCapturedPlayers)
        {
            await DropPlayersToGround(isSlam: false);
        }

        string enterAnim = isLeftArmBroken ? "weak_enter" : "weak_enter_right";
        string idleAnim = isLeftArmBroken ? "weak_idle" : "weak_idle_right";
        if (_isAngry)
        {
            enterAnim += "_angry";
            idleAnim += "_angry";
        }

        SetTrackAnimationBoth(enterAnim, loop: false, MainTrack);
        AddTrackAnimationBoth(idleAnim, delay: 0f, loop: true, MainTrack);
        _isWeakIdle = true;

        SfxCmd.Play("event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_stomp");
        NGame.Instance?.ScreenShake(ShakeStrength.Weak, ShakeDuration.Short);

        try
        {
            // 0.85s: ground thud impact
            await Cmd.Wait(0.85f, _cts.Token);
            NGame.Instance?.ScreenShake(ShakeStrength.Strong, ShakeDuration.Short);
            SfxCmd.Play("event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_eruption");

            // Remaining enter settle time: 2.20s - 0.85s = 1.35s
            await Cmd.Wait(1.35f, _cts.Token);
            Log.Info($"[CaveGodBackground] Weak enter animation completed ({enterAnim} -> {idleAnim}).");
        }
        catch (OperationCanceledException)
        {
            Log.Info("[CaveGodBackground] Weak enter animation cancelled.");
        }
    }

    public void StartWeakAttackAnim(bool isLeftArmBroken)
    {
        _cts?.Cancel();
        _cts?.Dispose();
        _cts = new CancellationTokenSource();

        string attackAnim = isLeftArmBroken ? "weak_attack" : "weak_attack_right";
        string idleAnim = isLeftArmBroken ? "weak_idle" : "weak_idle_right";
        if (_isAngry)
        {
            attackAnim += "_angry";
            idleAnim += "_angry";
        }

        PrepareContactAim(attackAnim);
        SetTrackAnimationBoth(attackAnim, loop: false, MainTrack);
        AddTrackAnimationBoth(idleAnim, delay: 0f, loop: true, MainTrack);
        Log.Info($"[CaveGodBackground] Started weak attack animation: {attackAnim}");
    }

    public async Task PlayWeakRecoverAnim(bool isLeftArmBroken)
    {
        _cts?.Cancel();
        _cts?.Dispose();
        _cts = new CancellationTokenSource();

        string recoverAnim = isLeftArmBroken ? "weak_recover" : "weak_recover_right";
        string idleAnim = _isAngry ? "idle_front_angry" : "idle_front";
        if (_isAngry)
        {
            recoverAnim += "_angry";
        }

        ResetVisualState();

        SetTrackAnimationBoth(recoverAnim, loop: false, MainTrack);
        AddTrackAnimationBoth(idleAnim, delay: 0f, loop: true, MainTrack);
        _isWeakIdle = false;

        try
        {
            // 0.45s: push ground
            await Cmd.Wait(0.45f, _cts.Token);
            SfxCmd.Play("event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_stomp");

            // 1.20s: apex rise (0.75s later)
            await Cmd.Wait(0.75f, _cts.Token);
            NGame.Instance?.ScreenShake(ShakeStrength.Weak, ShakeDuration.Short);

            // 2.60s total duration: remaining 1.40s
            await Cmd.Wait(1.40f, _cts.Token);
            Log.Info($"[CaveGodBackground] Weak recover animation completed ({recoverAnim} -> {idleAnim}).");
        }
        catch (OperationCanceledException)
        {
            Log.Info("[CaveGodBackground] Weak recover animation cancelled.");
        }
    }

    public void PlayHurtAnim(bool forceGroan = false, Vector2? hitPos = null)
    {
        if (_isRetreating)
        {
            return;
        }

        ulong now = Time.GetTicksMsec();
        if (!forceGroan && now - _lastHurtAnimTicks < HurtAnimCooldownMs)
        {
            return;
        }
        _lastHurtAnimTicks = now;

        if (_isGrabTracking)
        {
            // During grab tracking, DO NOT play hit_recoil on Track 1!
            // hit_recoil overwrites arm bones and the player_grab bone, causing violent twitching/spasms
            // while the giant stone hand is holding the player in mid-air.
            // Instead, play stone flash, rock debris VFX, stone impact sound, and screen shake!
            PlayGrabHurtFeedback(hitPos, forceGroan);
            return;
        }

        if (!_isWeakIdle)
        {
            string hurtAnim = _isAngry ? "hit_recoil_angry" : "hit_recoil";
            SetHurtTrackAnimationBoth(hurtAnim);
            PlayHurtGroan(forceGroan);
        }
        else
        {
            PlayWeakHurtAnim(hitPos, forceGroan);
        }
    }

    public void PlayGrabHurtFeedback(Vector2? hitPos = null, bool forceGroan = false)
    {
        // 1. Rock Shatter Particle VFX at hit position
        Control? vfxContainer = NCombatRoom.Instance?.CombatVfxContainer;
        if (vfxContainer != null)
        {
            Vector2 offset = HurtScatterOffsets[_hurtScatterIndex % HurtScatterOffsets.Length];
            _hurtScatterIndex++;
            Vector2 defaultPos = new Vector2(960f, 400f);
            Transform2D? boneTransform = _armsController?.GetGlobalBoneTransform("player_grab");
            if (boneTransform.HasValue)
            {
                defaultPos = boneTransform.Value.Origin;
            }
            Vector2 spawnPos = (hitPos ?? defaultPos) + offset;
            VfxCmd.PlayVfx(spawnPos, VfxCmd.rockShatterPath, vfxContainer);
        }

        // 2. Heavy Stone Flash on Arms Modulate (white flash in 0.12s)
        if (_armsNode != null)
        {
            Color flashColor = _isAngry ? new Color(1.6f, 0.9f, 0.8f, 1f) : new Color(1.4f, 1.4f, 1.5f, 1f);
            _armsNode.Modulate = flashColor;
            _weakFlashTween?.Kill();
            _weakFlashTween = CreateTween().SetEase(Tween.EaseType.Out).SetTrans(Tween.TransitionType.Quad);
            _weakFlashTween.TweenProperty(_armsNode, "modulate", Colors.White, 0.12f);
        }

        // 3. Audio & Shake
        SfxCmd.Play("event:/sfx/enemy/enemy_impact_enemy_size/enemy_impact_stone");
        NGame.Instance?.ScreenShake(ShakeStrength.Weak, ShakeDuration.Short);
        PlayHurtGroan(forceGroan);
    }

    /// <summary>
    /// 晶簇崩发 wind-up. Reuses the central_slam body motion (it has an _angry palette twin)
    /// and charges both rigs toward a crystal glow that peaks on the impact frame.
    /// </summary>
    public void StartCrystalBurstAnim()
    {
        StartAttackAnim("central_slam");
        if (_isRetreating || _bodyNode == null || _armsNode == null) return;
        Color charge = _isAngry ? CrystalChargeAngry : CrystalCharge;
        _crystalTween?.Kill();
        _crystalTween = CreateTween().SetParallel().SetEase(Tween.EaseType.In).SetTrans(Tween.TransitionType.Sine);
        _crystalTween.TweenProperty(_bodyNode, "modulate", charge, CaveGodAnimTiming.CentralSlamHit);
        _crystalTween.TweenProperty(_armsNode, "modulate", charge, CaveGodAnimTiming.CentralSlamHit);
        NGame.Instance?.ScreenShake(ShakeStrength.Weak, ShakeDuration.Long);
    }

    /// <summary>Impact frame of 晶簇崩发: crystal debris erupts across the whole stage.</summary>
    public void PlayCrystalBurstImpact()
    {
        NGame.Instance?.ScreenShake(ShakeStrength.Strong, ShakeDuration.Normal);
        Control? vfxContainer = NCombatRoom.Instance?.CombatVfxContainer;
        if (vfxContainer != null)
        {
            foreach (Vector2 pos in new[] { new Vector2(640f, 640f), new Vector2(983f, 600f), new Vector2(1320f, 640f) })
                VfxCmd.PlayVfx(pos, VfxCmd.rockShatterPath, vfxContainer);
        }
        FadeCrystalGlow(0.45f);
    }

    /// <summary>崩落裂痕 paid off: the exposed core cracks open with a hot flash.</summary>
    public void PlayFissureBreak()
    {
        if (_isRetreating) return;
        SfxCmd.Play("event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_eruption");
        NGame.Instance?.ScreenShake(ShakeStrength.Medium, ShakeDuration.Short);
        Control? vfxContainer = NCombatRoom.Instance?.CombatVfxContainer;
        if (vfxContainer != null)
        {
            foreach (Vector2 pos in new[] { new Vector2(900f, 600f), new Vector2(983f, 560f), new Vector2(1066f, 600f) })
                VfxCmd.PlayVfx(pos, VfxCmd.rockShatterPath, vfxContainer);
        }
        if (_bodyNode != null)
        {
            _bodyNode.Modulate = new Color(1.8f, 1.2f, 0.8f, 1f);
            FadeCrystalGlow(0.35f);
        }
    }

    private void FadeCrystalGlow(float seconds)
    {
        if (_bodyNode == null || _armsNode == null) return;
        _crystalTween?.Kill();
        _crystalTween = CreateTween().SetParallel().SetEase(Tween.EaseType.Out).SetTrans(Tween.TransitionType.Quad);
        _crystalTween.TweenProperty(_bodyNode, "modulate", Colors.White, seconds);
        _crystalTween.TweenProperty(_armsNode, "modulate", Colors.White, seconds);
    }

    /// <summary>
    /// Plays the authentic Living Megalith prone hurt feedback:
    /// 1. Rock shatter particle VFX (vfx_rock_shatter) bursting with stone debris & dust;
    /// 2. Heavy body stone flash (magma red/gold if angry, pale granite white if normal);
    /// 3. Crisp ground thud impulse tween (Y-axis downward stomp 7px + spring-back in 0.15s);
    /// 4. Heavy stone impact sound + low guttural hurt groan.
    /// Does NOT mix upright hit_recoil animation, completely preventing prone posture twisting.
    /// </summary>
    public void PlayWeakHurtAnim(Vector2? hitPos = null, bool forceGroan = false)
    {
        if (_isRetreating)
        {
            return;
        }

        // 1. Rock Shatter Particle VFX
        Control? vfxContainer = NCombatRoom.Instance?.CombatVfxContainer;
        if (vfxContainer != null)
        {
            Vector2 offset = HurtScatterOffsets[_hurtScatterIndex % HurtScatterOffsets.Length];
            _hurtScatterIndex++;
            Vector2 defaultPos = new Vector2(983f, 620f);
            Vector2 spawnPos = (hitPos ?? defaultPos) + offset;
            VfxCmd.PlayVfx(spawnPos, VfxCmd.rockShatterPath, vfxContainer);
        }

        // 2. Heavy Stone Flash (Modulate Tween)
        if (_bodyNode != null && _armsNode != null)
        {
            Color flashColor = _isAngry ? new Color(1.6f, 0.9f, 0.8f, 1f) : new Color(1.4f, 1.4f, 1.5f, 1f);
            _bodyNode.Modulate = flashColor;
            _armsNode.Modulate = flashColor;

            _weakFlashTween?.Kill();
            _weakFlashTween = CreateTween().SetParallel().SetEase(Tween.EaseType.Out).SetTrans(Tween.TransitionType.Quad);
            _weakFlashTween.TweenProperty(_bodyNode, "modulate", Colors.White, 0.14f);
            _weakFlashTween.TweenProperty(_armsNode, "modulate", Colors.White, 0.14f);
        }

        // 3. Ground Thud Impulse (Downward stomp & spring rebound on stone floor)
        if (_bodyNode != null && _armsNode != null)
        {
            _weakHurtTween?.Kill();
            _weakHurtTween = CreateTween().SetEase(Tween.EaseType.Out).SetTrans(Tween.TransitionType.Quad);

            // 0.04s: Heavy impact crushes body down 7px
            _weakHurtTween.TweenProperty(_bodyNode, "position:y", 22f, 0.04f);
            _weakHurtTween.Parallel().TweenProperty(_armsNode, "position:y", 22f, 0.04f);

            // 0.06s: Elastic rebound rises slightly above resting baseline
            _weakHurtTween.Chain().TweenProperty(_bodyNode, "position:y", 13f, 0.06f);
            _weakHurtTween.Parallel().TweenProperty(_armsNode, "position:y", 13f, 0.06f);

            // 0.05s: Smoothly settles back to resting baseline (15f)
            _weakHurtTween.Chain().TweenProperty(_bodyNode, "position:y", 15f, 0.05f);
            _weakHurtTween.Parallel().TweenProperty(_armsNode, "position:y", 15f, 0.05f);
        }

        // 4. SFX & Screen Shake
        SfxCmd.Play("event:/sfx/enemy/enemy_impact_enemy_size/enemy_impact_stone");
        NGame.Instance?.ScreenShake(ShakeStrength.Weak, ShakeDuration.Short);
        PlayHurtGroan(forceGroan);
    }

    private void SetHurtTrackAnimationBoth(string animName)
    {
        MegaAnimationState? bodyState = _bodyController?.TryGetAnimationState();
        MegaAnimationState? armsState = _armsController?.TryGetAnimationState();

        if (bodyState != null && HasBossAnimation(_bodyController, animName))
        {
            bodyState.SetAnimation(animName, false, ReactionTrack);
            using (TrackEntryScope(bodyState.GetCurrent(ReactionTrack), out MegaTrackEntry? track))
            {
                if (track != null)
                {
                    track.BoundObject.Call("set_alpha", 0.38f);
                    track.SetMixDuration(0.15f);
                }
            }
            bodyState.AddEmptyAnimation(ReactionTrack);
        }

        if (armsState != null && HasBossAnimation(_armsController, animName))
        {
            armsState.SetAnimation(animName, false, ReactionTrack);
            using (TrackEntryScope(armsState.GetCurrent(ReactionTrack), out MegaTrackEntry? track))
            {
                if (track != null)
                {
                    track.BoundObject.Call("set_alpha", 0.38f);
                    track.SetMixDuration(0.15f);
                }
            }
            armsState.AddEmptyAnimation(ReactionTrack);
        }
    }

    public void PlayHurtGroan(bool force = false)
    {
        ulong now = Time.GetTicksMsec();
        if (!force && now - _lastGroanTicks < GroanCooldownMs)
        {
            return;
        }

        _lastGroanTicks = now;
        int variant = (int)(now % 5) + 1;
        NativeSfxPlayer.Play($"res://sfx/cave_god/cave_god_hurt-{variant:D2}.wav", volumeDb: 6f);
    }

    public void PlayBodyDeathAnim()
    {
        _cts?.Cancel();
        _cts?.Dispose();
        _cts = new CancellationTokenSource();

        if (HasCapturedPlayers)
        {
            RestoreCapturedPlayersInstantly();
        }

        _isRetreating = true;
        _weakHurtTween?.Kill();
        _weakHurtTween = null;
        _weakFlashTween?.Kill();
        _weakFlashTween = null;

        ZAsRelative = true;
        ZIndex = 0;

        // Reset all custom ZIndex overrides so native Tree Ordering takes absolute precedence
        if (_armsNode != null)
        {
            _armsNode.ZAsRelative = true;
            _armsNode.ZIndex = 0;
        }
        if (_bodyNode != null)
        {
            _bodyNode.ZAsRelative = true;
            _bodyNode.ZIndex = 0;
        }

        Control? foreground = GetNodeOrNull<Control>("%Foreground")
            ?? GetParent()?.GetNodeOrNull<Control>("%Foreground")
            ?? GetParent()?.GetNodeOrNull<Control>("Foreground");
        if (foreground != null)
        {
            foreground.ZAsRelative = true;
            foreground.ZIndex = 0;
            if (foreground.GetChildCount() > 0 && foreground.GetChild(0) is CanvasItem fgChild)
            {
                fgChild.ZAsRelative = true;
                fgChild.ZIndex = 0;
            }

            // Move Foreground platform to the very end of the background scene tree!
            // In Godot 2D native tree ordering, the last child in the parent renders in front of all previous siblings.
            // By moving Foreground to the last index, the basalt platform is guaranteed to render in front of BOTH
            // CaveGodBody (index 1) and CaveGodArms (index 2), seamlessly occluding all retreating geometry!
            Node? parent = foreground.GetParent() ?? _armsNode?.GetParent();
            if (parent != null)
            {
                if (_armsNode != null && _armsNode.GetParent() == parent)
                {
                    parent.MoveChild(_armsNode, 1);
                }
                parent.MoveChild(foreground, parent.GetChildCount() - 1);
                Log.Info($"[CaveGodBackground] Moved Foreground platform to tail index {foreground.GetIndex()} (arms at index {_armsNode?.GetIndex()}) to strictly cover retreating body and arms.");
            }
        }

        // Clear reaction track so hurt anim cannot glitch retreat anim
        AddEmptyReactionAnimation();

        const float Speed = 1.0f; // 7.20s authentic native speed retreat sink into magma floor
        string hideAnim = _isAngry ? "hide_angry" : "hide";

        if (HasBossAnimation(_bodyController, hideAnim))
        {
            SetTimeScaleBoth(Speed);
            SetTrackAnimationBoth(hideAnim, loop: false, MainTrack);
        }
        else
        {
            string recoilAnim = _isAngry ? "hit_recoil_angry" : "hit_recoil";
            SetTrackAnimationBoth(recoilAnim, loop: false, MainTrack);
        }

        NGame.Instance?.ScreenShake(ShakeStrength.Strong, ShakeDuration.Normal);
        SfxCmd.Play("event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_knockout");

        Log.Info($"[CaveGodBackground] Playing authentic retreat death animation '{hideAnim}' (speed={Speed}x, duration={7.2f / Speed:F2}s, ZIndex=-1 behind floor).");
    }

    private void SetTrackAnimationBoth(string animName, bool loop, int track)
    {
        MegaAnimationState? bodyState = _bodyController?.TryGetAnimationState();
        MegaAnimationState? armsState = _armsController?.TryGetAnimationState();

        if (bodyState != null && HasBossAnimation(_bodyController, animName))
        {
            bodyState.SetAnimation(animName, loop, track);
            using (TrackEntryScope(bodyState.GetCurrent(track), out MegaTrackEntry? entry))
            {
                entry?.SetMixDuration(0.3f);
            }
        }
        if (armsState != null && HasBossAnimation(_armsController, animName))
        {
            armsState.SetAnimation(animName, loop, track);
            using (TrackEntryScope(armsState.GetCurrent(track), out MegaTrackEntry? entry))
            {
                entry?.SetMixDuration(0.3f);
            }
        }
    }

    private void AddTrackAnimationBoth(string animName, float delay, bool loop, int track)
    {
        MegaAnimationState? bodyState = _bodyController?.TryGetAnimationState();
        MegaAnimationState? armsState = _armsController?.TryGetAnimationState();

        if (bodyState != null && HasBossAnimation(_bodyController, animName))
        {
            bodyState.AddAnimation(animName, delay, loop, track);
        }
        if (armsState != null && HasBossAnimation(_armsController, animName))
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
    /// Starts real-time bone tracking for grabbed players.
    /// Captures players, elevates CaveGodArms ZIndex above player stage, and locks player
    /// positions frame-by-frame to the 'player_grab' bone as it lifts from ground to sky.
    /// </summary>
    public void StartGrabTracking(IReadOnlyList<Creature> targets, bool isFlipped = false)
    {
        if (_presentationEnded) return;
        _isRightGrab = _isRightGrab || isFlipped;
        _capturedPlayers.Clear();
        NCombatRoom? combatRoom = NCombatRoom.Instance;
        if (combatRoom == null) return;

        Node2D? armsNode = GetNodeOrNull<Node2D>("%CaveGodArms") ?? GetParent()?.GetNodeOrNull<Node2D>("%CaveGodArms");
        if (armsNode != null)
        {
            armsNode.ZAsRelative = true;
            armsNode.ZIndex = 5;
            armsNode.Scale = new Vector2(1.3f, 1.3f);
        }

        foreach (Creature target in targets)
        {
            NCreature? node = combatRoom.GetCreatureNode(target);
            if (node != null && GodotObject.IsInstanceValid(node))
            {
                _capturedPlayers.Add((node, node.Position, node.Rotation, node.Scale));
                node.ZAsRelative = false;
                node.ZIndex = BackgroundZIndex + 3;
                if (node.Entity.IsAlive) node.SetAnimationTrigger("Hit");
            }
        }

        ElevateHandsUi(combatRoom);

        _isGrabTracking = true;
        Log.Info($"[CaveGodBackground] Started real-time bone grab tracking for {_capturedPlayers.Count} players (isFlipped={isFlipped}).");
    }

    /// <summary>
    /// Starts real-time bone tracking for grabbed players and awaits the upward lift duration.
    /// </summary>
    public async Task LiftPlayersToAir(IReadOnlyList<Creature> targets, float duration = 1.10f, bool isFlipped = false)
    {
        StartGrabTracking(targets, isFlipped);
        if (duration > 0f)
        {
            await Cmd.Wait(duration);
        }
    }

    /// <summary>
    /// Releases captured players back onto the stage floor.
    /// When <paramref name="isSlam"/> is true the giant fist has just driven them into the basalt,
    /// so this plays the full slam reaction: hurt pose, vertical squash, dust + debris burst,
    /// screen shake, a short hit-stop, then a back-eased bounce back into formation slots.
    /// When false (claw shattered) players are safely eased down from mid-air with cubic ease.
    /// </summary>
    public async Task DropPlayersToGround(bool isSlam)
    {
        _isGrabTracking = false;
        _isSlamDescending = false;

        if (_capturedPlayers.Count == 0) return;
        NCombatRoom? combatRoom = NCombatRoom.Instance;
        if (combatRoom == null)
        {
            RestoreCapturedPlayersInstantly();
            return;
        }

        if (isSlam)
        {
            // ---------------------------------------------------------------
            // Impact frame: the fist has just crushed the captives into the stage.
            // Everything below is driven off a single clock so every player in a
            // multiplayer cluster lands on exactly the same frame.
            // ---------------------------------------------------------------
            Control? impactVfx = NCombatRoom.Instance?.CombatVfxContainer;

            foreach ((NCreature node, Vector2 origPos, float origRot, Vector2 origScale) in _capturedPlayers)
            {
                if (!GodotObject.IsInstanceValid(node))
                {
                    continue;
                }

                // Crumple instead of gliding: the captive is thrown into its hurt reaction.
                if (node.Entity.IsAlive) node.SetAnimationTrigger("Hit");

                // Vertical squash reads as the body being flattened into the stone floor.
                node.Scale = new Vector2(origScale.X * 1.26f, origScale.Y * 0.60f);
                node.Rotation = origRot;

                if (impactVfx != null)
                {
                    // Dust kicked off the basalt at floor level, plus a spray of shattered rock.
                    Vector2 groundPos = node.GlobalPosition + new Vector2(0f, 26f);
                    VfxCmd.PlayVfx(groundPos, VfxCmd.sandyImpactPath, impactVfx);
                    VfxCmd.PlayVfx(groundPos, VfxCmd.rockShatterPath, impactVfx);
                }
            }

            SfxCmd.Play("event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_attack_stomp");
            NGame.Instance?.ScreenShake(ShakeStrength.Strong, ShakeDuration.Long);

            // Hit-stop: hold the crushed pose so the impact registers before recovery starts.
            await Cmd.Wait(SlamImpactHoldDuration);
            if (_presentationEnded || _capturedPlayers.Count == 0) return;

            // ---------------------------------------------------------------
            // Recovery: a back-ease overshoots slightly, so the captives peel off the
            // floor and bounce back into formation instead of sliding there.
            // ---------------------------------------------------------------
            Tween recoverTween = combatRoom.CreateTween().SetParallel()
                .SetEase(Tween.EaseType.Out).SetTrans(Tween.TransitionType.Back);
            _releaseTween?.Kill();
            _releaseTween = recoverTween;
            foreach ((NCreature node, Vector2 origPos, float origRot, Vector2 origScale) in _capturedPlayers)
            {
                if (!GodotObject.IsInstanceValid(node))
                {
                    continue;
                }
                recoverTween.TweenProperty(node, "position", origPos, SlamRecoverDuration);
                recoverTween.TweenProperty(node, "rotation", origRot, SlamRecoverDuration);
                recoverTween.TweenProperty(node, "scale", origScale, SlamRecoverDuration);
            }

            await Cmd.Wait(SlamRecoverDuration);
            RestoreCapturedPlayersInstantly();
            return;
        }

        // Safe release upon shattered claw: smooth cubic descent back to original stage floor
        // AND smoothly lower the giant stone arm from the sky back to resting ground idle!
        string idleAnim = _isAngry ? "idle_front_angry" : "idle_front";
        MegaAnimationState? bodyState = _bodyController?.TryGetAnimationState();
        MegaAnimationState? armsState = _armsController?.TryGetAnimationState();
        if (bodyState != null)
        {
            bodyState.SetAnimation(idleAnim, true, MainTrack);
            using var trackScope = TrackEntryScope(bodyState.GetCurrent(MainTrack), out MegaTrackEntry? track);
            track?.SetMixDuration(0.5f);
        }
        if (armsState != null)
        {
            armsState.SetAnimation(idleAnim, true, MainTrack);
            using var trackScope = TrackEntryScope(armsState.GetCurrent(MainTrack), out MegaTrackEntry? track);
            track?.SetMixDuration(0.5f);
        }

        float duration = 0.50f;
        Tween tween = combatRoom.CreateTween().SetParallel().SetEase(Tween.EaseType.Out).SetTrans(Tween.TransitionType.Cubic);
        _releaseTween?.Kill();
        _releaseTween = tween;
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
    /// Resets CaveGodArms and CaveGodBody ZIndex back to default layer and ensures arms return to idle.
    /// </summary>
    public void RestoreCapturedPlayersInstantly()
    {
        _releaseTween?.Kill();
        _releaseTween = null;
        _isGrabTracking = false;
        _isSlamDescending = false;
        _isRightGrab = false;
        ResetHandsUi(NCombatRoom.Instance);
        if (!_isRetreating)
        {
            Node2D? armsNode = GetNodeOrNull<Node2D>("%CaveGodArms") ?? GetParent()?.GetNodeOrNull<Node2D>("%CaveGodArms");
            if (armsNode != null)
            {
                armsNode.ZAsRelative = true;
                armsNode.ZIndex = 2;
                armsNode.Scale = new Vector2(1.3f, 1.3f);
            }
            if (_bodyNode != null)
            {
                _bodyNode.ZAsRelative = true;
                _bodyNode.ZIndex = 0;
            }
        }

        string idleAnim = _isAngry ? "idle_front_angry" : "idle_front";
        // On room exit the Spine children have already left the tree. Restore
        // player transforms, but do not create track wrappers from a torn-down rig.
        MegaAnimationState? bodyState = _presentationEnded ? null : _bodyController?.TryGetAnimationState();
        MegaAnimationState? armsState = _presentationEnded ? null : _armsController?.TryGetAnimationState();
        if (bodyState != null)
        {
            using var currentTrackScope = TrackEntryScope(bodyState.GetCurrent(MainTrack), out MegaTrackEntry? currentTrack);
            if (currentTrack != null)
            {
                string currentName = currentTrack.GetAnimationName();
                if (currentName is "grab_player" or "grab_player_angry" or "grab_slam" or "grab_slam_angry"
                    or "grab_player_right" or "grab_player_right_angry" or "grab_slam_right" or "grab_slam_right_angry")
                {
                    bodyState.SetAnimation(idleAnim, true, MainTrack);
                    using var trackScope = TrackEntryScope(bodyState.GetCurrent(MainTrack), out MegaTrackEntry? track);
                    track?.SetMixDuration(0.3f);
                }
            }
        }
        if (armsState != null)
        {
            using var currentTrackScope = TrackEntryScope(armsState.GetCurrent(MainTrack), out MegaTrackEntry? currentTrack);
            if (currentTrack != null)
            {
                string currentName = currentTrack.GetAnimationName();
                if (currentName is "grab_player" or "grab_player_angry" or "grab_slam" or "grab_slam_angry"
                    or "grab_player_right" or "grab_player_right_angry" or "grab_slam_right" or "grab_slam_right_angry")
                {
                    armsState.SetAnimation(idleAnim, true, MainTrack);
                    using var trackScope = TrackEntryScope(armsState.GetCurrent(MainTrack), out MegaTrackEntry? track);
                    track?.SetMixDuration(0.3f);
                }
            }
        }

        foreach ((NCreature node, Vector2 origPos, float origRot, Vector2 origScale) in _capturedPlayers)
        {
            if (GodotObject.IsInstanceValid(node))
            {
                node.ZAsRelative = true;
                node.ZIndex = 0;
                node.Position = origPos;
                node.Rotation = origRot;
                node.Scale = origScale;
                // Preserve the native death pose and keep end-of-combat UI hidden.
                if (!_presentationEnded && node.Entity.IsAlive && CombatManager.Instance.IsInProgress && !CombatManager.Instance.IsEnding)
                {
                    node.AnimEnableUi();
                    node.SetAnimationTrigger("Idle");
                }
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
    /// Pauses Living Megalith's grab animation at apex (t = 2.20s) so the giant fist remains
    /// suspended in the air holding the players while they choose cards and attack the claw.
    /// </summary>
    public void HoldGrabAnim()
    {
        using (TrackEntryScope(_bodyController?.TryGetAnimationState()?.GetCurrent(MainTrack), out MegaTrackEntry? trackBody))
        {
            if (trackBody != null)
            {
                trackBody.SetTrackTime(2.60f);
                trackBody.SetTimeScale(0f);
            }
        }
        using (TrackEntryScope(_armsController?.TryGetAnimationState()?.GetCurrent(MainTrack), out MegaTrackEntry? trackArms))
        {
            if (trackArms != null)
            {
                trackArms.SetTrackTime(2.60f);
                trackArms.SetTimeScale(0f);
            }
        }
        Log.Info("[CaveGodBackground] Grab animation held precisely at apex 2.60s plateau.");
    }

    /// <summary>
    /// Plays the dedicated slam animation (grab_slam / grab_slam_angry) when captives are not freed in time.
    /// Features an upward windup haul into the high sky, followed by a violent downward plunge slam at t = 0.75s.
    /// Seamlessly connects to grab apex hold (mix duration = 0f) since bone frames are 100% pixel-aligned.
    /// </summary>
    public void ResumeSlamAnim()
    {
        _isSlamDescending = false;
        SetTimeScaleBoth(1.0f);
        string slamAnim = _isAngry
            ? (_isRightGrab ? "grab_slam_right_angry" : "grab_slam_angry")
            : (_isRightGrab ? "grab_slam_right" : "grab_slam");
        PrepareContactAim(slamAnim);
        SetTrackAnimationBoth(slamAnim, loop: false, MainTrack);

        // 0f mix duration: initial pose of grab_slam is 100% pixel-aligned with grab_player at 2.60s plateau
        using (TrackEntryScope(_bodyController?.TryGetAnimationState()?.GetCurrent(MainTrack), out MegaTrackEntry? entryBody)) entryBody?.SetMixDuration(0f);
        using (TrackEntryScope(_armsController?.TryGetAnimationState()?.GetCurrent(MainTrack), out MegaTrackEntry? entryArms)) entryArms?.SetMixDuration(0f);

        string idleAnim = _isAngry ? "idle_front_angry" : "idle_front";
        AddTrackAnimationBoth(idleAnim, delay: 0f, loop: true, MainTrack);
        Log.Info($"[CaveGodBackground] Triggered dedicated slam animation '{slamAnim}' (seamless 0f blend from apex).");
    }

    public Marker2D? GetStolenCardPos(bool isLeft)
    {
        if (isLeft)
        {
            return _stolenCardPosLeft ??= GetNodeOrNull<Marker2D>("%StolenCardPosLeft")
                ?? GetParent()?.GetNodeOrNull<Marker2D>("%StolenCardPosLeft")
                ?? GetParent()?.GetNodeOrNull<Marker2D>("StolenCardPosLeft");
        }
        else
        {
            return _stolenCardPosRight ??= GetNodeOrNull<Marker2D>("%StolenCardPosRight")
                ?? GetParent()?.GetNodeOrNull<Marker2D>("%StolenCardPosRight")
                ?? GetParent()?.GetNodeOrNull<Marker2D>("StolenCardPosRight");
        }
    }

    public void AttachStolenCard(bool isLeft, CardModel card)
    {
        if (_presentationEnded) return;
        Marker2D? target = GetStolenCardPos(isLeft);
        if (target == null)
        {
            NCombatRoom? room = NCombatRoom.Instance;
            if (room != null)
            {
                NCreature? creature = room.CreatureNodes.FirstOrDefault(c =>
                    isLeft ? c.Entity?.Monster is ThingsCaveGodLeftHand : c.Entity?.Monster is ThingsCaveGodRightHand);
                target = creature?.GetSpecialNode<Marker2D>("%StolenCardPos");
            }
        }

        if (target != null && GodotObject.IsInstanceValid(target))
        {
            NCard? nCard = null;
            bool wasTestMode = TestMode.IsOn;
            if (wasTestMode)
            {
                TestMode.IsOn = false;
            }
            try
            {
                nCard = NCard.Create(card);
            }
            catch (Exception ex)
            {
                Log.Warn($"[CaveGodBackground] NCard.Create failed ({ex.Message}), falling back to direct instantiation.");
            }
            finally
            {
                if (wasTestMode)
                {
                    TestMode.IsOn = true;
                }
            }

            if (nCard == null)
            {
                var cardScene = GD.Load<PackedScene>("res://scenes/cards/card.tscn");
                if (cardScene != null)
                {
                    nCard = cardScene.Instantiate<NCard>();
                }
            }

            if (nCard != null)
            {
                target.AddChildSafely(nCard);
                try
                {
                    nCard.Model = card;
                }
                catch (Exception ex)
                {
                    Log.Warn($"[CaveGodBackground] Setting NCard.Model threw {ex.Message}");
                }
                var heldCards = target.GetChildren().OfType<NCard>().ToArray();
                for (int i = 0; i < heldCards.Length; i++)
                {
                    float spread = i - (heldCards.Length - 1) * 0.5f;
                    heldCards[i].Position = new Vector2(spread * 22f, Math.Abs(spread) * 5f);
                    heldCards[i].Rotation = spread * 0.07f;
                }
                try
                {
                    nCard.UpdateVisuals(PileType.Deck, CardPreviewMode.Normal);
                }
                catch (Exception ex)
                {
                    Log.Warn($"[CaveGodBackground] NCard.UpdateVisuals threw {ex.Message}");
                }
                target.Visible = true;
                nCard.MouseFilter = Control.MouseFilterEnum.Ignore;
                UpdateStolenCardPositions();
                Log.Info($"[CaveGodBackground] Attached stolen card visual '{card.Id}' to {(isLeft ? "Left" : "Right")} hand.");
            }
            else
            {
                Log.Warn($"[CaveGodBackground] Failed to instantiate NCard for stolen card '{card.Id}'.");
            }
        }
        else
        {
            Log.Warn($"[CaveGodBackground] Could not find StolenCardPos marker for {(isLeft ? "Left" : "Right")} hand.");
        }
    }

    public void ClearStolenCard(bool isLeft)
    {
        Marker2D? target = GetStolenCardPos(isLeft);
        if (target != null && GodotObject.IsInstanceValid(target))
        {
            foreach (Node child in target.GetChildren())
            {
                child.QueueFreeSafely();
            }
            target.Visible = false;
        }

        NCombatRoom? room = NCombatRoom.Instance;
        if (room != null)
        {
            NCreature? creature = room.CreatureNodes.FirstOrDefault(c =>
                isLeft ? c.Entity?.Monster is ThingsCaveGodLeftHand : c.Entity?.Monster is ThingsCaveGodRightHand);
            Marker2D? creatureMarker = creature?.GetSpecialNode<Marker2D>("%StolenCardPos");
            if (creatureMarker != null && GodotObject.IsInstanceValid(creatureMarker) && creatureMarker != target)
            {
                foreach (Node child in creatureMarker.GetChildren())
                {
                    child.QueueFreeSafely();
                }
                creatureMarker.Visible = false;
            }
        }
    }

    public void ClearAllStolenCards()
    {
        ClearStolenCard(true);
        ClearStolenCard(false);
    }

    public const float StolenCardScale = 0.50f;

    private void UpdateStolenCardPositions()
    {
        if (_armsController == null) return;

        // 1. Left hand: bone "arm1_3" (with fallback to "fist1")
        Transform2D? leftHand = _armsController.GetGlobalBoneTransform("arm1_3")
            ?? _armsController.GetGlobalBoneTransform("fist1");
        if (leftHand.HasValue)
        {
            // Carry the card inside the knuckles; use the full bone transform so
            // reaching, wrist rotation, and camera zoom never leave it floating behind.
            Vector2 pos = leftHand.Value * new Vector2(160f, -5f);
            float rot = leftHand.Value.X.Angle() + MathF.PI / 2 - 0.12f;
            Marker2D? leftMarker = GetStolenCardPos(true);
            if (leftMarker != null && GodotObject.IsInstanceValid(leftMarker))
            {
                leftMarker.GlobalPosition = pos;
                leftMarker.GlobalRotation = rot;
                leftMarker.Scale = new Vector2(StolenCardScale, StolenCardScale);
                leftMarker.ZIndex = StolenCardZIndex;
                leftMarker.ZAsRelative = false;
            }

            NCombatRoom? room = NCombatRoom.Instance;
            if (room != null)
            {
                NCreature? leftCreature = room.CreatureNodes.FirstOrDefault(c => c.Entity?.Monster is ThingsCaveGodLeftHand);
                Marker2D? creatureMarker = leftCreature?.GetSpecialNode<Marker2D>("%StolenCardPos");
                if (creatureMarker != null && GodotObject.IsInstanceValid(creatureMarker))
                {
                    creatureMarker.GlobalPosition = pos;
                    creatureMarker.GlobalRotation = rot;
                    creatureMarker.Scale = new Vector2(StolenCardScale, StolenCardScale);
                    creatureMarker.ZIndex = StolenCardZIndex;
                    creatureMarker.ZAsRelative = false;
                }
            }
        }

        // 2. Right hand: bone "arm2_3" (with fallback to "fist2")
        Transform2D? rightHand = _armsController.GetGlobalBoneTransform("arm2_3")
            ?? _armsController.GetGlobalBoneTransform("fist2");
        if (rightHand.HasValue)
        {
            // The right wrist has its own native bind pose; use its transform directly.
            Vector2 pos = rightHand.Value * new Vector2(160f, 5f);
            float rot = rightHand.Value.X.Angle() + MathF.PI / 2 + 0.12f;
            Marker2D? rightMarker = GetStolenCardPos(false);
            if (rightMarker != null && GodotObject.IsInstanceValid(rightMarker))
            {
                rightMarker.GlobalPosition = pos;
                rightMarker.GlobalRotation = rot;
                rightMarker.Scale = new Vector2(StolenCardScale, StolenCardScale);
                rightMarker.ZIndex = StolenCardZIndex;
                rightMarker.ZAsRelative = false;
            }

            NCombatRoom? room = NCombatRoom.Instance;
            if (room != null)
            {
                NCreature? rightCreature = room.CreatureNodes.FirstOrDefault(c => c.Entity?.Monster is ThingsCaveGodRightHand);
                Marker2D? creatureMarker = rightCreature?.GetSpecialNode<Marker2D>("%StolenCardPos");
                if (creatureMarker != null && GodotObject.IsInstanceValid(creatureMarker))
                {
                    creatureMarker.GlobalPosition = pos;
                    creatureMarker.GlobalRotation = rot;
                    creatureMarker.Scale = new Vector2(StolenCardScale, StolenCardScale);
                    creatureMarker.ZIndex = StolenCardZIndex;
                    creatureMarker.ZAsRelative = false;
                }
            }
        }
    }
}
