using System.Reflection;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text.Json;
using Godot;
using Godot.Bridge;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.RelicPools;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Nodes.HoverTips;
using MegaCrit.Sts2.Core.Nodes.Relics;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Relics;

// Instantiate the real game components directly: their factories deliberately
// return null in TestMode. No production code or gameplay hooks are replaced.
public partial class DepthsProbeNode : Node
{
    private static int _checks;
    private string _root = null!;
    private static void Assert(bool ok, string message)
    {
        if (!ok) throw new InvalidOperationException(message);
        _checks++;
    }

    public override void _Ready()
    {
        AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency;
#if !STS2_V107_1
        EnsureRuntimeDependency("Sentry");
        EnsureRuntimeDependency("Sentry.Godot");
#endif
        _ = Run();
    }

    private async Task Run()
    {
        bool originalHoverBlock = NHoverTipSet.shouldBlockHoverTips;
        try
        {
            _root = Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "../.."));
            TestMode.TurnOnInternal();
            Assert(ProjectSettings.LoadResourcePack(System.Environment.GetEnvironmentVariable("THINGS_VANILLA_PCK")!), "Native game PCK");
            Assert(ProjectSettings.LoadResourcePack(System.Environment.GetEnvironmentVariable("THINGS_PROBE_PCK")!), "Final mod PCK");
            ModHelper.AddModelToPool<EventRelicPool, BottledEcho>();
            ModHelper.AddModelToPool<EventRelicPool, ShadowClaimTicket>();
            ModHelper.AddModelToPool<EventRelicPool, MycelialDeposit>();
            ModHelper.AddModelToPool<EventRelicPool, BorrowedEmber>();
            ModHelper.AddModelToPool<EventRelicPool, ThingsMedusaHair>();
            InitializeModelDb();
            ScriptManagerBridge.LookupScriptsInAssembly(typeof(ModelDb).Assembly);
            ScriptManagerBridge.LookupScriptsInAssembly(typeof(BottledEcho).Assembly);
            SaveManager.Instance.InitSettingsDataForTest();
            SaveManager.Instance.InitPrefsDataForTest();
            SaveManager.Instance.SettingsSave.Language = "zhs";
            LocManager.Initialize();
            var player = Player.CreateForNewRun<Ironclad>(UnlockState.all, 1UL);
            var run = RunState.CreateForNewRun([player], ActModel.GetDefaultList().Select(a => a.ToMutable()).ToList(),
                [], GameMode.Standard, 0, "relic-art-render");
            typeof(RunManager).GetProperty("State", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(RunManager.Instance, run);
            typeof(RunManager).GetProperty("NetService")!.SetValue(RunManager.Instance, new NetSingleplayerGameService());
            // The isolated component host has no NGame hover-tip container.
            // Block tips using the native flag, while testing the actual focus tween.
            NHoverTipSet.shouldBlockHoverTips = true;
            string output = System.Environment.GetEnvironmentVariable("THINGS_PROBE_OUTPUT")!;
            Directory.CreateDirectory(output);
            var view = new SubViewport { Size = new Vector2I(1120, 970), Disable3D = true,
                RenderTargetUpdateMode = SubViewport.UpdateMode.Always };
            AddChild(view);
            GetTree().Root.Size = view.Size;
            var board = new Control { Size = view.Size };
            view.AddChild(board);
            board.AddChild(new ColorRect { Color = new Color("#242930"), Size = view.Size });
            var font = new SystemFont { FontNames = ["Microsoft YaHei"] };
            void LabelAt(string text, Vector2 pos, int size = 19)
            {
                var label = new Label { Text = text, Position = pos };
                label.AddThemeFontOverride("font", font);
                label.AddThemeFontSizeOverride("font_size", size);
                label.AddThemeColorOverride("font_color", new Color("#eee6ce"));
                board.AddChild(label);
            }
            LabelAt("深处事件遗物 · 原生 NRelic / 遗物栏组件", new Vector2(28, 16), 25);
            LabelAt("奖励大图", new Vector2(233, 66));
            LabelAt("遗物栏 / 计数", new Vector2(421, 66));
            LabelAt("聚焦放大", new Vector2(568, 66));
            LabelAt("原生灰置", new Vector2(708, 66));
            LabelAt("原版参考", new Vector2(871, 66));
            (RelicModel Relic, RelicModel Reference, string Key, string Name)[] rows =
            [
                (ModelDb.Relic<BottledEcho>(), ModelDb.Relic<MawBank>(), "bottled_echo", "瓶中回声"),
                (ModelDb.Relic<ShadowClaimTicket>(), ModelDb.Relic<MealTicket>(), "shadow_claim_ticket", "寄存收据"),
                (ModelDb.Relic<MycelialDeposit>(), ModelDb.Relic<ArcaneScroll>(), "mycelial_deposit", "菌根存单"),
                (ModelDb.Relic<BorrowedEmber>(), ModelDb.Relic<EmberTea>(), "borrowed_ember", "余烬约定"),
                (ModelDb.Relic<ThingsMedusaHair>(), ModelDb.Relic<SilkenTress>(), "things_medusa_hair", "美杜莎之发")
            ];
            var focusHolders = new List<NRelicInventoryHolder>();
            for (int i = 0; i < rows.Length; i++)
            {
                var row = rows[i];
                float y = 116 + i * 163;
                board.AddChild(new ColorRect { Position = new Vector2(20, y + 148), Size = new Vector2(1080, 1),
                    Color = new Color("#41454a") });
                LabelAt(row.Name, new Vector2(28, y + 53), 22);
                VerifyPixels(row.Relic.BigIcon, $"images/relics/{row.Key}.png", new Vector2I(256, 256));
                VerifyPixels(row.Relic.Icon, $"images/relics/{row.Key}_packed.png", new Vector2I(85, 85));
                VerifyPixels(row.Relic.IconOutline, $"images/atlases/relic_outline_atlas.sprites/{row.Key}_outline.png", new Vector2I(85, 85));
                Assert(row.Relic.Icon is AtlasTexture && row.Relic.IconOutline is AtlasTexture,
                    row.Key + " uses native AtlasTexture resources");
                var bigModel = Mutable(row.Relic, player);
                var big = GD.Load<PackedScene>("res://scenes/relics/relic.tscn").Instantiate<NRelic>();
                big.Model = bigModel;
                typeof(NRelic).GetField("_iconSize", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(big, NRelic.IconSize.Large);
                big.Position = new Vector2(218, y);
                big.Size = new Vector2(140, 140);
                board.AddChild(big);
                Assert(!big.Outline.Visible && big.Icon.Texture.GetSize() == new Vector2I(256, 256), row.Key + " large component");
                var normal = AddHolder(board, Mutable(row.Relic, player), new Vector2(437, y + 35));
                Assert(normal.Relic.Icon.Texture.GetSize() == new Vector2I(85, 85) && normal.Relic.Outline.Visible,
                    row.Key + " small component and outline");
                var counter = normal.GetNode<Label>("%AmountLabel");
                Assert(counter.Visible == row.Relic.ShowCounter, row.Key + " native counter visibility");
                if (row.Relic.ShowCounter) Assert(counter.Text == row.Relic.DisplayAmount.ToString(), row.Key + " counter value");
                var focus = AddHolder(board, Mutable(row.Relic, player), new Vector2(583, y + 35));
                typeof(NRelicInventoryHolder).GetMethod("OnFocus", BindingFlags.NonPublic | BindingFlags.Instance)!.Invoke(focus, null);
                focusHolders.Add(focus);
                var disabledModel = Mutable(row.Relic, player);
                var disabled = AddHolder(board, disabledModel, new Vector2(722, y + 35));
                disabledModel.Status = RelicStatus.Disabled;
                Assert(disabled.Relic.Icon.Modulate == new Color("#808080"), row.Key + " native disabled tint");
                Assert(((ShaderMaterial)disabled.Relic.Icon.Material).GetShaderParameter("is_used").AsInt32() == 1,
                    row.Key + " native used shader");
                AddHolder(board, Mutable(row.Reference, player), new Vector2(887, y + 35));
            }
            await ToSignal(GetTree().CreateTimer(.25), SceneTreeTimer.SignalName.Timeout);
            foreach (var holder in focusHolders)
                Assert(holder.Relic.Icon.Scale.IsEqualApprox(Vector2.One * 1.25f), "Native focus tween scale");
            await ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
            using (var image = view.GetTexture().GetImage())
                Assert(image.SavePng(Path.Combine(output, "native-relic-components.png")) == Error.Ok, "Native rendered screenshot");
            File.WriteAllText(Path.Combine(output, "report.json"), JsonSerializer.Serialize(new
            {
                assertions = _checks,
                target =
#if STS2_V107_1
                    "v107.1",
#else
                    "v111",
#endif
                relics = rows.Select(r => r.Key).ToArray(),
                render = "Real NRelic / NRelicInventoryHolder, native counter, focus tween and disabled shader; isolated host, not a full client",
                hoverTips = "Blocked in isolated host; tooltip panels not exercised"
            }, new JsonSerializerOptions { WriteIndented = true }));
            NHoverTipSet.shouldBlockHoverTips = originalHoverBlock;
            view.QueueFree();
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            typeof(RunManager).GetProperty("State", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(RunManager.Instance, null);
            GD.Print($"Depths relic art probe: PASS ({_checks} assertions)");
            GetTree().Quit(0);
        }
        catch (Exception e)
        {
            NHoverTipSet.shouldBlockHoverTips = originalHoverBlock;
            GD.PushError(e.ToString());
            GetTree().Quit(1);
        }
    }

    private RelicModel Mutable(RelicModel canonical, Player owner)
    {
        var model = canonical.ToMutable();
        model.Owner = owner;
        return model;
    }

    private static NRelicInventoryHolder AddHolder(Control parent, RelicModel model, Vector2 position)
    {
        var holder = GD.Load<PackedScene>("res://scenes/relics/relic_inventory_holder.tscn").Instantiate<NRelicInventoryHolder>();
        typeof(NRelicInventoryHolder).GetField("_model", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(holder, model);
        holder.Position = position;
        parent.AddChild(holder);
        return holder;
    }

    private void VerifyPixels(Texture2D texture, string path, Vector2I size)
    {
        using var imported = texture.GetImage();
        using var expected = Image.LoadFromFile(Path.Combine(_root, path));
        Assert(imported.GetSize() == size, "Texture dimensions: " + path);
        imported.Convert(Image.Format.Rgba8);
        expected.Convert(Image.Format.Rgba8);
        expected.FixAlphaEdges();
        Assert(SHA256.HashData(imported.GetData()).SequenceEqual(SHA256.HashData(expected.GetData())),
            "Final packaged pixels match selected art: " + path);
    }
}
