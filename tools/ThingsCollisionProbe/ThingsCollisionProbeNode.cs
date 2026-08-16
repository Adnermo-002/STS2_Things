using System.Collections;
using System.Reflection;
using System.Runtime.Loader;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.CardPools;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;

public partial class ThingsCollisionProbeNode : Node
{
    private const string CollisionTypeName = "STS2_Things.Cards.ThingsCollision";
    private static readonly Assembly ImplementationAssembly = typeof(STS2_ThingsInit).Assembly;

    public override async void _Ready()
    {
        try
        {
            TestMode.TurnOnInternal();
            InitializeModelDb();
            VerifyModelAndPoolContract();
            VerifyUpgradeCloneAndSaveContract();
            await VerifyGameplayAndMultiplayerIsolation();
            GD.Print("Things Collision behavior probe: PASS");
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
        Type collisionType = RequireCollisionType();
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

        ModHelper.AddModelToPool(typeof(IroncladCardPool), collisionType);

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
        manifestType.GetField("name")?.SetValue(manifest, "STS2_Things Collision Probe");
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

    private static void VerifyModelAndPoolContract()
    {
        CardModel canonical = CanonicalCollision();
        Assert(canonical.Id.Entry == "THINGS_COLLISION",
            $"Collision ModelId entry is {canonical.Id.Entry} instead of THINGS_COLLISION.");
        Assert(canonical.Type == CardType.Attack &&
               canonical.Rarity == CardRarity.Uncommon &&
               canonical.TargetType == TargetType.AnyEnemy,
            "Collision card type, rarity, or target contract drifted.");
        Assert(Cost(canonical) == 1,
            $"Collision costs {Cost(canonical)} instead of 1 Energy.");
        Assert(canonical.DynamicVars.Damage.BaseValue == 10m &&
               canonical.DynamicVars["StrengthLoss"].BaseValue == 2m,
            "Collision canonical values are not 10 damage and 2 Strength loss.");
        Assert(canonical.CanonicalKeywords.SequenceEqual([CardKeyword.Exhaust]),
            "Collision must Exhaust after its permanent symmetrical Strength loss.");

        CardModel[] entries = ModelDb.CardPool<IroncladCardPool>().AllCards
            .Where(card => card.Id == canonical.Id)
            .ToArray();
        Assert(entries.Length == 1,
            $"Ironclad pool contains {entries.Length} Collision entries instead of one.");
        Assert(canonical.Pool is IroncladCardPool &&
               canonical.VisualCardPool is IroncladCardPool,
            "Collision does not use the Ironclad pool and red visual frame.");

        FieldInfo[] gameplayFields = RequireCollisionType().GetFields(
            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic |
            BindingFlags.DeclaredOnly);
        Assert(gameplayFields.Length == 0,
            "Collision introduced per-instance fields that need an explicit save/network contract.");
    }

    private static void VerifyUpgradeCloneAndSaveContract()
    {
        CardModel upgraded = (CardModel)CanonicalCollision().ToMutable();
        upgraded.UpgradeInternal();
        upgraded.FinalizeUpgradeInternal();
        Assert(upgraded.DynamicVars.Damage.BaseValue == 14m,
            $"Upgraded Collision deals {upgraded.DynamicVars.Damage.BaseValue} instead of 14.");
        Assert(upgraded.DynamicVars["StrengthLoss"].BaseValue == 2m,
            "Upgrading Collision changed its symmetrical Strength loss.");

        CardModel clone = (CardModel)upgraded.ClonePreservingMutability();
        Assert(clone.Id == upgraded.Id && clone.CurrentUpgradeLevel == 1 &&
               clone.DynamicVars.Damage.BaseValue == 14m &&
               clone.DynamicVars["StrengthLoss"].BaseValue == 2m,
            "Collision clone drifted from its upgraded deterministic values.");

        CardModel loaded = CardModel.FromSerializable(upgraded.ToSerializable());
        Assert(loaded.Id == upgraded.Id && loaded.CurrentUpgradeLevel == 1 &&
               loaded.DynamicVars.Damage.BaseValue == 14m &&
               loaded.DynamicVars["StrengthLoss"].BaseValue == 2m,
            "Collision save/load drifted from its upgraded deterministic values.");
    }

    private static async Task VerifyGameplayAndMultiplayerIsolation()
    {
        PlaySignature firstOwner = await PlayScenario(actorIndex: 0, upgraded: false);
        PlaySignature firstOwnerReplay = await PlayScenario(actorIndex: 0, upgraded: false);
        PlaySignature secondOwner = await PlayScenario(actorIndex: 1, upgraded: false);
        PlaySignature upgradedSecondOwner = await PlayScenario(actorIndex: 1, upgraded: true);

        PlaySignature expectedBase = new(10, -2, 3, 2, true);
        PlaySignature expectedUpgrade = new(14, -2, 3, 2, true);
        Assert(firstOwner == expectedBase,
            $"Base Collision produced {firstOwner}; expected {expectedBase}.");
        Assert(firstOwnerReplay == firstOwner,
            "Fixed-seed Collision replay produced a different gameplay signature.");
        Assert(secondOwner == firstOwner,
            "Changing the owning player slot changed Collision's gameplay signature.");
        Assert(upgradedSecondOwner == expectedUpgrade,
            $"Upgraded Collision produced {upgradedSecondOwner}; expected {expectedUpgrade}.");
    }

    private static async Task<PlaySignature> PlayScenario(int actorIndex, bool upgraded)
    {
        Scenario scenario = CreateScenario("THINGS_COLLISION_SYNC_PROBE");
        Player actor = scenario.RunState.Players[actorIndex];
        Player bystander = scenario.RunState.Players[1 - actorIndex];
        Creature target = AddMonster(scenario);

        ActivateSyntheticCombat(scenario.Room.CombatState, actor);
        try
        {
            var choiceContext = new BlockingPlayerChoiceContext();
            await PowerCmd.Apply<StrengthPower>(
                choiceContext, bystander.Creature, 3m, bystander.Creature, null, silent: true);
            await PowerCmd.Apply<StrengthPower>(
                choiceContext, target, 4m, target, null, silent: true);

            CardModel card = scenario.Room.CombatState.CreateCard(CanonicalCollision(), actor);
            if (upgraded)
            {
                card.UpgradeInternal();
                card.FinalizeUpgradeInternal();
            }

            int hpBefore = target.CurrentHp;
            await CardCmd.AutoPlay(
                choiceContext, card, target, skipCardPileVisuals: true);

            return new PlaySignature(
                Damage: hpBefore - target.CurrentHp,
                ActorStrength: GetStrength(actor.Creature),
                BystanderStrength: GetStrength(bystander.Creature),
                TargetStrength: GetStrength(target),
                InActorExhaust: card.Pile?.Type == PileType.Exhaust &&
                                ReferenceEquals(card.Owner, actor));
        }
        finally
        {
            DeactivateSyntheticCombat();
        }
    }

    private static Scenario CreateScenario(string seed)
    {
        Player[] players =
        [
            Player.CreateForNewRun<Ironclad>(UnlockState.all, 101UL),
            Player.CreateForNewRun<Ironclad>(UnlockState.all, 202UL)
        ];
        RunState runState = RunState.CreateForTest(players, seed: seed);
        var room = new CombatRoom(ModelDb.Encounter<CultistsNormal>().ToMutable(), runState);
        runState.PushRoom(room);
        foreach (Player player in players)
        {
            player.ResetCombatState();
            room.CombatState.AddPlayer(player);
        }
        return new Scenario(runState, room);
    }

    private static Creature AddMonster(Scenario scenario)
    {
        MonsterModel monster = ModelDb.Monster<DampCultist>().ToMutable();
        Creature creature = scenario.Room.CombatState.CreateCreature(
            monster, CombatSide.Enemy, "collision_target");
        scenario.Room.CombatState.AddCreature(creature);
        return creature;
    }

    private static void ActivateSyntheticCombat(CombatState state, Player localPlayer)
    {
        LocalContext.NetId = localPlayer.NetId;
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

    private static CardModel CanonicalCollision()
    {
        Type collisionType = RequireCollisionType();
        MethodInfo lookup = typeof(ModelDb)
            .GetMethods(BindingFlags.Public | BindingFlags.Static)
            .Single(method =>
                method.Name == "Card" &&
                method.IsGenericMethodDefinition &&
                method.GetParameters().Length == 0);
        return (CardModel)(lookup.MakeGenericMethod(collisionType).Invoke(null, null)
            ?? throw new InvalidOperationException(
                $"ModelDb.Card<{collisionType.Name}> returned null."));
    }

    private static Type RequireCollisionType()
    {
        Type type = ImplementationAssembly.GetType(CollisionTypeName, throwOnError: true)!;
        Assert(typeof(CardModel).IsAssignableFrom(type),
            $"{CollisionTypeName} does not derive from CardModel.");
        return type;
    }

    private static int GetStrength(Creature creature)
    {
        return creature.Powers
            .Where(power => power is StrengthPower)
            .Sum(power => power.Amount);
    }

    private static int Cost(CardModel card)
    {
        return card.EnergyCost.GetWithModifiers(CostModifiers.None);
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
        string projectRoot = ProjectSettings.GlobalizePath("res://");
        string? assemblyDirectory = Path.GetDirectoryName(
            typeof(ThingsCollisionProbeNode).Assembly.Location);
        string[] candidates =
        [
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

    private sealed record PlaySignature(
        int Damage,
        int ActorStrength,
        int BystanderStrength,
        int TargetStrength,
        bool InActorExhaust);
}
