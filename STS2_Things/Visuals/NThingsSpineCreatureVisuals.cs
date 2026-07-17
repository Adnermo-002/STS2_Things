using System;
using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Nodes.Combat;

namespace STS2_Things.Visuals;

/// <summary>
/// Native Spine-backed creature visuals.  The <c>%Visuals</c> node in each
/// scene is itself a SpineSprite, so the complete monster is submitted as one
/// CanvasItem and its internal slot order cannot leak across combat/UI layers.
/// </summary>
[GlobalClass]
public partial class NThingsSpineCreatureVisuals : NCreatureVisuals
{
    private static readonly string[] _requiredAnimations =
    [
        "idle_loop",
        "attack",
        "cast",
        "hurt",
        "die",
        "summon",
        "power_up",
        "revive",
    ];

    public override void _Ready()
    {
        base._Ready();
        if (SpineBody == null)
        {
            GD.PushWarning($"{Name}: native STS2_Things SpineSprite did not load its skeleton data.");
            return;
        }

        foreach (string animation in _requiredAnimations)
        {
            if (!SpineBody.HasAnimation(animation))
                GD.PushWarning($"{Name}: native Spine skeleton is missing '{animation}'.");
        }

        Log.Info($"[ThingsSpine] {Name}: native SpineSprite ready; " +
                 $"animations={_requiredAnimations.Length}; canvasItem=single");
    }

    /// <summary>
    /// Compatibility path for a Spine visual used by a model that has not yet
    /// adopted ThingsSpineMonster.GenerateAnimator.  The mod monsters use that
    /// native CreatureAnimator state graph directly; this method prevents a
    /// future standalone scene from silently dropping the three extra semantic
    /// triggers.
    /// </summary>
    public bool TryPlaySupplementalAnimation(string trigger)
    {
        string animation = trigger switch
        {
            "Summon" => "summon",
            "PowerUp" => "power_up",
            "Revive" => "revive",
            _ => string.Empty,
        };
        if (animation.Length == 0 || SpineBody == null ||
            !SpineBody.HasAnimation(animation) || !SpineBody.HasAnimation("idle_loop"))
        {
            return false;
        }

        MegaAnimationState? state = SpineBody.TryGetAnimationState();
        if (state == null)
            return false;

        state.SetAnimation(animation, loop: false);
        state.AddAnimation("idle_loop", delay: 0f, loop: true);
        return true;
    }
}
