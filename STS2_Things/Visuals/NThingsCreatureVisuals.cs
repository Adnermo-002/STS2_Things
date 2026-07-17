using System;
using System.Collections.Generic;
using Godot;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Nodes.Combat;

namespace STS2_Things.Visuals;

/// <summary>
/// Godot 场景脚本入口。实际视觉节点遵循 NCreatureVisuals 的 %Visuals、%Bounds、
/// %CenterPos 与 %IntentPos 合同，不需要全局 Harmony 注入或反射替换 _body。
/// </summary>
[GlobalClass]
public partial class NThingsCreatureVisuals : NCreatureVisuals
{
    public enum RigProfileType
    {
        Humanoid,
        Wide,
        Cluster,
        Orb
    }

    public enum RigPersonalityType
    {
        Default,
        OriginFogmog,
        BowlbugProgenitor,
        ScaleBeetle,
        SoulRoes,
        SoulRoe,
        TheLegacy,
        ThiefRaider
    }

    private enum BoneRole
    {
        Root,
        Core,
        Head,
        Left,
        Right
    }

    private sealed class RigBone
    {
        public required string Name { get; init; }
        public required string ParentName { get; init; }
        public required int Depth { get; init; }
        public required Bone2D Node { get; init; }
        public required BoneRole Role { get; init; }
        public required Vector2 NormalizedPosition { get; init; }
        public required Vector2 RestPosition { get; init; }
        public required Vector2 RestScale { get; init; }
        public required float RestRotation { get; init; }
    }

    private readonly List<RigBone> _rigBones = [];
    private Node2D? _rigStage;
    private Vector2 _stagePivot;
    private int _cutoutPartCount;
    private double _idleTime;
    private float _instancePhase;
    private string _action = string.Empty;
    private double _actionTime;
    private double _actionDuration;
    private readonly HashSet<string> _loggedTriggers = new(StringComparer.Ordinal);

    [Export]
    public RigProfileType RigProfile { get; set; } = RigProfileType.Humanoid;

    [Export(PropertyHint.Range, "0.25,2.0,0.05")]
    public float RigMotionScale { get; set; } = 1f;

    [Export]
    public RigPersonalityType RigPersonality { get; set; } = RigPersonalityType.Default;

    [Export(PropertyHint.Range, "0.5,2.0,0.05")]
    public float RigActionScale { get; set; } = 1f;

    [Export(PropertyHint.Range, "0.0,6.28,0.05")]
    public float IdlePhaseOffset { get; set; }

    [Export(PropertyHint.Range, "0.0,1.0,0.05")]
    public float RigStiffness { get; set; } = 0.5f;

    public override void _Ready()
    {
        base._Ready();
        _instancePhase = (GetInstanceId() % 997UL) * 0.0063f;
        BuildCutoutRig();
        SetProcess(_rigStage != null && _cutoutPartCount > 0);
    }

    public override void _Process(double delta)
    {
        if (_rigStage == null || _cutoutPartCount <= 0)
            return;

        _idleTime += delta;
        if (!string.IsNullOrEmpty(_action))
        {
            _actionTime = Math.Min(_actionTime + delta, _actionDuration);
            if (_actionTime >= _actionDuration && _action != "Dead")
                _action = string.Empty;
        }
        ApplyPose();
    }

    /// <summary>
    /// Receives the same semantic triggers as the native CreatureAnimator.  The
    /// implementation is visual-only and intentionally has no gameplay RNG/state.
    /// </summary>
    public void PlayRigAnimation(string trigger)
    {
        if (_rigStage == null || _cutoutPartCount <= 0)
            return;

        if (trigger == "Idle")
        {
            _action = string.Empty;
            _actionTime = 0.0;
            return;
        }
        if (_action == "Dead" && trigger != "Revive")
            return;

        _action = trigger switch
        {
            "Summon" => "Cast",
            "PowerUp" => "Cast",
            _ => trigger
        };
        _actionTime = 0.0;
        _actionDuration = _action switch
        {
            "Attack" => RigPersonality switch
            {
                RigPersonalityType.ScaleBeetle => 1.03,
                RigPersonalityType.OriginFogmog => 0.77,
                RigPersonalityType.TheLegacy => 0.92,
                _ => 0.78
            },
            "Cast" => RigPersonality switch
            {
                RigPersonalityType.ScaleBeetle => 1.33,
                RigPersonalityType.OriginFogmog => 2.20,
                RigPersonalityType.TheLegacy => 1.16,
                _ => 0.98
            },
            "Hit" => RigPersonality switch
            {
                RigPersonalityType.OriginFogmog => 0.58,
                RigPersonalityType.ScaleBeetle => 0.83,
                _ => 0.46
            },
            "Dead" => RigPersonality switch
            {
                RigPersonalityType.OriginFogmog => 1.90,
                RigPersonalityType.ScaleBeetle => 1.37,
                _ => 1.02
            },
            "Revive" => 1.04,
            _ => 0.58
        };
        if (_loggedTriggers.Add(trigger))
        {
            Log.Info($"[ThingsRig] {Name}: firstTrigger={trigger} mappedAction={_action} " +
                     $"duration={_actionDuration:0.00}s personality={RigPersonality}");
        }
    }

    private void BuildCutoutRig()
    {
        var source = GetNodeOrNull<Sprite2D>("%Visuals");
        if (source?.Texture == null)
        {
            GD.PushWarning($"{Name}: cutout rig source sprite or texture is missing.");
            return;
        }

        int width = source.Texture.GetWidth();
        int height = source.Texture.GetHeight();
        if (width <= 0 || height <= 0)
        {
            GD.PushWarning($"{Name}: cutout source texture has invalid dimensions {width}x{height}.");
            return;
        }

        string rigKey = GetCutoutRigKey();
        IReadOnlyList<CutoutPartSpec> parts;
        IReadOnlyList<CutoutBoneSpec> boneSpecs;
        try
        {
            parts = GeneratedCutoutRigData.Get(rigKey);
            boneSpecs = GeneratedCutoutRigData.GetBones(rigKey);
        }
        catch (KeyNotFoundException)
        {
            GD.PushWarning($"{Name}: no rigid cutout data exists for '{rigKey}'.");
            return;
        }
        if (parts.Count == 0)
        {
            GD.PushWarning($"{Name}: rigid cutout data for '{rigKey}' is empty.");
            return;
        }
        if (boneSpecs.Count == 0)
        {
            GD.PushWarning($"{Name}: rigid cutout hierarchy for '{rigKey}' is empty.");
            return;
        }

        // The source Sprite2D remains the native %Visuals node so hitboxes, VFX
        // anchors, encounter scaling and liquid-overlay contracts remain intact.
        // Rigid part sprites live below a dedicated stage; no Polygon2D skin or
        // weighted texture deformation is used.
        var stage = new Node2D { Name = "ThingsRigStage" };
        source.AddChild(stage);
        var skeleton = new Skeleton2D { Name = "ThingsSkeleton2D" };
        stage.AddChild(skeleton);

        var definitions = GetBoneDefinitions();
        var specsByName = new Dictionary<string, CutoutBoneSpec>(StringComparer.Ordinal);
        foreach (CutoutBoneSpec spec in boneSpecs)
        {
            if (!specsByName.TryAdd(spec.Name, spec))
            {
                GD.PushWarning($"{Name}: rigid cutout hierarchy contains duplicate bone '{spec.Name}'.");
                stage.QueueFree();
                return;
            }
        }

        var bonesByName = new Dictionary<string, Bone2D>(StringComparer.Ordinal);
        var boneDepths = new Dictionary<string, int>(StringComparer.Ordinal);
        var visitingBones = new HashSet<string>(StringComparer.Ordinal);
        try
        {
            foreach (CutoutBoneSpec spec in boneSpecs)
            {
                EnsureCutoutBone(
                    spec.Name,
                    skeleton,
                    specsByName,
                    bonesByName,
                    boneDepths,
                    visitingBones,
                    width,
                    height,
                    definitions);
            }
        }
        catch (InvalidOperationException exception)
        {
            GD.PushWarning($"{Name}: invalid rigid cutout hierarchy for '{rigKey}': {exception.Message}");
            stage.QueueFree();
            _rigBones.Clear();
            return;
        }

        // GeneratedCutoutRigData is the single source of truth for the skeleton.
        // Silently creating animation-only root bones here would turn a typo into
        // an invisible control and recreate the old flat pseudo-rig.  Every
        // authored animation bone must therefore exist in the generated tree.
        foreach (var (name, _, _, _) in definitions)
        {
            if (!bonesByName.ContainsKey(name))
            {
                GD.PushWarning($"{Name}: animation definition references missing cutout bone '{name}'.");
                AbortCutoutRig(stage);
                return;
            }
        }

        // Resolve the complete part set transactionally before adding any Sprite2D
        // or hiding the native source.  A partial rig is worse than the intact
        // fallback art because it can leave invisible limbs while still reporting
        // a successful monster scene.
        var preparedParts = new List<(CutoutPartSpec Part, Bone2D Bone, Texture2D Texture)>();
        foreach (CutoutPartSpec part in parts)
        {
            if (!bonesByName.TryGetValue(part.BoneName, out Bone2D? bone) ||
                !specsByName.TryGetValue(part.BoneName, out CutoutBoneSpec boneSpec))
            {
                GD.PushWarning(
                    $"{Name}: cutout part '{part.Name}' references unknown bone '{part.BoneName}'.");
                AbortCutoutRig(stage);
                return;
            }
            if (!boneSpec.PivotPosition.IsEqualApprox(part.PivotPosition))
            {
                GD.PushWarning(
                    $"{Name}: cutout part '{part.Name}' pivot {part.PivotPosition} differs from " +
                    $"bone '{part.BoneName}' bind pivot {boneSpec.PivotPosition}.");
                AbortCutoutRig(stage);
                return;
            }

            if (!ResourceLoader.Exists(part.TexturePath))
            {
                GD.PushWarning($"{Name}: cutout texture is missing: {part.TexturePath}");
                AbortCutoutRig(stage);
                return;
            }
            Texture2D? texture;
            try
            {
                texture = ResourceLoader.Load<Texture2D>(part.TexturePath);
            }
            catch (Exception exception)
            {
                GD.PushWarning(
                    $"{Name}: cutout texture failed to load: {part.TexturePath} ({exception.Message})");
                AbortCutoutRig(stage);
                return;
            }
            if (texture == null)
            {
                GD.PushWarning($"{Name}: cutout texture resolved to null: {part.TexturePath}");
                AbortCutoutRig(stage);
                return;
            }
            preparedParts.Add((part, bone, texture));
        }

        foreach (var prepared in preparedParts)
        {
            CutoutPartSpec part = prepared.Part;
            var sprite = new Sprite2D
            {
                Name = $"{part.Name}Sprite",
                Texture = prepared.Texture,
                Position = part.SpriteOffset,
                ZIndex = part.ZIndex,
                Centered = true,
                TextureFilter = source.TextureFilter,
                Material = source.Material
            };
            prepared.Bone.AddChild(sprite);
            _cutoutPartCount++;
        }

        // SelfModulate affects only the original sprite, leaving its rigged children
        // visible.  Keeping the Sprite2D as %Visuals preserves the native NCreature
        // body, scale, facing and liquid-overlay contracts.
        source.SelfModulate = new Color(1f, 1f, 1f, 0f);
        _rigStage = stage;
        _stagePivot = ResolveStagePivot();
        int hierarchyEdges = 0;
        int maxHierarchyDepth = 0;
        foreach (CutoutBoneSpec spec in boneSpecs)
        {
            if (!string.IsNullOrEmpty(spec.ParentBoneName))
                hierarchyEdges++;
            if (boneDepths.TryGetValue(spec.Name, out int depth))
                maxHierarchyDepth = Math.Max(maxHierarchyDepth, depth);
        }
        Log.Info(
            $"[ThingsRig] {Name}: profile={RigProfile} personality={RigPersonality} bones={_rigBones.Count} " +
            $"rig=rigid-cutout parts={_cutoutPartCount} hierarchyEdges={hierarchyEdges} " +
            $"maxDepth={maxHierarchyDepth} pivot={_stagePivot} key={rigKey}");
        ApplyPose();
    }

