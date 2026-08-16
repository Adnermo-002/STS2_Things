using System.Collections;
using System.Reflection;
using System.Runtime.Loader;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Encounters;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Potions;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Potions;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Encounters;
using STS2_Things.Modifiers;
using STS2_Things.Monsters;
using STS2_Things.Powers;

public partial class QuirkyHopperProbeNode : Node
{
    public override async void _Ready()
    {
        try
        {
            TestMode.TurnOnInternal();
            InitializeModelDb();
            VerifyEncounterAndMoveContract();
            VerifyPrioritySelection();
            await VerifyKillReturnsExactLoot();
            await VerifyEscapeKeepsExactLoot();
            await VerifyFullBeltRewardPolicy();
            GD.Print("Quirky Hopper behavior probe: PASS");
            GetTree().Quit(0);
        }
        catch (Exception exception)
        {
            GD.PushError(exception.ToString());
            GetTree().Quit(1);
        }
    }

    private static void InitializeModelDb()
    {
        AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency;
        EnsureRuntimeDependency("System.IO.Hashing");
        Type[] modTypes = typeof(QuirkyHopper).Assembly.GetTypes();
        Type[] modelTypes = AbstractModelSubtypes.All
            .Concat(modTypes.Where(type => !type.IsAbstract && typeof(AbstractModel).IsAssignableFrom(type)))
            .Distinct()
            .ToArray();
        // RunState queries ReflectionHelper again for badges and other runtime model
        // classes. A standalone probe has no normal ModManager boot sequence, so seed
        // the exact post-initialization state that the real loader provides.
        typeof(ReflectionHelper).GetField("_modTypes", BindingFlags.NonPublic | BindingFlags.Static)!
            .SetValue(null, modTypes);
        RegisterSyntheticMod(typeof(QuirkyHopper).Assembly);
        // V111 exposes ModManager.State/ModManagerState, while V107.1 does not.
        // Seed it when present without creating a compile-time dependency on the
        // newer API so this same probe source validates both shipped targets.
        PropertyInfo? managerState = typeof(ModManager).GetProperty(
            "State", BindingFlags.Public | BindingFlags.Static);
        if (managerState != null)
        {
            managerState.SetValue(null, Enum.Parse(managerState.PropertyType, "Initialized"));
        }
        Type? assemblyInfo = typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Modding.AssemblyInfo");
        assemblyInfo?.GetMethod("Init", BindingFlags.Public | BindingFlags.Static)?.Invoke(null, null);
        typeof(ModelDb).GetMethod("ResetForTest", BindingFlags.Public | BindingFlags.Static)?
            .Invoke(null, null);
        MethodInfo init = typeof(ModelDb).GetMethods(BindingFlags.Public | BindingFlags.Static)
            .Single(method => method.Name == "Init");
        init.Invoke(null, init.GetParameters().Length == 0 ? null : [modelTypes]);
        Type serializationCache = typeof(ModelDb).Assembly.GetType(
            "MegaCrit.Sts2.Core.Multiplayer.Serialization.ModelIdSerializationCache",
            throwOnError: true)!;
        serializationCache.GetMethod("Init", BindingFlags.Public | BindingFlags.Static)!
            .Invoke(null, null);
        typeof(ModelDb).GetMethod("InitIds", BindingFlags.Public | BindingFlags.Static)!
            .Invoke(null, null);
    }

    private static void EnsureRuntimeDependency(string assemblyName)
    {
        if (AppDomain.CurrentDomain.GetAssemblies().Any(
                assembly => string.Equals(assembly.GetName().Name, assemblyName, StringComparison.Ordinal)))
        {
            return;
        }

        string path = FindRuntimeDependencyPath(assemblyName)
            ?? throw new FileNotFoundException(
                $"Could not locate probe runtime dependency {assemblyName}.dll.");
        AssemblyLoadContext.Default.LoadFromAssemblyPath(path);
    }

    private static Assembly? ResolveRuntimeDependency(
        AssemblyLoadContext context,
        AssemblyName assemblyName)
    {
        if (string.IsNullOrWhiteSpace(assemblyName.Name))
        {
            return null;
        }

        string? path = FindRuntimeDependencyPath(assemblyName.Name);
        return path == null ? null : context.LoadFromAssemblyPath(path);
    }

