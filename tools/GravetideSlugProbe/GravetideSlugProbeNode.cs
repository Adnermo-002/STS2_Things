using System.Collections;
using System.Reflection;
using System.Runtime.Loader;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.Entities.Encounters;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves.Runs;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using MegaCrit.Sts2.Core.ValueProps;

public partial class GravetideSlugProbeNode : Node
{
    private const string BossTypeName = "STS2_Things.Monsters.GravetideSlug";
    private const string SlugBaseTypeName = "STS2_Things.Monsters.GravetideSlugBase";
    private const string SlugTypeName = "STS2_Things.Monsters.GravetideCorpseSlug";
    private const string CorpseTypeName = "STS2_Things.Monsters.GravetideSlugCorpse";
    private const string DigestionTypeName = "STS2_Things.Powers.GravetideDigestionPower";
    private const string MinionTypeName = "STS2_Things.Powers.GravetideMinionPower";
    private const string EncounterTypeName = "STS2_Things.Encounters.GravetideSlugBossEncounter";

    private static readonly Assembly ImplementationAssembly = typeof(STS2_ThingsInit).Assembly;

    public override async void _Ready()
    {
        try
        {
            TestMode.TurnOnInternal();
            InitializeModelDb();
            VerifyModelCategories();
            VerifyDevourAnimationContract();
            VerifyEncounterContract();
            VerifyFixedSeedReproducibility();
            VerifyCloneAndSerializationContract();
            await VerifyAttendantHpContract();
            await VerifyAttendantPowerContract();
            await VerifyRavenousPowerContract();
            await VerifySummonMoveContract();
            await VerifyGoopCorpseDigestionDeferral();
            await VerifyCorpseNativeHpScaling();
            await VerifyDeathReplacement();
            await VerifyPreventedDeathDoesNotCreateCorpse();
            await VerifyDigestionContract();
            await VerifyBossDeathDoesNotLeaveCorpseCombat();
            GD.Print("Gravetide Slug behavior probe: PASS");
            GetTree().Quit(0);
        }
        catch (Exception exception)
        {
            GD.PushError(exception.ToString());
            GetTree().Quit(1);
        }
        finally
        {
            DeactivateSyntheticCombat();
        }
    }

    private static void InitializeModelDb()
    {
        AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency;
        EnsureRuntimeDependency("System.IO.Hashing");

        Type[] modTypes = ImplementationAssembly.GetTypes();
        Type[] modelTypes = AbstractModelSubtypes.All
            .Concat(modTypes.Where(type =>
                !type.IsAbstract && typeof(AbstractModel).IsAssignableFrom(type)))
            .Distinct()
            .ToArray();
        typeof(ReflectionHelper).GetField(
                "_modTypes", BindingFlags.NonPublic | BindingFlags.Static)!
            .SetValue(null, modTypes);
        RegisterSyntheticMod(ImplementationAssembly);

        PropertyInfo? managerState = typeof(ModManager).GetProperty(
            "State", BindingFlags.Public | BindingFlags.Static);
        if (managerState != null)
        {
            managerState.SetValue(null, Enum.Parse(managerState.PropertyType, "Initialized"));
        }

        Type? assemblyInfo = typeof(ModelDb).Assembly.GetType(
            "MegaCrit.Sts2.Core.Modding.AssemblyInfo");
        assemblyInfo?.GetMethod("Init", BindingFlags.Public | BindingFlags.Static)?
            .Invoke(null, null);
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

        // The normal loader calls STS2_ThingsInit before ModelDb setup. The
        // isolated probe intentionally builds its own model database, so apply
        // the narrowly scoped Ravenous adapter here as well.
        new Harmony("STS2_Things.GravetideSlugProbe").PatchAll(ImplementationAssembly);
    }

    private static void RegisterSyntheticMod(Assembly implementationAssembly)
    {
        Assembly gameAssembly = typeof(ModManager).Assembly;
        Type modType = gameAssembly.GetType(
            "MegaCrit.Sts2.Core.Modding.Mod", throwOnError: true)!;
        Type manifestType = gameAssembly.GetType(
            "MegaCrit.Sts2.Core.Modding.ModManifest", throwOnError: true)!;
        object mod = Activator.CreateInstance(modType)!;
        object manifest = Activator.CreateInstance(manifestType)!;
        manifestType.GetField("id")!.SetValue(manifest, "STS2_Things");
        manifestType.GetField("name")?.SetValue(manifest, "STS2_Things Gravetide Probe");
        manifestType.GetField("affectsGameplay")?.SetValue(manifest, true);
        modType.GetField("path")!.SetValue(mod, "probe://STS2_Things");
        modType.GetField("manifest")!.SetValue(mod, manifest);
        FieldInfo stateField = modType.GetField("state")!;
        stateField.SetValue(mod, Enum.Parse(stateField.FieldType, "Loaded"));

        if (modType.GetField("assemblies")?.GetValue(mod) is IList assemblies)
        {
            assemblies.Add(implementationAssembly);
        }
        else
        {
            modType.GetField("assembly")!.SetValue(mod, implementationAssembly);
        }

        IList mods = (IList)typeof(ModManager)
            .GetField("_mods", BindingFlags.NonPublic | BindingFlags.Static)!
            .GetValue(null)!;
        mods.Clear();
        mods.Add(mod);
    }

    private static void VerifyModelCategories()
    {
        RequireModelType<MonsterModel>(BossTypeName);
        RequireModelType<MonsterModel>(SlugTypeName);
        RequireModelType<MonsterModel>(CorpseTypeName);
        RequireModelType<PowerModel>(DigestionTypeName);
        RequireModelType<PowerModel>(MinionTypeName);
        RequireModelType<EncounterModel>(EncounterTypeName);
    }

