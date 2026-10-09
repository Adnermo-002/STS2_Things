using System.Reflection;
using System.Runtime.Loader;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Acts;
using STS2_Things.Cards;
using STS2_Things.Encounters;
using STS2_Things.Monsters;
using STS2_Things.Powers;

public partial class WaterSpongeProbeNode : Node
{
    private static readonly ThrowingPlayerChoiceContext Choice = new();
    private static int _checks;
    private string _root = null!;

    public override void _Ready()
    {
        AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency;
        _ = RunProbe();
    }

    private async Task RunProbe()
    {
        try
        {
            _root = Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "../.."));
            TestMode.TurnOnInternal();
            ProjectSettings.LoadResourcePack("D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck");
            string pack = System.Environment.GetEnvironmentVariable("THINGS_PROBE_PCK") ?? Path.Combine(_root, "build/water_sponge/v111/STS2_Things.pck");
            if (File.Exists(pack)) Assert(ProjectSettings.LoadResourcePack(pack), "Shipping mod PCK mounts.");
            SaveManager.Instance.InitSettingsDataForTest();
            SaveManager.Instance.InitPrefsDataForTest();
            SaveManager.Instance.SettingsSave.Language = "eng";
            LocManager.Initialize();
            InitializeModelDb();
            await VerifyPoolsAndSeeds();
            await VerifyAbsorption();
            await VerifyMoveTransitions();
            await VerifySprayAndRinse();
            await VerifyRinseStatuses();
            await VerifyParasiteReinfestation();
            await VerifyNativePowerHooks();
            if (OS.GetCmdlineUserArgs().Contains("--visual")) await RenderProbe();
            DeactivateSyntheticCombat();
            GD.Print($"Water Sponge probe: PASS ({_checks} assertions)");
            GetTree().Quit(0);
        }
        catch (Exception exception) { GD.PushError(exception.ToString()); GetTree().Quit(1); }
    }

    private static async Task<Fixture> Scenario(bool weak = false, int players = 1, int ascension = 0, bool keepOpeningHand = false)
    {
        DeactivateSyntheticCombat();
        var party = Enumerable.Range(1, players).Select(i => Player.CreateForNewRun<Ironclad>(UnlockState.all, (ulong)i)).ToList();
        var run = RunState.CreateForNewRun(party, ActModel.GetDefaultList().Select(act => act.ToMutable()).ToList(), [], GameMode.Standard, ascension, "water-sponge-probe");
        run.CurrentActIndex = 1;
        typeof(RunManager).GetProperty("State", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(RunManager.Instance, run);
        typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance, new AscensionManager(ascension));
        typeof(RunManager).GetProperty("NetService")!.SetValue(RunManager.Instance, new NetSingleplayerGameService());
        EncounterModel encounter = (weak ? ModelDb.Encounter<SpongeLeechWeak>() as EncounterModel : ModelDb.Encounter<SpongeLeechEncounter>()).ToMutable();
        run.AppendToMapPointHistory(MapPointType.Monster, RoomType.Monster, encounter.Id);
        var room = new CombatRoom(encounter, run); run.PushRoom(room);
        foreach (var player in party) { player.ResetCombatState(); room.CombatState.AddPlayer(player); player.PopulateCombatState(run.Rng.Shuffle, room.CombatState); }
        encounter.GenerateMonstersWithSlots(run);
        foreach (var (monster, slot) in encounter.MonstersWithSlots)
        {
            var entity = room.CombatState.CreateCreature(monster, CombatSide.Enemy, slot);
            room.CombatState.AddCreature(entity); monster.SetUpForCombat();
            monster.RollMove(party.Select(player => player.Creature));
        }
        room.CombatState.CurrentSide = CombatSide.Player;
        ActivateSyntheticCombat(room.CombatState);
        await Hook.BeforeCombatStart(run, room.CombatState);
        foreach (var player in party)
            await Hook.BeforeHandDraw(room.CombatState, player, Choice);
        // Most isolated effect cases provide their own hand. Pool/opening cases
        // explicitly retain the newly generated opening parasites for inspection.
        if (!keepOpeningHand)
            foreach (var player in party)
                foreach (var card in player.PlayerCombatState!.Hand.Cards.ToArray())
                    await CardCmd.Discard(Choice, card);
        return new(run, room, party, encounter);
    }

    private static async Task VerifyPoolsAndSeeds()
    {
        var depths = ModelDb.Act<Depths>();
        Assert(depths.AllWeakEncounters.Any(e => e is SpongeLeechWeak), "Mixed weak encounter in Depths.");
        Assert(depths.AllRegularEncounters.Any(e => e is SpongeLeechEncounter), "Mixed regular encounter in Depths.");
        Assert(depths.AllWeakEncounters.Any(e => e is SanguineLeechWeak) && depths.AllRegularEncounters.Any(e => e is SanguineLeechEncounter), "Pure leech encounters retained.");
        Assert(depths.AllWeakEncounters.Any(e => e is LanternFishWeak) && depths.AllRegularEncounters.Any(e => e is LanternFishEncounter), "Fish encounters retained.");
        foreach (bool weak in new[] { true, false })
        foreach (int players in new[] { 1, 2, 4 })
        {
            var s = await Scenario(weak, players, keepOpeningHand: true);
            Assert(s.Encounter.IsWeak == weak && s.Leeches.Length == (weak ? 1 : 2), "One/two leeches alongside one sponge.");
            Assert(s.Encounter.MonstersWithSlots.Count == (weak ? 2 : 3), "Mixed encounter creature count.");
            Assert(s.Encounter.MonstersWithSlots.All(item => s.Encounter.Slots.Contains(item.Item2!)), "All mixed slots resolve.");
            Assert(s.Sponge.Creature.GetPower<AbsorbentSpongePower>() != null && s.Sponge.Water == 0, "Empty reservoir and passive at combat start.");
            Assert(s.Leeches.All(leech => leech.Creature.GetPower<LeechInfestationPower>() is { IsVisible: false, ShouldPlayVfx: false }),
                "Leech exhaust hooks use a native hidden power without a HUD icon or application effect.");
            Assert(s.Sponge.MinInitialHp == 44 && s.Sponge.MaxInitialHp == 48, "A0 sponge HP.");
            foreach (var player in s.Players)
            {
                Assert(player.PlayerCombatState!.Hand.Cards.OfType<LeechParasite>().Count() == s.Leeches.Length, "Native opening hand hook puts each leech's parasite directly in hand.");
                Assert(!player.PlayerCombatState.DrawPile.Cards.OfType<LeechParasite>().Any(), "Opening parasites do not pollute the draw pile.");
                Assert(!player.Deck.Cards.OfType<LeechParasite>().Any(), "Permanent deck remains parasite-free.");
            }
        }
        var high = await Scenario(ascension: 20);
        Assert(high.Sponge.MinInitialHp == 48 && high.Sponge.MaxInitialHp == 52, "Tough-enemy sponge HP.");
        GD.Print("PASS mixed pools, counts, opening parasites, multiplayer ownership and HP.");
    }

    private static Task Hit(Fixture s, int? damage = null) => CreatureCmd.Damage(Choice, s.Sponge.Creature,
        damage ?? s.Sponge.DamagePerWater, ValueProp.Move, s.Player.Creature);

    private static async Task VerifyAbsorption()
    {
        var blocked = await Scenario();
        await CreatureCmd.GainBlock(blocked.Sponge.Creature, 20, ValueProp.Unpowered, null);
        await Hit(blocked, 4);
        Assert(blocked.Sponge.Water == 0, "Fully blocked attacks do not fill the sponge.");
        var unpowered = await Scenario();
        await CreatureCmd.Damage(Choice, unpowered.Sponge.Creature, 2, ValueProp.Unpowered, unpowered.Player.Creature);
        Assert(unpowered.Sponge.Water == 0, "Unpowered/poison-like damage does not add water.");
        var single = await Scenario(); await Hit(single, single.Sponge.DamagePerWater * 2 + 1);
        Assert(single.Sponge.Water == 2 && single.Sponge.StoredDamage == 1,
            "Attack damage grants complete threshold stacks and retains the remainder.");
        var multiple = await Scenario();
        var attackCard = multiple.Room.CombatState.CreateCard<StrikeIronclad>(multiple.Player);
#if STS2_V107_1
        await DamageCmd.Attack(1).FromCard(attackCard).Targeting(multiple.Sponge.Creature).WithHitCount(3).Execute(Choice);
#else
        await DamageCmd.Attack(1).FromCard(attackCard, null).Targeting(multiple.Sponge.Creature).WithHitCount(3).Execute(Choice);
#endif
        Assert(multiple.Sponge.Water == 0 && multiple.Sponge.StoredDamage == 3,
            "Three one-damage hits only add three damage toward the shared threshold.");
        await Hit(multiple, multiple.Sponge.DamagePerWater * 3 - 3);
        Assert(multiple.Sponge.Water == 3 && multiple.Sponge.NextMove.Id == WaterSponge.SprayMoveId,
            "Three full damage thresholds fill the reservoir and refresh the intent.");
        await Hit(multiple, 1); Assert(multiple.Sponge.Water == 3 && multiple.Sponge.StoredDamage == 0,
            "A full reservoir discards extra damage instead of banking another spray.");
        var lethal = await Scenario(); await Hit(lethal, 999);
        Assert(!lethal.Sponge.Creature.IsAlive && lethal.Sponge.Water == 0, "Lethal damage never schedules a post-death spray.");
        var coop = await Scenario(players: 4); await Hit(coop);
        Assert(coop.Sponge.Water == 1, "One multiplayer-scaled damage threshold gives one water.");
        GD.Print("PASS native damage hooks, full block, non-attacks, multi-hit, cap and lethal handling.");
    }

    private static async Task VerifyMoveTransitions()
    {
        var s = await Scenario();
        Assert(s.Sponge.NextMove.Id == "SOAK_MOVE", "Starts with Soak.");
        await s.Sponge.PerformMove();
        Assert(s.Sponge.Creature.Block == 8 && s.Sponge.Water == 1, "Soak gives block and one water.");
        s.Sponge.RollMove(s.Players.Select(p => p.Creature));
        Assert(s.Sponge.NextMove.Id == "SLAP_MOVE", "Unfilled Soak follows with Slap.");
        int hp = s.Player.Creature.CurrentHp; await s.Sponge.PerformMove();
        Assert(s.Player.Creature.CurrentHp == hp - 9, "Slap uses native nine damage.");
        s.Sponge.RollMove(s.Players.Select(p => p.Creature));
        Assert(s.Sponge.NextMove.Id == "SOAK_MOVE", "Normal cycle returns to Soak.");

        s = await Scenario(); await Hit(s); await Hit(s);
        Assert(s.Sponge.NextMove.Id == "SOAK_MOVE", "Two water keeps the scheduled move.");
        await s.Sponge.PerformMove();
        Assert(s.Sponge.Water == 3 && s.Sponge.NextMove.Id == WaterSponge.SprayMoveId, "Soak can fill its own reservoir.");
        s.Sponge.RollMove(s.Players.Select(p => p.Creature));
        Assert(s.Sponge.NextMove.Id == WaterSponge.SprayMoveId, "Native move roll must not skip a spray selected mid-Soak.");
        await s.Sponge.PerformMove();
        Assert(s.Sponge.Water == 0, "Spray empties stored water.");
        s.Sponge.RollMove(s.Players.Select(p => p.Creature));
        Assert(s.Sponge.NextMove.Id == "SOAK_MOVE", "Spray recovers to normal cycle.");

        s = await Scenario();
        await CreatureCmd.Stun(s.Sponge.Creature, _ => Task.CompletedTask, "SOAK_MOVE");
        await Hit(s); await Hit(s); await Hit(s);
        Assert(s.Sponge.NextMove.Id == MonsterModel.stunnedMoveId, "Filling does not cancel a native stun.");
        await s.Sponge.PerformMove();
        await s.Sponge.Creature.GetPower<AbsorbentSpongePower>()!.AfterSideTurnEnd(Choice, CombatSide.Enemy, [s.Sponge.Creature]);
        s.Sponge.RollMove(s.Players.Select(p => p.Creature));
        Assert(s.Sponge.NextMove.Id == WaterSponge.SprayMoveId, "Spray remains pending after the stun turn.");
        GD.Print("PASS Soak/Slap cycle, mid-action fill, mandatory spray, reset and stun priority.");
    }

    private static async Task<T> AddToDraw<T>(Fixture s, Player player) where T : CardModel
    {
        var card = s.Room.CombatState.CreateCard<T>(player);
        await CardPileCmd.AddGeneratedCardToCombat(card, PileType.Draw, null, CardPilePosition.Top);
        return card;
    }

    private static async Task EndHand(Player player)
    {
        var method = typeof(CombatManager).GetMethod("DoTurnEnd", BindingFlags.Instance | BindingFlags.NonPublic)!;
        object?[] args = method.GetParameters().Length == 3
            ? [typeof(CombatManager).GetField("_turnState", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(CombatManager.Instance), player, Choice]
            : [player, Choice];
        await (Task)method.Invoke(CombatManager.Instance, args)!;
    }

    private static Task EndEnemySide(Fixture fixture, params Creature[] participants)
    {
        var hook = typeof(Hook).GetMethod("AfterSideTurnEnd", BindingFlags.Public | BindingFlags.Static)
            ?? typeof(Hook).GetMethod("AfterTurnEnd", BindingFlags.Public | BindingFlags.Static)!;
        return (Task)hook.Invoke(null, [fixture.Room.CombatState, CombatSide.Enemy, participants])!;
    }

    private static async Task VerifySprayAndRinse()
    {
        foreach (int ascension in new[] { 0, 20 })
        {
            var s = await Scenario(ascension: ascension, players: 2);
            string[] leechMoves = s.Leeches.Select(leech => leech.NextMove.Id).ToArray();
            await PowerCmd.Apply<SpongeReservoirPower>(Choice, s.Sponge.Creature, 3, s.Sponge.Creature, null);
            int[] hp = s.Players.Select(p => p.Creature.CurrentHp).ToArray();
            await s.Sponge.PerformMove();
            for (int index = 0; index < s.Players.Count; index++)
            {
                var player = s.Players[index];
                Assert(player.Creature.CurrentHp == hp[index] - (ascension == 0 ? 15 : 17), "Spray damage and ascension apply to each player.");
                Assert(player.Creature.GetPower<SpongeRinsePower>()?.Amount == 1, "Each player gains one independent Rinsed charge.");
                var normal = await AddToDraw<StrikeIronclad>(s, player);
                await CardPileCmd.Draw(Choice, 1, player);
                Assert(player.PlayerCombatState!.Hand.Cards.Contains(normal) && player.Creature.GetPower<SpongeRinsePower>()?.Amount == 1, "Ordinary draws do not consume Rinsed.");
                var parasite = await AddToDraw<LeechParasite>(s, player);
                await CardPileCmd.Draw(Choice, 1, player);
                Assert(player.PlayerCombatState.ExhaustPile.Cards.Contains(parasite) && !player.PlayerCombatState.Hand.Cards.Contains(parasite), "Native draw exhausts the parasite before it can be retained.");
                Assert(player.Creature.GetPower<SpongeRinsePower>() == null, "One parasite spends exactly one charge.");
                Assert(s.Leeches.Select(leech => leech.NextMove.Id).SequenceEqual(leechMoves),
                    "Rinsing a parasite preserves every leech's advertised action for this turn.");
                await EndHand(player);
                Assert(s.Leeches.All(leech => leech.Creature.GetPower<StrengthPower>() == null && leech.Creature.GetPower<RegenPower>() == null), "Cleansed parasite cannot feed leeches at native turn end.");
            }
            foreach (var leech in s.Leeches) await leech.PerformMove();
            await EndEnemySide(s, s.Leeches.Select(leech => leech.Creature).ToArray());
            foreach (var leech in s.Leeches) leech.RollMove(s.Players.Select(p => p.Creature));
            Assert(s.Leeches.All(leech => leech.NextMove.Id == SanguineLeech.ReinfestMoveId),
                "Parasites rinsed for multiple players schedule one refill per leech for the following turn.");
        }
        var cleansed = await Scenario(); var owner = cleansed.Player.Creature;
        await PowerCmd.Apply<WeakPower>(Choice, owner, 2, cleansed.Sponge.Creature, null);
        await PowerCmd.Apply<VulnerablePower>(Choice, owner, 2, cleansed.Sponge.Creature, null);
        await PowerCmd.Apply<FrailPower>(Choice, owner, 2, cleansed.Sponge.Creature, null);
        await PowerCmd.Apply<LanternBlindnessPower>(Choice, owner, 2, cleansed.Sponge.Creature, null);
        await PowerCmd.Apply<StrengthPower>(Choice, owner, 2, owner, null);
        await PowerCmd.Apply<SpongeReservoirPower>(Choice, cleansed.Sponge.Creature, 3, cleansed.Sponge.Creature, null);
        int before = owner.CurrentHp; await cleansed.Sponge.PerformMove();
        Assert(before-owner.CurrentHp == 22, "Vulnerable affects the spray before being washed down.");
        Assert(owner.GetPower<WeakPower>()?.Amount == 1 && owner.GetPower<VulnerablePower>()?.Amount == 1 && owner.GetPower<FrailPower>()?.Amount == 1 && owner.GetPower<LanternBlindnessPower>()?.Amount == 1, "Only one layer of each supported debuff is washed away.");
        Assert(owner.GetPower<StrengthPower>()?.Amount == 2, "Positive powers are preserved.");
        await PowerCmd.Apply<SpongeRinsePower>(Choice, owner, 9, owner, null);
        Assert(owner.GetPower<SpongeRinsePower>()?.Amount == 2, "Rinsed caps at two charges.");

        var foreign = await Scenario(players: 2);
        await PowerCmd.Apply<SpongeRinsePower>(Choice, foreign.Player.Creature, 1, foreign.Sponge.Creature, null);
        var other = foreign.Players[1]; var otherParasite = await AddToDraw<LeechParasite>(foreign, other);
        await CardPileCmd.Draw(Choice, 1, other);
        Assert(other.PlayerCombatState!.Hand.Cards.Contains(otherParasite) && foreign.Player.Creature.GetPower<SpongeRinsePower>()?.Amount == 1, "One player's Rinsed never consumes another player's cards or charges.");
        GD.Print("PASS cleansing order, four debuffs, owner-only native draw/exhaust and parasite end-turn prevention.");
    }

    private static async Task VerifyCleansedStatus<T>() where T : CardModel
    {
        var s = await Scenario();
        string[] moves = s.Leeches.Select(leech => leech.NextMove.Id).ToArray();
        await PowerCmd.Apply<SpongeRinsePower>(Choice, s.Player.Creature, 1, s.Sponge.Creature, null);
        var status = await AddToDraw<T>(s, s.Player);
        await CardPileCmd.Draw(Choice, 1, s.Player);
        Assert(status.Type == CardType.Status && s.Player.PlayerCombatState!.ExhaustPile.Cards.Contains(status), "Rinsed exhausts native status " + status.Id);
        Assert(s.Player.Creature.GetPower<SpongeRinsePower>() == null, "Each native status consumes exactly one Rinsed charge.");
        Assert(s.Leeches.Select(leech => leech.NextMove.Id).SequenceEqual(moves), "Exhausting non-parasite statuses does not redirect leeches.");
    }

    private static async Task VerifyRinseStatuses()
    {
        await VerifyCleansedStatus<Burn>();
        await VerifyCleansedStatus<Wound>();
        await VerifyCleansedStatus<Dazed>();
        await VerifyCleansedStatus<Slimed>();
        await VerifyCleansedStatus<MegaCrit.Sts2.Core.Models.Cards.Void>();
        var curse = await Scenario();
        await PowerCmd.Apply<SpongeRinsePower>(Choice, curse.Player.Creature, 1, curse.Sponge.Creature, null);
        var doubt = await AddToDraw<Doubt>(curse, curse.Player);
        await CardPileCmd.Draw(Choice, 1, curse.Player);
        Assert(curse.Player.PlayerCombatState!.Hand.Cards.Contains(doubt) && curse.Player.Creature.GetPower<SpongeRinsePower>()?.Amount == 1,
            "Curses are not Status cards and do not consume Rinsed.");

        var nested = await Scenario();
        await PowerCmd.Apply<SpongeRinsePower>(Choice, nested.Player.Creature, 2, nested.Sponge.Creature, null);
        await PowerCmd.Apply<DarkEmbracePower>(Choice, nested.Player.Creature, 1, nested.Player.Creature, null);
        for (int i = 0; i < 3; i++) await AddToDraw<Wound>(nested, nested.Player);
        await CardPileCmd.Draw(Choice, 1, nested.Player);
        Assert(nested.Player.PlayerCombatState!.ExhaustPile.Cards.OfType<Wound>().Count() == 2
            && nested.Player.PlayerCombatState.Hand.Cards.OfType<Wound>().Count() == 1
            && nested.Player.Creature.GetPower<SpongeRinsePower>() == null,
            "Native exhaust-triggered draws cannot reuse a spent charge; two charges remove two statuses.");
        GD.Print("PASS all five native Status types, curse exclusion, nested draws and non-parasite leech behavior.");
    }

    private static async Task VerifyParasiteReinfestation()
    {
        string[] cycle = ["SIP_MOVE", "INFEST_MOVE", "SIP_AGAIN_MOVE", "CURL_MOVE"];
        foreach (bool play in new[] { true, false })
        foreach (int phase in Enumerable.Range(0, cycle.Length))
        {
            var s = await Scenario();
            for (int i = 0; i < s.Leeches.Length; i++)
                s.Leeches[i].SetMoveImmediate((MoveState)s.Leeches[i].MoveStateMachine!.States[cycle[(phase + i) % cycle.Length]]);
            string[] advertised = s.Leeches.Select(leech => leech.NextMove.Id).ToArray();
            int flashes = 0;
            foreach (var leech in s.Leeches)
                leech.Creature.GetPower<LeechInfestationPower>()!.Flashed += _ => flashes++;
            var parasite = await AddToDraw<LeechParasite>(s, s.Player);
            await CardPileCmd.Draw(Choice, 1, s.Player);
            if (play) await CardCmd.AutoPlay(Choice, parasite, null, skipCardPileVisuals: true);
            else await CardCmd.Exhaust(Choice, parasite, skipVisuals: true);
            Assert(s.Player.PlayerCombatState!.ExhaustPile.Cards.Contains(parasite), "Parasite really enters the native exhaust pile.");
            Assert(s.Leeches.Select(leech => leech.NextMove.Id).SequenceEqual(advertised),
                "Play and external exhaust preserve this turn's attack, defense or Infest intent.");
            Assert(flashes == 0, "The hidden infestation mechanic never flashes a buff icon.");
            // Several clears before a move produce one refill, not a queue of turns.
            await CardCmd.Exhaust(Choice, await AddToDraw<LeechParasite>(s, s.Player), skipVisuals: true);
            foreach (var leech in s.Leeches)
                await leech.AfterSideTurnEnd(Choice, CombatSide.Player, [s.Player.Creature]);
            Assert(s.Leeches.Select(leech => leech.NextMove.Id).SequenceEqual(advertised),
                "Repeated clears and player turn end cannot replace this turn's advertised action.");
            foreach (var leech in s.Leeches)
            {
                string move = leech.NextMove.Id;
                int hp = s.Player.Creature.CurrentHp;
                int hand = s.Player.PlayerCombatState.Hand.Cards.OfType<LeechParasite>().Count();
                await leech.PerformMove();
                Assert(move is "SIP_MOVE" or "SIP_AGAIN_MOVE" ? s.Player.Creature.CurrentHp == hp - 6 :
                    move == "CURL_MOVE" ? leech.Creature.Block == SanguineLeech.CurlBlock :
                    s.Player.PlayerCombatState.Hand.Cards.OfType<LeechParasite>().Count() == hand + 1,
                    "The original action really executes before any queued refill.");
            }
            await EndEnemySide(s, s.Leeches.Select(leech => leech.Creature).ToArray());
            int before = s.Player.PlayerCombatState.Hand.Cards.OfType<LeechParasite>().Count();
            foreach (var leech in s.Leeches)
            {
                leech.RollMove(s.Players.Select(p => p.Creature));
                Assert(leech.NextMove.Id == SanguineLeech.ReinfestMoveId, "Refill is announced for the next turn, even after a normal Infest.");
                leech.RollMove(s.Players.Select(p => p.Creature));
                Assert(leech.NextMove.Id == SanguineLeech.ReinfestMoveId, "A mandatory refill cannot be rolled past before acting.");
                await leech.PerformMove();
            }
            await EndEnemySide(s, s.Leeches.Select(leech => leech.Creature).ToArray());
            for (int i = 0; i < s.Leeches.Length; i++)
            {
                var leech = s.Leeches[i];
                leech.RollMove(s.Players.Select(p => p.Creature));
                Assert(leech.NextMove.Id == cycle[(phase + i + 1) % cycle.Length],
                    "Insertion resumes this individual leech's saved next action without resetting its cycle.");
            }
            Assert(s.Player.PlayerCombatState.Hand.Cards.OfType<LeechParasite>().Count() == before + s.Leeches.Length, "Each leech inserts exactly one parasite directly in hand.");
        }

        var discard = await Scenario();
        var kept = await AddToDraw<LeechParasite>(discard, discard.Player);
        await CardPileCmd.Draw(Choice, 1, discard.Player);
        string[] originalMoves = discard.Leeches.Select(l => l.NextMove.Id).ToArray();
        await CardCmd.Discard(Choice, kept);
        await CardCmd.Exhaust(Choice, await AddToDraw<StrikeIronclad>(discard, discard.Player), skipVisuals: true);
        Assert(discard.Leeches.Select(l => l.NextMove.Id).SequenceEqual(originalMoves), "Discard and exhausting a different card do not trigger refill.");
        await CardPileCmd.Add(kept, PileType.Hand);
        await EndHand(discard.Player);
        Assert(discard.Leeches.Select(l => l.NextMove.Id).SequenceEqual(originalMoves), "Ordinary turn-end discard does not trigger refill.");
        foreach (var leech in discard.Leeches) await leech.PerformMove();
        await EndEnemySide(discard, discard.Leeches.Select(leech => leech.Creature).ToArray());
        foreach (var leech in discard.Leeches) leech.RollMove(discard.Players.Select(p => p.Creature));
        Assert(discard.Leeches.All(leech => leech.NextMove.Id != SanguineLeech.ReinfestMoveId),
            "Discard and non-parasite exhaust do not leave a delayed refill request.");

        var dead = await Scenario();
        var deadLeech = dead.Leeches[0];
        string deadMove = deadLeech.NextMove.Id;
        await CreatureCmd.Damage(Choice, deadLeech.Creature, 999, ValueProp.Unpowered, dead.Player.Creature);
        var removed = await AddToDraw<LeechParasite>(dead, dead.Player);
        await CardCmd.Exhaust(Choice, removed, skipVisuals: true);
        await deadLeech.AfterCardExhausted(Choice, removed, false);
        Assert(deadLeech.NextMove.Id == deadMove && dead.Leeches[1].NextMove.Id == "SIP_AGAIN_MOVE", "Death and exhaust preserve the survivor's current action.");
        await dead.Leeches[1].PerformMove();
        await EndEnemySide(dead, dead.Leeches.Select(leech => leech.Creature).ToArray());
        dead.Leeches[1].RollMove(dead.Players.Select(p => p.Creature));
        Assert(deadLeech.NextMove.Id == deadMove && dead.Leeches[1].NextMove.Id == SanguineLeech.ReinfestMoveId, "Only survivors announce the next-turn refill.");

        var stunned = await Scenario(weak: true);
        var waiting = stunned.Leeches.Single();
        await CreatureCmd.Stun(waiting.Creature, _ => Task.CompletedTask, "SIP_MOVE");
        await CardCmd.Exhaust(Choice, await AddToDraw<LeechParasite>(stunned, stunned.Player), skipVisuals: true);
        Assert(waiting.NextMove.Id == MonsterModel.stunnedMoveId, "Clearing a parasite cannot cancel an unperformed stun.");
        await waiting.PerformMove();
        await EndEnemySide(stunned, waiting.Creature);
        waiting.RollMove(stunned.Players.Select(p => p.Creature));
        Assert(waiting.NextMove.Id == SanguineLeech.ReinfestMoveId, "Pending refill survives the stun turn.");
        // Clearing again while a refill is already advertised must schedule
        // another refill next turn, without changing the current action.
        await CardCmd.Exhaust(Choice, await AddToDraw<LeechParasite>(stunned, stunned.Player), skipVisuals: true);
        Assert(waiting.NextMove.Id == SanguineLeech.ReinfestMoveId && !waiting.NextMove.CanTransitionAway,
            "A new clear leaves the currently advertised refill intact.");
        await waiting.PerformMove();
        await EndEnemySide(stunned, waiting.Creature);
        waiting.RollMove(stunned.Players.Select(p => p.Creature));
        Assert(waiting.NextMove.Id == SanguineLeech.ReinfestMoveId && !waiting.NextMove.CanTransitionAway,
            "A clear on a refill turn schedules another refill for the following turn.");
        await waiting.PerformMove();
        // Model a nested exhaust after the current Infest has begun; native hooks
        // must defer the new request until the current action safely completes.
        var performing = typeof(MonsterModel).GetProperty(nameof(MonsterModel.IsPerformingMove))!;
        performing.SetValue(waiting, true);
        await CardCmd.Exhaust(Choice, await AddToDraw<LeechParasite>(stunned, stunned.Player), skipVisuals: true);
        Assert(waiting.NextMove.CanTransitionAway, "Nested exhaust does not reset the active action midway through it.");
        performing.SetValue(waiting, false);
        await EndEnemySide(stunned, waiting.Creature);
        waiting.RollMove(stunned.Players.Select(p => p.Creature));
        Assert(waiting.NextMove.Id == SanguineLeech.ReinfestMoveId && !waiting.NextMove.CanTransitionAway, "Nested request re-arms the refill for the following action.");
        await waiting.PerformMove();
        await EndEnemySide(stunned, waiting.Creature);
        waiting.RollMove(stunned.Players.Select(p => p.Creature));
        Assert(waiting.NextMove.Id == "SIP_MOVE", "Repeated insertions after a stun preserve the stun's original resume action.");

        // Repeated player clears must still let the complete base cycle advance;
        // the previous implementation kept jumping back to SIP_AGAIN_MOVE.
        var repeated = await Scenario(weak: true);
        var alternating = repeated.Leeches.Single();
        for (int turn = 0; turn < 8; turn++)
        {
            Assert(alternating.NextMove.Id == cycle[turn % cycle.Length], "Repeated inserts preserve two complete normal cycles.");
            await CardCmd.Exhaust(Choice, await AddToDraw<LeechParasite>(repeated, repeated.Player), skipVisuals: true);
            await alternating.PerformMove();
            await EndEnemySide(repeated, alternating.Creature);
            alternating.RollMove(repeated.Players.Select(p => p.Creature));
            Assert(alternating.NextMove.Id == SanguineLeech.ReinfestMoveId, "A clear inserts exactly the following turn.");
            await alternating.PerformMove();
            await EndEnemySide(repeated, alternating.Creature);
            alternating.RollMove(repeated.Players.Select(p => p.Creature));
            foreach (var card in repeated.Player.PlayerCombatState!.Hand.Cards.ToArray())
                await CardCmd.Discard(Choice, card);
        }
        GD.Print("PASS delayed inserted turns, per-leech cycle resume, two complete interrupted cycles, hand generation, hidden power, death and stun.");
    }

    private static async Task VerifyNativePowerHooks()
    {
        var s = await Scenario();
        foreach (var (monster, _) in s.Encounter.MonstersWithSlots)
            Assert(monster.MoveStateMachine!.States.Values.OfType<MoveState>().SelectMany(move => move.Intents)
                .All(intent => intent.GetType().Assembly == typeof(AbstractIntent).Assembly), "Every intent is an original game intent class.");

        int absorptionFlashes = 0;
        s.Sponge.Creature.GetPower<AbsorbentSpongePower>()!.Flashed += _ => absorptionFlashes++;
        await Hit(s);
        Assert(absorptionFlashes == 1, "Absorption emits the native PowerModel flash event.");
        var reservoir = s.Sponge.Creature.GetPower<SpongeReservoirPower>()!;
        int updates = 0; bool removed = false;
        reservoir.DisplayAmountChanged += () => updates++;
        reservoir.Removed += () => removed = true;
        await Hit(s);
        Assert(reservoir.Amount == 2 && updates == 1, "Native power amount event updates the HUD counter.");
        await PowerCmd.Remove(reservoir);
        Assert(removed && s.Sponge.Creature.GetPower<SpongeReservoirPower>() == null, "Native removal event clears the power.");

        var rinse = await PowerCmd.Apply<SpongeRinsePower>(Choice, s.Player.Creature, 2, s.Sponge.Creature, null);
        int rinseFlashes = 0;
        rinse!.Flashed += _ => rinseFlashes++;
        await AddToDraw<LeechParasite>(s, s.Player);
        await CardPileCmd.Draw(Choice, 1, s.Player);
        Assert(rinse.Amount == 1 && rinseFlashes == 1, "Rinse consumes a native power charge and flashes once.");
        await AddToDraw<LeechParasite>(s, s.Player);
        await CardPileCmd.Draw(Choice, 1, s.Player);
        Assert(s.Player.Creature.GetPower<SpongeRinsePower>() == null, "The native command removes Rinsed at zero.");

        var blindness = await PowerCmd.Apply<LanternBlindnessPower>(Choice, s.Player.Creature, 1, s.Sponge.Creature, null);
        int blindnessFlashes = 0;
        blindness!.Flashed += _ => blindnessFlashes++;
        await AddToDraw<StrikeIronclad>(s, s.Player);
        await CardPileCmd.Draw(Choice, 1, s.Player);
        Assert(blindnessFlashes == 1 && s.Player.Creature.GetPower<LanternBlindnessPower>() == null,
            "Blindness also uses native power flash and zero-stack removal.");
        GD.Print("PASS original intent types and native power display, flash, decrement and removal events.");
    }

    private static void Assert(bool condition, string message) { if (!condition) throw new Exception(message); _checks++; }
    private sealed record Fixture(RunState Run, CombatRoom Room, List<Player> Players, EncounterModel Encounter)
    {
        public Player Player => Players[0];
        public WaterSponge Sponge => Encounter.MonstersWithSlots.Select(item => item.Item1).OfType<WaterSponge>().Single();
        public SanguineLeech[] Leeches => Encounter.MonstersWithSlots.Select(item => item.Item1).OfType<SanguineLeech>().ToArray();
    }
}