    private void AbortCutoutRig(Node2D stage)
    {
        stage.QueueFree();
        _rigBones.Clear();
        _cutoutPartCount = 0;
        _rigStage = null;
        _stagePivot = Vector2.Zero;
    }

    private Vector2 ResolveStagePivot()
    {
        foreach (RigBone bone in _rigBones)
        {
            if (bone.Depth == 0 && (bone.Name == "Root" || bone.Role == BoneRole.Root))
                return bone.RestPosition;
        }
        return Vector2.Zero;
    }

    private Bone2D EnsureCutoutBone(
        string boneName,
        Skeleton2D skeleton,
        IReadOnlyDictionary<string, CutoutBoneSpec> specsByName,
        Dictionary<string, Bone2D> bonesByName,
        Dictionary<string, int> boneDepths,
        HashSet<string> visitingBones,
        int width,
        int height,
        IReadOnlyList<(string name, BoneRole role, Vector2 normalizedPosition, float phase)> definitions)
    {
        if (bonesByName.TryGetValue(boneName, out Bone2D? existing))
            return existing;
        if (!specsByName.TryGetValue(boneName, out CutoutBoneSpec spec))
            throw new InvalidOperationException($"missing bone specification '{boneName}'");
        if (!visitingBones.Add(boneName))
            throw new InvalidOperationException($"cycle detected at bone '{boneName}'");

        Node parentNode = skeleton;
        Vector2 localPosition = spec.PivotPosition;
        int depth = 0;
        if (!string.IsNullOrEmpty(spec.ParentBoneName))
        {
            if (!specsByName.TryGetValue(spec.ParentBoneName, out CutoutBoneSpec parentSpec))
            {
                throw new InvalidOperationException(
                    $"bone '{boneName}' references missing parent '{spec.ParentBoneName}'");
            }
            Bone2D parentBone = EnsureCutoutBone(
                spec.ParentBoneName,
                skeleton,
                specsByName,
                bonesByName,
                boneDepths,
                visitingBones,
                width,
                height,
                definitions);
            parentNode = parentBone;
            localPosition = spec.PivotPosition - parentSpec.PivotPosition;
            depth = boneDepths[spec.ParentBoneName] + 1;
        }

        Bone2D bone = CreateCutoutBone(
            spec.Name,
            spec.ParentBoneName,
            depth,
            localPosition,
            spec.PivotPosition,
            width,
            height,
            definitions);
        parentNode.AddChild(bone);
        bone.Rest = bone.Transform;
        bonesByName.Add(spec.Name, bone);
        boneDepths.Add(spec.Name, depth);
        visitingBones.Remove(boneName);
        return bone;
    }

    private Bone2D CreateCutoutBone(
        string name,
        string parentName,
        int depth,
        Vector2 localPosition,
        Vector2 absolutePosition,
        int width,
        int height,
        IReadOnlyList<(string name, BoneRole role, Vector2 normalizedPosition, float phase)> definitions)
    {
        BoneRole role = InferBoneRole(name, absolutePosition.X);
        Vector2 normalizedPosition = new(
            absolutePosition.X / width + 0.5f,
            absolutePosition.Y / height + 0.5f);
        foreach (var definition in definitions)
        {
            if (!string.Equals(definition.name, name, StringComparison.Ordinal))
                continue;
            role = definition.role;
            normalizedPosition = definition.normalizedPosition;
            break;
        }

        var bone = new Bone2D { Name = name, Position = localPosition };
        bone.SetAutocalculateLengthAndAngle(false);
        bone.SetLength(Math.Max(width, height) * 0.10f);
        bone.SetBoneAngle(0f);
        _rigBones.Add(new RigBone
        {
            Name = name,
            ParentName = parentName,
            Depth = depth,
            Node = bone,
            Role = role,
            NormalizedPosition = normalizedPosition,
            RestPosition = localPosition,
            RestRotation = bone.Rotation,
            RestScale = bone.Scale
        });
        return bone;
    }

    private static BoneRole InferBoneRole(string name, float x)
    {
        if (name.Contains("Root", StringComparison.Ordinal))
            return BoneRole.Root;
        if (name.Contains("Head", StringComparison.Ordinal) ||
            name.Contains("Face", StringComparison.Ordinal) ||
            name.Contains("Cap", StringComparison.Ordinal) ||
            name.Contains("Antenna", StringComparison.Ordinal) ||
            name.Contains("Jaw", StringComparison.Ordinal))
            return BoneRole.Head;
        if (name.Contains("Left", StringComparison.Ordinal) ||
            name.Contains("Front", StringComparison.Ordinal) || x < 0f)
            return BoneRole.Left;
        if (name.Contains("Right", StringComparison.Ordinal) ||
            name.Contains("Rear", StringComparison.Ordinal) || x > 0f)
            return BoneRole.Right;
        return BoneRole.Core;
    }

    private string GetCutoutRigKey()
    {
        return RigPersonality switch
        {
            RigPersonalityType.OriginFogmog => "origin_fogmog",
            RigPersonalityType.BowlbugProgenitor => "bowlbug_progenitor",
            RigPersonalityType.ScaleBeetle => "scale_beetle",
            RigPersonalityType.SoulRoes => "soul_roes",
            RigPersonalityType.SoulRoe => $"soul_roe_{GetSoulRoeVariant() + 1}",
            RigPersonalityType.TheLegacy => "the_legacy",
            RigPersonalityType.ThiefRaider => "thief_raider",
            _ => string.Empty
        };
    }