    private static void VerifyDevourAnimationContract()
    {
        Type slugBaseType = RequireType(SlugBaseTypeName);
        Type digestionType = RequireType(DigestionTypeName);

        Assert(ReadConstant<string>(slugBaseType, "DevourStartTrigger") ==
               CorpseSlug.devourStartTrigger,
            "Gravetide Slug does not use the native Corpse Slug devour-start trigger.");
        Assert(ReadConstant<string>(slugBaseType, "DevourEndTrigger") ==
               CorpseSlug.devourEndTrigger,
            "Gravetide Slug does not use the native Corpse Slug devour-end trigger.");
        Assert(ReadConstant<float>(digestionType, "DevourDownDuration") == 0.5f &&
               ReadConstant<float>(digestionType, "DevourUpDuration") == 0.5f,
            "Gravetide digestion no longer matches the native 0.5-second down/up timing.");

        PropertyInfo? isDevouring = slugBaseType.GetProperty(
            "IsDevouring", BindingFlags.Instance | BindingFlags.NonPublic);
        Assert(isDevouring?.PropertyType == typeof(bool) && isDevouring.CanWrite,
            "Gravetide Slug is missing its mutable devour animation state.");
    }

    private static void VerifyEncounterContract()
    {
        EncounterModel canonical = CanonicalEncounter();
        Assert(canonical.RoomType == RoomType.Boss,
            "Gravetide encounter is not a boss room.");

        string[] slots = canonical.Slots.ToArray();
        Assert(slots.Length == 7,
            $"Expected one boss slot plus six slug slots, found {slots.Length} slots.");
        Assert(slots.Distinct(StringComparer.Ordinal).Count() == slots.Length,
            "Gravetide encounter contains duplicate slot names.");

        Type[] possibleTypes = canonical.AllPossibleMonsters
            .Select(monster => monster.GetType())
            .ToArray();
        foreach (string typeName in new[]
                 {
                     BossTypeName, SlugTypeName, CorpseTypeName,
                 })
        {
            Type expectedType = RequireType(typeName);
            Assert(possibleTypes.Contains(expectedType),
                $"AllPossibleMonsters omits {expectedType.Name}.");
        }

        Type bossType = RequireType(BossTypeName);
        Type slugType = RequireType(SlugTypeName);
        string? expectedSignature = null;
        for (int playerCount = 1; playerCount <= 4; playerCount++)
        {
            RunState runState = CreateRun(
                playerCount, "GRAVETIDE_ENCOUNTER_LAYOUT");
            EncounterModel encounter = canonical.ToMutable();
            encounter.GenerateMonstersWithSlots(runState);
            var opening = encounter.MonstersWithSlots.ToArray();

            Assert(opening.Length == 3,
                $"Opening wave contains {opening.Length} monsters instead of one boss and two slugs.");
            Assert(opening.Count(entry => entry.Item1.GetType() == bossType) == 1,
                "Opening wave does not contain exactly one Gravetide Slug.");
            Assert(opening.Count(entry => entry.Item1.GetType() == slugType) == 2,
                "Opening wave does not contain exactly two half-health Corpse Slugs.");
            Assert(opening.All(entry => entry.Item2 != null && slots.Contains(entry.Item2)),
                "Opening wave uses a slot outside EncounterModel.Slots.");
            Assert(opening.Select(entry => entry.Item2).Distinct(StringComparer.Ordinal).Count() == 3,
                "Opening wave places multiple monsters in the same slot.");

            string bossSlot = opening.Single(entry => entry.Item1.GetType() == bossType).Item2!;
            string[] slugSlots = slots.Where(slot => slot != bossSlot).ToArray();
            Assert(slugSlots.Length == 6,
                "The boss slot does not leave exactly six Corpse Slug slots.");
            string[] openingSlugSlots = opening
                .Where(entry => entry.Item1.GetType() == slugType)
                .Select(entry => entry.Item2!)
                .ToArray();
            Assert(openingSlugSlots.SequenceEqual(
                    new[] { slugSlots[0], slugSlots[5] },
                    StringComparer.Ordinal),
                "Opening attendants are not in the intended left/right slots 1 and 6.");

            int[] starterMoves = opening
                .Where(entry => entry.Item1.GetType() == slugType)
                .Select(entry => (int)(entry.Item1.GetType()
                    .GetProperty("StarterMoveIndex")!.GetValue(entry.Item1)
                    ?? throw new InvalidOperationException("StarterMoveIndex was null.")))
                .ToArray();
            Assert(starterMoves.Distinct().Count() == 2 &&
                   starterMoves.All(index => index is >= 0 and <= 2),
                "Opening attendants do not start on two distinct native moves.");

            string signature = string.Join("|", opening.Select(entry =>
                $"{entry.Item1.GetType().Name}:{entry.Item2}:" +
                $"{(entry.Item1.GetType() == slugType ? entry.Item1.GetType().GetProperty("StarterMoveIndex")!.GetValue(entry.Item1) : "boss")}"));
            expectedSignature ??= signature;
            Assert(string.Equals(signature, expectedSignature, StringComparison.Ordinal),
                "Encounter generation changed with player count and would desynchronize peers.");
        }
    }

    private static async Task VerifyAttendantHpContract()
    {
        MonsterModel attendant = CanonicalMonster(SlugTypeName);
        Assert(attendant.MinInitialHp == 7 && attendant.MaxInitialHp == 12,
            $"Gravetide attendant range is {attendant.MinInitialHp}-{attendant.MaxInitialHp}; " +
            "expected 7-12 at every difficulty.");

        for (int playerCount = 1; playerCount <= 4; playerCount++)
        {
            Scenario scenario = CreateScenario(playerCount, $"GRAVETIDE_ATTENDANT_HP_{playerCount}");
            Creature attendantCreature = AddMonster(
                scenario, SlugTypeName, "corpse_slug_slot_1");
            await attendantCreature.AfterAddedToRoom();
            int expectedMin = (int)Creature.ScaleHpForMultiplayer(
                7m,
                scenario.Room.CombatState.Encounter,
                playerCount,
                scenario.RunState.CurrentActIndex);
            int expectedMax = (int)Creature.ScaleHpForMultiplayer(
                12m,
                scenario.Room.CombatState.Encounter,
                playerCount,
                scenario.RunState.CurrentActIndex);
            Assert(attendantCreature.CurrentHp >= expectedMin &&
                   attendantCreature.CurrentHp <= expectedMax &&
                   attendantCreature.MaxHp == attendantCreature.CurrentHp,
                $"{playerCount}-player Gravetide attendant spawned at " +
                $"{attendantCreature.CurrentHp}/{attendantCreature.MaxHp}; expected " +
                $"the scaled 7-12 range {expectedMin}-{expectedMax}.");
        }
    }

