using Godot;
using MegaCrit.Sts2.Core.Nodes.Combat;

namespace STS2_Things.Visuals;

/// <summary>
/// Visual controller for the Living Megalith (活体巨岩) arm creature nodes.
/// Keeps creature UI at the native world ZIndex 0
/// above the background composition and below later native overlays,
/// so health bars and tooltips remain readable without escaping the game-over backstop.
/// </summary>
[GlobalClass]
public partial class NCaveGodHandCreatureVisuals : NCreatureVisuals
{
    public const int CreatureUiZIndex = 0;

    public override void _Ready()
    {
        base._Ready();
        ElevateCreatureUi();
        Callable.From(ElevateCreatureUi).CallDeferred();
    }

    public void ElevateCreatureUi()
    {
        if (GetParent() is CanvasItem parentItem)
        {
            parentItem.ZIndex = CreatureUiZIndex;
            parentItem.ZAsRelative = false;

            // Elevate StateDisplay / HealthBar (health bar, power container, nameplate)
            Node? healthBar = parentItem.GetNodeOrNull("%HealthBar") 
                ?? parentItem.GetNodeOrNull("HealthBar")
                ?? parentItem.GetNodeOrNull("StateDisplay")
                ?? parentItem.FindChild("HealthBar", recursive: true, owned: false)
                ?? parentItem.FindChild("StateDisplay", recursive: true, owned: false);
            if (healthBar is CanvasItem hpCanvas)
            {
                hpCanvas.ZIndex = CreatureUiZIndex;
                hpCanvas.ZAsRelative = false;
            }

            // Elevate Intents (node in NCreature is %Intents)
            Node? intents = parentItem.GetNodeOrNull("%Intents") 
                ?? parentItem.GetNodeOrNull("Intents")
                ?? parentItem.GetNodeOrNull("%IntentContainer") 
                ?? parentItem.GetNodeOrNull("IntentContainer") 
                ?? parentItem.FindChild("Intents", recursive: true, owned: false)
                ?? parentItem.FindChild("IntentContainer", recursive: true, owned: false);
            if (intents is CanvasItem intentCanvas)
            {
                intentCanvas.ZIndex = CreatureUiZIndex;
                intentCanvas.ZAsRelative = false;
            }
        }
    }
}
