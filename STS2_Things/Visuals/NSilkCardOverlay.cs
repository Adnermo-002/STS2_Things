using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;

namespace STS2_Things.Visuals;

/// <summary>Queen-style masked card VFX, owned by the native Affliction overlay.</summary>
[GlobalClass]
public partial class NSilkCardOverlay : Control
{
    public const string EffectScenePath = "res://scenes/vfx/ui/card/silk/silk_card_effect.tscn";
    public override void _Ready() => MouseFilter = MouseFilterEnum.Ignore;
    public static void Release(CardModel card)
    {
        if (NCard.FindOnTable(card) is not { } node) return;
        node.OverlayContainer.AddChild(new NSilkUnbindVfx());
    }
}