    private static void VerifyFixedSeedReproducibility()
    {
        Type slugType = RequireType(SlugTypeName);
        string? expectedSignature = null;
        for (int playerCount = 1; playerCount <= 4; playerCount++)
        {
            for (int replay = 0; replay < 8; replay++)
            {
                RunState runState = CreateRun(
                    playerCount, "GRAVETIDE_FIXED_SEED_REPLAY");
                EncounterModel encounter = CanonicalEncounter().ToMutable();
                encounter.GenerateMonstersWithSlots(runState);
                string signature = string.Join("|", encounter.MonstersWithSlots.Select(entry =>
                {
                    object move = entry.Item1.GetType() == slugType
                        ? entry.Item1.GetType().GetProperty("StarterMoveIndex")!
                            .GetValue(entry.Item1)
                            ?? throw new InvalidOperationException(
                                "StarterMoveIndex was null during replay verification.")
                        : "boss";
                    return $"{entry.Item1.Id.Entry}:{entry.Item2}:{move}";
                }));
                expectedSignature ??= signature;
                Assert(string.Equals(signature, expectedSignature, StringComparison.Ordinal),
                    $"Fixed-seed opening drifted for {playerCount} players replay {replay}: " +
                    $"{signature} != {expectedSignature}.");
            }
        }
    }

