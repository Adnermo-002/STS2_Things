using System.Security.Cryptography;
using Godot;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Saves;
using STS2_Things.Events;

public partial class DepthsProbeNode
{
    private async Task VerifyEventRefresh()
    {
        foreach (var (path, size) in new[] {
            ("images/events/things_medusa.png", new Vector2I(3440,1616)),
            ("images/events/cutting_it_close.png", new Vector2I(3440,1616)),
            ("images/relics/things_medusa_hair.png", new Vector2I(256,256)),
            ("images/atlases/relic_outline_atlas.sprites/things_medusa_hair_outline.png", new Vector2I(85,85)),
            ("images/enchantments/things_split.png", new Vector2I(64,64)) })
        {
            var texture = ResourceLoader.Load<Texture2D>("res://"+path);
            Assert(texture != null, "Packaged event image exists: "+path);
            using var packed = texture!.GetImage();
            using var expected = Image.LoadFromFile(Path.Combine(_root,path));
            Assert(packed.GetSize() == size, "Native image size: "+path);
            packed.Convert(Image.Format.Rgba8); expected.Convert(Image.Format.Rgba8);
            // The established texture importer uses this native alpha-border
            // correction; compare against its result, not unprocessed PNG RGB
            // hidden underneath fully transparent icon pixels.
            if (!path.StartsWith("images/events/")) expected.FixAlphaEdges();
            Assert(SHA256.HashData(packed.GetData()).SequenceEqual(SHA256.HashData(expected.GetData())),
                "Packaged image pixels match selected artwork: "+path);
        }
        foreach (string lang in new[] { "zhs", "eng" })
        {
            SaveManager.Instance.SettingsSave.Language=lang; LocManager.Initialize();
            var run = CreateRun("event-refresh-"+lang,1,0);
            foreach (var canonical in new EventModel[] {ModelDb.Event<ThingsMedusa>(),ModelDb.Event<CuttingItClose>()})
            {
                var model = canonical.ToMutable();
                var begin = typeof(EventModel).GetMethods().Single(method => method.Name == "BeginEvent");
                object?[] arguments = begin.GetParameters().Select(parameter =>
                    parameter.ParameterType == typeof(MegaCrit.Sts2.Core.Entities.Players.Player) ? (object)run.Players[0] :
                    parameter.ParameterType == typeof(bool) ? false : null).ToArray();
                await (Task)begin.Invoke(model,arguments)!;
                Assert(!string.IsNullOrWhiteSpace(model.Description!.GetFormattedText()), "Native initial narrative formats");
                foreach(var option in model.CurrentOptions)
                {
                    // Same binding performed by native NEventOptionButton.
                    model.DynamicVars.AddTo(option.Title);
                    model.DynamicVars.AddTo(option.Description);
                    Assert(!string.IsNullOrWhiteSpace(option.Title.GetFormattedText()), "Native option title formats");
                    string text=option.Description.GetFormattedText();
                    Assert(!text.Contains('{') && !text.Contains('}'), "Native option variables resolve");
                }
                GD.Print($"EVENT TEXT {lang} {model.Id.Entry}: {model.CurrentOptions.Count} native options");
            }
            foreach(string key in new[] {"THINGS_MEDUSA.pages.RETURN_TO_OWNER.description","THINGS_MEDUSA.pages.OFFER_GOLD.description",
                "THINGS_MEDUSA.pages.GREET.description","CUTTING_IT_CLOSE.pages.IMPROVISE.description",
                "CUTTING_IT_CLOSE.pages.THROW.description","CUTTING_IT_CLOSE.pages.ABORTED.description"})
                Assert(!string.IsNullOrWhiteSpace(new LocString("events",key).GetFormattedText()), "Native outcome formats: "+key);
            string relic = new LocString("relics","THINGS_MEDUSA_HAIR.description").GetFormattedText();
            Assert(relic.Contains(lang=="zhs"?"巨石":"Giant Rock") && relic.Contains(lang=="zhs"?"消耗":"Exhaust"),
                "Relic copy describes both generated cards and Exhaust");
        }
        GD.Print("PASS packaged event paintings, transparent icons and native bilingual page formatting");
    }
}