    private List<(string name, BoneRole role, Vector2 normalizedPosition, float phase)> GetBoneDefinitions()
    {
        return RigPersonality switch
        {
            RigPersonalityType.OriginFogmog =>
            [
                ("Root", BoneRole.Root, new Vector2(0.50f, 0.89f), 0.0f),
                ("Body", BoneRole.Core, new Vector2(0.50f, 0.59f), 0.8f),
                ("Face", BoneRole.Head, new Vector2(0.50f, 0.39f), 1.6f),
                ("CapCenter", BoneRole.Head, new Vector2(0.50f, 0.13f), 2.4f),
                ("LeftArm", BoneRole.Left, new Vector2(0.24f, 0.59f), 3.2f),
                ("RightArm", BoneRole.Right, new Vector2(0.76f, 0.59f), 4.0f),
                ("LeftFoot", BoneRole.Left, new Vector2(0.36f, 0.84f), 4.8f),
                ("RightFoot", BoneRole.Right, new Vector2(0.64f, 0.84f), 5.6f)
            ],
            RigPersonalityType.BowlbugProgenitor =>
            [
                ("Root", BoneRole.Root, new Vector2(0.52f, 0.78f), 0.0f),
                ("Mandible", BoneRole.Left, new Vector2(0.035f, 0.62f), 0.65f),
                ("Head", BoneRole.Left, new Vector2(0.10f, 0.51f), 1.3f),
                ("Crest", BoneRole.Head, new Vector2(0.15f, 0.28f), 1.95f),
                ("FrontLeg", BoneRole.Left, new Vector2(0.23f, 0.78f), 2.6f),
                ("FrontShell", BoneRole.Core, new Vector2(0.28f, 0.40f), 3.25f),
                ("MidShell", BoneRole.Core, new Vector2(0.48f, 0.43f), 3.9f),
                ("EggSac", BoneRole.Core, new Vector2(0.68f, 0.48f), 4.55f),
                ("RearShell", BoneRole.Right, new Vector2(0.86f, 0.43f), 5.2f),
                ("MidLegA", BoneRole.Core, new Vector2(0.49f, 0.75f), 5.85f),
                ("MidLegB", BoneRole.Core, new Vector2(0.67f, 0.75f), 6.5f),
                ("RearLegA", BoneRole.Right, new Vector2(0.79f, 0.75f), 7.15f),
                ("RearLegB", BoneRole.Right, new Vector2(0.92f, 0.75f), 7.8f)
            ],
            RigPersonalityType.ScaleBeetle =>
            [
                ("Root", BoneRole.Root, new Vector2(0.55f, 0.80f), 0.0f),
                ("JawUpper", BoneRole.Left, new Vector2(0.055f, 0.61f), 0.55f),
                ("JawLower", BoneRole.Left, new Vector2(0.09f, 0.69f), 1.10f),
                ("Head", BoneRole.Left, new Vector2(0.18f, 0.53f), 1.65f),
                ("ForeClaw", BoneRole.Left, new Vector2(0.20f, 0.75f), 2.20f),
                ("FrontLeg", BoneRole.Left, new Vector2(0.36f, 0.80f), 2.75f),
                ("MidLeg", BoneRole.Core, new Vector2(0.58f, 0.81f), 3.30f),
                ("RearLeg", BoneRole.Right, new Vector2(0.78f, 0.80f), 3.85f),
                ("FrontShell", BoneRole.Core, new Vector2(0.39f, 0.39f), 4.40f),
                ("Core", BoneRole.Core, new Vector2(0.59f, 0.49f), 4.95f),
                ("RearShell", BoneRole.Right, new Vector2(0.80f, 0.45f), 5.50f),
                ("AntennaFrontBase", BoneRole.Head, new Vector2(0.112f, 0.625f), 6.05f),
                ("AntennaFront1", BoneRole.Head, new Vector2(0.122f, 0.550f), 6.35f),
                ("AntennaFront2", BoneRole.Head, new Vector2(0.147f, 0.424f), 6.65f),
                ("AntennaFront3", BoneRole.Head, new Vector2(0.196f, 0.331f), 6.95f),
                ("AntennaFront4", BoneRole.Head, new Vector2(0.265f, 0.246f), 7.25f),
                ("AntennaFront5", BoneRole.Head, new Vector2(0.348f, 0.185f), 7.55f),
                ("AntennaFrontTip", BoneRole.Head, new Vector2(0.421f, 0.165f), 7.85f),
                ("AntennaBackBase", BoneRole.Head, new Vector2(0.090f, 0.622f), 8.15f),
                ("AntennaBack1", BoneRole.Head, new Vector2(0.075f, 0.550f), 8.45f),
                ("AntennaBack2", BoneRole.Head, new Vector2(0.074f, 0.435f), 8.75f),
                ("AntennaBack3", BoneRole.Head, new Vector2(0.106f, 0.324f), 9.05f),
                ("AntennaBack4", BoneRole.Head, new Vector2(0.165f, 0.227f), 9.35f),
                ("AntennaBack5", BoneRole.Head, new Vector2(0.231f, 0.137f), 9.65f),
                ("AntennaBackTip", BoneRole.Head, new Vector2(0.293f, 0.067f), 9.95f)
            ],
            RigPersonalityType.SoulRoes =>
            [
                ("Root", BoneRole.Root, new Vector2(0.50f, 0.76f), 0.0f),
                ("RoeTopLeft", BoneRole.Left, new Vector2(0.27f, 0.24f), 0.8f),
                ("RoeTop", BoneRole.Head, new Vector2(0.50f, 0.18f), 1.6f),
                ("RoeTopRight", BoneRole.Right, new Vector2(0.74f, 0.26f), 2.4f),
                ("RoeMiddleFarLeft", BoneRole.Left, new Vector2(0.11f, 0.52f), 2.8f),
                ("RoeMiddleLeft", BoneRole.Left, new Vector2(0.18f, 0.49f), 3.2f),
                ("RoeCore", BoneRole.Core, new Vector2(0.50f, 0.48f), 4.0f),
                ("RoeMiddleRight", BoneRole.Right, new Vector2(0.82f, 0.51f), 4.8f),
                ("RoeFarRight", BoneRole.Right, new Vector2(0.91f, 0.66f), 5.2f),
                ("RoeBottomLeft", BoneRole.Left, new Vector2(0.27f, 0.73f), 5.6f),
                ("RoeBottom", BoneRole.Core, new Vector2(0.51f, 0.78f), 6.4f),
                ("RoeBottomRight", BoneRole.Right, new Vector2(0.74f, 0.73f), 7.2f),
                ("RoeBottomFarRight", BoneRole.Right, new Vector2(0.87f, 0.63f), 8.0f)
            ],
            RigPersonalityType.SoulRoe =>
            [
                ("Root", BoneRole.Root, new Vector2(0.50f, 0.50f), 0.0f),
                ("Core", BoneRole.Core, new Vector2(0.50f, 0.54f), 1.25f)
            ],
            RigPersonalityType.TheLegacy =>
            [
                ("Root", BoneRole.Root, new Vector2(0.50f, 0.84f), 0.0f),
                ("HeartAnchor", BoneRole.Core, new Vector2(0.51f, 0.62f), 0.75f),
                ("LeftLobe", BoneRole.Left, new Vector2(0.25f, 0.55f), 1.50f),
                ("HeartCore", BoneRole.Core, new Vector2(0.49f, 0.56f), 2.25f),
                ("RightLobe", BoneRole.Right, new Vector2(0.73f, 0.54f), 3.00f),
                ("TopPurple", BoneRole.Head, new Vector2(0.58f, 0.28f), 3.75f),
                ("LeftTubes", BoneRole.Left, new Vector2(0.18f, 0.40f), 4.50f),
                ("TopTubes", BoneRole.Head, new Vector2(0.49f, 0.21f), 5.25f),
                ("RightTubes", BoneRole.Right, new Vector2(0.84f, 0.50f), 6.00f)
            ],
            RigPersonalityType.ThiefRaider =>
            [
                ("Root", BoneRole.Root, new Vector2(0.51f, 0.91f), 0.0f),
                ("Pelvis", BoneRole.Core, new Vector2(0.52f, 0.72f), 0.8f),
                ("Torso", BoneRole.Core, new Vector2(0.52f, 0.49f), 1.6f),
                ("Head", BoneRole.Head, new Vector2(0.55f, 0.20f), 2.4f),
                ("Bag", BoneRole.Left, new Vector2(0.23f, 0.43f), 3.2f),
                ("Cloak", BoneRole.Left, new Vector2(0.37f, 0.58f), 4.0f),
                ("GuardArm", BoneRole.Left, new Vector2(0.43f, 0.46f), 4.8f),
                ("DaggerUpperArm", BoneRole.Right, new Vector2(0.74f, 0.32f), 5.6f),
                ("DaggerForearm", BoneRole.Right, new Vector2(0.80f, 0.44f), 6.4f),
                ("Dagger", BoneRole.Right, new Vector2(0.88f, 0.56f), 7.2f),
                ("LeftLeg", BoneRole.Left, new Vector2(0.43f, 0.84f), 8.0f),
                ("RightLeg", BoneRole.Right, new Vector2(0.61f, 0.84f), 8.8f)
            ],
            _ => GetFallbackBoneDefinitions()
        };
    }

    private List<(string name, BoneRole role, Vector2 normalizedPosition, float phase)> GetFallbackBoneDefinitions()
    {
        return RigProfile switch
        {
            RigProfileType.Wide =>
            [
                ("Root", BoneRole.Root, new Vector2(0.50f, 0.75f), 0.0f),
                ("Head", BoneRole.Left, new Vector2(0.15f, 0.50f), 1.0f),
                ("Core", BoneRole.Core, new Vector2(0.50f, 0.48f), 2.0f),
                ("Rear", BoneRole.Right, new Vector2(0.85f, 0.52f), 3.0f),
                ("FrontLeg", BoneRole.Left, new Vector2(0.28f, 0.80f), 4.0f),
                ("RearLeg", BoneRole.Right, new Vector2(0.74f, 0.80f), 5.0f)
            ],
            RigProfileType.Cluster =>
            [
                ("Root", BoneRole.Root, new Vector2(0.50f, 0.76f), 0.0f),
                ("TopLeft", BoneRole.Left, new Vector2(0.25f, 0.25f), 1.0f),
                ("Top", BoneRole.Head, new Vector2(0.50f, 0.20f), 2.0f),
                ("TopRight", BoneRole.Right, new Vector2(0.75f, 0.25f), 3.0f),
                ("Core", BoneRole.Core, new Vector2(0.50f, 0.50f), 4.0f),
                ("BottomLeft", BoneRole.Left, new Vector2(0.28f, 0.75f), 5.0f),
                ("BottomRight", BoneRole.Right, new Vector2(0.72f, 0.75f), 6.0f)
            ],
            RigProfileType.Orb =>
            [
                ("Core", BoneRole.Core, new Vector2(0.50f, 0.50f), 0.0f),
                ("Top", BoneRole.Head, new Vector2(0.50f, 0.14f), 1.25f),
                ("Bottom", BoneRole.Root, new Vector2(0.50f, 0.86f), 2.50f),
                ("Left", BoneRole.Left, new Vector2(0.14f, 0.50f), 3.75f),
                ("Right", BoneRole.Right, new Vector2(0.86f, 0.50f), 5.00f)
            ],
            _ =>
            [
                ("Root", BoneRole.Root, new Vector2(0.50f, 0.90f), 0.0f),
                ("Pelvis", BoneRole.Core, new Vector2(0.50f, 0.72f), 0.8f),
                ("Torso", BoneRole.Core, new Vector2(0.50f, 0.49f), 1.6f),
                ("Head", BoneRole.Head, new Vector2(0.50f, 0.20f), 2.4f),
                ("LeftArm", BoneRole.Left, new Vector2(0.25f, 0.49f), 3.2f),
                ("RightArm", BoneRole.Right, new Vector2(0.75f, 0.49f), 4.0f),
                ("LeftLeg", BoneRole.Left, new Vector2(0.39f, 0.82f), 4.8f),
                ("RightLeg", BoneRole.Right, new Vector2(0.61f, 0.82f), 5.6f)
            ]
        };
    }