    private static string? FindRuntimeDependencyPath(string assemblyName)
    {
        string configuration =
#if DEBUG
            "Debug";
#else
            "Release";
#endif
        string projectRoot = ProjectSettings.GlobalizePath("res://");
        string? assemblyDirectory = Path.GetDirectoryName(
            typeof(QuirkyHopperProbeNode).Assembly.Location);
        string[] candidates =
        [
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", configuration, $"{assemblyName}.dll"),
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", "Debug", $"{assemblyName}.dll"),
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", "Release", $"{assemblyName}.dll"),
            Path.Combine(assemblyDirectory ?? string.Empty, $"{assemblyName}.dll")
        ];
        return candidates.FirstOrDefault(File.Exists);
    }

    private static void RegisterSyntheticMod(Assembly implementationAssembly)
    {
        Type gameAssemblyMarker = typeof(ModManager);
        Type modType = gameAssemblyMarker.Assembly.GetType("MegaCrit.Sts2.Core.Modding.Mod", throwOnError: true)!;
        Type manifestType = gameAssemblyMarker.Assembly.GetType("MegaCrit.Sts2.Core.Modding.ModManifest", throwOnError: true)!;
        object mod = Activator.CreateInstance(modType)!;
        object manifest = Activator.CreateInstance(manifestType)!;
        manifestType.GetField("id")!.SetValue(manifest, "STS2_Things");
        manifestType.GetField("name")?.SetValue(manifest, "STS2_Things Probe");
        manifestType.GetField("affectsGameplay")?.SetValue(manifest, true);
        modType.GetField("path")!.SetValue(mod, "probe://STS2_Things");
        modType.GetField("manifest")!.SetValue(mod, manifest);
        FieldInfo stateField = modType.GetField("state")!;
        stateField.SetValue(mod, Enum.Parse(stateField.FieldType, "Loaded"));

        FieldInfo? assembliesField = modType.GetField("assemblies");
        if (assembliesField?.GetValue(mod) is IList assemblies)
        {
            assemblies.Add(implementationAssembly);
        }
        else
        {
            modType.GetField("assembly")!.SetValue(mod, implementationAssembly);
        }

        IList mods = (IList)typeof(ModManager).GetField("_mods", BindingFlags.NonPublic | BindingFlags.Static)!
            .GetValue(null)!;
        mods.Clear();
        mods.Add(mod);
    }

    private static void VerifyEncounterAndMoveContract()
    {
        QuirkyHopperWeak encounter = ModelDb.Encounter<QuirkyHopperWeak>();
        Assert(encounter.RoomType == RoomType.Monster, "Encounter is not a normal hallway room.");
        Assert(encounter.IsWeak, "Encounter is not in the Act 2 weak hallway subset.");
        Assert(encounter.Tags.SequenceEqual([EncounterTag.Thieves]), "Encounter tag differs from the native thief encounter.");

        QuirkyHopper hopper = (QuirkyHopper)ModelDb.Monster<QuirkyHopper>().ToMutable();
        hopper.SetUpForCombat();
        MonsterMoveStateMachine machine = hopper.MoveStateMachine
            ?? throw new InvalidOperationException("Move state machine was not initialized.");
        string[] ids = machine.States.Keys.OrderBy(id => id, StringComparer.Ordinal).ToArray();
        string[] expectedIds =
        [
            "ESCAPE_MOVE",
            "FLUTTER_MOVE",
            "HAT_TRICK_MOVE",
            "NAB_MOVE",
            "THIEVERY_MOVE"
        ];
        Assert(ids.SequenceEqual(expectedIds), "Move state machine differs from the native five-turn chain.");
        MoveState thievery = (MoveState)machine.States["THIEVERY_MOVE"];
        Assert(
            thievery.Intents.Count == 2 &&
            thievery.Intents[0] is SingleAttackIntent &&
            thievery.Intents[1] is CardDebuffIntent,
            "Thievery does not expose the native attack + card-debuff intents.");
    }

