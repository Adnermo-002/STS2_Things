using System.Reflection;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Cards;
using STS2_Things.Encounters;
using STS2_Things.Monsters;
using STS2_Things.Powers;

public partial class LanternFishProbeNode : Node
{
    private static readonly ThrowingPlayerChoiceContext Choice = new();
    private static int _assertions;
    public override async void _Ready()
    {
        try
        {
            string root = Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "../.."));
            TestMode.TurnOnInternal();
            ProjectSettings.LoadResourcePack("D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck");
            if (OS.GetCmdlineUserArgs().Contains("--visual"))
                ProjectSettings.LoadResourcePack(Path.Combine(root, "build/lantern_fish/v111/STS2_Things.pck"));
            SaveManager.Instance.InitSettingsDataForTest();
            SaveManager.Instance.SettingsSave.Language = "eng";
            MegaCrit.Sts2.Core.Localization.LocManager.Initialize();
            InitializeModelDb();
            SaveManager.Instance.InitPrefsDataForTest();
            var harmony = new Harmony("LanternFishProbe");
            foreach (Type patch in typeof(LanternFish).Assembly.GetTypes().Where(t =>
                         t.Name.StartsWith("LanternBlindness") && t.Name.EndsWith("Patch")))
                harmony.CreateClassProcessor(patch).Patch();
            if (OS.GetCmdlineUserArgs().Contains("--visual"))
            {
                await RenderProbe(root);
                GD.Print($"Lantern Fish visual probe: PASS ({_assertions} assertions)");
                GetTree().Quit(0); return;
            }
            VerifyEncounter();
            await VerifyDraws();
            await VerifySpecialCosts();
            await VerifyPreventionAndStars();
            await VerifyGenerationAndBlockedDraws();
            await VerifyNativeMoves();
            GD.Print($"Lantern Fish behavior probe: PASS ({_assertions} assertions)");
            DeactivateSyntheticCombat();
            GetTree().Quit(0);
        }
        catch (Exception e) { GD.PushError(e.ToString()); GetTree().Quit(1); }
    }

    private static Fixture Scenario(int players = 1, int ascension = 0, string seed = "lantern-depths")
    {
        var party = Enumerable.Range(1, players).Select(i => Player.CreateForNewRun<Ironclad>(UnlockState.all, (ulong)i)).ToList();
        var run = RunState.CreateForNewRun(party, ActModel.GetDefaultList().Select(a => a.ToMutable()).ToList(), [], GameMode.Standard, ascension, seed);
        typeof(RunManager).GetProperty("State", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(RunManager.Instance, run);
        typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance, new MegaCrit.Sts2.Core.Entities.Ascension.AscensionManager(ascension));
        var encounter = (LanternFishEncounter)ModelDb.Encounter<LanternFishEncounter>().ToMutable();
        run.AppendToMapPointHistory(MegaCrit.Sts2.Core.Map.MapPointType.Monster, RoomType.Monster, encounter.Id);
        var room = new CombatRoom(encounter, run); run.PushRoom(room);
        foreach (var player in party)
        {
            player.ResetCombatState(); room.CombatState.AddPlayer(player);
            player.PopulateCombatState(run.Rng.Shuffle, room.CombatState);
        }
        encounter.GenerateMonstersWithSlots(run);
        foreach (var (model, slot) in encounter.MonstersWithSlots)
        {
            var creature = room.CombatState.CreateCreature(model, CombatSide.Enemy, slot);
            room.CombatState.AddCreature(creature); model.SetUpForCombat();
        }
        room.CombatState.CurrentSide = CombatSide.Player;
        ActivateSyntheticCombat(room.CombatState);
        return new(run, room, party, encounter);
    }

    private static void VerifyEncounter()
    {
        var s = Scenario();
        Assert(!s.Encounter.IsWeak, "Three fish belong to the strong hallway pool.");
        var fish = s.Encounter.MonstersWithSlots.Select(x => (LanternFish)x.Item1).ToArray();
        Assert(fish.Length == 3 && fish.Select(f => f.OpeningPhase).SequenceEqual([0,1,3]), "Three staggered fish.");
        Assert(fish.All(f => f.MinInitialHp == 46 && f.MaxInitialHp == 50), "A0 HP.");
        string[] cycle = ["BITE_MOVE", "FLASH_MOVE", "TAIL_MOVE", "GUARD_MOVE"];
        for (int turn = 0; turn < 8; turn++)
        {
            int flashes = 0;
            foreach (var f in fish)
            {
                var move = f.MoveStateMachine!.RollMove([s.Player.Creature], f.Creature, s.Run.Rng.MonsterAi);
                Assert(move.Id == cycle[(f.OpeningPhase + turn) % 4], "Staggered move cycle.");
                if (move.Id == "FLASH_MOVE") flashes++;
                f.MoveStateMachine.OnMovePerformed(move);
            }
            Assert(flashes == (turn % 4 == 3 ? 0 : 1), "One flash or respite.");
        }
        GD.Print($"Encounter ID: {s.Encounter.Id.Entry}; monster ID: {fish[0].Id.Entry}; power ID: {ModelDb.Power<LanternBlindnessPower>().Id.Entry}");
        DeactivateSyntheticCombat();
        var high = Scenario(ascension: 20);
        Assert(high.Encounter.MonstersWithSlots.All(x => x.Item1.MinInitialHp == 50 && x.Item1.MaxInitialHp == 54), "High ascension HP.");
        DeactivateSyntheticCombat();
    }

    private static async Task<LanternBlindnessPower> Blind(Player player, int charges)
    {
        return await PowerCmd.Apply<LanternBlindnessPower>(Choice, player.Creature, charges, null, null, silent: true)
            ?? throw new Exception("Power apply failed.");
    }

    private static CardModel Put<T>(Fixture s, Player player, PileType pile) where T : CardModel
    {
        var card = s.Room.CombatState.CreateCard<T>(player);
        pile.GetPile(player).AddInternal(card, silent: true); return card;
    }

    private static async Task VerifyDraws()
    {
        var s = Scenario(players: 2); var player = s.Player; var pc = player.PlayerCombatState!;
        foreach (var p in s.Players) p.PlayerCombatState!.DrawPile.Clear(silent: true);
        var first = Put<StrikeIronclad>(s, player, PileType.Draw);
        var second = Put<DefendIronclad>(s, player, PileType.Draw);
        var third = Put<StrikeIronclad>(s, player, PileType.Draw);
        first.EnergyCost.SetThisCombat(0);
        var power = await Blind(player, 2);
        var teamCard = Put<StrikeIronclad>(s, s.Players[1], PileType.Draw);
        await CardPileCmd.Draw(Choice, s.Players[1]);
        Assert(power.Amount == 2 && !LanternBlindness.IsBlinded(teamCard), "Teammate isolation.");
        var rng = new RunRngSet(s.Run.Rng.StringSeed).CombatEnergyCosts;
        int expected1 = rng.NextInt(3) + 1, expected2 = rng.NextInt(3) + 1;
        await CardPileCmd.Draw(Choice, 3, player);
        Assert(first.EnergyCost.GetWithModifiers(CostModifiers.Local) == expected1, "Deterministic first cost.");
        Assert(second.EnergyCost.GetWithModifiers(CostModifiers.Local) == expected2, "Deterministic second cost.");
        Assert(!player.Creature.HasPower<LanternBlindnessPower>(), "Charges deplete exactly.");
        Assert(LanternBlindness.IsBlinded(first) && LanternBlindness.IsBlinded(second) && !LanternBlindness.IsBlinded(third), "Marks survive counter depletion.");
        first.EnergyCost.AfterCardPlayedCleanup();
        Assert(first.EnergyCost.GetWithModifiers(CostModifiers.Local) == expected1 && LanternBlindness.IsBlinded(first), "Playing retains blindness this turn.");
        var clone = first.CreateClone(); pc.DiscardPile.AddInternal(clone, silent: true);
        Assert(LanternBlindness.IsBlinded(clone) && clone.EnergyCost.GetWithModifiers(CostModifiers.Local) == expected1, "Clone keeps visual and cost.");
        await CardPileCmd.Add(first, PileType.Draw);
        await CardPileCmd.Draw(Choice, player);
        Assert(first.EnergyCost.GetWithModifiers(CostModifiers.Local) == expected1, "Redraw without charges keeps prior roll.");
        var free = await PowerCmd.Apply<FreeAttackPower>(Choice, player.Creature, 1, null, null, silent: true);
        Assert(first.EnergyCost.GetWithModifiers(CostModifiers.All) == 0, "Native free-attack modifier preserved.");
        free!.RemoveInternal();
        pc.EndOfTurnCleanup();
        Assert(!LanternBlindness.IsBlinded(first) && !LanternBlindness.IsBlinded(clone), "Native turn cleanup clears all piles.");
        Assert(first.EnergyCost.GetWithModifiers(CostModifiers.Local) == 0 && clone.EnergyCost.GetWithModifiers(CostModifiers.Local) == 0, "Combat modifier preserved after blindness.");
        Assert(second.EnergyCost.GetWithModifiers(CostModifiers.Local) == second.EnergyCost.Canonical, "Normal cost restored.");
        var capped = await Blind(player, 5); await Blind(player, 5);
        Assert(capped.Amount == 6, "Pending charges cap at six.");
        pc.EndOfTurnCleanup(); Assert(capped.Amount == 6, "Unused charges persist.");
        DeactivateSyntheticCombat(); GD.Print("PASS native draws, deterministic rolls, clones, play/redraw, discounts and cleanup.");
    }

    private static async Task VerifySpecialCosts()
    {
        var s = Scenario(); var player = s.Player; player.PlayerCombatState!.DrawPile.Clear(silent: true);
        var x = Put<Whirlwind>(s, player, PileType.Draw);
        var status = Put<Wound>(s, player, PileType.Draw);
        int before = RngCounter(s.Run.Rng.CombatEnergyCosts);
        await Blind(player, 2); await CardPileCmd.Draw(Choice, 2, player);
        Assert(x.EnergyCost.CostsX && !x.EnergyCost.HasLocalModifiers, "X cost remains X.");
        Assert(status.EnergyCost.GetWithModifiers(CostModifiers.All) < 0, "Unplayable remains unplayable.");
        Assert(LanternBlindness.IsBlinded(x) && LanternBlindness.IsBlinded(status), "Special cards still obscured.");
        Assert(RngCounter(s.Run.Rng.CombatEnergyCosts) == before, "Special cards consume no cost roll.");
        player.PlayerCombatState.EndOfTurnCleanup(); DeactivateSyntheticCombat();
        GD.Print("PASS special costs and RNG isolation.");
    }

    private static async Task VerifyGenerationAndBlockedDraws()
    {
        var s = Scenario(); var player = s.Player;
        var p = await Blind(player, 2);
        var generated = s.Room.CombatState.CreateCard<StrikeIronclad>(player);
        await CardPileCmd.AddGeneratedCardToCombat(generated, PileType.Hand, player);
        Assert(p.Amount == 2 && !LanternBlindness.IsBlinded(generated), "Generated cards aren't draws.");
        var noDraw = await PowerCmd.Apply<NoDrawPower>(Choice, player.Creature, 1, null, null, silent: true);
        var drawn = (await CardPileCmd.Draw(Choice, 2, player)).ToArray();
        Assert(drawn.Length == 0 && p.Amount == 2, "Blocked draw consumes no charges.");
        noDraw!.RemoveInternal();
        for (int i = player.PlayerCombatState!.Hand.Cards.Count; i < CardPile.MaxCardsInHand; i++) Put<StrikeIronclad>(s, player, PileType.Hand);
        drawn = (await CardPileCmd.Draw(Choice, 2, player)).ToArray();
        Assert(drawn.Length == 0 && p.Amount == 2, "Full hand consumes no charges.");
        DeactivateSyntheticCombat(); GD.Print("PASS generated cards, blocked draw and full hand.");
    }

    private static async Task VerifyPreventionAndStars()
    {
        var s = Scenario(players: 2); var player = s.Player;
        var artifact = await PowerCmd.Apply<ArtifactPower>(Choice, player.Creature, 1, null, null, silent: true);
        await PowerCmd.Apply<LanternBlindnessPower>(Choice, player.Creature, 2, s.Encounter.MonstersWithSlots[0].Item1.Creature, null, silent: true);
        Assert(!player.Creature.HasPower<LanternBlindnessPower>(), "Artifact prevents new blindness.");
        Assert(!player.Creature.HasPower<ArtifactPower>(), "Artifact charge consumed normally.");
        var template = ModelDb.AllCards.First(card => card.CanonicalStarCost > 0 && !card.EnergyCost.CostsX && card.EnergyCost.Canonical >= 0);
        var stars = s.Room.CombatState.CreateCard(template, player);
        player.PlayerCombatState!.Hand.AddInternal(stars, silent: true);
        int starCost = stars.GetStarCostWithModifiers();
        var blind = await Blind(player, 1); await blind.AfterCardDrawn(Choice, stars, false);
        Assert(stars.GetStarCostWithModifiers() == starCost, "Star cost unchanged.");
        Assert(stars.EnergyCost.GetWithModifiers(CostModifiers.Local) is >= 1 and <= 3, "Normal energy still randomized on star card.");
        player.PlayerCombatState.EndOfTurnCleanup();
        var fish = (LanternFish)s.Encounter.MonstersWithSlots[0].Item1;
        await ((MoveState)fish.MoveStateMachine!.States["FLASH_MOVE"]).PerformMove([s.Player.Creature]);
        Assert(s.Players.All(p => p.Creature.GetPower<LanternBlindnessPower>()?.Amount == 2), "Flash affects every living player.");
        DeactivateSyntheticCombat(); GD.Print("PASS Artifact, Star cost and multiplayer flash.");
    }

    private static async Task VerifyNativeMoves()
    {
        var s = Scenario(); var fish = (LanternFish)s.Encounter.MonstersWithSlots[0].Item1;
        var moves = fish.MoveStateMachine!.States;
        await ((MoveState)moves["FLASH_MOVE"]).PerformMove([s.Player.Creature]);
        Assert(s.Player.Creature.GetPower<LanternBlindnessPower>()?.Amount == 2, "Native flash applies two charges.");
        await ((MoveState)moves["GUARD_MOVE"]).PerformMove([s.Player.Creature]);
        Assert(fish.Creature.Block == 9, "Native guard grants nine block.");
        int hp = s.Player.Creature.CurrentHp;
        await ((MoveState)moves["BITE_MOVE"]).PerformMove([s.Player.Creature]);
        Assert(s.Player.Creature.CurrentHp == hp - 6, "Native bite damage.");
        hp = s.Player.Creature.CurrentHp;
        await ((MoveState)moves["TAIL_MOVE"]).PerformMove([s.Player.Creature]);
        Assert(s.Player.Creature.CurrentHp == hp - 8, "Native two-hit claw damage.");
        DeactivateSyntheticCombat(); GD.Print("PASS native flash, guard, bite and double tail swipe commands.");
    }

    private static void Assert(bool ok, string message) { if (!ok) throw new Exception(message); _assertions++; }
    private static int RngCounter(MegaCrit.Sts2.Core.Random.Rng rng) =>
        (int)(rng.GetType().GetProperty("Counter")?.GetValue(rng) ??
              rng.GetType().GetField("_counter", BindingFlags.NonPublic | BindingFlags.Instance)!.GetValue(rng)!);
    private sealed record Fixture(RunState Run, CombatRoom Room, List<Player> Players, LanternFishEncounter Encounter)
    { public Player Player => Players[0]; }
}