    private void ApplyPose()
    {
        if (_rigStage == null)
            return;

        float idle = (float)_idleTime + IdlePhaseOffset + _instancePhase;
        float motion = Math.Max(0.10f, RigMotionScale);
        float actionMotion = motion * Math.Max(0.25f, RigActionScale) * GetActionPersonalityScale();
        float flex = Mathf.Lerp(1.18f, 0.72f, Mathf.Clamp(RigStiffness, 0f, 1f));
        float normalizedAction = _actionDuration <= 0.0
            ? 0f
            : Mathf.Clamp((float)(_actionTime / _actionDuration), 0f, 1f);
        float pulse = MathF.Sin(normalizedAction * MathF.PI);
        float attackWindup = ActionWindow(normalizedAction, 0f, 0.24f, 0.46f);
        float attackStrike = ActionWindow(normalizedAction, 0.20f, 0.48f, 1f);
        float settle = 1f - MathF.Pow(1f - normalizedAction, 3f);
        float idleBlend = _action switch
        {
            "Dead" => 1f - settle,
            "Revive" => settle,
            "Attack" or "Cast" or "Hit" => 1f - pulse * 0.92f,
            _ => 1f
        };
        // Idle is deliberately restrained and independent from the exaggerated
        // action multiplier.  This prevents a high-action scene tune from making
        // a grounded monster writhe continuously between turns.
        float idleMotion = Math.Min(motion, 1f) * idleBlend;

        Vector2 stagePosition = Vector2.Zero;
        Vector2 stageScale = Vector2.One;
        float stageRotation = 0f;
        ApplyStableStageIdlePose(idle, idleMotion, ref stagePosition, ref stageScale);
        ApplyStageActionPose(
            normalizedAction,
            settle,
            actionMotion,
            ref stagePosition,
            ref stageRotation,
            ref stageScale);
        ApplyStagePivotCompensation(_stagePivot, stageRotation, stageScale, ref stagePosition);

        _rigStage.Position = stagePosition;
        _rigStage.Rotation = stageRotation;
        _rigStage.Scale = stageScale;

        foreach (var bone in _rigBones)
        {
            Vector2 position = bone.RestPosition;
            float rotation = bone.RestRotation;
            Vector2 scale = bone.RestScale;

            ApplyStableIdleBonePose(bone, ref position, ref rotation, ref scale);
            ApplyRigidPartIdleAccent(
                bone,
                idle,
                idleMotion,
                ref position,
                ref rotation,
                ref scale);
            ApplyBoneActionPose(
                bone,
                normalizedAction,
                pulse,
                attackWindup,
                attackStrike,
                settle,
                actionMotion,
                flex,
                ref position,
                ref rotation,
                ref scale);
            EnforceRigidAssemblyPose(bone, ref position, ref rotation, ref scale);

            bone.Node.Position = position;
            bone.Node.Rotation = rotation;
            bone.Node.Scale = scale;
        }
    }

    private static void ApplyStagePivotCompensation(
        Vector2 pivot,
        float rotation,
        Vector2 scale,
        ref Vector2 position)
    {
        // Node2D transforms around its local origin.  Offset the stage so the
        // authored Root/contact point remains stationary under rotation/scale;
        // explicit action translation still moves that point intentionally.
        Vector2 scaledPivot = new(pivot.X * scale.X, pivot.Y * scale.Y);
        position += pivot - scaledPivot.Rotated(rotation);
    }

    private float GetActionPersonalityScale()
    {
        return (RigPersonality, _action) switch
        {
            (RigPersonalityType.ThiefRaider, "Attack") => 1.32f,
            (RigPersonalityType.OriginFogmog, "Cast") => 1.00f,
            (RigPersonalityType.BowlbugProgenitor, "Cast") => 1.18f,
            (RigPersonalityType.SoulRoes, _) => 1.12f,
            (RigPersonalityType.SoulRoe, "Dead" or "Revive") => 0.58f,
            (RigPersonalityType.SoulRoe, _) => 0.92f,
            (RigPersonalityType.TheLegacy, "Cast") => 1.00f,
            _ => 1f
        };
    }

    private int GetSoulRoeVariant()
    {
        float phase = Mathf.PosMod(IdlePhaseOffset, MathF.Tau);
        if (phase < 1.0f)
            return 0;
        return phase < 3.3f ? 1 : 2;
    }

    private void ApplyStableStageIdlePose(
        float idle,
        float motion,
        ref Vector2 position,
        ref Vector2 scale)
    {
        float slow = MathF.Sin(idle * 1.03f);
        float medium = MathF.Sin(idle * 1.67f + 0.8f);
        float quick = MathF.Sin(idle * 2.31f + 1.4f);

        switch (RigPersonality)
        {
            case RigPersonalityType.OriginFogmog:
                // Keep the assembled cutout planted and express life through one
                // tiny stage breath; structural bones stay at their bind transforms.
                float fogmogBreath = MathF.Sin(idle / 7.667f * MathF.Tau);
                position.Y -= MathF.Max(0f, fogmogBreath) * 0.45f * motion;
                scale += Vector2.One * fogmogBreath * 0.0018f * motion;
                break;
            case RigPersonalityType.BowlbugProgenitor:
                position.Y -= MathF.Max(0f, slow) * 0.35f * motion;
                scale += Vector2.One * slow * 0.0012f * motion;
                break;
            case RigPersonalityType.ScaleBeetle:
                // Shrinker Beetle keeps its armored mass planted for most of its
                // long idle.  Antenna joints animate separately below, so the
                // armored stage needs only a barely visible whole-body breath.
                float beetleBreath = MathF.Sin(idle * 0.72f);
                position.Y -= MathF.Max(0f, beetleBreath) * 0.25f * motion;
                scale += Vector2.One * beetleBreath * 0.0010f * motion;
                break;
            case RigPersonalityType.SoulRoes:
                position += new Vector2(medium * 0.45f, slow * 3.0f) * motion;
                scale += Vector2.One * slow * 0.004f * motion;
                break;
            case RigPersonalityType.SoulRoe:
                switch (GetSoulRoeVariant())
                {
                    case 0:
                        position += new Vector2(medium * 0.45f, slow * 3.6f) * motion;
                        break;
                    case 1:
                        position += new Vector2(medium * 1.0f, MathF.Sin(idle * 1.34f) * 4.0f) * motion;
                        break;
                    default:
                        position += new Vector2(
                            medium * 0.7f,
                            slow * 3.4f + MathF.Sin(idle * 2.6f + 0.7f) * 0.45f) * motion;
                        break;
                }
                scale += Vector2.One * quick * 0.004f * motion;
                break;
            case RigPersonalityType.TheLegacy:
                // The reef stage stays planted; HeartAnchor owns the anatomical
                // contraction while its four rigid child lobes remain locked.
                break;
            case RigPersonalityType.ThiefRaider:
                position.Y -= MathF.Max(0f, slow) * 0.45f * motion;
                scale += Vector2.One * slow * 0.0014f * motion;
                break;
            default:
                if (RigProfile == RigProfileType.Orb)
                    position.Y += slow * 3f * motion;
                break;
        }
    }

    private static void ApplyStableIdleBonePose(
        RigBone bone,
        ref Vector2 position,
        ref float rotation,
        ref Vector2 scale)
    {
        // Every cutout starts from its exact authored bind pose.  Personality
        // accents may then rotate real joints without rubber-warping a sprite.
        position = bone.RestPosition;
        rotation = bone.RestRotation;
        scale = bone.RestScale;
    }

    private void ApplyRigidPartIdleAccent(
        RigBone bone,
        float idle,
        float motion,
        ref Vector2 position,
        ref float rotation,
        ref Vector2 scale)
    {
        switch (RigPersonality)
        {
            case RigPersonalityType.ScaleBeetle
                when bone.Name.StartsWith("Antenna", StringComparison.Ordinal):
                // Lead each seven-joint sweep from the base.  A travelling phase
                // plus a weaker counter-wave prevents the chain from rotating as
                // one rigid rod, while attenuation keeps the tip from whipping.
                float antennaCycle = idle / 8.4f * MathF.Tau;
                float antennaSide = bone.Name.Contains("Front", StringComparison.Ordinal) ? 1f : -1f;
                int antennaJoint = Math.Clamp(bone.Depth - 3, 0, 6);
                float jointRatio = antennaJoint / 6f;
                float antennaAmplitude = Mathf.Lerp(0.030f, 0.006f, jointRatio);
                float antennaSweep = MathF.Sin(
                    antennaCycle + antennaSide * 0.62f + antennaJoint * 0.42f);
                float antennaCounterWave = MathF.Sin(
                    antennaCycle * 1.61f - antennaSide * 1.10f - antennaJoint * 0.55f) * 0.32f;
                rotation += (antennaSweep + antennaCounterWave) * antennaAmplitude * motion;
                break;

            case RigPersonalityType.SoulRoes:
                // Each roe is an independent rigid cell now.  Their fixed spatial
                // phase makes the cluster float organically without changing any
                // individual circular silhouette.
                if (bone.Name == "Root")
                    break;
                float roePhase = bone.NormalizedPosition.X * 7.3f + bone.NormalizedPosition.Y * 11.1f;
                position.Y += MathF.Sin(idle * 1.28f + roePhase) * 1.35f * motion;
                position.X += MathF.Cos(idle * 0.83f + roePhase) * 0.35f * motion;
                break;

            case RigPersonalityType.SoulRoe when bone.Name == "Core":
                scale += Vector2.One * MathF.Sin(idle * 1.65f) * 0.010f * motion;
                break;

            case RigPersonalityType.TheLegacy when bone.Name == "HeartAnchor":
                // Contract the assembled heart from one anatomical anchor.  The
                // four rigid lobes inherit the same 0.7% peak systole, so their
                // seams never open and the surrounding tubes remain planted.
                float heartbeat = GetLegacyHeartbeat((float)_idleTime);
                scale += Vector2.One * heartbeat * 0.007f * motion;
                break;
        }
    }

