using Godot;

namespace STS2_Things.Encounters;

/// <summary>
/// Keeps the single Living Rock slot on the combat canvas centerline while
/// preserving the native creature ground-line convention below screen center.
/// </summary>
public partial class LivingRockEncounterLayout : Control
{
    private const float GroundLineOffset = 280f;

    public override void _Ready()
    {
        RecenterLivingRock();
        GetViewport().Connect(Viewport.SignalName.SizeChanged, Callable.From(RecenterLivingRock));
    }

    private void RecenterLivingRock()
    {
        Marker2D? slot = GetNodeOrNull<Marker2D>("living_rock");
        if (slot == null)
            return;

        Vector2 viewportSize = GetViewportRect().Size;
        slot.Position = new Vector2(
            viewportSize.X * 0.5f,
            viewportSize.Y * 0.5f + GroundLineOffset);
    }
}