    private static void VerifyPrioritySelection()
    {
        Scenario basic = CreateScenario(
            "QUIRKY_PRIORITY_BASIC",
            addCurse: false,
            addFirePotion: false,
            configureDeck: static (runState, player) =>
            {
                player.Deck.AddInternal(runState.CreateCard<Anger>(player), silent: true);
                player.Deck.AddInternal(runState.CreateCard<Uppercut>(player), silent: true);
                player.Deck.AddInternal(runState.CreateCard<Abrasive>(player), silent: true);
            });
        CardModel selectedBasic = SelectCardToSteal(basic.Hopper, basic.Player);
        Assert(
            selectedBasic.Id.Entry.StartsWith("STRIKE_", StringComparison.Ordinal) ||
            selectedBasic.Id.Entry.StartsWith("DEFEND_", StringComparison.Ordinal),
            $"Basic priority selected {selectedBasic.Id.Entry} instead of a starter Strike/Defend.");

        Scenario cursed = CreateScenario("QUIRKY_PRIORITY_CURSE", addCurse: true, addFirePotion: false);
        CardModel selectedCurse = SelectCardToSteal(cursed.Hopper, cursed.Player);
        Assert(selectedCurse.Type == CardType.Curse, "Curse priority did not win.");
        Assert(ReferenceEquals(selectedCurse.DeckVersion, cursed.CurseCard), "The selected curse lost its exact deck identity.");

        Scenario common = CreateScenario(
            "QUIRKY_PRIORITY_COMMON",
            addCurse: false,
            addFirePotion: false,
            configureDeck: static (runState, player) => ReplaceDeck(
                player,
                runState.CreateCard<Anger>(player),
                runState.CreateCard<Uppercut>(player),
                runState.CreateCard<Abrasive>(player)));
        Assert(
            SelectCardToSteal(common.Hopper, common.Player).Rarity == CardRarity.Common,
            "Common priority did not beat Uncommon and Rare cards.");

        Scenario uncommon = CreateScenario(
            "QUIRKY_PRIORITY_UNCOMMON",
            addCurse: false,
            addFirePotion: false,
            configureDeck: static (runState, player) => ReplaceDeck(
                player,
                runState.CreateCard<Uppercut>(player),
                runState.CreateCard<Abrasive>(player)));
        Assert(
            SelectCardToSteal(uncommon.Hopper, uncommon.Player).Rarity == CardRarity.Uncommon,
            "Uncommon priority did not beat Rare cards.");

        Scenario rare = CreateScenario(
            "QUIRKY_PRIORITY_RARE",
            addCurse: false,
            addFirePotion: false,
            configureDeck: static (runState, player) => ReplaceDeck(
                player,
                runState.CreateCard<Abrasive>(player)));
        Assert(
            SelectCardToSteal(rare.Hopper, rare.Player).Rarity == CardRarity.Rare,
            "Rare cards were not selected when no higher-priority cards remained.");
    }

    private static async Task VerifyKillReturnsExactLoot()
    {
        Scenario scenario = CreateScenario("QUIRKY_KILL_RETURN", addCurse: false, addFirePotion: true);
        int deckCount = scenario.Player.Deck.Cards.Count;
        CardModel deckCard = scenario.Player.Deck.Cards[0];
        LootStates states = ConfigureTheft(scenario, deckCard, rehydrate: false);

        Assert(History(scenario).StolenLoot == 2, "The card and potion theft were not both recorded.");
        Assert(scenario.Player.PotionSlots[scenario.PotionSlot] is null, "The stolen potion stayed in the belt.");
        Assert(scenario.Player.Deck.Cards.Count == deckCount, "The save-safe deck escrow changed at theft time.");
        Assert(!IsVisibleInternal(states.PotionState) && IsVisibleInternal(states.CardState), "Hidden/visible Quirk state split is wrong.");
        AssertHoverPayload(states.CardState);

        await states.PotionState.BeforeDeath(scenario.HopperCreature);
        await states.CardState.BeforeDeath(scenario.HopperCreature);

        PotionModel? returnedPotion = scenario.Player.PotionSlots[scenario.PotionSlot];
        Assert(returnedPotion is FirePotion, "Kill returned a different potion.");
        Assert(ReferenceEquals(returnedPotion, scenario.FirePotion), "Live kill did not return the exact potion instance.");
        Assert(scenario.Player.Deck.Cards.Count == deckCount, "Kill did not leave the exact card in the deck.");
        Assert(ReferenceEquals(scenario.Player.Deck.Cards[0], deckCard), "Kill replaced the stolen deck card.");
        Assert(History(scenario).StolenLoot == 0 && !History(scenario).WasMugged, "Kill still resolves to the mugged header.");
    }