    private float GetLegacyHeartbeat(float idle)
    {
        bool isEnraged = GetParent() is NCreature creature &&
            creature.Entity.CurrentHp <= creature.Entity.MaxHp / 2;
        float period = isEnraged ? 0.75f : 1.50f;
        float phase = Mathf.PosMod(idle, period) / period;
        float beat =
            -BellPulse(phase, 0.105f, 0.030f)
            + BellPulse(phase, 0.175f, 0.050f) * 0.34f
            - BellPulse(phase, 0.275f, 0.025f) * 0.30f
            + BellPulse(phase, 0.340f, 0.055f) * 0.12f;
        return Mathf.Clamp(beat, -1f, 0.35f) * (isEnraged ? 0.85f : 1f);
    }

    private static float BellPulse(float value, float center, float width)
    {
        float distance = (value - center) / Math.Max(width, 0.001f);
        return MathF.Exp(-distance * distance * 0.5f);
    }

    private void ApplyStageActionPose(
        float normalizedAction,
        float settle,
        float motion,
        ref Vector2 position,
        ref float rotation,
        ref Vector2 scale)
    {
        if (TryApplyPrototypeStageActionPose(
                normalizedAction,
                motion,
                ref position,
                ref rotation,
                ref scale))
            return;

        switch (_action)
        {
            case "Attack":
                float attackAnticipation = ActionWindow(normalizedAction, 0f, 0.18f, 0.34f);
                float attackImpact = ActionWindow(normalizedAction, 0.24f, 0.40f, 0.62f);
                float attackRebound = ActionWindow(normalizedAction, 0.50f, 0.68f, 0.88f);
                float attackStabilize = ActionWindow(normalizedAction, 0.76f, 0.86f, 1f);
                float attackTravel = RigPersonality switch
                {
                    RigPersonalityType.BowlbugProgenitor or RigPersonalityType.ThiefRaider => 1.10f,
                    RigPersonalityType.SoulRoes or RigPersonalityType.SoulRoe => 0.72f,
                    _ => 1f
                };
                position += new Vector2(
                    attackAnticipation * 7f - attackImpact * 20f
                        + attackRebound * 5f - attackStabilize * 1.2f,
                    attackAnticipation * 2.5f - attackImpact * 3f
                        + attackRebound * 1.2f) * (motion * attackTravel);
                rotation += (attackAnticipation * 0.012f - attackImpact * 0.022f
                    + attackRebound * 0.009f) * motion;
                scale += Vector2.One * (-attackAnticipation * 0.004f
                    + attackImpact * 0.009f - attackRebound * 0.003f) * motion;
                break;
            case "Cast":
                float castCharge = ActionWindow(normalizedAction, 0f, 0.22f, 0.42f);
                float castRelease = ActionWindow(normalizedAction, 0.32f, 0.52f, 0.72f);
                float castRecovery = ActionWindow(normalizedAction, 0.62f, 0.78f, 1f);
                position += new Vector2(
                    castCharge * 2.5f - castRelease * 7f + castRecovery * 2f,
                    castCharge * 3f - castRelease * 8f + castRecovery * 2f) * motion;
                rotation += (castCharge * 0.008f - castRelease * 0.014f
                    + castRecovery * 0.006f) * motion;
                scale += Vector2.One * (castCharge * 0.005f
                    + castRelease * 0.010f - castRecovery * 0.003f) * motion;
                break;
            case "Hit":
                float hitImpact = ActionWindow(normalizedAction, 0f, 0.10f, 0.28f);
                float hitRebound = ActionWindow(normalizedAction, 0.18f, 0.38f, 0.62f);
                float hitStabilize = ActionWindow(normalizedAction, 0.52f, 0.70f, 1f);
                position += new Vector2(
                    hitImpact * 14f - hitRebound * 4f + hitStabilize * 1.2f,
                    -hitImpact * 2.5f + hitRebound * 1f) * motion;
                rotation += (hitImpact * 0.018f - hitRebound * 0.008f
                    + hitStabilize * 0.002f) * motion;
                scale += Vector2.One * (-hitImpact * 0.006f + hitRebound * 0.002f) * motion;
                break;
            case "Dead":
                if (RigPersonality == RigPersonalityType.OriginFogmog)
                {
                    float fogmogFall = Smooth01((normalizedAction - 0.08f) / 0.62f);
                    float fogmogSettle = Smooth01((normalizedAction - 0.36f) / 0.46f);
                    position += (new Vector2(24f, 48f) * fogmogFall
                               + new Vector2(4f, 8f) * fogmogSettle) * motion;
                    rotation += (fogmogFall * 0.26f + fogmogSettle * 0.02f) * motion;
                    scale = scale.Lerp(Vector2.One * 0.985f, fogmogFall);
                    break;
                }
                if (RigPersonality == RigPersonalityType.ScaleBeetle)
                {
                    position += new Vector2(42f, 48f) * settle * motion;
                    rotation -= settle * 0.42f * motion;
                    scale = scale.Lerp(Vector2.One * 0.985f, settle);
                    break;
                }
                Vector2 deathOffset = RigProfile switch
                {
                    RigProfileType.Orb => new Vector2(6f, 30f),
                    RigProfileType.Cluster => new Vector2(16f, 48f),
                    _ => new Vector2(24f, 58f)
                };
                position += deathOffset * settle * motion;
                rotation += settle * 0.12f * motion;
                scale = scale.Lerp(Vector2.One * 0.98f, settle);
                break;
            case "Revive":
                float revive = 1f - settle;
                float overshoot = MathF.Sin(normalizedAction * MathF.PI);
                if (RigPersonality == RigPersonalityType.OriginFogmog)
                {
                    position += new Vector2(28f, 56f) * revive * motion;
                    position.Y -= overshoot * 5f * motion;
                    rotation += revive * 0.28f * motion;
                    scale = scale.Lerp(Vector2.One * 0.985f, revive);
                    break;
                }
                if (RigPersonality == RigPersonalityType.ScaleBeetle)
                {
                    position += new Vector2(42f, 48f) * revive * motion;
                    position.Y -= overshoot * 5f * motion;
                    rotation -= revive * 0.42f * motion;
                    scale = scale.Lerp(Vector2.One * 0.985f, revive);
                    break;
                }
                Vector2 reviveOffset = RigProfile switch
                {
                    RigProfileType.Orb => new Vector2(6f, 30f),
                    RigProfileType.Cluster => new Vector2(16f, 48f),
                    _ => new Vector2(24f, 58f)
                };
                position += reviveOffset * revive * motion;
                position.Y -= overshoot * 6f * motion;
                rotation += revive * 0.12f * motion;
                scale = scale.Lerp(Vector2.One * 0.98f, revive);
                scale += Vector2.One * overshoot * 0.012f * motion;
                break;
        }
    }

