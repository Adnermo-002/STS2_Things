using System.Reflection;
using System.Text.Json;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Acts;
using STS2_Things.Cards;
using STS2_Things.Encounters;
using STS2_Things.Monsters;
using STS2_Things.Powers;

public partial class DepthsProbeNode
{
    private static readonly ThrowingPlayerChoiceContext Choice = new();
    // Independent specification: include the old entries as regression controls.
    private static readonly Dictionary<Type, Type[]> StrongRosterContracts = new()
    {
        [typeof(LanternFishEncounter)] = [typeof(LanternFish), typeof(LanternFish), typeof(LanternFish)],
        [typeof(SanguineLeechEncounter)] = [typeof(SanguineLeech), typeof(SanguineLeech), typeof(SanguineLeech)],
        [typeof(LeechMotherEncounter)] = [typeof(LeechMother)],
        [typeof(SpongeLeechEncounter)] = [typeof(WaterSponge), typeof(SanguineLeech), typeof(SanguineLeech)],
        [typeof(SilkMothEncounter)] = [typeof(SilkMoth), typeof(SanguineLeech), typeof(SanguineLeech)],
        [typeof(SilkMothTrio)] = [typeof(SilkMoth), typeof(GreatSilkMoth), typeof(SilkMoth)],
        [typeof(CaveMawEncounter)] = [typeof(CaveMaw), typeof(SilkMoth), typeof(SanguineLeech)],
        [typeof(HumanFaceColumnEncounter)] = [typeof(HumanFaceColumn), typeof(HumanFaceColumn), typeof(HumanFaceColumn)],
        [typeof(LanternSpongeEncounter)] = [typeof(LanternFish), typeof(WaterSponge), typeof(CrystalSnail)],
        [typeof(SilkSnailEncounter)] = [typeof(SilkMoth), typeof(RockSnail), typeof(SlimeSnail)],
        [typeof(CaveMawSnailEncounter)] = [typeof(CaveMaw), typeof(CrystalSnail), typeof(SlimeSnail)],
        [typeof(SpongeSnailEncounter)] = [typeof(WaterSponge), typeof(RockSnail), typeof(CrystalSnail)],
        [typeof(LanternMothEncounter)] = [typeof(LanternFish), typeof(SilkMoth), typeof(CrystalSnail)],
        [typeof(CaveMawLanternEncounter)] = [typeof(CaveMaw), typeof(LanternFish)],
    };
    private static readonly Type[] NewStrongTypes = [typeof(LanternSpongeEncounter), typeof(SilkSnailEncounter),
        typeof(CaveMawSnailEncounter), typeof(SpongeSnailEncounter), typeof(LanternMothEncounter), typeof(CaveMawLanternEncounter)];

    private sealed record Battle(RunState Run, CombatRoom Room, EncounterModel Encounter)
    {
        public CombatState State => Room.CombatState;
        public IReadOnlyList<Player> Players => Run.Players;
        public Creature[] Enemies => State.Enemies.Where(c => c.IsAlive).ToArray();
        public T Monster<T>() where T : MonsterModel => Enemies.Select(c => c.Monster).OfType<T>().Single();
    }

    private static async Task<Battle> StrongBattle(EncounterModel canonical, int players = 1, int ascension = 0, string? seed = null)
    {
        DeactivateSyntheticCombat();
        var run = CreateRun(seed ?? "variety-" + canonical.Id.Entry, players, ascension);
        run.CurrentActIndex = 1;
        typeof(RunManager).GetProperty("State", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(RunManager.Instance, run);
        typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance, new AscensionManager(ascension));
        typeof(RunManager).GetProperty("NetService")!.SetValue(RunManager.Instance, new NetSingleplayerGameService());
        var encounter = canonical.ToMutable();
        run.AppendToMapPointHistory(MapPointType.Monster, RoomType.Monster, encounter.Id);
        var room = new CombatRoom(encounter, run);
        run.PushRoom(room);
        foreach (var player in run.Players)
        {
            player.ResetCombatState();
            room.CombatState.AddPlayer(player);
            player.PopulateCombatState(run.Rng.Shuffle, room.CombatState);
        }
        encounter.GenerateMonstersWithSlots(run);
        foreach (var (monster, slot) in encounter.MonstersWithSlots)
        {
            var creature = room.CombatState.CreateCreature(monster, CombatSide.Enemy, slot);
            room.CombatState.AddCreature(creature);
            // CombatState.CreateCreature applies the native multiplayer HP scale.
            monster.SetUpForCombat();
            monster.RollMove(run.Players.Select(p => p.Creature));
        }
        room.CombatState.CurrentSide = CombatSide.Player;
        ActivateSyntheticCombat(room.CombatState);
        await Hook.BeforeCombatStart(run, room.CombatState);
        return new Battle(run, room, encounter);
    }