    private static async Task VerifyEscapeKeepsExactLoot()
    {
        Scenario scenario = CreateScenario("QUIRKY_ESCAPE_LOSS", addCurse: false, addFirePotion: true);
        int deckCount = scenario.Player.Deck.Cards.Count;
        CardModel deckCard = scenario.Player.Deck.Cards[0];
        LootStates states = ConfigureTheft(scenario, deckCard, rehydrate: true);

        await states.PotionState.ResolveEscape();
        await states.CardState.ResolveEscape();

        Assert(scenario.Player.PotionSlots[scenario.PotionSlot] is null, "Escape returned the stolen potion.");
        Assert(scenario.Player.Deck.Cards.Count == deckCount - 1, "Escape did not remove the stolen deck card.");
        Assert(!scenario.Player.Deck.Cards.Contains(deckCard), "Escaped card remains in the deck.");
        Assert(History(scenario).StolenLoot == 2 && History(scenario).WasMugged, "Escape does not resolve to the mugged header.");
    }

    private static async Task VerifyFullBeltRewardPolicy()
    {
        Scenario scenario = CreateScenario("QUIRKY_FULL_BELT", addCurse: false, addFirePotion: true);
        LootStates states = ConfigureTheft(scenario, scenario.Player.Deck.Cards[0], rehydrate: true);

        for (int slot = 0; slot < scenario.Player.PotionSlots.Count; slot++)
        {
            if (scenario.Player.PotionSlots[slot] is null)
            {
                PotionProcureResult result = scenario.Player.AddPotionInternal(ModelDb.Potion<ColorlessPotion>().ToMutable(), slot, silent: true);
                Assert(result.success, $"Failed to fill potion slot {slot}.");
            }
        }

        await states.PotionState.BeforeDeath(scenario.HopperCreature);
        await states.CardState.BeforeDeath(scenario.HopperCreature);
        Assert(History(scenario).StolenLoot == 0 && !History(scenario).WasMugged, "Full-belt kill still resolves as mugged.");

        List<Reward> extraRewards = scenario.Room.ExtraRewards[scenario.Player];
        Assert(extraRewards.Count == 1, "Full-belt kill did not create exactly one exact potion reward.");
        PotionReward returnedReward = (PotionReward)extraRewards[0];
        Assert(returnedReward.Potion is FirePotion, "Full-belt reward changed the stolen potion type.");

        var rewards = new List<Reward>
        {
            new PotionReward(ModelDb.Potion<FirePotion>().ToMutable(), scenario.Player),
            returnedReward
        };
        QuirkyHopperRewardPolicy policy = ModelDb.Modifier<QuirkyHopperRewardPolicy>();
        bool modified = policy.TryModifyRewardsLate(scenario.Player, rewards, scenario.Room);
        Assert(modified, "Exact-potion reward policy did not run.");
        Assert(rewards.Count == 1 && ReferenceEquals(rewards[0], returnedReward), "Duplicate potion reward was not removed deterministically.");
    }

    private static Scenario CreateScenario(
        string seed,
        bool addCurse,
        bool addFirePotion,
        Action<RunState, Player>? configureDeck = null)
    {
        Player player = Player.CreateForNewRun<Ironclad>(UnlockState.all, 1UL);
        RunState runState = RunState.CreateForNewRun(
            [player],
            ActModel.GetDefaultList().Select(act => act.ToMutable()).ToList(),
            [],
            GameMode.Standard,
            0,
            seed);

        CardModel? curseCard = null;
        if (addCurse)
        {
            curseCard = runState.CreateCard<Clumsy>(player);
            player.Deck.AddInternal(curseCard, silent: true);
        }
        configureDeck?.Invoke(runState, player);

        QuirkyHopperWeak encounter = (QuirkyHopperWeak)ModelDb.Encounter<QuirkyHopperWeak>().ToMutable();
        runState.AppendToMapPointHistory(MapPointType.Monster, RoomType.Monster, encounter.Id);
        var room = new CombatRoom(encounter, runState);
        runState.PushRoom(room);

        player.ResetCombatState();
        room.CombatState.AddPlayer(player);
        player.PopulateCombatState(runState.Rng.Shuffle, room.CombatState);

        QuirkyHopper hopper = (QuirkyHopper)ModelDb.Monster<QuirkyHopper>().ToMutable();
        Creature creature = room.CombatState.CreateCreature(hopper, CombatSide.Enemy, null);
        room.CombatState.AddCreature(creature);

        PotionModel? firePotion = null;
        const int potionSlot = 1;
        if (addFirePotion)
        {
            firePotion = ModelDb.Potion<FirePotion>().ToMutable();
            PotionProcureResult result = player.AddPotionInternal(firePotion, potionSlot, silent: true);
            Assert(result.success, "Failed to add the test Fire Potion.");
        }

        return new Scenario(player, runState, room, hopper, creature, firePotion, potionSlot, curseCard);
    }