    private bool TryApplyPrototypeStageActionPose(
        float normalizedAction,
        float motion,
        ref Vector2 position,
        ref float rotation,
        ref Vector2 scale)
    {
        if (_action is not ("Attack" or "Cast" or "Hit"))
            return false;

        switch (RigPersonality)
        {
            case RigPersonalityType.OriginFogmog:
                switch (_action)
                {
                    case "Attack":
                        float fogAttackAnticipation = ActionWindow(normalizedAction, 0f, 0.18f, 0.34f);
                        float fogAttackImpact = ActionWindow(normalizedAction, 0.24f, 0.42f, 0.62f);
                        float fogAttackRebound = ActionWindow(normalizedAction, 0.50f, 0.68f, 0.88f);
                        float fogAttackStabilize = ActionWindow(normalizedAction, 0.76f, 0.86f, 1f);
                        position += new Vector2(
                            fogAttackAnticipation * 6f - fogAttackImpact * 24f
                                + fogAttackRebound * 6f - fogAttackStabilize * 1.5f,
                            fogAttackAnticipation * 2f - fogAttackImpact * 3f
                                + fogAttackRebound) * motion;
                        rotation += (fogAttackAnticipation * 0.010f - fogAttackImpact * 0.020f
                            + fogAttackRebound * 0.008f) * motion;
                        scale += Vector2.One * (-fogAttackAnticipation * 0.004f
                            + fogAttackImpact * 0.009f - fogAttackRebound * 0.003f) * motion;
                        break;
                    case "Cast":
                        float fogCastCharge = ActionWindow(normalizedAction, 0f, 0.20f, 0.38f);
                        float fogCastRelease = ActionWindow(normalizedAction, 0.30f, 0.52f, 0.70f);
                        float fogCastRebound = ActionWindow(normalizedAction, 0.60f, 0.76f, 1f);
                        position += new Vector2(
                            fogCastCharge * 4f - fogCastRelease * 14f + fogCastRebound * 3f,
                            fogCastCharge * 5f - fogCastRelease * 5f + fogCastRebound * 2f) * motion;
                        rotation += (fogCastCharge * 0.008f - fogCastRelease * 0.015f
                            + fogCastRebound * 0.006f) * motion;
                        scale += Vector2.One * (fogCastCharge * 0.006f
                            + fogCastRelease * 0.009f - fogCastRebound * 0.003f) * motion;
                        break;
                    case "Hit":
                        float fogHitImpact = ActionWindow(normalizedAction, 0f, 0.10f, 0.28f);
                        float fogHitRebound = ActionWindow(normalizedAction, 0.18f, 0.38f, 0.62f);
                        float fogHitStabilize = ActionWindow(normalizedAction, 0.50f, 0.70f, 1f);
                        position += new Vector2(
                            fogHitImpact * 18f - fogHitRebound * 5f + fogHitStabilize * 1.5f,
                            -fogHitImpact * 3f + fogHitRebound) * motion;
                        rotation += (fogHitImpact * 0.022f - fogHitRebound * 0.009f
                            + fogHitStabilize * 0.002f) * motion;
                        scale += Vector2.One * (-fogHitImpact * 0.007f
                            + fogHitRebound * 0.002f) * motion;
                        break;
                }
                return true;

            case RigPersonalityType.ScaleBeetle:
                switch (_action)
                {
                    case "Attack":
                        float beetleAnticipation = ActionWindow(normalizedAction, 0f, 0.13f, 0.27f);
                        float beetleImpact = ActionWindow(normalizedAction, 0.18f, 0.32f, 0.54f);
                        float beetleSecondBite = BellPulse(normalizedAction, 0.47f, 0.045f);
                        float beetleRebound = ActionWindow(normalizedAction, 0.44f, 0.62f, 0.82f);
                        float beetleStabilize = ActionWindow(normalizedAction, 0.72f, 0.84f, 1f);
                        position += new Vector2(
                            beetleAnticipation * 8f - beetleImpact * 28f
                                - beetleSecondBite * 4f + beetleRebound * 7f
                                - beetleStabilize * 1.5f,
                            beetleAnticipation * 3f - beetleImpact * 4f
                                + beetleRebound * 1.5f) * motion;
                        rotation += (beetleAnticipation * 0.012f - beetleImpact * 0.022f
                            + beetleRebound * 0.010f) * motion;
                        scale += Vector2.One * (-beetleAnticipation * 0.006f
                            + beetleImpact * 0.010f - beetleRebound * 0.004f) * motion;
                        break;
                    case "Cast":
                        float beetleCharge = ActionWindow(normalizedAction, 0f, 0.18f, 0.36f);
                        float beetleRelease = ActionWindow(normalizedAction, 0.28f, 0.48f, 0.68f);
                        float beetleCastRebound = ActionWindow(normalizedAction, 0.58f, 0.72f, 1f);
                        position += new Vector2(
                            beetleCharge * 4f - beetleRelease * 12f + beetleCastRebound * 3f,
                            beetleCharge * 5f - beetleRelease * 4f + beetleCastRebound) * motion;
                        rotation += (beetleCharge * 0.010f - beetleRelease * 0.018f
                            + beetleCastRebound * 0.007f) * motion;
                        scale += Vector2.One * (-beetleCharge * 0.004f
                            + beetleRelease * 0.009f - beetleCastRebound * 0.003f) * motion;
                        break;
                    case "Hit":
                        float beetleHitImpact = ActionWindow(normalizedAction, 0f, 0.10f, 0.28f);
                        float beetleHitRebound = ActionWindow(normalizedAction, 0.18f, 0.38f, 0.60f);
                        float beetleHitStabilize = ActionWindow(normalizedAction, 0.48f, 0.67f, 1f);
                        position += new Vector2(
                            beetleHitImpact * 18f - beetleHitRebound * 6f
                                + beetleHitStabilize * 2f,
                            -beetleHitImpact * 3f + beetleHitRebound) * motion;
                        rotation += (beetleHitImpact * 0.018f - beetleHitRebound * 0.009f
                            + beetleHitStabilize * 0.003f) * motion;
                        scale += Vector2.One * (-beetleHitImpact * 0.007f
                            + beetleHitRebound * 0.003f) * motion;
                        break;
                }
                return true;

            case RigPersonalityType.TheLegacy:
                switch (_action)
                {
                    case "Attack":
                        float legacyAnticipation = ActionWindow(normalizedAction, 0f, 0.18f, 0.34f);
                        float legacyImpact = ActionWindow(normalizedAction, 0.24f, 0.42f, 0.62f);
                        float legacyRebound = ActionWindow(normalizedAction, 0.50f, 0.68f, 0.90f);
                        position += new Vector2(
                            legacyAnticipation * 2.5f - legacyImpact * 7f + legacyRebound * 2f,
                            legacyAnticipation * 1.5f - legacyImpact + legacyRebound * 0.5f) * motion;
                        rotation += (legacyAnticipation * 0.006f - legacyImpact * 0.012f
                            + legacyRebound * 0.005f) * motion;
                        scale += Vector2.One * (-legacyAnticipation * 0.003f
                            + legacyImpact * 0.006f - legacyRebound * 0.002f) * motion;
                        break;
                    case "Cast":
                        float legacyCharge = ActionWindow(normalizedAction, 0f, 0.22f, 0.42f);
                        float legacyRelease = ActionWindow(normalizedAction, 0.32f, 0.52f, 0.72f);
                        float legacyCastRebound = ActionWindow(normalizedAction, 0.62f, 0.78f, 1f);
                        position += new Vector2(
                            legacyCharge * 1.5f - legacyRelease * 2.5f + legacyCastRebound,
                            legacyCharge * 3f - legacyRelease * 4f + legacyCastRebound * 1.5f) * motion;
                        rotation += (legacyCharge * 0.005f - legacyRelease * 0.009f
                            + legacyCastRebound * 0.004f) * motion;
                        scale += Vector2.One * (legacyCharge * 0.004f
                            + legacyRelease * 0.007f - legacyCastRebound * 0.002f) * motion;
                        break;
                    case "Hit":
                        float legacyHitImpact = ActionWindow(normalizedAction, 0f, 0.10f, 0.28f);
                        float legacyHitRebound = ActionWindow(normalizedAction, 0.18f, 0.38f, 0.62f);
                        float legacyHitStabilize = ActionWindow(normalizedAction, 0.50f, 0.70f, 1f);
                        position += new Vector2(
                            legacyHitImpact * 9.5f - legacyHitRebound * 3f
                                + legacyHitStabilize,
                            -legacyHitImpact * 2f + legacyHitRebound * 0.8f) * motion;
                        rotation += (legacyHitImpact * 0.012f - legacyHitRebound * 0.005f
                            + legacyHitStabilize * 0.0015f) * motion;
                        scale += Vector2.One * (-legacyHitImpact * 0.005f
                            + legacyHitRebound * 0.002f) * motion;
                        break;
                }
                return true;

            default:
                return false;
        }
    }

    private void ApplyBoneActionPose(
        RigBone bone,
        float normalizedAction,
        float pulse,
        float attackWindup,
        float attackStrike,
        float settle,
        float motion,
        float flex,
        ref Vector2 position,
        ref float rotation,
        ref Vector2 scale)
    {
        // Whole-body displacement and squash live on ThingsRigStage.  Bone
        // transforms below are strictly local joint residuals; applying the old
        // flat-rig translation/scale block to every hierarchy depth would multiply
        // motion down antenna, limb and organ chains.
        ApplyPersonalityActionAccent(
            bone,
            normalizedAction,
            pulse,
            attackWindup,
            attackStrike,
            settle,
            motion,
            flex,
            ref position,
            ref rotation,
            ref scale);
    }

    private void EnforceRigidAssemblyPose(
        RigBone bone,
        ref Vector2 position,
        ref float rotation,
        ref Vector2 scale)
    {
        switch (RigPersonality)
        {
            case RigPersonalityType.OriginFogmog:
                // Body -> Face -> CapCenter is one locked silhouette.  Arms and
                // feet are pin joints: rotation is allowed, translation/stretch is not.
                bool fogmogJoint = bone.Name.EndsWith("Arm", StringComparison.Ordinal) ||
                    bone.Name.EndsWith("Foot", StringComparison.Ordinal);
                position = bone.RestPosition;
                scale = bone.RestScale;
                if (!fogmogJoint)
                    rotation = bone.RestRotation;
                break;

            case RigPersonalityType.ScaleBeetle:
                // Keep every armored mass at bind pose.  Only actual appendage
                // joints may rotate; chained antenna motion therefore propagates
                // naturally without translating or stretching any cutout.
                bool beetleJoint = bone.Name.StartsWith("Antenna", StringComparison.Ordinal) ||
                    bone.Name.StartsWith("Jaw", StringComparison.Ordinal) ||
                    bone.Name == "ForeClaw" ||
                    bone.Name.Contains("Leg", StringComparison.Ordinal);
                position = bone.RestPosition;
                scale = bone.RestScale;
                if (!beetleJoint)
                    rotation = bone.RestRotation;
                break;

            case RigPersonalityType.TheLegacy:
                // HeartAnchor is the sole organ control.  Each lobe and every
                // root-level tube stays at its authored local bind transform.
                if (bone.Name != "HeartAnchor")
                {
                    position = bone.RestPosition;
                    rotation = bone.RestRotation;
                    scale = bone.RestScale;
                }
                break;
        }
    }

