using System.Collections;
using System.Reflection;
using System.Runtime.Loader;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves.Runs;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Enchantments;
using STS2_Things.Events;

public partial class ThingsSplitProbeNode : Node
{
    private static StrikeIronclad? _throwAfterUpgradeForCard;

    public override void _Ready()
    {
        try
        {
            TestMode.TurnOnInternal();
            InitializeModelDb();
            InstallThingsSplitPatches();
            VerifyEligibility();
            VerifyKnownAndUnknownDynamicVars();
            VerifyBasicStrikeLifecycle();
            VerifyPermanentMutationClearCloneAndSave();
            VerifyAllNumericValuesAndRounding();
            VerifyStarCostLifecycle();
            VerifyPermanentGrowthUpgradeDowngradeCloneAndSave();
            VerifyEnergyCostUpgrade();
            VerifyCalculatedValues();
            VerifyExceptionalUpgradeConsistency();
            VerifyEventCallbacks().GetAwaiter().GetResult();
            GD.Print("Things Split behavior probe: PASS");
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

        Type[] modTypes = [typeof(ThingsSplit), typeof(CuttingItClose)];
        Type[] modelTypes = AbstractModelSubtypes.All
            .Concat(modTypes)
            .Distinct()
            .ToArray();
        typeof(ReflectionHelper).GetField("_modTypes", BindingFlags.NonPublic | BindingFlags.Static)!
            .SetValue(null, modTypes);
        RegisterSyntheticMod(typeof(ThingsSplit).Assembly);

        PropertyInfo? state = typeof(ModManager).GetProperty(
            "State", BindingFlags.Public | BindingFlags.Static);
        if (state != null)
        {
            state.SetValue(null, Enum.Parse(state.PropertyType, "Initialized"));
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

    private static void RegisterSyntheticMod(Assembly implementationAssembly)
    {
        Assembly gameAssembly = typeof(ModManager).Assembly;
        Type modType = gameAssembly.GetType("MegaCrit.Sts2.Core.Modding.Mod", throwOnError: true)!;
        Type manifestType = gameAssembly.GetType(
            "MegaCrit.Sts2.Core.Modding.ModManifest", throwOnError: true)!;
        object mod = Activator.CreateInstance(modType)!;
        object manifest = Activator.CreateInstance(manifestType)!;
        manifestType.GetField("id")!.SetValue(manifest, "STS2_Things");
        manifestType.GetField("name")?.SetValue(manifest, "STS2_Things Split Probe");
        manifestType.GetField("affectsGameplay")?.SetValue(manifest, true);
        modType.GetField("path")!.SetValue(mod, "probe://STS2_Things");
        modType.GetField("manifest")!.SetValue(mod, manifest);
        FieldInfo state = modType.GetField("state")!;
        state.SetValue(mod, Enum.Parse(state.FieldType, "Loaded"));

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

    private static void InstallThingsSplitPatches()
    {
        var harmony = new Harmony($"Adnermo.STS2_Things.SplitProbe.{Guid.NewGuid():N}");
        Type[] patchTypes = typeof(ThingsSplit)
            .GetNestedTypes(BindingFlags.NonPublic)
            .Where(type => type.GetCustomAttributes(typeof(HarmonyPatch), inherit: true).Length > 0)
            .ToArray();
        Assert(patchTypes.Length >= 8,
            $"Expected the ThingsSplit lifecycle patch set, found only {patchTypes.Length} patches.");
        foreach (Type patchType in patchTypes)
        {
            harmony.CreateClassProcessor(patchType).Patch();
        }

        // The behavior probe intentionally runs without mounting the mod PCK or
        // initializing localization. Suppress only the option's decorative hover
        // tip so the full EventModel/EventOption lifecycle can still be exercised.
        MethodInfo hoverTipsGetter = typeof(EnchantmentModel).GetProperty(
            nameof(EnchantmentModel.HoverTips), BindingFlags.Public | BindingFlags.Instance)!
            .GetMethod!;
        MethodInfo suppressHoverTips = typeof(ThingsSplitProbeNode).GetMethod(
            nameof(SuppressEnchantmentHoverTips), BindingFlags.NonPublic | BindingFlags.Static)!;
        harmony.Patch(hoverTipsGetter, prefix: new HarmonyMethod(suppressHoverTips));

        MethodInfo getOptionTitle = typeof(EventModel).GetMethod(nameof(EventModel.GetOptionTitle))!;
        MethodInfo getSyntheticOptionTitle = typeof(ThingsSplitProbeNode).GetMethod(
            nameof(GetSyntheticOptionTitle), BindingFlags.NonPublic | BindingFlags.Static)!;
        harmony.Patch(getOptionTitle, prefix: new HarmonyMethod(getSyntheticOptionTitle));

        MethodInfo getOptionDescription =
            typeof(EventModel).GetMethod(nameof(EventModel.GetOptionDescription))!;
        MethodInfo getSyntheticOptionDescription = typeof(ThingsSplitProbeNode).GetMethod(
            nameof(GetSyntheticOptionDescription), BindingFlags.NonPublic | BindingFlags.Static)!;
        harmony.Patch(
            getOptionDescription,
            prefix: new HarmonyMethod(getSyntheticOptionDescription));

        MethodInfo addCharacterDetails = typeof(CharacterModel).GetMethod(
            nameof(CharacterModel.AddDetailsTo),
            BindingFlags.Public | BindingFlags.Instance)!;
        MethodInfo suppressCharacterDetails = typeof(ThingsSplitProbeNode).GetMethod(
            nameof(SuppressCharacterDetails), BindingFlags.NonPublic | BindingFlags.Static)!;
        harmony.Patch(
            addCharacterDetails,
            prefix: new HarmonyMethod(suppressCharacterDetails));
    }

    private static bool SuppressEnchantmentHoverTips(ref IEnumerable<IHoverTip> __result)
    {
        __result = Array.Empty<IHoverTip>();
        return false;
    }

    private static bool GetSyntheticOptionTitle(string key, ref LocString __result)
    {
        __result = new LocString("events", $"{key}.title");
        return false;
    }

    private static bool GetSyntheticOptionDescription(string key, ref LocString __result)
    {
        __result = new LocString("events", $"{key}.description");
        return false;
    }

    private static bool SuppressCharacterDetails() => false;

    private static void VerifyBasicStrikeLifecycle()
    {
        StrikeIronclad strike = ModelDb.Card<StrikeIronclad>().ToMutable() as StrikeIronclad
            ?? throw new InvalidOperationException("Could not create a mutable Strike.");
        CardCmd.Enchant<ThingsSplit>(strike, 1m);
        AssertSplit(strike, damage: 3m, cost: 0, "base Strike");

        decimal observedUpgradeDamage = -1m;
        StrikeIronclad? cloneCreatedDuringUpgradeEvent = null;
        void ObserveUpgrade()
        {
            observedUpgradeDamage = strike.DynamicVars.Damage.BaseValue;
            cloneCreatedDuringUpgradeEvent =
                (StrikeIronclad)strike.ClonePreservingMutability();
        }

        strike.Upgraded += ObserveUpgrade;
        strike.UpgradeInternal();
        strike.Upgraded -= ObserveUpgrade;
        strike.FinalizeUpgradeInternal();
        Assert(strike.CurrentUpgradeLevel == 1, "Strike upgrade level was not retained.");
        AssertSplit(strike, damage: 5m, cost: 0, "upgraded Strike");
        Assert(observedUpgradeDamage == 5m,
            $"Upgraded event observed transient damage {observedUpgradeDamage} instead of split damage 5.");
        Assert(cloneCreatedDuringUpgradeEvent?.DynamicVars.Damage.BaseValue == 5m,
            "A clone created from the Upgraded event copied a transient unsplit value.");
        Assert(cloneCreatedDuringUpgradeEvent is { Enchantment: ThingsSplit },
            "A clone created from the Upgraded event lost ThingsSplit.");

        StrikeIronclad clone = (StrikeIronclad)strike.ClonePreservingMutability();
        Assert(clone.Enchantment is ThingsSplit, "Clone lost ThingsSplit.");
        AssertSplit(clone, damage: 5m, cost: 0, "cloned upgraded Strike");

        clone.DowngradeInternal();
        Assert(clone.CurrentUpgradeLevel == 0, "Clone downgrade level is wrong.");
        AssertSplit(clone, damage: 3m, cost: 0, "downgraded clone");

        clone.UpgradeInternal();
        clone.FinalizeUpgradeInternal();
        AssertSplit(clone, damage: 5m, cost: 0, "re-upgraded clone");

        SerializableCard saved = clone.ToSerializable();
        Assert(saved.Enchantment?.Id == ModelDb.Enchantment<ThingsSplit>().Id,
            "Serialized card lost ThingsSplit model identity.");
        StrikeIronclad loaded = CardModel.FromSerializable(saved) as StrikeIronclad
            ?? throw new InvalidOperationException("Serialized Strike loaded as another card type.");
        Assert(loaded.Enchantment is ThingsSplit, "Loaded card lost ThingsSplit.");
        Assert(loaded.CurrentUpgradeLevel == 1, "Loaded card lost its upgrade level.");
        AssertSplit(loaded, damage: 5m, cost: 0, "save-loaded upgraded Strike");

        StrikeIronclad loadedClone = (StrikeIronclad)loaded.ClonePreservingMutability();
        loadedClone.DowngradeInternal();
        AssertSplit(loadedClone, damage: 3m, cost: 0, "save-loaded clone downgrade");
    }

    private static void VerifyEligibility()
    {
        ThingsSplit split = ModelDb.Enchantment<ThingsSplit>();
        Whirlwind xCost = ModelDb.Card<Whirlwind>().ToMutable() as Whirlwind
            ?? throw new InvalidOperationException("Could not create a mutable Whirlwind.");
        Assert(!split.CanEnchant(xCost), "X-cost cards must not be eligible for ThingsSplit.");

        Barricade noNumericValues = ModelDb.Card<Barricade>().ToMutable() as Barricade
            ?? throw new InvalidOperationException("Could not create a mutable Barricade.");
        Assert(split.CanEnchant(noNumericValues),
            "A fixed-cost card without numeric DynamicVars should remain eligible.");
        CardCmd.Enchant<ThingsSplit>(noNumericValues, 1m);
        Assert(Cost(noNumericValues) == 1, "Barricade's 3-cost did not round down to 1.");

        Stardust starXCost = MutableCard<Stardust>();
        Assert(starXCost.HasStarCostX,
            "The Stardust eligibility fixture is no longer a star-X card.");
        Assert(!split.CanEnchant(starXCost),
            "Star-X cards must not be eligible for ThingsSplit.");
    }

    private static void VerifyKnownAndUnknownDynamicVars()
    {
        Barricade card = ModelDb.Card<Barricade>().ToMutable() as Barricade
            ?? throw new InvalidOperationException("Could not create a mutable Barricade.");
        var known = new DynamicVar("KnownNumeric", 7m);
        var unknown = new ProbeThirdPartyDynamicVar("ThirdPartyNumeric", 7m);
        var vars = new DynamicVarSet([known, unknown]);
        vars.InitializeWithOwner(card);
        typeof(CardModel).GetField("_dynamicVars", BindingFlags.NonPublic | BindingFlags.Instance)!
            .SetValue(card, vars);

        CardCmd.Enchant<ThingsSplit>(card, 1m);
        Assert(known.BaseValue == 4m,
            "The exact base-game DynamicVar type was not treated as a numeric gameplay value.");
        Assert(unknown.BaseValue == 7m,
            "An unknown third-party DynamicVar subclass was split.");

        known.UpgradeValueBy(1m);
        Assert(known.BaseValue == 4m,
            "An odd known-var upgrade should update the full baseline without exposing a transient value.");
        known.BaseValue += 2m;
        unknown.BaseValue += 2m;
        Assert(known.BaseValue == 6m,
            "A direct write did not preserve its visible increment on the split value.");
        Assert(unknown.BaseValue == 9m,
            "An unknown third-party DynamicVar direct write was altered.");

        card.ClearEnchantmentInternal();
        Assert(known.BaseValue == 10m,
            "Clearing ThingsSplit did not restore the tracked known-var baseline plus growth.");
        Assert(unknown.BaseValue == 9m,
            "Clearing ThingsSplit modified an untracked third-party DynamicVar.");
        Assert(Cost(card) == 3,
            "Clearing ThingsSplit did not restore Barricade's original cost.");
    }

    private static void VerifyPermanentMutationClearCloneAndSave()
    {
        StrikeIronclad card = ModelDb.Card<StrikeIronclad>().ToMutable() as StrikeIronclad
            ?? throw new InvalidOperationException("Could not create a mutable Strike.");
        CardCmd.Enchant<ThingsSplit>(card, 1m);

        card.DynamicVars.Damage.BaseValue += 2m;
        card.EnergyCost.SetCustomBaseCost(2);
        AssertSplit(card, damage: 5m, cost: 2, "permanently changed split Strike");

        StrikeIronclad clone = (StrikeIronclad)card.ClonePreservingMutability();
        AssertSplit(clone, damage: 5m, cost: 2, "clone after permanent changes");
        clone.ClearEnchantmentInternal();
        Assert(clone.Enchantment == null, "Cleared clone retained ThingsSplit.");
        AssertSplit(clone, damage: 8m, cost: 3, "cleared clone after permanent changes");

        SerializableCard saved = card.ToSerializable();
        Assert(saved.Enchantment?.Props?.strings?.Any(
                property => property.name == nameof(ThingsSplit.SplitState) &&
                            !string.IsNullOrEmpty(property.value)) == true,
            "ThingsSplit did not serialize its lifecycle state.");
        StrikeIronclad loaded = CardModel.FromSerializable(saved) as StrikeIronclad
            ?? throw new InvalidOperationException("Serialized permanent-change Strike loaded as another type.");
        AssertSplit(loaded, damage: 5m, cost: 2,
            "save-loaded Strike after permanent changes");
        loaded.ClearEnchantmentInternal();
        AssertSplit(loaded, damage: 8m, cost: 3,
            "cleared save-loaded Strike after permanent changes");

        card.ClearEnchantmentInternal();
        AssertSplit(card, damage: 8m, cost: 3,
            "cleared original Strike after permanent changes");
    }

    private static void VerifyAllNumericValuesAndRounding()
    {
        Bash bash = ModelDb.Card<Bash>().ToMutable() as Bash
            ?? throw new InvalidOperationException("Could not create a mutable Bash.");
        CardCmd.Enchant<ThingsSplit>(bash, 1m);
        Assert(bash.DynamicVars.Damage.BaseValue == 4m, "Bash damage was not halved.");
        Assert(bash.DynamicVars.Vulnerable.BaseValue == 1m, "Bash Vulnerable was not halved.");
        Assert(Cost(bash) == 1, "Bash 2-cost did not become 1-cost.");

        bash.UpgradeInternal();
        bash.FinalizeUpgradeInternal();
        Assert(bash.DynamicVars.Damage.BaseValue == 5m, "Upgraded Bash damage is wrong.");
        Assert(bash.DynamicVars.Vulnerable.BaseValue == 2m,
            "Odd upgraded Bash Vulnerable did not round up.");
        Assert(Cost(bash) == 1, "Upgraded Bash cost changed unexpectedly.");

        Bash loaded = CardModel.FromSerializable(bash.ToSerializable()) as Bash
            ?? throw new InvalidOperationException("Serialized Bash loaded as another card type.");
        Assert(loaded.DynamicVars.Damage.BaseValue == 5m, "Loaded Bash damage drifted.");
        Assert(loaded.DynamicVars.Vulnerable.BaseValue == 2m, "Loaded Bash Vulnerable drifted.");
        Assert(Cost(loaded) == 1, "Loaded Bash cost drifted.");
    }

    private static void VerifyCalculatedValues()
    {
        PerfectedStrike card = ModelDb.Card<PerfectedStrike>().ToMutable() as PerfectedStrike
            ?? throw new InvalidOperationException("Could not create a mutable Perfected Strike.");
        CardCmd.Enchant<ThingsSplit>(card, 1m);
        Assert(card.DynamicVars.CalculationBase.BaseValue == 3m,
            "Calculated base value was not halved.");
        Assert(card.DynamicVars.ExtraDamage.BaseValue == 1m,
            "Calculated extra value was not halved.");
        Assert(card.DynamicVars.CalculatedDamage.BaseValue == 3m,
            "Derived CalculatedDamage was halved twice or not recalculated.");
        Assert(Cost(card) == 1, "Perfected Strike cost was not halved.");

        card.UpgradeInternal();
        card.FinalizeUpgradeInternal();
        Assert(card.DynamicVars.CalculationBase.BaseValue == 3m,
            "Calculated base value drifted after upgrade.");
        Assert(card.DynamicVars.ExtraDamage.BaseValue == 2m,
            "Odd upgraded extra damage did not round up.");
    }

    private static void VerifyEnergyCostUpgrade()
    {
        BansheesCry card = ModelDb.Card<BansheesCry>().ToMutable() as BansheesCry
            ?? throw new InvalidOperationException("Could not create a mutable Banshee's Cry.");
        CardCmd.Enchant<ThingsSplit>(card, 1m);
        Assert(card.DynamicVars.Damage.BaseValue == 17m,
            "Odd Banshee's Cry damage did not round up.");
        Assert(card.DynamicVars.Energy.BaseValue == 1m,
            "Banshee's Cry energy reduction amount was not halved.");
        Assert(Cost(card) == 4, "9-cost Banshee's Cry did not round down to 4.");

        card.UpgradeInternal();
        card.FinalizeUpgradeInternal();
        Assert(Cost(card) == 3,
            "Banshee's Cry cost upgrade was applied to the split value instead of the original value.");

        BansheesCry loaded = CardModel.FromSerializable(card.ToSerializable()) as BansheesCry
            ?? throw new InvalidOperationException("Serialized Banshee's Cry loaded as another card type.");
        Assert(Cost(loaded) == 3, "Loaded upgraded Banshee's Cry cost drifted.");
        Assert(loaded.DynamicVars.Damage.BaseValue == 17m,
            "Loaded Banshee's Cry damage drifted.");

        decimal observedCost = -1m;
        BansheesCry downgradeProbe = ModelDb.Card<BansheesCry>().ToMutable() as BansheesCry
            ?? throw new InvalidOperationException("Could not create a downgrade-probe Banshee's Cry.");
        CardCmd.Enchant<ThingsSplit>(downgradeProbe, 1m);
        void ObserveUpgrade() => observedCost = Cost(downgradeProbe);
        downgradeProbe.Upgraded += ObserveUpgrade;
        downgradeProbe.UpgradeInternal();
        downgradeProbe.Upgraded -= ObserveUpgrade;
        Assert(observedCost == 3m,
            $"Upgraded event observed transient energy cost {observedCost} instead of 3.");
        downgradeProbe.FinalizeUpgradeInternal();
        decimal observedDowngradeCost = -1m;
        void ObserveDowngrade() => observedDowngradeCost = Cost(downgradeProbe);
        downgradeProbe.Upgraded += ObserveDowngrade;
        downgradeProbe.DowngradeInternal();
        downgradeProbe.Upgraded -= ObserveDowngrade;
        Assert(downgradeProbe.CurrentUpgradeLevel == 0,
            "Banshee's Cry downgrade did not reset its upgrade level.");
        Assert(Cost(downgradeProbe) == 4,
            $"Energy downgrade produced cost {Cost(downgradeProbe)} instead of split canonical cost 4.");
        Assert(observedDowngradeCost == 4m,
            $"Downgrade event observed transient energy cost {observedDowngradeCost} instead of 4.");
        Assert(downgradeProbe.DynamicVars.Damage.BaseValue == 17m,
            "Downgrade did not refresh Banshee's Cry to its split canonical damage.");

        BansheesCry directCostProbe = ModelDb.Card<BansheesCry>().ToMutable() as BansheesCry
            ?? throw new InvalidOperationException("Could not create a direct-cost Banshee's Cry.");
        CardCmd.Enchant<ThingsSplit>(directCostProbe, 1m);
        directCostProbe.EnergyCost.SetCustomBaseCost(2);
        directCostProbe.EnergyCost.UpgradeBy(-2);
        Assert(Cost(directCostProbe) == 2,
            "A full-cost upgrade with no visible half-cost change drifted the displayed cost.");
        directCostProbe.ClearEnchantmentInternal();
        Assert(Cost(directCostProbe) == 5,
            "Direct cost writes and a no-visible-change upgrade did not update the full baseline.");
    }

    private static void VerifyStarCostLifecycle()
    {
        // Canonical star costs drift between game versions (v0.111.0 lowered
        // Alignment from 3 to 2). Derive both expectations from the current
        // vanilla model instead of hardcoding balance numbers.
        VerifyFixedStarCost<Comet>();
        VerifyFixedStarCost<SevenStars>();
        VerifyFixedStarCost<Alignment>();
    }

    private static void VerifyFixedStarCost<TCard>()
        where TCard : CardModel
    {
        TCard card = MutableCard<TCard>();
        int canonicalCost = card.BaseStarCost;
        Assert(canonicalCost > 0,
            $"{typeof(TCard).Name} has no positive canonical star cost to split.");
        int splitCost = canonicalCost / 2;

        CardCmd.Enchant<ThingsSplit>(card, 1m);
        Assert(card.BaseStarCost == splitCost,
            $"{typeof(TCard).Name} star cost is {card.BaseStarCost}, expected split cost {splitCost}.");
        Assert(card.CurrentStarCost == splitCost,
            $"{typeof(TCard).Name} current star cost is {card.CurrentStarCost}, expected {splitCost}.");

        TCard clone = (TCard)card.ClonePreservingMutability();
        Assert(clone.Enchantment is ThingsSplit,
            $"A cloned {typeof(TCard).Name} lost ThingsSplit.");
        Assert(clone.BaseStarCost == splitCost,
            $"A cloned {typeof(TCard).Name} star cost drifted to {clone.BaseStarCost}.");

        TCard loaded = CardModel.FromSerializable(card.ToSerializable()) as TCard
            ?? throw new InvalidOperationException(
                $"Serialized {typeof(TCard).Name} loaded as another card type.");
        Assert(loaded.Enchantment is ThingsSplit,
            $"A save-loaded {typeof(TCard).Name} lost ThingsSplit.");
        Assert(loaded.BaseStarCost == splitCost,
            $"A save-loaded {typeof(TCard).Name} star cost drifted to {loaded.BaseStarCost}.");

        clone.ClearEnchantmentInternal();
        loaded.ClearEnchantmentInternal();
        Assert(clone.BaseStarCost == canonicalCost,
            $"Clearing ThingsSplit from cloned {typeof(TCard).Name} restored star cost " +
            $"{clone.BaseStarCost}, expected {canonicalCost}.");
        Assert(loaded.BaseStarCost == canonicalCost,
            $"Clearing ThingsSplit from save-loaded {typeof(TCard).Name} restored star cost " +
            $"{loaded.BaseStarCost}, expected {canonicalCost}.");
    }

    private static void VerifyPermanentGrowthUpgradeDowngradeCloneAndSave()
    {
        VerifyRampageGrowthLifecycle();
        VerifyGeneticAlgorithmGrowthLifecycle();
        VerifyTheScytheGrowthLifecycle();
        VerifySovereignBladeGrowthDowngrade();
    }

    private static void VerifyRampageGrowthLifecycle()
    {
        Rampage card = MutableCard<Rampage>();
        CardCmd.Enchant<ThingsSplit>(card, 1m);

        decimal growth = card.DynamicVars["Increase"].BaseValue;
        card.DynamicVars.Damage.BaseValue += growth;
        PropertyInfo extraDamage = typeof(Rampage).GetProperty(
            "ExtraDamageFromPlays", BindingFlags.NonPublic | BindingFlags.Instance)
            ?? throw new MissingMemberException(typeof(Rampage).FullName, "ExtraDamageFromPlays");
        extraDamage.SetValue(card, (decimal)extraDamage.GetValue(card)! + growth);
        Assert(card.DynamicVars.Damage.BaseValue == 8m,
            $"Split Rampage growth produced {card.DynamicVars.Damage.BaseValue} damage, expected 8.");

        VerifyGrowthLifecycle(
            card,
            value => value.DynamicVars.Damage.BaseValue,
            expectedAfterDowngrade: 8m,
            "Rampage");
    }

    private static void VerifyGeneticAlgorithmGrowthLifecycle()
    {
        GeneticAlgorithm card = MutableCard<GeneticAlgorithm>();
        CardCmd.Enchant<ThingsSplit>(card, 1m);

        int growth = card.DynamicVars["Increase"].IntValue;
        card.IncreasedBlock += growth;
        card.CurrentBlock = 1 + card.IncreasedBlock;
        Assert(card.DynamicVars.Block.BaseValue == 3m,
            $"Split Genetic Algorithm growth produced {card.DynamicVars.Block.BaseValue} block, expected 3.");

        VerifyGrowthLifecycle(
            card,
            value => value.DynamicVars.Block.BaseValue,
            expectedAfterDowngrade: 3m,
            "Genetic Algorithm");
    }

    private static void VerifyTheScytheGrowthLifecycle()
    {
        TheScythe card = MutableCard<TheScythe>();
        CardCmd.Enchant<ThingsSplit>(card, 1m);

        int growth = card.DynamicVars["Increase"].IntValue;
        card.IncreasedDamage += growth;
        card.CurrentDamage = 13 + card.IncreasedDamage;
        decimal expectedVisibleDamage = decimal.Ceiling(13m / 2m) + growth;
        Assert(card.DynamicVars.Damage.BaseValue == expectedVisibleDamage,
            $"Split The Scythe growth produced {card.DynamicVars.Damage.BaseValue} damage, " +
            $"expected {expectedVisibleDamage}.");

        // The Scythe rebuilds CurrentDamage from its unsplit constant (13).
        // ThingsSplit must translate that setter back into the visible half-card
        // domain: 7 initial damage plus the current version's split Increase value.
        VerifyGrowthLifecycle(
            card,
            value => value.DynamicVars.Damage.BaseValue,
            expectedAfterDowngrade: expectedVisibleDamage,
            "The Scythe");
    }

    private static void VerifySovereignBladeGrowthDowngrade()
    {
        SovereignBlade card = MutableCard<SovereignBlade>();
        CardCmd.Enchant<ThingsSplit>(card, 1m);
        Assert(card.DynamicVars.Damage.BaseValue == 5m,
            "Split Sovereign Blade did not start at 5 damage.");

        card.AddDamage(3m);
        card.SetRepeats(2m);
        Assert(card.DynamicVars.Damage.BaseValue == 8m &&
               card.DynamicVars.Repeat.BaseValue == 2m,
            "Split Sovereign Blade did not retain its visible forge mutations.");

        card.UpgradeInternal();
        card.FinalizeUpgradeInternal();
        card.DowngradeInternal();
        Assert(card.DynamicVars.Damage.BaseValue == 8m &&
               card.DynamicVars.Repeat.BaseValue == 2m,
            "Split Sovereign Blade lost its forge mutations during downgrade.");
    }

    private static void VerifyGrowthLifecycle<TCard>(
        TCard card,
        Func<TCard, decimal> readValue,
        decimal expectedAfterDowngrade,
        string context)
        where TCard : CardModel
    {
        card.UpgradeInternal();
        card.FinalizeUpgradeInternal();
        Assert(card.CurrentUpgradeLevel == 1,
            $"{context} permanent-growth fixture did not upgrade.");

        card.DowngradeInternal();
        Assert(card.CurrentUpgradeLevel == 0,
            $"{context} permanent-growth fixture did not downgrade.");
        Assert(readValue(card) == expectedAfterDowngrade,
            $"{context} permanent growth drifted to {readValue(card)} after downgrade; " +
            $"expected {expectedAfterDowngrade}.");

        TCard clone = (TCard)card.ClonePreservingMutability();
        Assert(clone.Enchantment is ThingsSplit,
            $"A cloned permanently-grown {context} lost ThingsSplit.");
        Assert(readValue(clone) == expectedAfterDowngrade,
            $"A cloned permanently-grown {context} drifted to {readValue(clone)}.");

        TCard loaded = CardModel.FromSerializable(card.ToSerializable()) as TCard
            ?? throw new InvalidOperationException(
                $"Serialized permanently-grown {context} loaded as another card type.");
        Assert(loaded.Enchantment is ThingsSplit,
            $"A save-loaded permanently-grown {context} lost ThingsSplit.");
        Assert(loaded.CurrentUpgradeLevel == 0,
            $"A save-loaded permanently-grown {context} changed upgrade level.");
        Assert(readValue(loaded) == expectedAfterDowngrade,
            $"A save-loaded permanently-grown {context} drifted to {readValue(loaded)}.");
    }

    private static void VerifyExceptionalUpgradeConsistency()
    {
        MethodInfo onUpgrade = typeof(StrikeIronclad).GetMethod(
            "OnUpgrade", BindingFlags.NonPublic | BindingFlags.Instance)
            ?? throw new MissingMethodException(typeof(StrikeIronclad).FullName, "OnUpgrade");
        MethodInfo throwPostfix = typeof(ThingsSplitProbeNode).GetMethod(
            nameof(ThrowAfterSelectedStrikeUpgrade), BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new MissingMethodException(
                typeof(ThingsSplitProbeNode).FullName,
                nameof(ThrowAfterSelectedStrikeUpgrade));
        new Harmony($"Adnermo.STS2_Things.SplitExceptionProbe.{Guid.NewGuid():N}")
            .Patch(onUpgrade, postfix: new HarmonyMethod(throwPostfix));

        StrikeIronclad card = ModelDb.Card<StrikeIronclad>().ToMutable() as StrikeIronclad
            ?? throw new InvalidOperationException("Could not create an exceptional-upgrade Strike.");
        CardCmd.Enchant<ThingsSplit>(card, 1m);
        _throwAfterUpgradeForCard = card;
        try
        {
            card.UpgradeInternal();
            throw new InvalidOperationException("The exceptional upgrade probe did not throw.");
        }
        catch (ProbeUpgradeException)
        {
            // Expected: vanilla keeps mutations already made before OnUpgrade throws.
        }
        finally
        {
            _throwAfterUpgradeForCard = null;
        }

        Assert(card.CurrentUpgradeLevel == 1,
            "Exceptional upgrade diverged from the base game's retained upgrade level.");
        AssertSplit(card, damage: 5m, cost: 0,
            "exceptionally upgraded Strike");
        StrikeIronclad clone = (StrikeIronclad)card.ClonePreservingMutability();
        AssertSplit(clone, damage: 5m, cost: 0,
            "clone after exceptional upgrade");
        clone.ClearEnchantmentInternal();
        AssertSplit(clone, damage: 9m, cost: 1,
            "cleared clone after exceptional upgrade");
    }

    private static void ThrowAfterSelectedStrikeUpgrade(StrikeIronclad __instance)
    {
        if (ReferenceEquals(__instance, _throwAfterUpgradeForCard))
        {
            throw new ProbeUpgradeException();
        }
    }

    private static async Task VerifyEventCallbacks()
    {
        VerifyEventEligibility();
        VerifyConsoleJumpScreenCleanupDecision();
        await VerifyImproviseSelectionFilter();
        await VerifyImproviseCallback();
        await VerifyImproviseWithMoltenEgg();
        await VerifyThrowCallback();
        await VerifyEmptyImproviseSelection();
        await VerifyEmptyThrowSelection();
        await VerifyMultiplayerIndependentChoices();
        await VerifyRemoteUnfinishedDuplicateGuard();
    }

    private static void VerifyConsoleJumpScreenCleanupDecision()
    {
        Type patchType = typeof(CuttingItClose).Assembly.GetType(
            "STS2_Things.Events.CuttingItCloseConsoleReentryPatch",
            throwOnError: true)!;
        MethodInfo decision = patchType.GetMethod(
            "ShouldPrepareScreens",
            BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Static)
            ?? throw new MissingMethodException(patchType.FullName, "ShouldPrepareScreens");

        bool ShouldPrepare(
            string[] args,
            bool hasIssuingPlayer = true,
            bool runInProgress = true,
            bool duplicateActive = false)
        {
            return (bool)(decision.Invoke(
                null,
                [args, hasIssuingPlayer, runInProgress, duplicateActive]) ?? false);
        }

        Assert(ShouldPrepare(["CUTTING_IT_CLOSE"]),
            "The first CUTTING_IT_CLOSE console jump did not request stale screen cleanup.");
        Assert(ShouldPrepare(["cutting_it_close"]),
            "CUTTING_IT_CLOSE screen cleanup was not case-insensitive.");
        Assert(!ShouldPrepare(["CUTTING_IT_CLOSE"], duplicateActive: true),
            "A rejected duplicate CUTTING_IT_CLOSE jump would clear the active event UI.");
        Assert(!ShouldPrepare(["CUTTING_IT_CLOSE"], hasIssuingPlayer: false),
            "A console jump without an issuing player would clear screens.");
        Assert(!ShouldPrepare(["CUTTING_IT_CLOSE"], runInProgress: false),
            "A CUTTING_IT_CLOSE command outside a run would clear screens.");
        Assert(!ShouldPrepare(["BACKROOMS"]),
            "The CUTTING_IT_CLOSE patch would clear screens for another event command.");
        Assert(!ShouldPrepare(Array.Empty<string>()),
            "The CUTTING_IT_CLOSE patch would clear screens for an empty command.");
    }

    private static void VerifyEventEligibility()
    {
        CuttingItClose eventModel = ModelDb.Event<CuttingItClose>();
        ThingsSplit split = ModelDb.Enchantment<ThingsSplit>();
        MethodInfo candidateMethod = typeof(CuttingItClose).GetMethod(
            "IsSplitCandidate",
            BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new MissingMethodException(typeof(CuttingItClose).FullName, "IsSplitCandidate");

        bool IsCandidate(CardModel card)
        {
            return (bool)(candidateMethod.Invoke(null, [split, card]) ?? false);
        }

        Assert(IsCandidate(MutableCard<StrikeIronclad>()),
            "Cutting It Close rejected an Attack card from Split selection.");
        Assert(IsCandidate(MutableCard<DefendIronclad>()),
            "Cutting It Close rejected a Skill card from Split selection.");
        Assert(!IsCandidate(MutableCard<Barricade>()),
            "Cutting It Close accepted a Power card for Split selection.");
        Assert(!IsCandidate(MutableCard<Burn>()),
            "Cutting It Close accepted a Status card for Split selection.");
        Assert(!IsCandidate(MutableCard<AscendersBane>()),
            "Cutting It Close accepted a Curse card for Split selection.");

        Player eligible = CreateIroncladPlayer(101UL);
        RunState eligibleRun = RunState.CreateForTest(
            [eligible], seed: "THINGS_SPLIT_EVENT_ALLOWED");
        Assert(eventModel.IsAllowed(eligibleRun),
            "Cutting It Close rejected a normal deck containing split candidates.");

        Player empty = CreateIroncladPlayer(102UL);
        empty.Deck.Clear(silent: true);
        RunState emptyRun = RunState.CreateForTest(
            [empty], seed: "THINGS_SPLIT_EVENT_EMPTY");
        Assert(!eventModel.IsAllowed(emptyRun),
            "Cutting It Close accepted a run whose only player has no candidate cards.");

        Player multiplayerEligible = CreateIroncladPlayer(103UL);
        Player multiplayerEmpty = CreateIroncladPlayer(104UL);
        multiplayerEmpty.Deck.Clear(silent: true);
        RunState multiplayerRun = RunState.CreateForTest(
            [multiplayerEligible, multiplayerEmpty],
            seed: "THINGS_SPLIT_EVENT_MULTIPLAYER_EMPTY");
        Assert(!eventModel.IsAllowed(multiplayerRun),
            "Cutting It Close accepted multiplayer when one player had no candidate cards.");

        Player powerOnly = CreateIroncladPlayer(105UL);
        RunState powerOnlyRun = RunState.CreateForTest(
            [powerOnly], seed: "THINGS_SPLIT_EVENT_POWER_ONLY");
        powerOnly.Deck.Clear(silent: true);
        powerOnly.Deck.AddInternal(
            powerOnlyRun.CreateCard<Barricade>(powerOnly),
            silent: true);
        Assert(!eventModel.IsAllowed(powerOnlyRun),
            "Cutting It Close accepted a deck whose only enchantable card was a Power.");
    }

    private static async Task VerifyImproviseSelectionFilter()
    {
        Player player = CreateIroncladPlayer(106UL);
        RunState runState = RunState.CreateForTest(
            [player], seed: "THINGS_SPLIT_EVENT_SELECTION_FILTER");
        player.Deck.Clear(silent: true);

        CardModel attack = runState.CreateCard<StrikeIronclad>(player);
        CardModel skill = runState.CreateCard<DefendIronclad>(player);
        CardModel power = runState.CreateCard<Barricade>(player);
        CardModel status = runState.CreateCard<Burn>(player);
        CardModel curse = runState.CreateCard<AscendersBane>(player);
        foreach (CardModel card in new[] { attack, skill, power, status, curse })
        {
            player.Deck.AddInternal(card, silent: true);
        }

        CuttingItClose eventModel = await CreateStartedEvent(player);
        var selector = new CapturingCardSelector();
        using (CardSelectCmd.UseSelector(selector))
        {
            await eventModel.CurrentOptions[0].Chosen();
        }

        Assert(selector.Options.SequenceEqual([attack, skill]),
            "Improvise selection did not expose exactly the Attack and Skill cards.");
        Assert(eventModel.IsFinished,
            "The selection-filter probe left Cutting It Close unfinished.");
    }

    private static async Task VerifyImproviseCallback()
    {
        Player player = CreateIroncladRunPlayer();
        CardModel original = player.Deck.Cards.OfType<StrikeIronclad>().First();
        CardModel[] deckBefore = player.Deck.Cards.ToArray();

        CuttingItClose eventModel = await CreateStartedEvent(player);
        Assert(eventModel.CurrentOptions.Count == 2,
            "Cutting It Close did not expose both initial event options.");
        Assert(eventModel.CurrentOptions[0].TextKey ==
               "CUTTING_IT_CLOSE.pages.INITIAL.options.IMPROVISE",
            "Cutting It Close generated an unexpected Improvise option key.");
        Assert(!eventModel.CurrentOptions[0].IsLocked,
            "Cutting It Close generated a locked Improvise option.");
        AssertDuplicateJumpGuard(eventModel, expected: true);
        var option = eventModel.CurrentOptions[0];
        var selector = new TestCardSelector();
        selector.PrepareToSelect([original]);
        using (CardSelectCmd.UseSelector(selector))
        {
            await option.Chosen();
        }

        CardModel[] deckAfter = player.Deck.Cards.ToArray();
        CardModel[] addedCards = deckAfter
            .Where(card => deckBefore.All(previous => !ReferenceEquals(previous, card)))
            .ToArray();

        Assert(deckAfter.Length == deckBefore.Length + 1,
            "Improvise did not increase the deck size by exactly one.");
        Assert(deckAfter.All(card => !ReferenceEquals(card, original)),
            "Improvise left the selected original card in the deck.");
        Assert(original.HasBeenRemovedFromState,
            "Improvise did not remove the selected original card from run state.");
        Assert(addedCards.Length == 2,
            $"Improvise added {addedCards.Length} new cards instead of two.");
        Assert(!ReferenceEquals(addedCards[0], addedCards[1]),
            "Improvise reused one card instance for both copies.");
        Assert(addedCards.All(card => card.Id == original.Id),
            "Improvise changed the selected card's ModelId while cloning it.");
        Assert(addedCards.All(card => card.Enchantment is ThingsSplit),
            "Improvise did not apply ThingsSplit to both copies.");
        foreach (CardModel copy in addedCards)
        {
            AssertSplit(copy, damage: 3m, cost: 0, "event-created Strike copy");
        }
        Assert(option.WasChosen,
            "Improvise's EventOption did not record the click.");
        Assert(eventModel.IsFinished, "Improvise did not finish the event.");
        AssertDuplicateJumpGuard(eventModel, expected: false);
    }

    private static async Task VerifyThrowCallback()
    {
        Player player = CreateIroncladRunPlayer();
        CardModel original = player.Deck.Cards.OfType<StrikeIronclad>().First();
        CardModel[] deckBefore = player.Deck.Cards.ToArray();

        CuttingItClose eventModel = await CreateStartedEvent(player);
        Assert(eventModel.CurrentOptions.Count == 2,
            "Cutting It Close did not expose both initial event options.");
        Assert(eventModel.CurrentOptions[1].TextKey ==
               "CUTTING_IT_CLOSE.pages.INITIAL.options.THROW",
            "Cutting It Close generated an unexpected Throw option key.");
        Assert(!eventModel.CurrentOptions[1].IsLocked,
            "Cutting It Close generated a locked Throw option.");
        AssertDuplicateJumpGuard(eventModel, expected: true);
        var option = eventModel.CurrentOptions[1];
        var selector = new TestCardSelector();
        selector.PrepareToSelect([original]);
        using (CardSelectCmd.UseSelector(selector))
        {
            await option.Chosen();
        }

        CardModel[] deckAfter = player.Deck.Cards.ToArray();
        Assert(deckAfter.Length == deckBefore.Length - 1,
            "Throw did not decrease the deck size by exactly one.");
        Assert(deckAfter.All(card => !ReferenceEquals(card, original)),
            "Throw left the selected card in the deck.");
        Assert(original.HasBeenRemovedFromState,
            "Throw did not remove the selected card from run state.");
        Assert(deckAfter.All(card => deckBefore.Any(previous => ReferenceEquals(previous, card))),
            "Throw unexpectedly created a new card.");
        Assert(option.WasChosen,
            "Throw's EventOption did not record the click.");
        Assert(eventModel.IsFinished, "Throw did not finish the event.");
        AssertDuplicateJumpGuard(eventModel, expected: false);
    }

    private static async Task VerifyImproviseWithMoltenEgg()
    {
        Player player = CreateIroncladRunPlayer();
        player.AddRelicInternal(ModelDb.Relic<MoltenEgg>().ToMutable(), silent: true);
        CardModel original = player.Deck.Cards.OfType<StrikeIronclad>().First();
        CardModel[] deckBefore = player.Deck.Cards.ToArray();

        CuttingItClose eventModel = await CreateStartedEvent(player);
        var selector = new TestCardSelector();
        selector.PrepareToSelect([original]);
        using (CardSelectCmd.UseSelector(selector))
        {
            await eventModel.CurrentOptions[0].Chosen();
        }

        CardModel[] addedCards = player.Deck.Cards
            .Where(card => deckBefore.All(previous => !ReferenceEquals(previous, card)))
            .ToArray();
        Assert(addedCards.Length == 2,
            $"Molten Egg Improvise added {addedCards.Length} cards instead of two.");
        Assert(addedCards.All(card =>
                card is StrikeIronclad &&
                card.Enchantment is ThingsSplit &&
                card.CurrentUpgradeLevel == 1),
            "Molten Egg did not preserve and upgrade both split event copies.");
        foreach (CardModel copy in addedCards)
        {
            AssertSplit(copy, damage: 5m, cost: 0,
                "Molten Egg event-created Strike copy");
        }
        Assert(eventModel.IsFinished,
            "Molten Egg Improvise did not finish Cutting It Close.");
    }

    private static async Task VerifyEmptyImproviseSelection()
    {
        Player player = CreateIroncladRunPlayer();
        CardModel[] deckBefore = player.Deck.Cards.ToArray();
        CuttingItClose eventModel = await CreateStartedEvent(player);
        EventOption option = eventModel.CurrentOptions[0];
        var selector = new TestCardSelector();
        selector.PrepareToSelect(Array.Empty<CardModel>());
        using (CardSelectCmd.UseSelector(selector))
        {
            await option.Chosen();
        }

        AssertSameDeck(deckBefore, player.Deck.Cards,
            "An empty Improvise selection changed the player's deck.");
        Assert(option.WasChosen,
            "An empty Improvise selection did not record the option click.");
        Assert(eventModel.IsFinished,
            "An empty Improvise selection left Cutting It Close unfinished.");
        AssertDuplicateJumpGuard(eventModel, expected: false);
    }

    private static async Task VerifyEmptyThrowSelection()
    {
        Player player = CreateIroncladRunPlayer();
        CardModel[] deckBefore = player.Deck.Cards.ToArray();
        CuttingItClose eventModel = await CreateStartedEvent(player);
        EventOption option = eventModel.CurrentOptions[1];
        var selector = new TestCardSelector();
        selector.PrepareToSelect(Array.Empty<CardModel>());
        using (CardSelectCmd.UseSelector(selector))
        {
            await option.Chosen();
        }

        AssertSameDeck(deckBefore, player.Deck.Cards,
            "An empty Throw selection changed the player's deck.");
        Assert(option.WasChosen,
            "An empty Throw selection did not record the option click.");
        Assert(eventModel.IsFinished,
            "An empty Throw selection left Cutting It Close unfinished.");
        AssertDuplicateJumpGuard(eventModel, expected: false);
    }

    private static async Task VerifyRemoteUnfinishedDuplicateGuard()
    {
        Player player = CreateIroncladRunPlayer();
        CuttingItClose completedLocal = await CreateStartedEvent(player);
        EventOption localOption = completedLocal.CurrentOptions[1];
        var selector = new TestCardSelector();
        selector.PrepareToSelect(Array.Empty<CardModel>());
        using (CardSelectCmd.UseSelector(selector))
        {
            await localOption.Chosen();
        }
        Assert(completedLocal.IsFinished,
            "Remote duplicate-guard fixture did not finish the local event.");

        CuttingItClose unfinishedRemote =
            (CuttingItClose)ModelDb.Event<CuttingItClose>().ToMutable();
        Assert(!unfinishedRemote.IsFinished,
            "Remote duplicate-guard fixture unexpectedly started finished.");
        AssertDuplicateJumpGuard(
            [completedLocal, unfinishedRemote],
            expected: true,
            "a completed local event plus an unfinished remote event");
    }

    private static async Task VerifyMultiplayerIndependentChoices()
    {
        Player improvisingPlayer = CreateIroncladPlayer(201UL);
        Player throwingPlayer = CreateIroncladPlayer(202UL);
        _ = RunState.CreateForTest(
            [improvisingPlayer, throwingPlayer],
            seed: "THINGS_SPLIT_EVENT_MULTIPLAYER_CHOICES");

        CardModel improviseOriginal =
            improvisingPlayer.Deck.Cards.OfType<StrikeIronclad>().First();
        CardModel throwOriginal =
            throwingPlayer.Deck.Cards.OfType<StrikeIronclad>().First();
        CardModel[] improviseDeckBefore = improvisingPlayer.Deck.Cards.ToArray();
        CardModel[] throwDeckBefore = throwingPlayer.Deck.Cards.ToArray();

        CuttingItClose improviseEvent = await CreateStartedEvent(improvisingPlayer);
        CuttingItClose throwEvent = await CreateStartedEvent(throwingPlayer);

        var improviseSelector = new TestCardSelector();
        improviseSelector.PrepareToSelect([improviseOriginal]);
        using (CardSelectCmd.UseSelector(improviseSelector))
        {
            await improviseEvent.CurrentOptions[0].Chosen();
        }

        var throwSelector = new TestCardSelector();
        throwSelector.PrepareToSelect([throwOriginal]);
        using (CardSelectCmd.UseSelector(throwSelector))
        {
            await throwEvent.CurrentOptions[1].Chosen();
        }

        CardModel[] improvisingDeckAfter = improvisingPlayer.Deck.Cards.ToArray();
        CardModel[] throwingDeckAfter = throwingPlayer.Deck.Cards.ToArray();
        CardModel[] multiplayerCopies = improvisingDeckAfter
            .Where(card => improviseDeckBefore.All(
                previous => !ReferenceEquals(previous, card)))
            .ToArray();

        Assert(improviseEvent.IsFinished && throwEvent.IsFinished,
            "Two multiplayer Cutting It Close instances did not both finish.");
        Assert(improvisingDeckAfter.Length == improviseDeckBefore.Length + 1 &&
               multiplayerCopies.Length == 2 &&
               multiplayerCopies.All(card => card.Enchantment is ThingsSplit),
            "The multiplayer Improvise owner did not receive two split copies.");
        Assert(improvisingDeckAfter.All(card => !ReferenceEquals(card, improviseOriginal)),
            "The multiplayer Improvise owner retained the selected original card.");
        Assert(throwingDeckAfter.Length == throwDeckBefore.Length - 1 &&
               throwingDeckAfter.All(card => !ReferenceEquals(card, throwOriginal)),
            "The multiplayer Throw owner did not lose exactly the selected card.");
        Assert(throwingDeckAfter.All(card =>
                throwDeckBefore.Any(previous => ReferenceEquals(previous, card))),
            "The multiplayer Throw owner unexpectedly received a new card.");
        Assert(improvisingDeckAfter.All(card =>
                throwingDeckAfter.All(other => !ReferenceEquals(card, other))),
            "Multiplayer event choices leaked a card instance between player decks.");
    }

    private static Player CreateIroncladRunPlayer()
    {
        Player player = CreateIroncladPlayer(1UL);
        _ = RunState.CreateForTest([player], seed: "THINGS_SPLIT_EVENT_PROBE");
        return player;
    }

    private static Player CreateIroncladPlayer(ulong netId)
    {
        return Player.CreateForNewRun<Ironclad>(UnlockState.all, netId);
    }

    private static async Task<CuttingItClose> CreateStartedEvent(Player owner)
    {
        CuttingItClose canonical = ModelDb.Event<CuttingItClose>();
        var probeVars = new DynamicVarSet([new StringVar("Enchantment", "Split")]);
        probeVars.InitializeWithOwner(canonical);
        FieldInfo dynamicVarsField = typeof(EventModel).GetField(
            "_dynamicVars", BindingFlags.NonPublic | BindingFlags.Instance)
            ?? throw new MissingFieldException(typeof(EventModel).FullName, "_dynamicVars");
        dynamicVarsField.SetValue(canonical, probeVars);

        var eventModel = (CuttingItClose)canonical.ToMutable();
        MethodInfo beginEvent = typeof(EventModel).GetMethods(
                BindingFlags.Public | BindingFlags.Instance)
            .Single(method => method.Name == nameof(EventModel.BeginEvent));
        object?[] arguments = beginEvent.GetParameters()
            .Select(parameter => parameter.ParameterType == typeof(Player)
                ? (object)owner
                : parameter.ParameterType == typeof(bool)
                    ? false
                    : null)
            .ToArray();
        Task beginTask = beginEvent.Invoke(eventModel, arguments) as Task
            ?? throw new InvalidOperationException("EventModel.BeginEvent did not return a Task.");
        await beginTask;
        return eventModel;
    }

    private static void AssertDuplicateJumpGuard(CuttingItClose mutableEvent, bool expected)
    {
        AssertDuplicateJumpGuard(
            [mutableEvent],
            expected,
            "the supplied mutable event set");
    }

    private static void AssertDuplicateJumpGuard(
        IEnumerable<EventModel> mutableEvents,
        bool expected,
        string context)
    {
        Type patchType = typeof(CuttingItClose).Assembly.GetType(
            "STS2_Things.Events.CuttingItCloseConsoleReentryPatch",
            throwOnError: true)!;
        MethodInfo guard = patchType.GetMethod(
            "ShouldBlockDuplicate",
            BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Static)
            ?? throw new MissingMethodException(patchType.FullName, "ShouldBlockDuplicate");
        bool actual = (bool)(guard.Invoke(
            null,
            [
                new[] { "CUTTING_IT_CLOSE" },
                ModelDb.Event<CuttingItClose>(),
                mutableEvents
            ]) ?? false);
        Assert(actual == expected,
            $"Duplicate CUTTING_IT_CLOSE console jump guard returned {actual} for {context}; " +
            $"expected {expected}.");
    }

    private static void AssertSameDeck(
        IReadOnlyList<CardModel> expected,
        IReadOnlyList<CardModel> actual,
        string message)
    {
        Assert(expected.Count == actual.Count &&
               expected.Zip(actual).All(pair => ReferenceEquals(pair.First, pair.Second)),
            message);
        Assert(expected.All(card => !card.HasBeenRemovedFromState),
            $"{message} At least one original card was removed from run state.");
    }

    private static TCard MutableCard<TCard>() where TCard : CardModel
    {
        return ModelDb.Card<TCard>().ToMutable() as TCard
            ?? throw new InvalidOperationException(
                $"Could not create a mutable {typeof(TCard).Name}.");
    }

    private static void AssertSplit(CardModel card, decimal damage, int cost, string context)
    {
        Assert(card.DynamicVars.Damage.BaseValue == damage,
            $"{context} damage is {card.DynamicVars.Damage.BaseValue}, expected {damage}.");
        Assert(Cost(card) == cost, $"{context} cost is {Cost(card)}, expected {cost}.");
    }

    private static int Cost(CardModel card)
    {
        return card.EnergyCost.GetWithModifiers(CostModifiers.None);
    }

    private static void EnsureRuntimeDependency(string assemblyName)
    {
        if (AppDomain.CurrentDomain.GetAssemblies().Any(
                assembly => string.Equals(assembly.GetName().Name, assemblyName, StringComparison.Ordinal)))
        {
            return;
        }

        string path = FindRuntimeDependencyPath(assemblyName)
            ?? throw new FileNotFoundException($"Could not locate {assemblyName}.dll.");
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
        string? assemblyDirectory = Path.GetDirectoryName(typeof(ThingsSplitProbeNode).Assembly.Location);
        string[] candidates =
        [
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", "Debug", $"{assemblyName}.dll"),
            Path.Combine(projectRoot, ".godot", "mono", "temp", "bin", "Release", $"{assemblyName}.dll"),
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
}

internal sealed class ProbeThirdPartyDynamicVar(string name, decimal value)
    : DynamicVar(name, value);

internal sealed class ProbeUpgradeException : Exception;

internal sealed class CapturingCardSelector : ICardSelector
{
    public IReadOnlyList<CardModel> Options { get; private set; } = Array.Empty<CardModel>();

    public Task<IEnumerable<CardModel>> GetSelectedCards(
        IEnumerable<CardModel> options,
        int minSelect,
        int maxSelect)
    {
        Options = options.ToArray();
        return Task.FromResult<IEnumerable<CardModel>>(Array.Empty<CardModel>());
    }

    public CardRewardSelection GetSelectedCardReward(
        IReadOnlyList<CardCreationResult> options,
        IReadOnlyList<MegaCrit.Sts2.Core.Entities.CardRewardAlternatives.CardRewardAlternative> alternatives)
    {
        return default;
    }
}