    private static void VerifyCloneAndSerializationContract()
    {
        Type slugBaseType = RequireType(SlugBaseTypeName);
        Type slugType = RequireType(SlugTypeName);
        Type corpseType = RequireType(CorpseTypeName);
        var source = (MonsterModel)CanonicalMonster(SlugTypeName).ToMutable();
        PropertyInfo starterMove = slugType.GetProperty("StarterMoveIndex")
            ?? throw new MissingMemberException(slugType.FullName, "StarterMoveIndex");
        PropertyInfo isDevouring = slugBaseType.GetProperty(
                "IsDevouring", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingMemberException(slugBaseType.FullName, "IsDevouring");
        starterMove.SetValue(source, 2);
        isDevouring.SetValue(source, true);

        var clone = (MonsterModel)source.MutableClone();
        Assert(!ReferenceEquals(source, clone),
            "Mutable Gravetide attendant clone reused the source instance.");
        Assert((int)(starterMove.GetValue(clone) ?? -1) == 2 &&
               (bool)(isDevouring.GetValue(clone) ?? false),
            "Mutable Gravetide attendant clone lost its deterministic move or visual state.");
        starterMove.SetValue(source, 1);
        isDevouring.SetValue(source, false);
        Assert((int)(starterMove.GetValue(clone) ?? -1) == 2 &&
               (bool)(isDevouring.GetValue(clone) ?? false),
            "Mutable Gravetide attendant clone aliases source state.");

        PropertyInfo digestionDelay = corpseType.GetProperty(
                "DelayDigestionUntilNextEnemyTurn")
            ?? throw new MissingMemberException(
                corpseType.FullName, "DelayDigestionUntilNextEnemyTurn");
        Assert(digestionDelay.PropertyType == typeof(bool) &&
               digestionDelay.GetCustomAttribute<SavedPropertyAttribute>() != null,
            "Gravetide Goop corpse deferral is not a saved bool state.");
        var delayedCorpse = (MonsterModel)CanonicalMonster(CorpseTypeName).ToMutable();
        digestionDelay.SetValue(delayedCorpse, true);
        var delayedCorpseClone = (MonsterModel)delayedCorpse.MutableClone();
        Assert((bool)(digestionDelay.GetValue(delayedCorpseClone) ?? false),
            "Mutable Gravetide corpse clone lost its digestion deferral state.");

        Type serializationCache = typeof(ModelDb).Assembly.GetType(
            "MegaCrit.Sts2.Core.Multiplayer.Serialization.ModelIdSerializationCache",
            throwOnError: true)!;
        uint hash = (uint)(serializationCache.GetProperty(
                "Hash", BindingFlags.Public | BindingFlags.Static)!
            .GetValue(null)
            ?? 0u);
        Assert(hash != 0u, "Model ID serialization cache did not produce a gameplay hash.");
        string dump = (string)(serializationCache.GetMethod(
                "Dump", BindingFlags.Public | BindingFlags.Static)!
            .Invoke(null, null)
            ?? string.Empty);
        foreach (string typeName in new[]
                 {
                     BossTypeName, SlugTypeName, CorpseTypeName,
                     DigestionTypeName, MinionTypeName, EncounterTypeName,
                 })
        {
            AbstractModel model = CanonicalModel(RequireType(typeName));
            Assert(dump.IndexOf(model.Id.Entry, StringComparison.Ordinal) >= 0,
                $"Model ID cache omits Gravetide entry {model.Id.Entry}.");
        }
    }

    private static async Task VerifyAttendantPowerContract()
    {
        Scenario scenario = CreateScenario(1, "GRAVETIDE_ATTENDANT_POWER");
        Creature slug = AddMonster(scenario, SlugTypeName, "corpse_slug_slot_1");
        await slug.AfterAddedToRoom();
        RavenousPower ravenous = slug.Powers.OfType<RavenousPower>().SingleOrDefault()
            ?? throw new InvalidOperationException(
                "A half-health Gravetide Corpse Slug did not receive native Ravenous.");
        int expectedRavenousStrength = AscensionHelper.GetValueIfAscension(
            AscensionLevel.DeadlyEnemies, 5, 4);
        Assert(ravenous.Amount == expectedRavenousStrength,
            $"Gravetide Ravenous has {ravenous.Amount} Strength; " +
            $"expected native {expectedRavenousStrength}.");
        Assert(slug.IsSecondaryEnemy,
            "A Gravetide Corpse Slug is not marked as a secondary attendant.");
        PowerModel marker = slug.Powers.SingleOrDefault(
                power => power.GetType() == RequireType(MinionTypeName))
            ?? throw new InvalidOperationException(
                "A Gravetide Corpse Slug did not receive its minion marker.");
        Assert(!marker.ShouldPowerBeRemovedAfterOwnerDeath(),
            "The Gravetide minion marker is removed during native death cleanup.");
        Assert(!marker.ShouldOwnerDeathTriggerFatal(),
            "The Gravetide minion marker allows Fatal rewards.");
    }

    private static async Task VerifyRavenousPowerContract()
    {
        Scenario scenario = CreateScenario(1, "GRAVETIDE_RAVENOUS");
        Creature boss = AddMonster(scenario, BossTypeName, "gravetide_boss");
        Creature survivor = AddMonster(scenario, SlugTypeName, "corpse_slug_slot_1");
        Creature victim = AddMonster(scenario, SlugTypeName, "corpse_slug_slot_6");

        ActivateSyntheticCombat(scenario.Room.CombatState);
        try
        {
            await boss.AfterAddedToRoom();
            await survivor.AfterAddedToRoom();
            await victim.AfterAddedToRoom();
            RavenousPower ravenous = survivor.Powers.OfType<RavenousPower>().Single();
            int strengthBefore = GetStrength(survivor);

            await CreatureCmd.Kill(victim);

            Assert(GetStrength(survivor) == strengthBefore + ravenous.Amount,
                "Native Ravenous did not grant its full Strength amount to a Gravetide attendant.");
            Assert(survivor.IsStunned,
                "Native Ravenous did not retain its stunned recovery turn on a Gravetide attendant.");
            Assert(GetIsDevouring(survivor),
                "Native Ravenous did not enter the Gravetide devour animation state.");
        }
        finally
        {
            DeactivateSyntheticCombat();
        }
    }

    private static async Task VerifySummonMoveContract()
    {
        Type slugType = RequireType(SlugTypeName);
        Type corpseType = RequireType(CorpseTypeName);
        for (int playerCount = 1; playerCount <= 4; playerCount++)
        {
            Scenario scenario = CreateScenario(
                playerCount, $"GRAVETIDE_SUMMON_{playerCount}");
            string[] slugSlots = Enumerable.Range(0, 6)
                .Select(STS2_Things.Encounters.GravetideSlugBossEncounter.GetCorpseSlugSlotName)
                .ToArray();
            Creature boss = AddMonster(scenario, BossTypeName, "gravetide_boss");
            Creature openingLeft = AddMonster(scenario, SlugTypeName, slugSlots[0]);
            Creature openingRight = AddMonster(scenario, SlugTypeName, slugSlots[5]);

            ActivateSyntheticCombat(scenario.Room.CombatState);
            try
            {
                await boss.AfterAddedToRoom();
                await openingLeft.AfterAddedToRoom();
                await openingRight.AfterAddedToRoom();

                Assert(RollBossMove(boss).Id == "WHIP_SLAP_MOVE",
                    "Gravetide boss no longer starts with Whip Slap.");
                MarkBossMovePerformed(boss);
                Assert(RollBossMove(boss).Id == "GLOMP_MOVE",
                    "Gravetide boss did not advance from Whip Slap to Glomp.");
                MarkBossMovePerformed(boss);
                MoveState goop = RollBossMove(boss);
                Assert(goop.Id == "GOOP_MOVE",
                    "Gravetide boss did not advance from Glomp to Goop.");
                await goop.PerformMove(scenario.Room.CombatState.PlayerCreatures);
                MarkBossMovePerformed(boss);

                Assert(scenario.Room.CombatState.PlayerCreatures.All(player =>
                        player.Powers.OfType<FrailPower>().Any(power => power.Amount == 2)),
                    "Gravetide Goop no longer applies its native Frail effect.");
                Creature[] goopCorpses = scenario.Room.CombatState.Enemies
                    .Where(creature => creature.Monster?.GetType() == corpseType)
                    .OrderBy(creature => creature.SlotName ?? string.Empty, StringComparer.Ordinal)
                    .ToArray();
                Assert(goopCorpses.Length == 1 && goopCorpses[0].SlotName == slugSlots[1],
                    "Gravetide Goop did not create one corpse in the first vacant slug slot.");

                var summon = RollBossMove(boss);
                Assert(summon.Id == "SUMMON_CORPSE_SLUGS_MOVE",
                    "Gravetide boss did not expose its two-slug summon move while slots were vacant.");
                await summon.PerformMove(scenario.Room.CombatState.PlayerCreatures);
                MarkBossMovePerformed(boss);

                Creature[] summoned = scenario.Room.CombatState.Enemies
                    .Where(creature => creature.Monster?.GetType() == slugType)
                    .Where(creature => creature != openingLeft && creature != openingRight)
                    .OrderBy(creature => creature.SlotName ?? string.Empty, StringComparer.Ordinal)
                    .ToArray();
                Assert(summoned.Length == 2,
                    $"{playerCount}-player summon created {summoned.Length} slugs instead of two.");
                Assert(summoned.Select(creature => creature.SlotName ?? string.Empty).SequenceEqual(
                        new[] { slugSlots[2], slugSlots[3] }, StringComparer.Ordinal),
                    "Gravetide summon did not fill the first two vacant slots deterministically.");
                Assert(summoned.All(creature => creature.Powers.OfType<RavenousPower>().Any()),
                    "A summoned Gravetide Corpse Slug did not restore native Ravenous.");

                Creature[] growingSlugs = scenario.Room.CombatState.Enemies
                    .Where(creature => creature.IsAlive && creature.Monster?.GetType() == slugType)
                    .OrderBy(creature => creature.SlotName ?? string.Empty, StringComparer.Ordinal)
                    .ToArray();
                int bossStrengthBeforeGrowth = GetStrength(boss);
                int[] slugStrengthBeforeGrowth = growingSlugs
                    .Select(GetStrength)
                    .ToArray();
                decimal expectedGrowthBlock = boss.Block + Hook.ModifyBlock(
                    scenario.Room.CombatState, boss, 10m, ValueProp.Move, null, null, out _);

                MoveState growth = RollBossMove(boss);
                Assert(growth.Id == "GROW_MOVE",
                    "Gravetide boss did not follow a successful summon with Growth.");
                await growth.PerformMove(scenario.Room.CombatState.PlayerCreatures);
                MarkBossMovePerformed(boss);

                Assert(GetStrength(boss) == bossStrengthBeforeGrowth + 1,
                    "Gravetide Growth did not grant the boss one Strength.");
                Assert(boss.Block == expectedGrowthBlock,
                    $"Gravetide Growth left the boss at {boss.Block} Block; " +
                    $"expected its multiplayer-scaled 10-point move block ({expectedGrowthBlock}).");
                for (int index = 0; index < growingSlugs.Length; index++)
                {
                    Assert(GetStrength(growingSlugs[index]) == slugStrengthBeforeGrowth[index] + 1,
                        "Gravetide Growth did not grant every living Corpse Slug one Strength.");
                }

                foreach (string slot in slugSlots)
                {
                    if (!scenario.Room.CombatState.Enemies.Any(creature =>
                            string.Equals(creature.SlotName, slot, StringComparison.Ordinal)))
                    {
                        _ = AddMonster(scenario, SlugTypeName, slot);
                    }
                }
                Assert(scenario.Room.CombatState.Enemies.Count(creature =>
                        creature.SlotName is { } slot &&
                        slugSlots.Contains(slot, StringComparer.Ordinal)) == 6,
                    "The summon-full test did not occupy all six dedicated slug slots.");

                Assert(RollBossMove(boss).Id == "WHIP_SLAP_MOVE",
                    "Gravetide boss did not resume Whip Slap after Growth.");
                MarkBossMovePerformed(boss);
                Assert(RollBossMove(boss).Id == "GLOMP_MOVE",
                    "Gravetide boss did not preserve its normal cycle after Growth.");
                MarkBossMovePerformed(boss);
                MoveState fullGoop = RollBossMove(boss);
                Assert(fullGoop.Id == "GOOP_MOVE",
                    "Gravetide boss did not preserve Goop before its next summon branch.");
                int bossStrengthBeforeFullBranch = GetStrength(boss);
                decimal bossBlockBeforeFullBranch = boss.Block;
                await fullGoop.PerformMove(scenario.Room.CombatState.PlayerCreatures);
                MarkBossMovePerformed(boss);
                Assert(RollBossMove(boss).Id == "WHIP_SLAP_MOVE",
                    "Gravetide boss exposed an empty summon turn with all slug slots occupied.");
                Assert(GetStrength(boss) == bossStrengthBeforeFullBranch &&
                       boss.Block == bossBlockBeforeFullBranch,
                    "A full slug board still triggered Gravetide Growth without a summon.");
            }
            finally
            {
                DeactivateSyntheticCombat();
            }
        }
    }

    private static MoveState RollBossMove(Creature boss)
    {
        MonsterModel monster = boss.Monster
            ?? throw new InvalidOperationException("Gravetide boss creature has no monster model.");
        monster.RollMove(boss.CombatState?.PlayerCreatures
            ?? throw new InvalidOperationException("Gravetide boss has no combat state."));
        return monster.NextMove;
    }

    private static void MarkBossMovePerformed(Creature boss)
    {
        MonsterModel monster = boss.Monster
            ?? throw new InvalidOperationException("Gravetide boss creature has no monster model.");
        (monster.MoveStateMachine
            ?? throw new InvalidOperationException("Gravetide boss has no move state machine."))
            .OnMovePerformed(monster.NextMove);
    }

    private static bool GetIsDevouring(Creature creature)
    {
        Type slugBaseType = RequireType(SlugBaseTypeName);
        PropertyInfo state = slugBaseType.GetProperty(
                "IsDevouring", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingMemberException(slugBaseType.FullName, "IsDevouring");
        return (bool)(state.GetValue(creature.Monster)
            ?? throw new InvalidOperationException("Gravetide devour state was null."));
    }

    private static async Task VerifyGoopCorpseDigestionDeferral()
    {
        Type corpseType = RequireType(CorpseTypeName);
        for (int playerCount = 1; playerCount <= 4; playerCount++)
        {
            Scenario scenario = CreateScenario(
                playerCount, $"GRAVETIDE_GOOP_DEFERRAL_{playerCount}");
            Creature boss = AddMonster(scenario, BossTypeName, "gravetide_boss");

            ActivateSyntheticCombat(scenario.Room.CombatState);
            try
            {
                await boss.AfterAddedToRoom();

                Assert(RollBossMove(boss).Id == "WHIP_SLAP_MOVE",
                    "Gravetide boss no longer starts with Whip Slap.");
                MarkBossMovePerformed(boss);
                Assert(RollBossMove(boss).Id == "GLOMP_MOVE",
                    "Gravetide boss did not advance from Whip Slap to Glomp.");
                MarkBossMovePerformed(boss);
                MoveState goop = RollBossMove(boss);
                Assert(goop.Id == "GOOP_MOVE",
                    "Gravetide boss did not expose Goop before corpse deferral verification.");
                await goop.PerformMove(scenario.Room.CombatState.PlayerCreatures);
                MarkBossMovePerformed(boss);

                Creature freshCorpse = scenario.Room.CombatState.Enemies
                    .Single(creature => creature.Monster?.GetType() == corpseType);
                Assert(GetCorpseDigestionDelay(freshCorpse),
                    "A corpse created by Gravetide Goop was not marked for one-turn deferral.");
                int strengthBefore = GetStrength(boss);

                await DispatchAfterSideTurnEndHook(
                    scenario.Room.CombatState,
                    CombatSide.Enemy,
                    scenario.Room.CombatState.Enemies.ToArray());
                Assert(scenario.Room.CombatState.ContainsCreature(freshCorpse),
                    "Gravetide consumed its Goop corpse during the same enemy turn.");
                Assert(!GetCorpseDigestionDelay(freshCorpse),
                    "The Goop corpse did not become eligible after its spawning enemy turn.");
                Assert(GetStrength(boss) == strengthBefore,
                    "Same-turn Goop corpse digestion still granted Strength.");

                await DispatchAfterSideTurnEndHook(
                    scenario.Room.CombatState,
                    CombatSide.Enemy,
                    scenario.Room.CombatState.Enemies.ToArray());
                Assert(!scenario.Room.CombatState.ContainsCreature(freshCorpse),
                    "Gravetide did not consume its Goop corpse on the following enemy turn.");
                Assert(GetStrength(boss) == strengthBefore + 1,
                    "Following-turn Goop corpse digestion did not grant Strength.");
            }
            finally
            {
                DeactivateSyntheticCombat();
            }
        }
    }

    private static bool GetCorpseDigestionDelay(Creature corpse)
    {
        Type corpseType = RequireType(CorpseTypeName);
        PropertyInfo property = corpseType.GetProperty(
                "DelayDigestionUntilNextEnemyTurn")
            ?? throw new MissingMemberException(
                corpseType.FullName, "DelayDigestionUntilNextEnemyTurn");
        return (bool)(property.GetValue(corpse.Monster)
            ?? throw new InvalidOperationException(
                "Gravetide corpse digestion deferral state was null."));
    }

    private static async Task VerifyCorpseNativeHpScaling()
    {
        for (int playerCount = 1; playerCount <= 4; playerCount++)
        {
            Scenario scenario = CreateScenario(
                playerCount, $"GRAVETIDE_CORPSE_HP_{playerCount}");
            Creature corpse = AddMonster(scenario, CorpseTypeName, "corpse_hp_slot");
            await corpse.AfterAddedToRoom();
            int expectedHp = (int)Creature.ScaleHpForMultiplayer(
                6m,
                scenario.Room.CombatState.Encounter,
                playerCount,
                scenario.RunState.CurrentActIndex);
            Assert(corpse.MaxHp == expectedHp && corpse.CurrentHp == expectedHp,
                $"{playerCount}-player corpse HP is {corpse.CurrentHp}/{corpse.MaxHp}; " +
                $"expected native monster scaling {expectedHp}/{expectedHp}.");
        }
    }

    private static async Task VerifyDeathReplacement()
    {
        for (int playerCount = 1; playerCount <= 4; playerCount++)
        {
            Scenario scenario = CreateScenario(
                playerCount, $"GRAVETIDE_DEATH_REPLACEMENT_{playerCount}");
            Creature boss = AddMonster(scenario, BossTypeName, "gravetide_boss");
            Creature slug = AddMonster(scenario, SlugTypeName, "corpse_slug_slot_4");

            ActivateSyntheticCombat(scenario.Room.CombatState);
            try
            {
                await boss.AfterAddedToRoom();
                await slug.AfterAddedToRoom();
                await CreatureCmd.Kill(slug);

                Creature[] replacements = scenario.Room.CombatState.Enemies
                    .Where(creature => creature.Monster?.GetType() == RequireType(CorpseTypeName))
                    .ToArray();
                Assert(replacements.Length == 1,
                    $"A dead Gravetide Corpse Slug produced {replacements.Length} corpses.");
                Assert(replacements[0].SlotName == slug.SlotName,
                    "The spawned corpse did not preserve the dead slug's slot.");
                int expectedHp = (int)Creature.ScaleHpForMultiplayer(
                    6m,
                    scenario.Room.CombatState.Encounter,
                    playerCount,
                    scenario.RunState.CurrentActIndex);
                Assert(replacements[0].CurrentHp == expectedHp &&
                       replacements[0].MaxHp == expectedHp,
                    $"{playerCount}-player death replacement was " +
                    $"{replacements[0].CurrentHp}/{replacements[0].MaxHp}; " +
                    $"expected native scaling {expectedHp}/{expectedHp}.");
                Assert(!scenario.Room.CombatState.ContainsCreature(slug) && slug.IsDead,
                    "CreatureCmd.Kill did not complete the attendant's native death/removal path.");
                Assert(slug.Powers.Any(power =>
                        power.GetType() == RequireType(MinionTypeName)),
                    "Native death cleanup removed the attendant's minion marker.");
                Assert(scenario.Room.CombatState.EscapedCreatures.Count == 0,
                    "Killing an attendant or creating its corpse was recorded as an escape.");
            }
            finally
            {
                DeactivateSyntheticCombat();
            }
        }
    }

    private static async Task VerifyPreventedDeathDoesNotCreateCorpse()
    {
        Scenario scenario = CreateScenario(1, "GRAVETIDE_PREVENTED_DEATH");
        _ = AddMonster(scenario, BossTypeName, "gravetide_boss");
        Creature slug = AddMonster(scenario, SlugTypeName, "corpse_slug_slot_2");

        ActivateSyntheticCombat(scenario.Room.CombatState);
        try
        {
            await slug.Monster!.AfterDeath(
                new BlockingPlayerChoiceContext(), slug,
                wasRemovalPrevented: true, deathAnimLength: 0f);
            Assert(scenario.Room.CombatState.Enemies.All(creature =>
                    creature.Monster?.GetType() != RequireType(CorpseTypeName)),
                "A prevented attendant death created a corpse.");
        }
        finally
        {
            DeactivateSyntheticCombat();
        }
    }

    private static async Task VerifyDigestionContract()
    {
        for (int playerCount = 1; playerCount <= 4; playerCount++)
        {
            Scenario scenario = CreateScenario(
                playerCount, $"GRAVETIDE_DIGESTION_{playerCount}");
            Creature boss = AddMonster(scenario, BossTypeName, "gravetide_boss");
            Creature corpseA = AddMonster(scenario, CorpseTypeName, "corpse_slug_slot_1");
            Creature corpseB = AddMonster(scenario, CorpseTypeName, "corpse_slug_slot_5");
            Creature livingSlug = AddMonster(scenario, SlugTypeName, "corpse_slug_slot_3");

            ActivateSyntheticCombat(scenario.Room.CombatState);
            try
            {
                await boss.AfterAddedToRoom();
                await corpseA.AfterAddedToRoom();
                await corpseB.AfterAddedToRoom();
                await livingSlug.AfterAddedToRoom();
                PowerModel digestion = boss.Powers.SingleOrDefault(
                        power => power.GetType() == RequireType(DigestionTypeName))
                    ?? throw new InvalidOperationException(
                        "Gravetide Slug did not begin combat with Digestion.");

                int expectedHeal = (int)Math.Ceiling(boss.MaxHp * 0.05m);
                Assert(digestion.StackType == PowerStackType.None,
                    "Digestion exposes an amount label instead of a stackless icon.");
                Assert(digestion.Amount == expectedHeal,
                    $"{playerCount}-player Digestion stores {digestion.Amount}; " +
                    $"expected the scaled boss's 5% heal amount {expectedHeal}.");
                int damagedHp = Math.Max(1, boss.MaxHp - expectedHeal - 5);
                boss.SetCurrentHpInternal(damagedHp);

                var choiceContext = new BlockingPlayerChoiceContext();
                await digestion.AfterSideTurnEnd(
                    choiceContext, CombatSide.Player, scenario.Room.CombatState.Allies);
                Assert(boss.CurrentHp == damagedHp,
                    "Digestion healed at the end of the player side turn.");
                Assert(scenario.Room.CombatState.ContainsCreature(corpseA) &&
                       scenario.Room.CombatState.ContainsCreature(corpseB),
                    "Digestion cleared corpses before the enemy side turn ended.");

                await DispatchAfterSideTurnEndHook(
                    scenario.Room.CombatState,
                    CombatSide.Enemy,
                    scenario.Room.CombatState.Enemies.ToArray());
                Assert(!scenario.Room.CombatState.ContainsCreature(corpseA) &&
                       !scenario.Room.CombatState.ContainsCreature(corpseB),
                    "One Digestion trigger did not clear every corpse.");
                Assert(scenario.Room.CombatState.ContainsCreature(livingSlug),
                    "Digestion removed a living Corpse Slug instead of only corpses.");
                Assert(boss.CurrentHp == damagedHp + expectedHeal,
                    $"Digestion healed {boss.CurrentHp - damagedHp}; expected exactly {expectedHeal}.");
                Assert(GetStrength(boss) == 1,
                    $"Digestion granted {GetStrength(boss)} Strength; expected exactly 1.");
                Assert(scenario.Room.CombatState.EscapedCreatures.Count == 0,
                    "Consumed corpses were recorded as escaped enemies and would reduce rewards.");

                int hpAfterFirstTrigger = boss.CurrentHp;
                await DispatchAfterSideTurnEndHook(
                    scenario.Room.CombatState,
                    CombatSide.Enemy,
                    scenario.Room.CombatState.Enemies.ToArray());
                Assert(boss.CurrentHp == hpAfterFirstTrigger && GetStrength(boss) == 1,
                    "Digestion triggered again with no corpse present.");
            }
            finally
            {
                DeactivateSyntheticCombat();
            }
        }
    }

    private static async Task VerifyBossDeathDoesNotLeaveCorpseCombat()
    {
        for (int playerCount = 1; playerCount <= 4; playerCount++)
        {
            Scenario scenario = CreateScenario(
                playerCount, $"GRAVETIDE_BOSS_DEATH_{playerCount}");
            Creature boss = AddMonster(scenario, BossTypeName, "gravetide_boss");
            Creature slugA = AddMonster(scenario, SlugTypeName, "corpse_slug_slot_1");
            Creature slugB = AddMonster(scenario, SlugTypeName, "corpse_slug_slot_3");
            Creature corpseA = AddMonster(scenario, CorpseTypeName, "corpse_slug_slot_4");
            Creature corpseB = AddMonster(scenario, CorpseTypeName, "corpse_slug_slot_6");

            ActivateSyntheticCombat(scenario.Room.CombatState);
            try
            {
                await boss.AfterAddedToRoom();
                foreach (Creature minion in new[] { slugA, slugB, corpseA, corpseB })
                    await minion.AfterAddedToRoom();

                Assert(new[] { slugA, slugB, corpseA, corpseB }
                        .All(creature => creature.IsSecondaryEnemy),
                    "A Gravetide attendant or corpse is primary and would prolong combat.");
                await CreatureCmd.Kill(boss);

                Assert(boss.IsDead,
                    "CreatureCmd.Kill did not kill the Gravetide boss.");
                Assert(scenario.Room.CombatState.Enemies.Count == 0,
                    "Native boss-death cleanup left an attendant or corpse in combat.");
                Assert(new[] { slugA, slugB, corpseA, corpseB }
                        .All(creature => creature.IsDead && creature.CombatState == null),
                    "Native primary/secondary cleanup did not kill and detach every minion.");
                Assert(!scenario.Room.CombatState.Enemies.Any(creature =>
                        creature.Monster?.GetType() == RequireType(CorpseTypeName)),
                    "An attendant created a new corpse while the boss-death chain was running.");
                Assert(CombatManager.Instance.IsEnding,
                    "Combat is not in the native ending state after boss and minion cleanup.");
                Assert(!Hook.ShouldStopCombatFromEnding(scenario.Room.CombatState),
                    "A corpse or Digestion hook still votes to stop combat from ending after boss death.");
                Assert(scenario.Room.CombatState.EscapedCreatures.Count == 0,
                    "Boss-death cleanup recorded a minion as escaped.");

                scenario.Room.OnCombatEnded();
                Assert(Math.Abs(scenario.Room.GoldProportion - 1f) < 0.0001f,
                    $"Boss-death cleanup reduced gold proportion to {scenario.Room.GoldProportion}.");
                Assert(scenario.Room.Encounter.ShouldGiveRewards &&
                       scenario.Room.Encounter.MinGoldReward == 100 &&
                       scenario.Room.Encounter.MaxGoldReward == 100,
                    "The encounter no longer follows the normal boss reward contract.");
                Assert(scenario.Room.ExtraRewards.Count == 0,
                    "Minion cleanup injected duplicate encounter rewards.");
            }
            finally
            {
                DeactivateSyntheticCombat();
            }
        }
    }

    private static int GetStrength(Creature creature)
    {
        return creature.Powers
            .Where(power => power is StrengthPower)
            .Sum(power => power.Amount);
    }

    private static async Task DispatchAfterSideTurnEndHook(
        CombatState combatState,
        CombatSide side,
        IEnumerable<Creature> participants)
    {
        // The public dispatcher was renamed from AfterTurnEnd in v0.107.1 to
        // AfterSideTurnEnd in v0.109.0; the model hook signature stayed stable.
        MethodInfo dispatcher = typeof(Hook).GetMethod(
                "AfterSideTurnEnd", BindingFlags.Public | BindingFlags.Static)
            ?? typeof(Hook).GetMethod(
                "AfterTurnEnd", BindingFlags.Public | BindingFlags.Static)
            ?? throw new MissingMethodException(
                typeof(Hook).FullName, "AfterSideTurnEnd/AfterTurnEnd");
        Task task = (Task)(dispatcher.Invoke(null, [combatState, side, participants])
            ?? throw new InvalidOperationException(
                $"{dispatcher.Name} returned null."));
        await task;
    }

    private static Scenario CreateScenario(int playerCount, string seed)
    {
        RunState runState = CreateRun(playerCount, seed);
        EncounterModel encounter = CanonicalEncounter().ToMutable();
        var room = new CombatRoom(encounter, runState);
        runState.PushRoom(room);
        foreach (Player player in runState.Players)
        {
            player.ResetCombatState();
            room.CombatState.AddPlayer(player);
        }
        return new Scenario(runState, room);
    }

    private static RunState CreateRun(int playerCount, string seed)
    {
        Player[] players = Enumerable.Range(1, playerCount)
            .Select(index => Player.CreateForNewRun<Ironclad>(UnlockState.all, (ulong)index))
            .ToArray();
        return RunState.CreateForTest(players, seed: seed);
    }

    private static Creature AddMonster(Scenario scenario, string typeName, string slot)
    {
        MonsterModel monster = CanonicalMonster(typeName).ToMutable();
        Creature creature = scenario.Room.CombatState.CreateCreature(
            monster, CombatSide.Enemy, slot);
        scenario.Room.CombatState.AddCreature(creature);
        // Mirror CombatManager.AddCreature for the synthetic room so move-state
        // tests and Ravenous's native stun contract use initialized state.
        monster.SetUpForCombat();
        return creature;
    }

    private static void ActivateSyntheticCombat(CombatState state)
    {
        LocalContext.NetId = state.Players[0].NetId;
        CombatManager manager = CombatManager.Instance;
        FieldInfo? legacyStateField = typeof(CombatManager).GetField(
            "_state", BindingFlags.NonPublic | BindingFlags.Instance);
        if (legacyStateField != null)
        {
            legacyStateField.SetValue(manager, state);
            typeof(CombatManager).GetField(
                    "<IsInProgress>k__BackingField",
                    BindingFlags.NonPublic | BindingFlags.Instance)!
                .SetValue(manager, true);
        }
        else
        {
            FieldInfo turnStateField = typeof(CombatManager).GetField(
                    "_turnState", BindingFlags.NonPublic | BindingFlags.Instance)
                ?? throw new MissingFieldException(typeof(CombatManager).FullName, "_turnState");
            object turnState = Activator.CreateInstance(
                    turnStateField.FieldType,
                    BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic,
                    binder: null,
                    args: [state],
                    culture: null)
                ?? throw new InvalidOperationException("Could not create the V111 combat turn state.");
            turnState.GetType().GetProperty("IsInProgress")!.SetValue(turnState, true);
            turnState.GetType().GetProperty("IsStarting")!.SetValue(turnState, false);
            turnStateField.SetValue(manager, turnState);
        }
        state.MultiplayerScalingModel?.OnCombatEntered(state);
        manager.StateTracker.SetState(state);
    }

    private static void DeactivateSyntheticCombat()
    {
        LocalContext.NetId = null;
        CombatManager manager = CombatManager.Instance;
        FieldInfo? legacyStateField = typeof(CombatManager).GetField(
            "_state", BindingFlags.NonPublic | BindingFlags.Instance);
        if (legacyStateField != null)
        {
            typeof(CombatManager).GetField(
                    "<IsInProgress>k__BackingField",
                    BindingFlags.NonPublic | BindingFlags.Instance)?
                .SetValue(manager, false);
            legacyStateField.SetValue(manager, null);
            return;
        }

        FieldInfo turnStateField = typeof(CombatManager).GetField(
                "_turnState", BindingFlags.NonPublic | BindingFlags.Instance)
            ?? throw new MissingFieldException(typeof(CombatManager).FullName, "_turnState");
        object? turnState = turnStateField.GetValue(manager);
        turnState?.GetType().GetMethod("Cancel", BindingFlags.Public | BindingFlags.Instance)?
            .Invoke(turnState, null);
        turnStateField.SetValue(manager, null);
    }

    private static EncounterModel CanonicalEncounter()
    {
        return (EncounterModel)CanonicalModel(RequireType(EncounterTypeName));
    }

    private static MonsterModel CanonicalMonster(string typeName)
    {
        return (MonsterModel)CanonicalModel(RequireType(typeName));
    }

    private static AbstractModel CanonicalModel(Type type)
    {
        string lookupName = typeof(MonsterModel).IsAssignableFrom(type)
            ? "Monster"
            : typeof(PowerModel).IsAssignableFrom(type)
                ? "Power"
                : typeof(EncounterModel).IsAssignableFrom(type)
                    ? "Encounter"
                    : throw new InvalidOperationException(
                        $"No probe ModelDb lookup is defined for {type.FullName}.");
        MethodInfo lookup = typeof(ModelDb)
            .GetMethods(BindingFlags.Public | BindingFlags.Static)
            .Single(method =>
                method.Name == lookupName &&
                method.IsGenericMethodDefinition &&
                method.GetParameters().Length == 0);
        return (AbstractModel)(lookup.MakeGenericMethod(type).Invoke(null, null)
            ?? throw new InvalidOperationException(
                $"ModelDb.{lookupName}<{type.Name}> returned null."));
    }

    private static Type RequireModelType<TBase>(string fullName) where TBase : AbstractModel
    {
        Type type = RequireType(fullName);
        Assert(typeof(TBase).IsAssignableFrom(type),
            $"{type.FullName} does not derive from {typeof(TBase).Name}.");
        _ = CanonicalModel(type);
        return type;
    }

    private static Type RequireType(string fullName)
    {
        return ImplementationAssembly.GetType(fullName, throwOnError: false)
            ?? throw new TypeLoadException($"Implementation is missing required type {fullName}.");
    }

    private static T ReadConstant<T>(Type owner, string name)
    {
        FieldInfo field = owner.GetField(
                name, BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
            ?? throw new MissingFieldException(owner.FullName, name);
        return (T)(field.GetRawConstantValue()
            ?? throw new InvalidOperationException($"{owner.FullName}.{name} is not a constant."));
    }

    private static void EnsureRuntimeDependency(string assemblyName)
    {
        if (AppDomain.CurrentDomain.GetAssemblies().Any(assembly =>
                string.Equals(assembly.GetName().Name, assemblyName, StringComparison.Ordinal)))
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
            typeof(GravetideSlugProbeNode).Assembly.Location);
        string[] candidates =
        [
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", configuration,
                $"{assemblyName}.dll"),
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", "Debug",
                $"{assemblyName}.dll"),
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", "Release",
                $"{assemblyName}.dll"),
            Path.Combine(assemblyDirectory ?? string.Empty, $"{assemblyName}.dll")
        ];
        return candidates.FirstOrDefault(File.Exists);
    }

    private static void Assert(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }

    private sealed record Scenario(RunState RunState, CombatRoom Room);
}
