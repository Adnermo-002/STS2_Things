using System.Text.Json;
using Godot;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Saves;
using STS2_Things.Cards;
using STS2_Things.Encounters;
using STS2_Things.Powers;

public partial class CaveGodProbeNode
{
    // Authoring review: use the shipped card and power scenes to inspect their
    // actual crops, locale text, native icon fallback and imported textures.
    private async Task RenderCaveGodUiArt()
    {
        string root = Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "../.."));
        string output = Path.Combine(root, "build/cavegod_ui_renew/native-review");
        Directory.CreateDirectory(output);
        SaveManager.Instance.InitPrefsDataForTest();
        SaveManager.Instance.SettingsSave.Language = "zhs";
        LocManager.Initialize();
        var scenario = Scenario();
        var player = scenario.State.Players[0];
        var view = new SubViewport { Size = new Vector2I(1920, 1080), Disable3D = true,
            RenderTargetUpdateMode = SubViewport.UpdateMode.Always };
        AddChild(view);
        void Backdrop() => view.AddChild(new ColorRect { Size = new Vector2(1920, 1080), Color = new Color("243137") });
        void Caption(string text, Vector2 position, int size = 24)
        {
            var label = new Label { Text = text, Position = position };
            label.AddThemeFontSizeOverride("font_size", size);
            view.AddChild(label);
        }
        void Texture(Texture2D texture, Vector2 position, Vector2 size, Color? tint = null)
        {
            view.AddChild(new TextureRect { ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
                Texture = texture, Position = position, Size = size,
                StretchMode = TextureRect.StretchModeEnum.KeepAspectCentered, Modulate = tint ?? Colors.White });
        }
        async Task Capture(string name)
        {
            for (int i = 0; i < 45; i++) await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            await ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
            using var image = view.GetTexture().GetImage();
            Assert(image.SavePng(Path.Combine(output, name + ".png")) == Error.Ok, "Save native UI image");
        }
        Backdrop();
        Caption("Cave God - native card scenes / Chinese locale", new Vector2(45, 45), 32);
        CardModel[] cards = [
            scenario.State.CreateCard<CaveGodBrokenBladeTrial>(player),
            scenario.State.CreateCard<CaveGodShatteredShieldTrial>(player),
            scenario.State.CreateCard<ThingsCaveGodCrystalShard>(player),
            scenario.State.CreateCard<CaveGodMartialTrial>(player),
            scenario.State.CreateCard<CaveGodArcaneTrial>(player),
        ];
        var paths = new List<string>();
        for (int i = 0; i < cards.Length; i++)
        {
            var model = cards[i];
            Assert(model.HasPortrait && model.Portrait.GetSize() == new Vector2(1000, 760), "Imported portrait: " + model.Id);
            var card = GD.Load<PackedScene>("res://scenes/cards/card.tscn").Instantiate<NCard>();
            card.Model = model;
            card.Position = new Vector2(205 + i * 377, 450);
            card.Scale = Vector2.One * 1.1f;
            view.AddChild(card);
            card.UpdateVisuals(PileType.Hand, CardPreviewMode.Normal);
            paths.Add(model.PortraitPath);
        }
        Caption("Active encounter", new Vector2(55, 760));
        Caption("Legacy cards retained for save compatibility", new Vector2(1165, 760));
        await Capture("native-cards");
        foreach (Node child in view.GetChildren()) { view.RemoveChild(child); child.QueueFree(); }
        await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);

        Backdrop();
        Caption("Cave God - native NPower HUD + hover icons", new Vector2(45, 45), 32);
        PowerModel[] powers = [
            ModelDb.Power<ThingsCaveGodAgingPower>(), ModelDb.Power<ThingsCaveGodAncientCorePower>(),
            ModelDb.Power<ThingsCaveGodCrystalVeinPower>(), ModelDb.Power<ThingsCaveGodFissurePower>(),
            ModelDb.Power<CaveGodBrokenBladePower>(), ModelDb.Power<CaveGodShatteredShieldPower>(),
            ModelDb.Power<CaveGodMartialPower>(), ModelDb.Power<CaveGodArcanePower>(),
        ];
        for (int i = 0; i < powers.Length; i++)
        {
            var canonical = powers[i];
            Assert(ResourceLoader.Exists(canonical.PackedIconPath) && !canonical.ResolvedBigIconPath.Contains("missing_power"), "Native power paths: " + canonical.Id);
            Assert(canonical.BigIcon.GetSize() == new Vector2(256, 256), "Large power image: " + canonical.Id);
            var mutable = canonical.ToMutable();
            mutable.ApplyInternal(scenario.Body.Creature, 2, silent: true);
            var hud = NPower.Create(mutable);
            hud.Position = new Vector2(110 + i * 230, 160);
            view.AddChild(hud);
            Texture(canonical.BigIcon, new Vector2(68 + i * 230, 295), new Vector2(144, 144));
            paths.Add(canonical.PackedIconPath);
            paths.Add(canonical.ResolvedBigIconPath);
        }
        Caption("Original map tint and outline assets", new Vector2(45, 580), 28);
        view.AddChild(new ColorRect { Position = new Vector2(45, 650), Size = new Vector2(755, 340), Color = new Color("b8ad90") });
        string mapPath = ModelDb.Encounter<CaveGodBossEncounter>().BossNodePath;
        Texture(GD.Load<Texture2D>(mapPath + ".png"), new Vector2(60, 665), new Vector2(352, 300), new Color("332c28"));
        Texture(GD.Load<Texture2D>(mapPath + "_outline.png"), new Vector2(430, 665), new Vector2(352, 300), new Color("6b4a26"));
        Texture(GD.Load<Texture2D>(mapPath + ".png"), new Vector2(430, 665), new Vector2(352, 300), new Color("332c28"));
        paths.Add(mapPath + ".png"); paths.Add(mapPath + "_outline.png");
        Caption("Run history - 88 px", new Vector2(1050, 650));
        foreach (string stem in new[] { "cave_god_boss", "cave_god_boss_encounter" })
        {
            float x = stem.EndsWith("encounter") ? 1300 : 1100;
            foreach (string suffix in new[] { "", "_outline" })
            {
                string path = "res://images/ui/run_history/" + stem + suffix + ".png";
                var texture = GD.Load<Texture2D>(path);
                Assert(texture.GetSize() == new Vector2(88, 88), "Run history size");
                Texture(texture, new Vector2(x, suffix.Length == 0 ? 745 : 860), new Vector2(88, 88));
                paths.Add(path);
            }
        }
        await Capture("native-powers-avatars");
        File.WriteAllText(Path.Combine(output, "loaded-assets.json"), JsonSerializer.Serialize(paths, new JsonSerializerOptions { WriteIndented = true }));
        view.QueueFree();
        await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
        GD.Print($"CaveGod UI art review: PASS ({cards.Length} native cards, {powers.Length} native powers, 6 avatars)");
    }
}
