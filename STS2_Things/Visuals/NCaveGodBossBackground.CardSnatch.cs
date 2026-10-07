using System;
using System.Collections.Generic;
using System.Linq;
using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Visuals;

public partial class NCaveGodBossBackground
{
    private Vector2 _cardSnatchAimOffset;
    private sealed record SnatchRig(GodotObject Skeleton, GodotObject LeftTarget, GodotObject RightTarget);
    private SnatchRig? _bodySnatchRig;
    private SnatchRig? _armsSnatchRig;
    private string _bodyMainAnimation = "idle_front";
    private string _armsMainAnimation = "idle_front";
    private MegaTrackEntry? _bodyMainEntry;
    private MegaTrackEntry? _armsMainEntry;
    private HashSet<string>? _bossAnimationNames;

    private bool HasBossAnimation(MegaSprite? sprite, string name)
    {
        if (sprite == null) return false;
        if (_bossAnimationNames == null)
        {
            using Variant dataRef = sprite.BoundObject.Get("skeleton_data_res");
            GodotObject data = dataRef.AsGodotObject();
            using Variant listRef = data.Call("get_animations");
            using var animations = listRef.AsGodotArray();
            _bossAnimationNames = new HashSet<string>(StringComparer.Ordinal);
            foreach (Variant animationRef in animations)
            {
                using (animationRef)
                using (GodotObject animation = animationRef.AsGodotObject())
                    _bossAnimationNames.Add(animation.Call("get_name").AsString());
            }
            GC.KeepAlive(data);
        }
        return _bossAnimationNames.Contains(name);
    }

    private void ObserveMainAnimation(MegaSprite sprite, bool foreground)
    {
        // The event's arguments are borrowed. Leaving them as Variants avoids
        // manufacturing an unused managed SpineTrackEntry for the third argument.
        sprite.ConnectAnimationStarted(Callable.From<Variant, Variant, Variant>((_, _, _) =>
        {
            if (_presentationEnded) return;
            // Retain the owned wrapper itself, not a copy of its disposed native
            // object. One reference per animation avoids per-frame signal churn.
            MegaTrackEntry? track = sprite.TryGetAnimationState()?.GetCurrent(MainTrack);
            string name = track?.GetAnimationName() ?? "";
            if (foreground)
            {
                ReleaseMainEntry(_armsMainEntry);_armsMainEntry=track;_armsMainAnimation=name;
            }
            else
            {
                ReleaseMainEntry(_bodyMainEntry);_bodyMainEntry=track;_bodyMainAnimation=name;
            }
        }));
    }

    private static void ReleaseMainEntry(MegaTrackEntry? track)
    {
        if(track==null)return;
        if((object)track is IDisposable disposable)disposable.Dispose();
        else track.BoundObject.Dispose();
    }

    private void ClearMainEntries()
    {
        ReleaseMainEntry(_bodyMainEntry);_bodyMainEntry=null;
        ReleaseMainEntry(_armsMainEntry);_armsMainEntry=null;
    }

    private void ApplyAnimatedHandPose(MegaSprite sprite, bool foreground)
    {
        MegaTrackEntry? track=foreground?_armsMainEntry:_bodyMainEntry;
        if (_presentationEnded || track == null) return;
        float time = track.GetTrackTime();
        ApplyCardSnatchPose(sprite, foreground, time);
        ApplyContactPose(sprite, foreground, time);
    }

