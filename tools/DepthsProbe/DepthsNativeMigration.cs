using System.Reflection;
using Godot;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using STS2_Things.Cards;
using STS2_Things.Monsters;
using STS2_Things.Relics;
using STS2_Things.RestSite;

public partial class DepthsProbeNode
{
    private async Task VerifyNativeMigration()
    {
        foreach (var card in new CardModel[] { ModelDb.Card<CaveGodBrokenBladeTrial>(),
                     ModelDb.Card<CaveGodShatteredShieldTrial>(), ModelDb.Card<CaveGodMartialTrial>(),
                     ModelDb.Card<CaveGodArcaneTrial>(), ModelDb.Card<ThingsCaveGodCrystalShard>() })
        {
            string expected = (string)typeof(CardModel).GetProperty("PortraitPngPath", BindingFlags.NonPublic | BindingFlags.Instance)!.GetValue(card)!;
            GD.Print($"NATIVE PORTRAIT {card.Id.Entry}: {expected}");
            Assert(expected == card.PortraitPath && card.HasPortrait, "Vanilla portrait discovery without a getter patch");
            Assert(card.Portrait.GetSize() == new Vector2(1000, 760), "Native card texture loads");
        }
        var sounds = ModelDb.Monster<OriginFogmog>().AssetPaths.Where(p => p.StartsWith("res://sfx/origin_fogmog/")).ToArray();
        Assert(sounds.Length > 0 && sounds.Distinct().Count() == sounds.Length, "Custom SFX belong to native monster AssetPaths");
        foreach (string path in sounds) Assert(ResourceLoader.Exists(path), "Native SFX asset: " + path);

        foreach (int count in new[] { 1, 4 })
        {
            DeactivateSyntheticCombat();
            var run = CreateRun("native-spent-camp-" + count, count);
            run.CurrentActIndex = 1;
            typeof(RunManager).GetProperty("State", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(RunManager.Instance, run);
            typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance, new AscensionManager(0));
            typeof(RunManager).GetProperty("NetService")!.SetValue(RunManager.Instance, new NetSingleplayerGameService());
            run.Map = run.Act.CreateMap(run, false);
            var point = run.Map.GetAllMapPoints().First(p => p.PointType == MapPointType.RestSite);
            run.AddVisitedMapCoord(point.coord);
            run.PushRoom(new RestSiteRoom());
            typeof(RunManager).GetProperty("State", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(RunManager.Instance, run);
            var player = run.Players[0];
            await RelicCmd.Obtain(ModelDb.Relic<Shovel>().ToMutable(), player);
            var ember = (BorrowedEmber)ModelDb.Relic<BorrowedEmber>().ToMutable();
            await RelicCmd.Obtain(ember, player);
            foreach (var (name, value) in new[] { ("CampAct", 1), ("CampColumn", point.coord.col), ("CampRow", point.coord.row) })
                typeof(BorrowedEmber).GetProperty(name)!.SetValue(ember, value);
            Assert(ember.IsSpentCampHere, "Spent-camp fixture matches its actual room and map coordinate");
            var options = RestSiteOption.Generate(player);
            Assert(options.Count == 1 && options[0] is SpentEmberRestSiteOption, "Native option hook replaces Heal/Smith/Shovel/Mend");
            Assert(await options[0].OnSelect(), "Native empty-reward option completes normally");
            if (count > 1)
                Assert(RestSiteOption.Generate(run.Players[1]).Any(o => o is HealRestSiteOption or SmithRestSiteOption), "Other players retain their personal camp options");
        }
        GD.Print("PASS native portrait paths, SFX preload and spent-camp option generation (1/4 players)");
    }
}
