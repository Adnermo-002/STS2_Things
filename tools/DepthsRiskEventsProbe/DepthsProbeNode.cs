using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
using System.Security.Cryptography;
using Godot;
using Godot.Bridge;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Relics;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.RelicPools;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Multiplayer.Serialization;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Saves.Runs;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Acts;
using STS2_Things.Encounters;
using STS2_Things.Events;
using STS2_Things.Relics;

public partial class DepthsProbeNode : Node
{
    private string _root = null!;
    private static int _checks;
    private static readonly ThrowingPlayerChoiceContext Choice = new();
    private static bool SkipUiGuard() => false;
    private static void Assert(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
        _checks++;
    }
    public override void _Ready()
    {
        AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency;
#if !STS2_V107_1
        EnsureRuntimeDependency("Sentry"); EnsureRuntimeDependency("Sentry.Godot");
#endif
        _ = Run();
    }
    private async Task Run()
    {
        try
        {
            _root = Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "../.."));
            TestMode.TurnOnInternal();
            Assert(ProjectSettings.LoadResourcePack("D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck"), "Native PCK");
            Assert(ProjectSettings.LoadResourcePack(System.Environment.GetEnvironmentVariable("THINGS_PROBE_PCK")!), "Final mod PCK");
            ModHelper.AddModelToPool<EventRelicPool, AnestheticChart>();
            typeof(AnestheticChart).Assembly.GetType("STS2_Things.Compatibility.Sts2VersionCompatibility")!
                .GetMethod("InitializeBeforeModelDatabase",BindingFlags.Static|BindingFlags.Public)!.Invoke(null,null);
            InitializeModelDb();
            ScriptManagerBridge.LookupScriptsInAssembly(typeof(ModelDb).Assembly);
            SaveManager.Instance.InitSettingsDataForTest(); SaveManager.Instance.InitPrefsDataForTest();
            var host = new Harmony("DepthsRiskEventsProbe.UiHost");
            host.Patch(AccessTools.Method(typeof(CombatStateTracker), "NotifyCombatStateChanged"),
                prefix: new HarmonyMethod(typeof(DepthsProbeNode), nameof(SkipUiGuard)));
            foreach (string lang in new[] {"zhs", "eng"})
            {
                SaveManager.Instance.SettingsSave.Language = lang; LocManager.Initialize();
                await VerifyBranches();
                await VerifyAnesthesia();
            }
            if (System.Environment.GetEnvironmentVariable("THINGS_RISK_RENDER") == "1") await RenderEventLayouts();
            host.UnpatchAll(host.Id); DeactivateSyntheticCombat();
            foreach (var canonical in new EventModel[] {ModelDb.Event<BitingChest>(), ModelDb.Event<CrowdedWard>()})
            {
                Assert(ModelDb.Act<Depths>().AllEvents.Any(e => e.Id == canonical.Id), "New event in Depths pool");
                foreach (string path in canonical.GetAssetPaths(NewRun("asset-check"))) Assert(ResourceLoader.Exists(path), "Event asset: " + path);
            }
            var icon = ModelDb.Relic<AnestheticChart>();
            Assert(icon.Icon.GetSize() == new Vector2(85,85) && icon.BigIcon.GetSize() == new Vector2(256,256), "Relic sizes");
            Assert(icon.IconOutline.GetSize() == new Vector2(85,85), "Relic outline");
            Assert(!icon.ToMutable().IsTradable, "Debt cannot be traded away");
            foreach (string key in new[] {"biting_chest","crowded_ward"})
            {
                using var packed = ResourceLoader.Load<Texture2D>($"res://images/events/{key}.png").GetImage();
                using var selected = Image.LoadFromFile(Path.Combine(_root,$"images/events/{key}.png"));
                packed.Convert(Image.Format.Rgba8);selected.Convert(Image.Format.Rgba8);
                Assert(packed.GetSize() == new Vector2I(3440,1616),"Native portrait canvas");
                Assert(SHA256.HashData(packed.GetData()).SequenceEqual(SHA256.HashData(selected.GetData())),"Final packaged portrait pixels: "+key);
            }
            var output = System.Environment.GetEnvironmentVariable("THINGS_PROBE_OUTPUT")!;
            File.WriteAllText(Path.Combine(output, "behavior-report.json"), JsonSerializer.Serialize(new
            {
                assertions = _checks, languages = new[] {"zhs", "eng"}, simulatedPlayerCounts = new[] {1,2,3,4},
                checks = "Both chest RNG outcomes, deterministic seed, all six choices, repeat clicks, depleted bags, HP cap, lethal warnings, owner isolation, native hand draw, modifiers, two-combat expiry and save round trip",
                limitation = "Native single-process model probe; not a real multiplayer session"
            }, new JsonSerializerOptions {WriteIndented = true}));
            GD.Print($"Depths risk events probe: PASS ({_checks} assertions)"); GetTree().Quit(0);
        }
        catch (Exception e) {GD.PushError(e.ToString()); GetTree().Quit(1);}
    }
    private RunState NewRun(string seed, int count = 1)
    {
        DeactivateSyntheticCombat();
        var players = Enumerable.Range(1,count).Select(i => Player.CreateForNewRun<Ironclad>(UnlockState.all,(ulong)i)).ToList();
        var run = RunState.CreateForNewRun(players, ActModel.GetDefaultList().Select(a => a.ToMutable()).ToList(), [], GameMode.Standard,0,seed);
        foreach (var p in players)
            if (!p.RelicGrabBag.IsPopulated) p.RelicGrabBag.Populate(p,run.Rng.UpFront);
        typeof(RunManager).GetProperty("State",BindingFlags.NonPublic|BindingFlags.Instance)!.SetValue(RunManager.Instance,run);
        typeof(RunManager).GetProperty("NetService")!.SetValue(RunManager.Instance,new NetSingleplayerGameService());
        typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance,new AscensionManager(0));
        LocalContext.NetId = players[0].NetId;
        return run;
    }
    private async Task<T> Begin<T>(Player owner) where T : EventModel
    {
        var model = (T)ModelDb.Event<T>().ToMutable();
        var method = typeof(EventModel).GetMethods().Single(m => m.Name == nameof(EventModel.BeginEvent));
        var args = method.GetParameters().Select(p => p.ParameterType == typeof(Player) ? (object)owner : p.ParameterType == typeof(bool) ? false : null).ToArray();
        await (Task)method.Invoke(model,args)!;
        foreach (var option in model.CurrentOptions)
        {
            // NEventOptionButton._Ready supplies the event vars before formatting.
            model.DynamicVars.AddTo(option.Description);
            model.DynamicVars.AddTo(option.Title);
            Assert(!option.Description.GetFormattedText().Contains('{'), "Formatted option " + option.TextKey);
            Assert(!string.IsNullOrWhiteSpace(option.Title.GetFormattedText()), "Option title " + option.TextKey);
        }
        return model;
    }
    private async Task VerifyBranches()
    {
        bool won = false, bitten = false;
        for (int seed = 0; seed < 12 && !(won && bitten); seed++)
        {
            var run = NewRun("risk-chest-" + seed, 2); var p = run.Players[0];
            int hp = p.Creature.CurrentHp, relics = p.Relics.Count, deck = p.Deck.Cards.Count;
            var model = await Begin<BitingChest>(p); var option = model.CurrentOptions[0];
            Assert(!option.IsLocked, "Rare relic is available");
            await option.Chosen();
            bool victory = p.Relics.Count == relics + 1;
            Assert(model.IsFinished, "Chest finishes");
            if (victory)
            {
                won = true;
                Assert(p.Relics.Last().Rarity == RelicRarity.Rare && p.Creature.CurrentHp == hp && p.Deck.Cards.Count == deck, "Success gives rare relic only");
            }
            else
            {
                bitten = true;
                Assert(p.Creature.CurrentHp == hp - 20 && p.Deck.Cards.Count == deck + 1 && p.Deck.Cards.Last() is Injury, "Failure damage and native Injury");
            }
            int afterHp = p.Creature.CurrentHp, afterRelics = p.Relics.Count, afterDeck = p.Deck.Cards.Count;
            await option.Chosen();
            Assert(p.Creature.CurrentHp == afterHp && p.Relics.Count == afterRelics && p.Deck.Cards.Count == afterDeck, "No repeated reward");
            Assert(run.Players[1].Creature.CurrentHp == run.Players[1].Creature.MaxHp && run.Players[1].Deck.Cards.Count == deck, "Personal chest result");
            var repeat = NewRun("risk-chest-" + seed); var repeatModel = await Begin<BitingChest>(repeat.Players[0]);
            int previous = repeat.Players[0].Relics.Count; await repeatModel.CurrentOptions[0].Chosen();
            Assert((repeat.Players[0].Relics.Count == previous + 1) == victory, "Seed replay keeps outcome");
        }
        Assert(won && bitten, "Both coin-flip outcomes tested");
        foreach (int branch in new[] {1,2})
        {
            var run = NewRun("chest-choice-" + branch); var p = run.Players[0];
            int hp = p.Creature.CurrentHp, gold = p.Gold, relics = p.Relics.Count;
            var model = await Begin<BitingChest>(p); var opt = model.CurrentOptions[branch];
            await opt.Chosen(); await opt.Chosen();
            Assert(model.IsFinished, "Chest branch finishes");
            Assert(branch == 1 ? p.Creature.CurrentHp == hp - 16 && p.Relics.Count == relics + 1 && p.Relics.Last().Rarity == RelicRarity.Common :
                p.Creature.CurrentHp == hp && p.Gold == gold + 25 && p.Relics.Count == relics, "Fixed chest branch");
        }
        var emptyRun = NewRun("empty-chest"); var empty = emptyRun.Players[0];
        empty.RelicGrabBag.LoadFromSerializable(new SerializableRelicGrabBag
        {
            RelicIdLists = new Dictionary<RelicRarity,List<ModelId>>
            {
                [RelicRarity.Rare] = [], [RelicRarity.Common] = []
            }
        });
        var emptyEvent = await Begin<BitingChest>(empty);
        Assert(emptyEvent.CurrentOptions[0].IsLocked && emptyEvent.CurrentOptions[1].IsLocked && !emptyEvent.CurrentOptions[2].IsLocked, "Exhausted rarity has safe choice");
        var lethalRun = NewRun("lethal-warning"); await CreatureCmd.SetCurrentHp(lethalRun.Players[0].Creature,16);
        var lethal = await Begin<BitingChest>(lethalRun.Players[0]);
        Assert(lethal.CurrentOptions[0].WillKillPlayer!(lethalRun.Players[0]) && lethal.CurrentOptions[1].WillKillPlayer!(lethalRun.Players[0]), "Native lethal warning");
        foreach (int branch in new[] {0,1,2})
        {
            var run = NewRun("ward-choice-" + branch, 4); var p = run.Players[0];
            await CreatureCmd.SetCurrentHp(p.Creature,10);
            int deck = p.Deck.Cards.Count; var model = await Begin<CrowdedWard>(p); var opt = model.CurrentOptions[branch];
            await opt.Chosen(); await opt.Chosen();
            Assert(model.IsFinished, "Ward finishes once");
            Assert(p.Creature.CurrentHp == (branch == 0 ? p.Creature.MaxHp : branch == 1 ? 35 : 16), "Ward healing amount");
            Assert(p.Deck.Cards.Count == deck + (branch == 0 ? 1 : 0), "Only full treatment adds curse");
            Assert(branch != 0 || p.Deck.Cards.Last() is Injury, "Native treatment curse");
            Assert(p.Relics.OfType<AnestheticChart>().Count() == (branch == 1 ? 1 : 0), "Only anesthesia adds debt");
            Assert(run.Players.Skip(1).All(other => other.Relics.All(r => r is not AnestheticChart) && other.Creature.CurrentHp == other.Creature.MaxHp), "Ward is personal");
        }
        var nearFull = NewRun("ward-cap"); var fullPlayer = nearFull.Players[0];
        await CreatureCmd.SetCurrentHp(fullPlayer.Creature,fullPlayer.Creature.MaxHp-1);
        var cap = await Begin<CrowdedWard>(fullPlayer); await cap.CurrentOptions[2].Chosen();
        Assert(fullPlayer.Creature.CurrentHp == fullPlayer.Creature.MaxHp, "Heal caps at native max HP");
    }
    private async Task VerifyAnesthesia()
    {
        foreach (int count in new[] {1,2,3,4})
        {
            var run = NewRun("anesthesia-" + count,count); var owner = run.Players[0];
            var ward = await Begin<CrowdedWard>(owner); await ward.CurrentOptions[1].Chosen();
            var chart = owner.Relics.OfType<AnestheticChart>().Single();
            Assert(chart.RemainingCombats == 2 && !chart.IsTradable, "Saved personal two-combat debt");
            for (int fight = 0; fight < 3; fight++)
            {
                var encounter = ModelDb.Encounter<LanternFishWeak>().ToMutable();
                var room = new CombatRoom(encounter,run); run.PushRoom(room);
                foreach (var p in run.Players) {p.ResetCombatState();room.CombatState.AddPlayer(p);p.PopulateCombatState(run.Rng.Shuffle,room.CombatState);}
                // An empty synthetic arena is already "over"; native combat
                // hooks deliberately stop there. Keep real living opponents.
                encounter.GenerateMonstersWithSlots(run);
                foreach (var (monster, slot) in encounter.MonstersWithSlots)
                {
                    var creature = room.CombatState.CreateCreature(monster,CombatSide.Enemy,slot);
                    room.CombatState.AddCreature(creature); monster.SetUpForCombat();
                }
                room.CombatState.CurrentSide = CombatSide.Player;
                ActivateSyntheticCombat(room.CombatState);
                foreach (var p in run.Players)
                {
                    await Hook.BeforeHandDraw(room.CombatState,p,Choice);
                    decimal draw = Hook.ModifyHandDraw(room.CombatState,p,5,out var modifiers);
                    await Hook.AfterModifyingHandDraw(room.CombatState,modifiers);
                    Assert(draw == (p == owner && fight < 2 ? 3 : 5), $"Native opening draw party={count} fight={fight} owner={p==owner} draw={draw} remaining={chart.RemainingCombats} applied={chart.AppliedThisCombat} modifiers={string.Join(',',modifiers.Select(m=>m.Id.Entry))}");
                    await CardPileCmd.Draw(Choice,draw,p,fromHandDraw:true);
                    Assert(p.PlayerCombatState!.Hand.Cards.Count == draw, "Actual native hand size");
                }
                if (fight < 2)
                {
                    var writer = new PacketWriter {WarnOnGrow=false};chart.ToSerializable().Serialize(writer);
                    var reader = new PacketReader();reader.Reset(writer.Buffer);
                    var serial = new SerializableRelic();serial.Deserialize(reader);
                    var saved = (AnestheticChart)RelicModel.FromSerializable(serial); saved.Owner = owner;
                    Assert(saved.AppliedThisCombat && saved.RemainingCombats == chart.RemainingCombats, $"Mid-combat debt saved: originalApplied={chart.AppliedThisCombat}, restoredApplied={saved.AppliedThisCombat}, originalCount={chart.RemainingCombats}, restoredCount={saved.RemainingCombats}");
                    Assert(saved.ModifyHandDraw(owner,5) == 5, "Reload does not reapply opening penalty");
                    await saved.AfterCombatEnd(room); await saved.AfterCombatEnd(room);
                    Assert(saved.RemainingCombats == chart.RemainingCombats-1, "Saved debt consumes exactly once");
                    await CardPileCmd.Draw(Choice,1,owner);
                    Assert(owner.PlayerCombatState!.Hand.Cards.Count == 4, "Card-driven draw is unaffected");
                }
                owner.PlayerCombatState!.IncrementTurnNumber();
                Assert(chart.ModifyHandDraw(owner,5) == 5, "Later turns unaffected");
                await Hook.AfterCombatEnd(run,room.CombatState,room);
                Assert(chart.RemainingCombats == Math.Max(0,1-fight), "Exactly two combat charges");
                DeactivateSyntheticCombat();
            }
            Assert(chart.IsUsedUp && chart.Status == RelicStatus.Disabled && chart.DisplayAmount == 0, "Expiry is native greyed relic");
            var restored = (AnestheticChart)RelicModel.FromSerializable(chart.ToSerializable());
            Assert(restored.IsUsedUp && restored.Status == RelicStatus.Disabled, "Spent debt save round trip");
        }
    }
}
