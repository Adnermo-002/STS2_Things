using Godot;
using HarmonyLib;
using MegaCrit.Sts2.addons.mega_text;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using STS2_Things.Cards;

namespace STS2_Things.Visuals;

/// <summary>Local visual clock; never reads gameplay RNG or modifies card text/models.</summary>
public partial class NBlindCardVeil : Node
{
    private const string ChildName = "LanternBlindVeil";
    private const string Glyphs = "#%&?+=/*01@$!:;";
    private NCard _card = null!;
    private MegaLabel? _title;
    private MegaRichTextLabel? _description;
    private readonly List<ColorRect> _portraits = [];
    private bool _active;
    private double _clock;
    private int _frame = -1;
    private CardPreviewMode _previewMode;

    public static void RefreshOnTable(CardModel model)
    {
        if (NCard.FindOnTable(model) is { } node &&
            (LanternBlindness.IsBlinded(model) || node.HasNode(ChildName)))
            node.UpdateVisuals(node.DisplayingPile, CardPreviewMode.Normal);
    }

    public static void Refresh(NCard card, CardPreviewMode mode)
    {
        if (!card.IsNodeReady()) return;
        var veil = card.GetNodeOrNull<NBlindCardVeil>(ChildName);
        if (veil == null && LanternBlindness.IsBlinded(card.Model))
        {
            veil = new NBlindCardVeil { Name = ChildName, _card = card };
            card.AddChild(veil);
        }
        if (veil == null) return;
        veil._previewMode = mode;
        veil.RefreshVisuals(nativeRefreshed: true);
    }

    public override void _Ready()
    {
        _title = _card.GetNodeOrNull<MegaLabel>("%TitleLabel");
        _description = _card.GetNodeOrNull<MegaRichTextLabel>("%DescriptionLabel");
        foreach (string name in new[] { "%Portrait", "%AncientPortrait" })
        {
            if (_card.GetNodeOrNull<TextureRect>(name) is not { } portrait) continue;
            var rect = new ColorRect
            {
                Name = "BlindStatic", MouseFilter = Control.MouseFilterEnum.Ignore,
                Material = new ShaderMaterial { Shader = GD.Load<Shader>("res://shaders/cards/lantern_blindness.gdshader") },
                Visible = false
            };
            portrait.AddChild(rect);
            rect.SetAnchorsAndOffsetsPreset(Control.LayoutPreset.FullRect);
            _portraits.Add(rect);
        }
        RefreshVisuals(true);
    }

    public override void _Process(double delta)
    {
        _clock += delta;
        RefreshVisuals(false);
    }

    private void RefreshVisuals(bool nativeRefreshed)
    {
        bool active = LanternBlindness.IsBlinded(_card.Model);
        bool changed = _active != active;
        _active = active;
        foreach (var rect in _portraits) rect.Visible = active;
        if (!active)
        {
            _frame = -1;
            if (changed && !nativeRefreshed && _card.Model != null)
                _card.UpdateVisuals(_card.DisplayingPile, _previewMode);
            return;
        }
        int frame = (int)(_clock * 8);
        if (!nativeRefreshed && frame == _frame) return;
        _frame = frame;
        // Stable lengths avoid layout jitter. BBCode delimiters are never generated.
        _title?.SetTextAutoSize(Scramble(frame, 8, 17));
        _description?.SetTextAutoSize("[center]" + Scramble(frame, 13, 71) + "\n" +
            Scramble(frame, 12, 137) + "\n" + Scramble(frame, 13, 251) + "[/center]");
    }

    private static string Scramble(int frame, int count, uint salt)
    {
        uint state = unchecked((uint)frame * 747796405u + salt);
        char[] chars = new char[count];
        for (int i = 0; i < count; i++)
        {
            state ^= state << 13; state ^= state >> 17; state ^= state << 5;
            chars[i] = Glyphs[(int)(state % Glyphs.Length)];
        }
        return new string(chars);
    }
}

[HarmonyPatch(typeof(NCard), nameof(NCard.UpdateVisuals))]
internal static class LanternBlindnessCardVisualPatch
{
    private static void Postfix(NCard __instance, CardPreviewMode previewMode) => NBlindCardVeil.Refresh(__instance, previewMode);
}