    private static Task SideEnded(Battle battle, CombatSide side, Creature[] participants)
    {
        var method = typeof(Hook).GetMethod("AfterSideTurnEnd", BindingFlags.Public | BindingFlags.Static)
            ?? typeof(Hook).GetMethod("AfterTurnEnd", BindingFlags.Public | BindingFlags.Static)!;
        return (Task)method.Invoke(null, [battle.State, side, participants])!;
    }

    private static Task SideEnding(Battle battle, CombatSide side, Creature[] participants)
    {
        var method = typeof(Hook).GetMethod("BeforeSideTurnEnd", BindingFlags.Public | BindingFlags.Static)
            ?? typeof(Hook).GetMethod("BeforeTurnEnd", BindingFlags.Public | BindingFlags.Static)!;
        return (Task)method.Invoke(null, [battle.State, side, participants])!;
    }

    private static async Task EndPlayer(Battle battle, Player player)
    {
        var method = typeof(CombatManager).GetMethod("DoTurnEnd", BindingFlags.Instance | BindingFlags.NonPublic)!;
        object?[] args = method.GetParameters().Length == 3
            ? [typeof(CombatManager).GetField("_turnState", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(CombatManager.Instance), player, Choice]
            : [player, Choice];
        await (Task)method.Invoke(CombatManager.Instance, args)!;
    }

    private async Task VerifyStrongEncounters()
    {
        Type? atlasType = typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Assets.AtlasResourceLoader");
        ResourceFormatLoader? atlas = atlasType == null ? null : (ResourceFormatLoader)Activator.CreateInstance(atlasType)!;
        if (atlas != null) ResourceLoader.AddResourceFormatLoader(atlas, true);
        var records = new List<object>();
        var normal = ModelDb.Act<Depths>().AllRegularEncounters.ToArray();
        Assert(!ModelDb.Act<MegaCrit.Sts2.Core.Models.Acts.Hive>().AllEncounters.Any(e => StrongRosterContracts.ContainsKey(e.GetType())), "Strong additions stay in Depths.");
        foreach (var canonical in normal)
        foreach (int players in new[] { 1, 2, 3, 4 })
        foreach (int ascension in new[] { 0, 20 })
        {
            var b = await StrongBattle(canonical, players, ascension);
            Type[] actual = b.Encounter.MonstersWithSlots.Select(x => x.Item1.GetType()).ToArray();
            Type[] expected = StrongRosterContracts[canonical.GetType()];
            Assert(actual.Take(expected.Length).SequenceEqual(expected), "Roster contract: " + canonical.Id.Entry);
            Assert(actual.Length == expected.Length, "No missing/extra enemy.");
            Assert(b.Enemies.Select(c => c.SlotName).Distinct().Count() == actual.Length, "Occupied slots are unique.");
            Assert(b.Enemies.All(c => b.Encounter.Slots.Contains(c.SlotName!)), "Every enemy has a declared slot.");
            var slots = b.Encounter.CreateScene();
            Assert(b.Enemies.All(c => slots.HasNode(c.SlotName!)), "Shipping scene contains every occupied slot.");
            slots.Free();
            if (players == 1 && ascension == 0)
            {
                foreach (var creature in b.Enemies)
                {
                    var visuals = creature.Monster!.CreateVisuals();
                    Assert(visuals != null && visuals.HasNode("Bounds") && visuals.HasNode("IntentPos"), "Native creature resource and HUD anchors load.");
                    _resourceFixtures.Add(visuals!);
                    foreach (string path in creature.Monster!.AssetPaths)
                        Assert(ResourceLoader.Exists(path), "Monster asset exists: " + path);
                }
                var bg = b.Encounter.CreateBackground(b.Run.Act, b.Run.Rng.UpFront);
                _resourceFixtures.Add(bg);
                Assert(bg.HasNode("Layer_00") && bg.HasNode("Foreground"), "Native custom background loads.");
            }
            records.Add(await ExerciseStrongBattle(b, ascension));
        }
        await VerifySnailInteractions();
        await VerifyMawInteractions();
        if (atlas != null) ResourceLoader.RemoveResourceFormatLoader(atlas);
        File.WriteAllText(Path.Combine(_output, "strong-combat-cases.json"), JsonSerializer.Serialize(records, new JsonSerializerOptions { WriteIndented = true }));
        GD.Print($"PASS {records.Count} native strong combat cases: 1-4 players, A0/A20, eight rounds, defeat and temporary-card isolation.");
    }

    private static async Task<object> ExerciseStrongBattle(Battle b, int ascension, string? seed = null)
    {
        foreach (var player in b.Players) { player.Creature.SetMaxHpInternal(10000); player.Creature.SetCurrentHpInternal(10000); }
        var moves = new Dictionary<string, HashSet<string>>();
        for (int turn = 0; turn < 8; turn++)
        {
            b.State.CurrentSide = CombatSide.Player;
            foreach (var player in b.Players)
            {
                await player.Creature.AfterTurnStart(CombatSide.Player);
                await PlayerCmd.SetEnergy(3, player);
                await Hook.BeforeHandDraw(b.State, player, Choice);
                await CardPileCmd.Draw(Choice, 5, player);
                await Hook.AfterPlayerTurnStart(b.State, Choice, player);
                Assert(player.PlayerCombatState!.Hand.Cards.All(card => card.Owner == player), "Card ownership across combined powers.");
            }
            await SideEnding(b, CombatSide.Player, b.Players.Select(p => p.Creature).ToArray());
            foreach (var player in b.Players) await EndPlayer(b, player);
            await SideEnded(b, CombatSide.Player, b.Players.Select(p => p.Creature).ToArray());
            b.State.CurrentSide = CombatSide.Enemy;
            var participants = b.Enemies;
            foreach (var creature in participants)
            {
                await creature.AfterTurnStart(CombatSide.Enemy);
                var monster = creature.Monster!;
                if (!moves.TryGetValue(monster.Id.Entry, out var seen)) moves[monster.Id.Entry] = seen = [];
                seen.Add(monster.NextMove.Id);
                Assert(monster.NextMove.Intents.Any(), "Every move supplies an intent.");
                await monster.PerformMove();
            }
            await SideEnding(b, CombatSide.Enemy, participants);
            await SideEnded(b, CombatSide.Enemy, participants);
            b.State.CurrentSide = CombatSide.Player;
            foreach (var creature in b.Enemies) creature.Monster!.RollMove(b.Players.Select(p => p.Creature));
        }
        Assert(b.Players.All(p => p.Creature.IsAlive), "Fixture survives full state cycles.");
        foreach (var player in b.Players)
            Assert(!player.Deck.Cards.Any(c => c.Type == CardType.Status || c is SnailCrystalChip), "Temporary enemy cards never enter permanent decks.");
        int kills = 0;
        while (b.Enemies.Length > 0 && kills < 12)
        {
            var target = b.Enemies.OrderBy(c => c.Monster is HumanFaceColumn column ? column.Level : -1).First();
            await CreatureCmd.Damage(Choice, target, 99999, ValueProp.Unpowered, b.Players[0].Creature);
            Assert(!target.IsAlive, "Native lethal damage finishes the targeted enemy.");
            kills++;
        }
        Assert(b.Enemies.Length == 0, "All enemies, including column reserves, can be defeated.");
        DeactivateSyntheticCombat();
        return new { encounter = b.Encounter.Id.Entry, players = b.Players.Count, ascension, seed, turns = 8, kills,
            moves = moves.ToDictionary(kv => kv.Key, kv => kv.Value.Order().ToArray()) };
    }

    private async Task VerifyStandaloneColumns()
    {
        var canonical = ModelDb.Encounter<HumanFaceColumnEncounter>();
        var records = new List<object>();
        foreach (string seed in new[] { "column-solo-0", "column-solo-1", "column-solo-2" })
        foreach (int players in new[] { 1, 2, 3, 4 })
        foreach (int ascension in new[] { 0, 20 })
        {
            var b = await StrongBattle(canonical, players, ascension, seed);
            Assert(b.Enemies.Length == 3 && b.Enemies.All(c => c.Monster is HumanFaceColumn),
                "Standalone strong column has three visible discs and no companion, for every tested seed");
            var slots = b.Encounter.CreateScene();
            Assert(b.Enemies.Select(c => c.SlotName).Distinct().Count() == 3 &&
                b.Enemies.All(c => slots.HasNode(c.SlotName!)), "All three discs occupy their native scene slots");
            slots.Free();
            records.Add(await ExerciseStrongBattle(b, ascension, seed));
        }
        File.WriteAllText(Path.Combine(_output, "column-standalone-cases.json"),
            JsonSerializer.Serialize(records, new JsonSerializerOptions { WriteIndented = true }));
        GD.Print($"PASS {records.Count} standalone strong-column combat cases: three seeds, 1-4 players, A0/A20, eight rounds and defeat.");
    }

    private static async Task VerifySnailInteractions()
    {
        foreach (int players in new[] { 1, 4 })
        foreach (var canonical in new EncounterModel[] { ModelDb.Encounter<CaveMawSnailEncounter>(), ModelDb.Encounter<SilkSnailEncounter>() })
        {
            var b = await StrongBattle(canonical, players);
            var mender = b.Monster<SlimeSnail>();
            var shell = b.Enemies.Select(c => c.Monster).OfType<DepthsSnail>().Single(s => s is not SlimeSnail);
            Assert(shell.HasShell, "Mender begins with a repairable ally.");
            await mender.PerformMove();
            mender.RollMove(b.Players.Select(p => p.Creature));
            Assert(mender.NextMove.Id == "REPAIR_MOVE", "Mender advertises repair with an intact shell.");
            decimal block = shell.Creature.Block;
            await mender.PerformMove();
            decimal expectedRepair = players == 1 ? 5 : 24; // Native 4 * 1.2 scale, then truncate.
            Assert(shell.Creature.Block == block + expectedRepair, $"Repair applies native multiplayer scaling: {players}p, {block} -> {shell.Creature.Block}.");
            mender.RollMove(b.Players.Select(p => p.Creature));
            await mender.PerformMove();
            mender.RollMove(b.Players.Select(p => p.Creature));
            int crawl = (shell as RockSnail)?.CrawlsRemaining ?? -1;
            await CreatureCmd.Damage(Choice, shell.Creature, shell.Creature.Block, ValueProp.Unpowered, b.Players[0].Creature);
            Assert(!shell.HasShell && shell.Creature.IsAlive, "Exact-block hit breaks shell without killing.");
            Assert(mender.NextMove.Id == "BITE_MOVE", "Repair intent becomes bite when no repair target remains.");
            if (shell is CrystalSnail)
            {
                Assert(shell.NextMove.Id == "BARE_BUMP_MOVE", "Broken crystal shell stops retreating.");
                foreach (var player in b.Players)
                    Assert(player.PlayerCombatState!.DiscardPile.Cards.OfType<SnailCrystalChip>().Count() == 1, "Each player receives exactly one crystal chip.");
            }
            else Assert(((RockSnail)shell).CrawlsRemaining == crawl + 1, "Broken rock shell delays crush once.");
            DeactivateSyntheticCombat();
        }
        GD.Print("PASS snail repair, live intent refresh, exact shell breaks, per-player rewards and crawl delay.");
    }

    private static async Task VerifyMawInteractions()
    {
        foreach (var canonical in new EncounterModel[] { ModelDb.Encounter<CaveMawSnailEncounter>(), ModelDb.Encounter<CaveMawLanternEncounter>() })
        foreach (int players in new[] { 1, 4 })
        {
            var b = await StrongBattle(canonical, players);
            var maw = b.Monster<CaveMaw>();
            await maw.PerformMove();
            foreach (var player in b.Players)
            {
                var debris = player.PlayerCombatState!.Hand.Cards.OfType<Debris>().ToArray();
                Assert(debris.Length == 2 && debris.All(c => c.Keywords.Contains(CardKeyword.Retain)), "Maw offers two retained vanilla Debris to each player.");
                await EndPlayer(b, player);
            }
            maw.RollMove(b.Players.Select(p => p.Creature));
            Assert(maw.NextMove.Id == "DEVOUR_MOVE", "Offer transitions to Devour.");
            await maw.PerformMove();
            foreach (var player in b.Players)
                Assert(player.PlayerCombatState!.ExhaustPile.Cards.OfType<Debris>().Count() == 2, "Devour exhausts retained Debris for every player.");
            Assert(maw.Creature.GetPower<StrengthPower>()?.Amount > 0, "Maw receives native Strength after the meal.");
            DeactivateSyntheticCombat();
        }
        Assert(!ModelDb.Card<Debris>().Keywords.Contains(CardKeyword.Retain), "Canonical Debris remains unchanged.");
        GD.Print("PASS both new maw combinations, retained Debris, multiplayer consumption and canonical-card isolation.");
    }
}