    public void StartCardSnatchAnim(bool isLeft, IReadOnlyList<Creature> targets)
    {
        _cardSnatchAimOffset = Vector2.Zero;
        if (_armsNode != null && NCombatRoom.Instance is { } room)
        {
            var positions = targets.Where(target => target.IsAlive && target.Player != null)
                .Select(room.GetCreatureNode).Where(node => node != null && GodotObject.IsInstanceValid(node))
                .Select(node => node!.Visuals != null ? node.VfxSpawnPosition : node.GlobalPosition + new Vector2(0, -65) * node.GetGlobalTransform().Scale.Abs())
                .ToArray();
            if (positions.Length > 0)
            {
                Vector2 center = positions.Aggregate(Vector2.Zero, (sum, position) => sum + position) / positions.Length;
                Vector2 local = _armsNode.ToLocal(center);
                // Spine uses Y-up; the authored closed palm is centered at (0,-175).
                _cardSnatchAimOffset = new Vector2(Mathf.Clamp(local.X, -170f, 170f), Mathf.Clamp(-local.Y + 175f, -110f, 110f));
            }
        }
        StartAttackAnim(isLeft ? "card_snatch" : "card_snatch_right");
        // Finish the entry blend during the small loading dip, before the arm
        // starts its large lift. A long blend would change velocity mid-lift.
        foreach (var sprite in new[] { _bodyController, _armsController })
        {
            using var scope = TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(MainTrack), out MegaTrackEntry? track);
            track?.SetMixDuration(0.12f);
        }
    }

    private void ApplyCardSnatchPose(MegaSprite sprite, bool foreground, float time)
    {
        // Skeleton and bone objects are shared by the sprite. Retain them for its
        // lifetime rather than disposing borrowed objects or creating frame-local
        // wrappers whose finalizers could disconnect signals while rendering.
        SnatchRig? binding = foreground ? _armsSnatchRig : _bodySnatchRig;
        if (binding == null)
        {
            var owner = sprite.GetSkeleton()?.BoundObject;
            if (owner == null) return;
            binding = new SnatchRig(owner, owner.Call("find_bone", "arm1_IK").AsGodotObject(),
                owner.Call("find_bone", "arm2_IK").AsGodotObject());
            if (foreground) _armsSnatchRig = binding; else _bodySnatchRig = binding;
        }
        GodotObject skeleton = binding.Skeleton;
        // The start event also covers queued idle and interrupted moves. Avoid
        // creating/disconnecting an animation wrapper on every rendered frame.
        string clip = foreground ? _armsMainAnimation : _bodyMainAnimation;
        bool snatching = clip.StartsWith("card_snatch", StringComparison.Ordinal);
        bool right = clip.Contains("right", StringComparison.Ordinal);
        if (snatching && _cardSnatchAimOffset != Vector2.Zero && _contactPlans.Length == 0)
        {
            float reach = Mathf.SmoothStep(0, 1, Mathf.Clamp((time - CaveGodAnimTiming.CardSnatchLaunch) /
                (CaveGodAnimTiming.CardSnatchTouch - CaveGodAnimTiming.CardSnatchLaunch), 0, 1));
            float retract = 1 - Mathf.SmoothStep(0, 1, Mathf.Clamp((time - CaveGodAnimTiming.CardSnatchRetract) /
                (CaveGodAnimTiming.CardSnatchSettled - CaveGodAnimTiming.CardSnatchRetract), 0, 1));
            GodotObject bone = right ? binding.RightTarget : binding.LeftTarget;
            bone.Call("set_x", bone.Call("get_x").AsSingle() + _cardSnatchAimOffset.X * reach * retract);
            bone.Call("set_y", bone.Call("get_y").AsSingle() + _cardSnatchAimOffset.Y * reach * retract);
        }
        if (!foreground) return;
        foreach (bool left in new[] { true, false })
        {
            Marker2D? marker = GetStolenCardPos(left);
            if (marker is not { Visible: true } || marker.GetChildCount() == 0) continue;
            // This hand can open to reach for another card or a player. Otherwise
            // retain the grip through idle and other attacks until its cards return.
            bool reaching = (snatching && right != left && time < CaveGodAnimTiming.CardSnatchClose) ||
                (clip.StartsWith("grab_player", StringComparison.Ordinal) && right != left && time < 1.08f);
            if (!reaching)
            {
                string slot = left ? "arm1_3" : "arm2_3";
                skeleton.Call("set_attachment", slot, slot);
            }
        }
    }
}