    private static void ReplaceDeck(Player player, params CardModel[] cards)
    {
        player.Deck.Clear(silent: true);
        foreach (CardModel card in cards)
        {
            player.Deck.AddInternal(card, silent: true);
        }
    }

    private static LootStates ConfigureTheft(Scenario scenario, CardModel deckCard, bool rehydrate)
    {
        PotionModel firePotion = scenario.FirePotion
            ?? throw new InvalidOperationException("Scenario has no potion to steal.");
        scenario.Player.DiscardPotionInternal(firePotion);

        var configuredPotion = (ThingsQuirkPower)ModelDb.Power<ThingsQuirkPower>().ToMutable();
        int potionAmount = configuredPotion.ConfigurePotionState(scenario.Player, firePotion, scenario.PotionSlot);
        configuredPotion.ApplyInternal(scenario.HopperCreature, potionAmount, silent: true);
        configuredPotion.RecordTheft();

        var configuredCard = (ThingsQuirkPower)ModelDb.Power<ThingsQuirkPower>().ToMutable();
        int cardAmount = configuredCard.ConfigureCardState(scenario.Player, deckCard, firePotion);
        configuredCard.ApplyInternal(scenario.HopperCreature, cardAmount, silent: true);
        configuredCard.RecordTheft();

        if (!rehydrate)
        {
            return new LootStates(configuredPotion, configuredCard);
        }

        configuredPotion.RemoveInternal();
        configuredCard.RemoveInternal();

        // Recreate each power from only its model id and Amount. This matches the
        // full-combat snapshot/checksum representation and proves the opaque payload
        // is sufficient after save/rejoin rather than relying on live references.
        var potionState = (ThingsQuirkPower)ModelDb.Power<ThingsQuirkPower>().ToMutable();
        var cardState = (ThingsQuirkPower)ModelDb.Power<ThingsQuirkPower>().ToMutable();
        potionState.ApplyInternal(scenario.HopperCreature, potionAmount, silent: true);
        cardState.ApplyInternal(scenario.HopperCreature, cardAmount, silent: true);
        return new LootStates(potionState, cardState);
    }

    private static CardModel SelectCardToSteal(QuirkyHopper hopper, Player player)
    {
        MethodInfo method = typeof(QuirkyHopper).GetMethod(
            "SelectCardToSteal",
            BindingFlags.Instance | BindingFlags.NonPublic)!;
        return (CardModel)method.Invoke(hopper, [player])!;
    }

    private static void AssertHoverPayload(ThingsQuirkPower cardState)
    {
        MethodInfo resolveCard = typeof(ThingsQuirkPower).GetMethod(
            "ResolveStolenDeckCard",
            BindingFlags.Instance | BindingFlags.NonPublic)!;
        MethodInfo findPotionState = typeof(ThingsQuirkPower).GetMethod(
            "FindPotionStateForSamePlayer",
            BindingFlags.Instance | BindingFlags.NonPublic)!;
        MethodInfo resolvePotion = typeof(ThingsQuirkPower).GetMethod(
            "ResolveStolenPotion",
            BindingFlags.Instance | BindingFlags.NonPublic)!;
        object? card = resolveCard.Invoke(cardState, null);
        object? potionState = findPotionState.Invoke(cardState, null);
        object? potion = potionState == null ? null : resolvePotion.Invoke(potionState, null);
        Assert(card is CardModel && potion is PotionModel, "Quirk hover payload does not contain one card and one potion.");
    }

    private static bool IsVisibleInternal(ThingsQuirkPower power)
    {
        PropertyInfo property = typeof(ThingsQuirkPower).GetProperty(
            "IsVisibleInternal",
            BindingFlags.Instance | BindingFlags.NonPublic)!;
        return (bool)property.GetValue(power)!;
    }

    private static MegaCrit.Sts2.Core.Runs.PlayerMapPointHistoryEntry History(Scenario scenario)
    {
        return scenario.RunState.CurrentMapPointHistoryEntry!.GetEntry(scenario.Player.NetId);
    }

    private static void Assert(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }

    private sealed record Scenario(
        Player Player,
        RunState RunState,
        CombatRoom Room,
        QuirkyHopper Hopper,
        Creature HopperCreature,
        PotionModel? FirePotion,
        int PotionSlot,
        CardModel? CurseCard);

    private sealed record LootStates(ThingsQuirkPower PotionState, ThingsQuirkPower CardState);
}