    private void ApplyPersonalityActionAccent(
        RigBone bone,
        float normalizedAction,
        float pulse,
        float attackWindup,
        float attackStrike,
        float settle,
        float motion,
        float flex,
        ref Vector2 position,
        ref float rotation,
        ref Vector2 scale)
    {
        Vector2 radial = bone.NormalizedPosition - new Vector2(0.5f, 0.5f);
        float side = radial.X < 0f ? -1f : 1f;

        switch (_action)
        {
            case "Cast":
                switch (RigPersonality)
                {
                    case RigPersonalityType.OriginFogmog:
                        float summonThrust = ActionWindow(normalizedAction, 0.30f, 0.52f, 0.70f);
                        if (bone.Name.EndsWith("Arm", StringComparison.Ordinal))
                            rotation += side * summonThrust * 0.10f * motion * flex;
                        else if (bone.Name.EndsWith("Foot", StringComparison.Ordinal))
                            rotation -= side * summonThrust * 0.035f * motion * flex;
                        break;

                    case RigPersonalityType.BowlbugProgenitor:
                        if (bone.Name == "EggSac")
                        {
                            position.Y -= pulse * 22f * motion;
                            scale += new Vector2(pulse * 0.045f, pulse * 0.16f) * motion;
                        }
                        else if (bone.Name is "RearShell" or "MidShell" or "FrontShell")
                        {
                            float shellDelay = bone.Name == "RearShell" ? 0f : bone.Name == "MidShell" ? 0.07f : 0.14f;
                            float shellPulse = ActionWindow(normalizedAction, shellDelay, shellDelay + 0.28f, 0.90f);
                            position.Y -= shellPulse * 14f * motion;
                            scale += new Vector2(shellPulse * 0.025f, shellPulse * 0.085f) * motion;
                        }
                        else if (bone.Name is "Mandible" or "Head")
                            rotation += pulse * 0.18f * motion * flex;
                        break;

                    case RigPersonalityType.ScaleBeetle:
                        float beetleCast = ActionWindow(normalizedAction, 0f, 0.20f, 0.42f)
                            + ActionWindow(normalizedAction, 0.32f, 0.52f, 0.78f) * 0.55f;
                        if (bone.Name.StartsWith("Antenna", StringComparison.Ordinal))
                        {
                            bool frontAntenna = bone.Name.Contains("Front", StringComparison.Ordinal);
                            int antennaJoint = Math.Clamp(bone.Depth - 3, 0, 6);
                            float antennaInfluence = Mathf.Lerp(0.018f, 0.005f, antennaJoint / 6f);
                            rotation += (frontAntenna ? -1f : 1f) * beetleCast
                                * antennaInfluence * motion * flex;
                        }
                        else if (bone.Name is "JawUpper" or "JawLower")
                            rotation += beetleCast * (bone.Name == "JawUpper" ? 0.07f : -0.10f) * motion * flex;
                        else if (bone.Name == "ForeClaw")
                            rotation -= beetleCast * 0.055f * motion * flex;
                        else if (bone.Name.Contains("Leg", StringComparison.Ordinal))
                            rotation += side * beetleCast * 0.040f * motion * flex;
                        break;

                    case RigPersonalityType.SoulRoes:
                        if (bone.Name == "Root")
                            break;
                        position += radial * (pulse * 32f * motion);
                        rotation += pulse * radial.X * 0.30f * motion * flex;
                        scale += Vector2.One * pulse * 0.055f * motion;
                        break;

                    case RigPersonalityType.SoulRoe:
                        if (bone.Name == "Root")
                            break;
                        float roeCast = GetSoulRoeVariant() == 2
                            ? MathF.Max(pulse, ActionWindow(normalizedAction, 0.50f, 0.68f, 0.94f) * 0.65f)
                            : pulse;
                        position += radial * (roeCast * 18f * motion);
                        scale += Vector2.One * roeCast * (bone.Name == "Core" ? 0.18f : 0.07f) * motion;
                        rotation += roeCast * radial.X * 0.18f * motion;
                        break;

                    case RigPersonalityType.TheLegacy:
                        if (bone.Name == "HeartAnchor")
                        {
                            float legacyCharge = ActionWindow(normalizedAction, 0f, 0.22f, 0.42f);
                            float legacyRelease = ActionWindow(normalizedAction, 0.32f, 0.52f, 0.72f);
                            position.Y += (legacyCharge * 1.5f - legacyRelease * 2f) * motion;
                            scale += Vector2.One * (legacyCharge * 0.008f
                                + legacyRelease * 0.010f) * motion;
                        }
                        break;

                    case RigPersonalityType.ThiefRaider:
                        if (bone.Name == "GuardArm")
                        {
                            position += new Vector2(-10f, -18f) * pulse * motion;
                            rotation -= 0.42f * pulse * motion * flex;
                        }
                        else if (bone.Name == "DaggerUpperArm")
                        {
                            position += new Vector2(-6f, -10f) * pulse * motion;
                            rotation += 0.20f * pulse * motion * flex;
                        }
                        else if (bone.Name == "DaggerForearm")
                        {
                            position += new Vector2(-4f, -6f) * pulse * motion;
                            rotation += 0.22f * pulse * motion * flex;
                        }
                        else if (bone.Name == "Dagger")
                        {
                            rotation += 0.10f * pulse * motion * flex;
                        }
                        else if (bone.Name == "Cloak")
                        {
                            position.X += pulse * 18f * motion;
                            scale.X += pulse * 0.11f * motion;
                        }
                        else if (bone.Name == "Head")
                            rotation += pulse * 0.10f * motion;
                        break;
                }
                break;

            case "Attack":
                switch (RigPersonality)
                {
                    case RigPersonalityType.OriginFogmog:
                        float fogAttackThrust = ActionWindow(normalizedAction, 0.24f, 0.42f, 0.62f);
                        if (bone.Name.EndsWith("Arm", StringComparison.Ordinal))
                            rotation += side * fogAttackThrust * 0.12f * motion * flex;
                        else if (bone.Name.EndsWith("Foot", StringComparison.Ordinal))
                            rotation -= side * fogAttackThrust * 0.045f * motion * flex;
                        break;

                    case RigPersonalityType.BowlbugProgenitor:
                        if (bone.Name is "Mandible" or "Head")
                        {
                            position.X -= attackStrike * (bone.Name == "Mandible" ? 42f : 28f) * motion;
                            position.Y += attackStrike * 7f * motion;
                            rotation += attackWindup * 0.24f * motion - attackStrike * 0.34f * motion;
                        }
                        else if (bone.Name == "FrontLeg" ||
                                 bone.Name.StartsWith("MidLeg", StringComparison.Ordinal))
                        {
                            position += new Vector2(-24f, -15f) * attackStrike * motion;
                            rotation -= attackStrike * 0.28f * motion * flex;
                        }
                        else if (bone.Name.StartsWith("RearLeg", StringComparison.Ordinal))
                        {
                            position.X += attackStrike * 8f * motion;
                            rotation += attackStrike * 0.12f * motion * flex;
                        }
                        else if (bone.Name is "EggSac" or "RearShell")
                            position.X += attackStrike * 12f * motion;
                        break;

                    case RigPersonalityType.ScaleBeetle:
                        float beetleLunge = ActionWindow(normalizedAction, 0.18f, 0.32f, 0.54f);
                        float jawOpen = MathF.Max(
                            ActionWindow(normalizedAction, 0.08f, 0.27f, 0.52f),
                            BellPulse(normalizedAction, 0.47f, 0.045f) * 0.55f);
                        if (bone.Name is "JawUpper" or "JawLower")
                            rotation += jawOpen * (bone.Name == "JawUpper" ? 0.18f : -0.28f) * motion * flex;
                        else if (bone.Name == "ForeClaw")
                            rotation -= beetleLunge * 0.12f * motion * flex;
                        else if (bone.Name.Contains("Leg", StringComparison.Ordinal))
                        {
                            float legRotation = bone.Name switch
                            {
                                "FrontLeg" => -0.085f,
                                "MidLeg" => -0.050f,
                                _ => 0.055f
                            };
                            rotation += beetleLunge * legRotation * motion * flex;
                        }
                        else if (bone.Name.StartsWith("Antenna", StringComparison.Ordinal))
                        {
                            int antennaJoint = Math.Clamp(bone.Depth - 3, 0, 6);
                            float antennaInfluence = Mathf.Lerp(0.020f, 0.006f, antennaJoint / 6f);
                            rotation += beetleLunge * antennaInfluence * motion * flex;
                        }
                        break;

                    case RigPersonalityType.SoulRoes:
                        if (bone.Name == "Root")
                            break;
                        position -= radial * attackWindup * 24f * motion;
                        position.X -= attackStrike * (22f - bone.NormalizedPosition.X * 12f) * motion;
                        rotation -= attackStrike * (0.20f + radial.Y * 0.12f) * motion * flex;
                        scale += new Vector2(attackStrike * 0.10f, -attackStrike * 0.06f) * motion;
                        break;

                    case RigPersonalityType.SoulRoe:
                        if (bone.Name == "Root")
                            break;
                        position.X -= attackStrike * 12f * motion;
                        scale += new Vector2(attackStrike * 0.14f, -attackStrike * 0.10f) * motion;
                        rotation += (GetSoulRoeVariant() - 1) * attackStrike * 0.16f * motion;
                        break;

                    case RigPersonalityType.TheLegacy:
                        if (bone.Name == "HeartAnchor")
                        {
                            float legacyAnticipation = ActionWindow(normalizedAction, 0f, 0.18f, 0.34f);
                            float legacyImpact = ActionWindow(normalizedAction, 0.24f, 0.42f, 0.62f);
                            float legacyRebound = ActionWindow(normalizedAction, 0.50f, 0.68f, 0.90f);
                            position.X += (legacyAnticipation * 1.5f - legacyImpact * 3f
                                + legacyRebound) * motion;
                            scale += Vector2.One * (-legacyAnticipation * 0.008f
                                + legacyImpact * 0.010f - legacyRebound * 0.003f) * motion;
                        }
                        break;

                    case RigPersonalityType.ThiefRaider:
                        if (bone.Name == "DaggerUpperArm")
                        {
                            position += new Vector2(-12f, -8f) * attackStrike * motion;
                            rotation -= attackStrike * 0.32f * motion * flex;
                        }
                        else if (bone.Name == "DaggerForearm")
                        {
                            position += new Vector2(-16f, -6f) * attackStrike * motion;
                            rotation -= attackStrike * 0.48f * motion * flex;
                        }
                        else if (bone.Name == "Dagger")
                        {
                            position.X -= attackStrike * 8f * motion;
                            rotation -= attackStrike * 0.18f * motion * flex;
                        }
                        else if (bone.Name is "Bag" or "Cloak")
                        {
                            position.X += attackStrike * 25f * motion;
                            rotation += attackStrike * 0.24f * motion * flex;
                        }
                        else if (bone.Name.Contains("Leg", StringComparison.Ordinal))
                        {
                            position.Y += attackWindup * 13f * motion;
                            rotation += side * attackWindup * 0.16f * motion;
                        }
                        break;
                }
                break;

            case "Hit":
                float hitShake = MathF.Sin(normalizedAction * MathF.PI * 6f) * (1f - normalizedAction);
                switch (RigPersonality)
                {
                    case RigPersonalityType.OriginFogmog:
                        float fogRecoil = ActionWindow(normalizedAction, 0f, 0.10f, 0.28f);
                        float armLag = ActionWindow(normalizedAction, 0.06f, 0.24f, 0.50f);
                        if (bone.Name.EndsWith("Arm", StringComparison.Ordinal))
                            rotation -= side * armLag * 0.10f * motion * flex;
                        else if (bone.Name.EndsWith("Foot", StringComparison.Ordinal))
                            rotation += side * fogRecoil * 0.035f * motion * flex;
                        break;
                    case RigPersonalityType.BowlbugProgenitor:
                        if (bone.Name.Contains("Shell", StringComparison.Ordinal) || bone.Name == "EggSac")
                            position.X += hitShake * 8f * motion;
                        if (bone.Name.Contains("Leg", StringComparison.Ordinal))
                            position += new Vector2(side * 10f, -10f) * pulse * motion;
                        break;
                    case RigPersonalityType.ScaleBeetle:
                        float beetleHitImpact = ActionWindow(normalizedAction, 0f, 0.10f, 0.28f);
                        float beetleHitRebound = ActionWindow(normalizedAction, 0.18f, 0.38f, 0.60f);
                        float beetleJointRecoil = beetleHitImpact - beetleHitRebound * 0.45f;
                        if (bone.Name.StartsWith("Antenna", StringComparison.Ordinal))
                        {
                            bool frontAntenna = bone.Name.Contains("Front", StringComparison.Ordinal);
                            int antennaJoint = Math.Clamp(bone.Depth - 3, 0, 6);
                            float antennaInfluence = Mathf.Lerp(0.022f, 0.007f, antennaJoint / 6f);
                            rotation += (frontAntenna ? 1f : -1f) * beetleJointRecoil
                                * antennaInfluence * motion * flex;
                        }
                        else if (bone.Name is "JawUpper" or "JawLower")
                            rotation += beetleJointRecoil
                                * (bone.Name == "JawUpper" ? 0.060f : -0.090f) * motion * flex;
                        else if (bone.Name == "ForeClaw" || bone.Name.Contains("Leg", StringComparison.Ordinal))
                            rotation -= side * beetleJointRecoil * 0.050f * motion * flex;
                        break;
                    case RigPersonalityType.SoulRoes:
                        if (bone.Name == "Root")
                            break;
                        float roeHit = ActionWindow(
                            normalizedAction,
                            bone.NormalizedPosition.X * 0.12f,
                            0.25f + bone.NormalizedPosition.X * 0.12f,
                            0.88f);
                        position.X += roeHit * (34f - bone.NormalizedPosition.X * 18f) * motion;
                        scale += new Vector2(-roeHit * 0.08f, roeHit * 0.06f) * motion;
                        break;
                    case RigPersonalityType.SoulRoe:
                        if (bone.Name == "Core")
                            position.X += pulse * 12f * motion;
                        rotation += (GetSoulRoeVariant() - 1) * pulse * 0.14f * motion;
                        break;
                    case RigPersonalityType.TheLegacy:
                        if (bone.Name == "HeartAnchor")
                        {
                            float legacyHitImpact = ActionWindow(normalizedAction, 0f, 0.10f, 0.28f);
                            float legacyHitRebound = ActionWindow(normalizedAction, 0.18f, 0.38f, 0.62f);
                            scale += Vector2.One * (-legacyHitImpact * 0.010f
                                + legacyHitRebound * 0.003f) * motion;
                            rotation += (legacyHitImpact * 0.010f
                                - legacyHitRebound * 0.004f) * motion;
                        }
                        break;
                    case RigPersonalityType.ThiefRaider:
                        if (bone.Name == "Head")
                            position.X += pulse * 22f * motion;
                        else if (bone.Name == "Bag")
                            position.X -= pulse * 12f * motion;
                        else if (bone.Name is "Cloak" or "DaggerUpperArm" or "DaggerForearm" or "Dagger")
                            rotation += side * pulse * 0.28f * motion * flex;
                        break;
                }
                break;

            case "Dead":
            case "Revive":
                float collapse = _action == "Dead" ? settle : 1f - settle;
                float revivalBounce = _action == "Revive" ? pulse : 0f;
                switch (RigPersonality)
                {
                    case RigPersonalityType.OriginFogmog:
                        if (bone.Name.EndsWith("Arm", StringComparison.Ordinal))
                            rotation += side * collapse * 0.12f * motion * flex;
                        else if (bone.Name.EndsWith("Foot", StringComparison.Ordinal))
                            rotation -= side * collapse * 0.05f * motion * flex;
                        break;
                    case RigPersonalityType.BowlbugProgenitor:
                        if (bone.Name.Contains("Leg", StringComparison.Ordinal))
                        {
                            position.X -= side * collapse * 24f * motion;
                            position.Y -= collapse * 10f * motion;
                            rotation -= side * collapse * 0.46f * motion * flex;
                        }
                        else if (bone.Name == "EggSac")
                            scale += new Vector2(collapse * 0.14f, -collapse * 0.30f) * motion;
                        else if (bone.Name is "Mandible" or "Head")
                            position.Y += collapse * 18f * motion;
                        break;
                    case RigPersonalityType.ScaleBeetle:
                        if (bone.Name.Contains("Leg", StringComparison.Ordinal) || bone.Name == "ForeClaw")
                            rotation -= side * collapse * 0.18f * motion * flex;
                        else if (bone.Name.StartsWith("Antenna", StringComparison.Ordinal))
                        {
                            bool frontAntenna = bone.Name.Contains("Front", StringComparison.Ordinal);
                            int antennaJoint = Math.Clamp(bone.Depth - 3, 0, 6);
                            float antennaInfluence = Mathf.Lerp(0.030f, 0.009f, antennaJoint / 6f);
                            rotation += (frontAntenna ? 1f : -1f) * collapse
                                * antennaInfluence * motion * flex;
                        }
                        else if (bone.Name is "JawUpper" or "JawLower")
                            rotation += collapse * (bone.Name == "JawUpper" ? 0.10f : -0.14f) * motion * flex;
                        break;
                    case RigPersonalityType.SoulRoes:
                        if (bone.Name == "Root")
                            break;
                        Vector2 scatter = radial * 34f + new Vector2(side * 5f, 22f);
                        position += scatter * collapse * motion;
                        rotation += side * collapse * 0.22f * motion;
                        scale += new Vector2(collapse * 0.08f, -collapse * 0.22f) * motion;
                        break;
                    case RigPersonalityType.SoulRoe:
                        if (bone.Name == "Root")
                            break;
                        position += radial * collapse * 8f * motion;
                        scale += new Vector2(collapse * 0.14f, -collapse * 0.42f) * motion;
                        if (bone.Name == "Core")
                            scale += Vector2.One * revivalBounce * 0.16f * motion;
                        break;
                    case RigPersonalityType.TheLegacy:
                        if (bone.Name == "HeartAnchor")
                        {
                            scale -= Vector2.One * collapse * 0.008f * motion;
                            scale += Vector2.One * revivalBounce * 0.006f * motion;
                        }
                        break;
                    case RigPersonalityType.ThiefRaider:
                        if (bone.Name.Contains("Leg", StringComparison.Ordinal))
                        {
                            position.X += side * collapse * 18f * motion;
                            position.Y -= collapse * 9f * motion;
                            rotation += side * collapse * 0.34f * motion * flex;
                        }
                        else if (bone.Name == "Torso")
                        {
                            position += new Vector2(-18f, 18f) * collapse * motion;
                            rotation -= collapse * 0.22f * motion * flex;
                        }
                        else if (bone.Name is "Head" or "Cloak")
                            rotation -= collapse * 0.08f * motion * flex;
                        else if (bone.Name == "DaggerUpperArm")
                        {
                            position.Y += collapse * 12f * motion;
                            rotation += collapse * 0.25f * motion * flex;
                        }
                        else if (bone.Name == "DaggerForearm")
                        {
                            position.Y += collapse * 10f * motion;
                            rotation += collapse * 0.25f * motion * flex;
                        }
                        else if (bone.Name == "Dagger")
                        {
                            position.Y += collapse * 6f * motion;
                            rotation += collapse * 0.10f * motion * flex;
                        }
                        break;
                }
                break;
        }
    }

    private static float ActionWindow(float value, float start, float peak, float end)
    {
        if (value <= start || value >= end)
            return 0f;
        if (value < peak)
            return Smooth01((value - start) / Math.Max(0.0001f, peak - start));
        return 1f - Smooth01((value - peak) / Math.Max(0.0001f, end - peak));
    }

    private static float Smooth01(float value)
    {
        value = Mathf.Clamp(value, 0f, 1f);
        return value * value * (3f - 2f * value);
    }
}
