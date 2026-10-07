using System;
using System.Collections.Generic;
using System.Linq;
using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Visuals;

public partial class NCaveGodBossBackground
{
    public const float PlayerStageOffsetY = 120f;
    private sealed record ContactRig(GodotObject LeftTarget, GodotObject RightTarget,
        GodotObject LeftWrist, GodotObject RightWrist, GodotObject Grab);
    private readonly record struct ContactPlan(CaveGodContactProfile Profile, Vector2 Offset, float Scale, Vector2 GrabOffset);
    private ContactRig? _bodyContactRig, _armsContactRig;
    private ContactPlan[] _contactPlans = [];

    private Vector2 ToSpine(Vector2 world)
    {
        Vector2 p = _armsNode!.ToLocal(world);
        return new Vector2(p.X, -p.Y);
    }

    private void PrepareContactAim(string clip)
    {
        _contactPlans = [];
        if (_armsNode == null || NCombatRoom.Instance is not { } room) return;
        var points = new List<(Vector2 Center, Vector2 Feet)>();
        foreach (var node in room.CreatureNodes.Where(n => n.Entity is { IsPlayer: true, IsAlive: true }))
        {
            Vector2 feet = node.GlobalPosition;
            Vector2 center = node.Visuals != null ? node.VfxSpawnPosition : feet + new Vector2(0, -100) * node.GetGlobalTransform().Scale.Abs();
            var captured = _capturedPlayers.FirstOrDefault(entry => entry.node == node);
            if (captured.node != null && node.GetParent() is CanvasItem parent)
            {
                Vector2 ground = parent.GetGlobalTransform() * captured.origPos;
                center += ground - feet;
                feet = ground;
            }
            points.Add((ToSpine(center), ToSpine(feet)));
        }
        if (points.Count == 0) return;
        points.Sort((a, b) => a.Center.X.CompareTo(b.Center.X));
        Vector2 groundCenter = points.Aggregate(Vector2.Zero, (sum, p) => sum + p.Feet) / points.Count;
        var plans = new List<ContactPlan>();
        foreach (var profile in CaveGodContactProfiles.All.Where(p => p.Clip == clip))
        {
            var group = points;
            if (profile.Paired && points.Count > 1)
            {
                int split = points.Count / 2;
                group = profile.Left ? points.Take(split).ToList() : points.Skip(split).ToList();
            }
            Vector2 center = group.Aggregate(Vector2.Zero, (sum, p) => sum + p.Center) / group.Count;
            if (profile.Paired && points.Count == 1) center.X += profile.Left ? -32 : 32;
            float spanX = group.Max(p => p.Center.X) - group.Min(p => p.Center.X) + 80;
            float spanY = group.Max(p => p.Center.Y) - group.Min(p => p.Center.Y) + 80;
            float scale = Mathf.Clamp(Math.Max(spanX / profile.Size.X, spanY / profile.Size.Y), 1f, 2.25f);
            Vector2 offset = center - profile.Center - profile.PalmOffset * (scale - 1);
            plans.Add(new(profile, offset, scale, groundCenter - new Vector2(-0.65f, -247f)));
        }
        _contactPlans = plans.ToArray();
    }

    private void ApplyContactPose(MegaSprite sprite, bool foreground, float time)
    {
        if (_contactPlans.Length == 0) return;
        string clip = foreground ? _armsMainAnimation : _bodyMainAnimation;
        if (_contactPlans[0].Profile.Clip != clip) return;
        ContactRig? rig = foreground ? _armsContactRig : _bodyContactRig;
        if (rig == null)
        {
            var skeleton = sprite.GetSkeleton()?.BoundObject;
            if (skeleton == null) return;
            rig = new(skeleton.Call("find_bone", "arm1_IK").AsGodotObject(),
                skeleton.Call("find_bone", "arm2_IK").AsGodotObject(),
                skeleton.Call("find_bone", "arm1_3").AsGodotObject(),
                skeleton.Call("find_bone", "arm2_3").AsGodotObject(),
                skeleton.Call("find_bone", "player_grab").AsGodotObject());
            if (foreground) _armsContactRig = rig; else _bodyContactRig = rig;
        }
        foreach (var plan in _contactPlans)
        {
            var p = plan.Profile;
            float weight = Mathf.SmoothStep(0, 1, Mathf.Clamp((time - p.Start) / (p.Hit - p.Start), 0, 1)) *
                (1 - Mathf.SmoothStep(0, 1, Mathf.Clamp((time - p.Hold) / (p.End - p.Hold), 0, 1)));
            if (weight <= 0) continue;
            GodotObject target = p.Left ? rig.LeftTarget : rig.RightTarget;
            GodotObject wrist = p.Left ? rig.LeftWrist : rig.RightWrist;
            target.Call("set_x", target.Call("get_x").AsSingle() + plan.Offset.X * weight);
            target.Call("set_y", target.Call("get_y").AsSingle() + plan.Offset.Y * weight);
            float scale = Mathf.Lerp(1, plan.Scale, weight);
            wrist.Call("set_scale_x", wrist.Call("get_scale_x").AsSingle() * scale);
            wrist.Call("set_scale_y", wrist.Call("get_scale_y").AsSingle() * scale);
            if (p.Grab)
            {
                rig.Grab.Call("set_x", rig.Grab.Call("get_x").AsSingle() + plan.GrabOffset.X * weight);
                rig.Grab.Call("set_y", rig.Grab.Call("get_y").AsSingle() + plan.GrabOffset.Y * weight);
            }
        }
    }
}
