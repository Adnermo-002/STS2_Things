using System.Globalization;
using System.Reflection;
using System.Text;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Localization.DynamicVars;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Saves.Runs;

namespace STS2_Things.Enchantments;

/// <summary>
/// Splits a card's fixed energy/star costs and known numeric gameplay values in half.
/// Costs round down and numeric values round up.
/// </summary>
public sealed class ThingsSplit : EnchantmentModel
{
    private const decimal DynamicVarMaximum = 999999999m;
    private const string SerializedStateVersion = "2";

    private static readonly Type[] KnownNumericDynamicVarBaseTypes =
    [
        typeof(BlockVar),
        typeof(CalculationBaseVar),
        typeof(CalculationExtraVar),
        typeof(CardsVar),
        typeof(DamageVar),
        typeof(EnergyVar),
        typeof(ExtraDamageVar),
        typeof(ForgeVar),
        typeof(GoldVar),
        typeof(HealVar),
        typeof(HpLossVar),
        typeof(IntVar),
        typeof(MaxHpVar),
        typeof(OstyDamageVar),
        typeof(RepeatVar),
        typeof(StarsVar),
        typeof(SummonVar)
    ];

    private static readonly MethodInfo BaseStarCostSetter =
        AccessTools.PropertySetter(typeof(CardModel), nameof(CardModel.BaseStarCost)) ??
        throw new MissingMethodException(typeof(CardModel).FullName,
            $"set_{nameof(CardModel.BaseStarCost)}");

    private Dictionary<string, decimal>? _unsplitDynamicValues;
    private int? _unsplitEnergyCost;
    private int? _unsplitStarCost;
    private int _internalWriteDepth;
    private DowngradeMutation? _pendingDowngrade;
    private DynamicUpgradeMutation? _pendingDynamicUpgrade;
    private EnergyUpgradeMutation? _pendingEnergyUpgrade;
    private StarUpgradeMutation? _pendingStarUpgrade;
    private SplitSerializedState? _pendingSerializedState;

    static ThingsSplit()
    {
#if STS2_V107_1
        // V107.1 builds its saved-property owner cache before mod models are
        // discovered. Register this owner when the model type is first created.
        SavedPropertiesTypeCache.InjectTypeIntoCache(typeof(ThingsSplit));
#endif
    }

    /// <summary>
    /// Persists both the logical unsplit baseline and the currently visible
    /// split values. The latter matters for cards that permanently grow after
    /// being split: their growth applies to the half-card, not to a temporarily
    /// restored full card.
    /// </summary>
    [SavedProperty]
    public string SplitState
    {
        get => SerializeSplitState();
        set
        {
            AssertMutable();
            _pendingSerializedState = TryDeserializeSplitState(value);
        }
    }

    public override bool CanEnchant(CardModel card)
    {
        return base.CanEnchant(card) && HasFixedEnergyCost(card) && !card.HasStarCostX;
    }

    protected override void OnEnchant()
    {
        if (_pendingDowngrade != null)
        {
            CompleteDowngradeTransition();
            return;
        }

        // Initial application and the pre-upgrade phase of deserialization both
        // arrive here without an active snapshot. Clones already carry a deep
        // copy of their snapshot and ModifyCard is intentionally not called for
        // them by the base game.
        if (_unsplitDynamicValues == null)
        {
            CaptureCurrentValuesAsUnsplit();
            ApplySplitValues();
        }
    }

    protected override void DeepCloneFields()
    {
        base.DeepCloneFields();
        _unsplitDynamicValues = _unsplitDynamicValues == null
            ? null
            : new Dictionary<string, decimal>(_unsplitDynamicValues, StringComparer.Ordinal);
        _internalWriteDepth = 0;
        _pendingDowngrade = null;
        _pendingDynamicUpgrade = null;
        _pendingEnergyUpgrade = null;
        _pendingStarUpgrade = null;
        _pendingSerializedState = null;
    }

    private static bool IsKnownGameplayNumericVar(DynamicVar value)
    {
        Type type = value.GetType();
        if (value is StringVar or BoolVar or IfUpgradedVar or CalculatedVar)
        {
            return false;
        }

        // A plain DynamicVar is the game's general-purpose numeric variable.
        // Subclasses are accepted only through an explicitly numeric base type;
        // this safely supports other mods' DamageVar/IntVar/etc. subclasses
        // without treating arbitrary text, boolean, conditional or calculated
        // variables as values that should be split.
        if (type == typeof(DynamicVar) ||
            KnownNumericDynamicVarBaseTypes.Any(baseType => baseType.IsAssignableFrom(type)))
        {
            return true;
        }

        for (Type? current = type; current != null; current = current.BaseType)
        {
            if (current.IsGenericType &&
                current.GetGenericTypeDefinition() == typeof(PowerVar<>))
            {
                return true;
            }
        }

        return false;
    }

    private static bool HasFixedEnergyCost(CardModel card)
    {
        return !card.EnergyCost.CostsX &&
               card.EnergyCost.GetWithModifiers(CostModifiers.None) >= 0;
    }

    private static decimal SplitDynamicValue(decimal value)
    {
        return decimal.Ceiling(value / 2m);
    }

    private static int SplitEnergyCost(int value)
    {
        return value < 0 ? value : value / 2;
    }

    private static ThingsSplit? GetSplit(AbstractModel? owner)
    {
        return owner is CardModel card ? card.Enchantment as ThingsSplit : null;
    }

    private void EnsureUnsplitSnapshot()
    {
        if (_unsplitDynamicValues == null)
        {
            CaptureCurrentValuesAsUnsplit();
        }
    }

    private void CaptureCurrentValuesAsUnsplit()
    {
        CaptureCurrentDynamicValuesAsUnsplit();
        _unsplitEnergyCost = Card.EnergyCost.CostsX
            ? null
            : Card.EnergyCost.GetWithModifiers(CostModifiers.None);
        _unsplitStarCost = Card.HasStarCostX || Card.BaseStarCost < 0
            ? null
            : Card.BaseStarCost;
    }

    private void CaptureCurrentDynamicValuesAsUnsplit()
    {
        _unsplitDynamicValues = Card.DynamicVars.Values
            .Where(IsKnownGameplayNumericVar)
            .ToDictionary(value => value.Name, value => value.BaseValue, StringComparer.Ordinal);
    }

    private void RestoreUnsplitValues()
    {
        EnsureUnsplitSnapshot();
        RunInternalWrite(() =>
        {
            foreach (DynamicVar value in Card.DynamicVars.Values)
            {
                if (_unsplitDynamicValues!.TryGetValue(value.Name, out decimal unsplitValue) &&
                    IsKnownGameplayNumericVar(value))
                {
                    value.BaseValue = unsplitValue;
                }
            }

            Card.DynamicVars.RecalculateForUpgradeOrEnchant();
            if (_unsplitEnergyCost.HasValue && !Card.EnergyCost.CostsX)
            {
                Card.EnergyCost.SetCustomBaseCost(_unsplitEnergyCost.Value);
            }

            if (_unsplitStarCost.HasValue && !Card.HasStarCostX)
            {
                SetBaseStarCost(Card, _unsplitStarCost.Value);
            }
        });
    }

    private void ApplySplitValues()
    {
        RunInternalWrite(() =>
        {
            ApplySplitDynamicValuesCore();
            if (_unsplitEnergyCost.HasValue && !Card.EnergyCost.CostsX)
            {
                Card.EnergyCost.SetCustomBaseCost(SplitEnergyCost(_unsplitEnergyCost.Value));
            }

            if (_unsplitStarCost.HasValue && !Card.HasStarCostX)
            {
                SetBaseStarCost(Card, SplitEnergyCost(_unsplitStarCost.Value));
            }
        });
    }

    private static void SetBaseStarCost(CardModel card, int value)
    {
        BaseStarCostSetter.Invoke(card, [value]);
    }

    private void ApplySplitDynamicValuesCore()
    {
        foreach (DynamicVar value in Card.DynamicVars.Values)
        {
            if (_unsplitDynamicValues!.TryGetValue(value.Name, out decimal unsplitValue) &&
                IsKnownGameplayNumericVar(value))
            {
                value.BaseValue = SplitDynamicValue(unsplitValue);
            }
        }

        Card.DynamicVars.RecalculateForUpgradeOrEnchant();
    }

    private void RunInternalWrite(Action action)
    {
        _internalWriteDepth++;
        try
        {
            action();
        }
        finally
        {
            _internalWriteDepth--;
        }
    }

    private void BeforeDynamicBaseValueWrite(DynamicVar value, decimal newValue)
    {
        if (_internalWriteDepth > 0 || _pendingDowngrade != null ||
            !IsKnownGameplayNumericVar(value))
        {
            return;
        }

        if (_pendingDynamicUpgrade?.Value == value)
        {
            _pendingDynamicUpgrade.WriteConsumed = true;
            return;
        }

        EnsureUnsplitSnapshot();
        if (_unsplitDynamicValues!.TryGetValue(value.Name, out decimal unsplitValue))
        {
            decimal clampedNewValue = decimal.Min(newValue, DynamicVarMaximum);
            _unsplitDynamicValues[value.Name] = unsplitValue + clampedNewValue - value.BaseValue;
        }
    }

    private FullValueSetterMutation? PrepareFullValueSetter(
        string dynamicVarName,
        decimal intendedFullValue)
    {
        if (_internalWriteDepth > 0 || _pendingDowngrade != null)
        {
            return null;
        }

        EnsureUnsplitSnapshot();
        if (!_unsplitDynamicValues!.TryGetValue(dynamicVarName,
                out decimal previousUnsplitValue) ||
            !Card.DynamicVars.TryGetValue(dynamicVarName, out DynamicVar? value) ||
            !IsKnownGameplayNumericVar(value))
        {
            return null;
        }

        return new FullValueSetterMutation(
            this,
            value,
            dynamicVarName,
            previousUnsplitValue,
            value.BaseValue,
            decimal.Min(intendedFullValue, DynamicVarMaximum));
    }

    private static void CompleteFullValueSetter(FullValueSetterMutation? mutation)
    {
        if (mutation == null)
        {
            return;
        }

        ThingsSplit split = mutation.Split;
        // A few vanilla permanent-growth cards rebuild their value from an
        // unsplit hard-coded constant (for example The Scythe uses 13 + growth).
        // Preserve the growth that happened to the visible half-card while
        // retaining the rebuilt full value as the clear/downgrade baseline.
        decimal visibleValue = mutation.PreviousVisibleValue +
            mutation.IntendedFullValue - mutation.PreviousUnsplitValue;
        split.RunInternalWrite(() =>
        {
            split._unsplitDynamicValues![mutation.Name] = mutation.IntendedFullValue;
            mutation.Value.BaseValue = decimal.Min(visibleValue, DynamicVarMaximum);
            split.Card.DynamicVars.RecalculateForUpgradeOrEnchant();
        });
    }

    private decimal NormalizeStoredFullValue(string dynamicVarName, decimal visibleValue)
    {
        if (_internalWriteDepth > 0 || _pendingDowngrade != null)
        {
            return visibleValue;
        }

        EnsureUnsplitSnapshot();
        return _unsplitDynamicValues!.GetValueOrDefault(dynamicVarName, visibleValue);
    }

    private DynamicUpgradeMutation? PrepareDynamicUpgrade(DynamicVar value, ref decimal addend)
    {
        if (_internalWriteDepth > 0 || _pendingDowngrade != null ||
            _pendingDynamicUpgrade != null || !IsKnownGameplayNumericVar(value))
        {
            return null;
        }

        EnsureUnsplitSnapshot();
        if (!_unsplitDynamicValues!.TryGetValue(value.Name, out decimal oldUnsplitValue))
        {
            return null;
        }

        decimal newUnsplitValue = decimal.Min(oldUnsplitValue + addend, DynamicVarMaximum);
        decimal expectedVisibleValue = SplitDynamicValue(newUnsplitValue);
        var mutation = new DynamicUpgradeMutation(
            this,
            value,
            value.Name,
            oldUnsplitValue,
            expectedVisibleValue);
        _pendingDynamicUpgrade = mutation;
        _unsplitDynamicValues[value.Name] = newUnsplitValue;
        addend = expectedVisibleValue - value.BaseValue;
        return mutation;
    }

    private static void CompleteDynamicUpgrade(
        DynamicUpgradeMutation? mutation,
        Exception? exception)
    {
        if (mutation == null)
        {
            return;
        }

        ThingsSplit split = mutation.Split;
        if (!ReferenceEquals(split._pendingDynamicUpgrade, mutation))
        {
            return;
        }

        split._pendingDynamicUpgrade = null;
        if (!mutation.WriteConsumed ||
            (exception != null && mutation.Value.BaseValue != mutation.ExpectedVisibleValue))
        {
            split._unsplitDynamicValues![mutation.Name] = mutation.PreviousUnsplitValue;
        }
    }

    private void BeforeCustomEnergyCostWrite(CardEnergyCost energyCost, int newBaseCost)
    {
        if (_internalWriteDepth > 0 || _pendingDowngrade != null)
        {
            return;
        }

        if (_pendingEnergyUpgrade != null)
        {
            _pendingEnergyUpgrade.WriteConsumed = true;
            return;
        }

        EnsureUnsplitSnapshot();
        if (_unsplitEnergyCost.HasValue)
        {
            int oldVisibleCost = energyCost.GetWithModifiers(CostModifiers.None);
            _unsplitEnergyCost += newBaseCost - oldVisibleCost;
        }
    }

    private EnergyUpgradeMutation? PrepareEnergyUpgrade(
        CardEnergyCost energyCost,
        ref int addend)
    {
        if (_internalWriteDepth > 0 || _pendingDowngrade != null ||
            _pendingEnergyUpgrade != null || energyCost.CostsX || addend == 0)
        {
            return null;
        }

        EnsureUnsplitSnapshot();
        if (!_unsplitEnergyCost.HasValue)
        {
            return null;
        }

        int oldUnsplitCost = _unsplitEnergyCost.Value;
        int oldVisibleCost = energyCost.GetWithModifiers(CostModifiers.None);
        int newUnsplitCost = Math.Max(oldUnsplitCost + addend, 0);
        int expectedVisibleCost = SplitEnergyCost(newUnsplitCost);
        var mutation = new EnergyUpgradeMutation(
            this,
            energyCost,
            oldUnsplitCost,
            oldVisibleCost,
            expectedVisibleCost);
        _pendingEnergyUpgrade = mutation;
        _unsplitEnergyCost = newUnsplitCost;
        addend = expectedVisibleCost - oldVisibleCost;
        return mutation;
    }

    private static void CompleteEnergyUpgrade(
        EnergyUpgradeMutation? mutation,
        Exception? exception)
    {
        if (mutation == null)
        {
            return;
        }

        ThingsSplit split = mutation.Split;
        if (!ReferenceEquals(split._pendingEnergyUpgrade, mutation))
        {
            return;
        }

        split._pendingEnergyUpgrade = null;
        int actualCost = mutation.EnergyCost.GetWithModifiers(CostModifiers.None);
        if (actualCost != mutation.ExpectedVisibleCost)
        {
            split._unsplitEnergyCost = mutation.PreviousUnsplitCost;
        }
    }

    private void BeforeBaseStarCostWrite(int newBaseCost)
    {
        if (_internalWriteDepth > 0 || _pendingDowngrade != null || Card.HasStarCostX)
        {
            return;
        }

        if (_pendingStarUpgrade != null)
        {
            _pendingStarUpgrade.WriteConsumed = true;
            return;
        }

        EnsureUnsplitSnapshot();
        if (_unsplitStarCost.HasValue)
        {
            _unsplitStarCost += newBaseCost - Card.BaseStarCost;
        }
    }

    private StarUpgradeMutation? PrepareStarUpgrade(ref int addend)
    {
        if (_internalWriteDepth > 0 || _pendingDowngrade != null ||
            _pendingStarUpgrade != null || Card.HasStarCostX || addend == 0)
        {
            return null;
        }

        EnsureUnsplitSnapshot();
        if (!_unsplitStarCost.HasValue)
        {
            return null;
        }

        int oldUnsplitCost = _unsplitStarCost.Value;
        int oldVisibleCost = Card.BaseStarCost;
        int newUnsplitCost = oldUnsplitCost + addend;
        int expectedVisibleCost = SplitEnergyCost(newUnsplitCost);
        var mutation = new StarUpgradeMutation(
            this,
            oldUnsplitCost,
            oldVisibleCost,
            expectedVisibleCost);
        _pendingStarUpgrade = mutation;
        _unsplitStarCost = newUnsplitCost;
        addend = expectedVisibleCost - oldVisibleCost;
        return mutation;
    }

    private static void CompleteStarUpgrade(
        StarUpgradeMutation? mutation,
        Exception? exception)
    {
        if (mutation == null)
        {
            return;
        }

        ThingsSplit split = mutation.Split;
        if (!ReferenceEquals(split._pendingStarUpgrade, mutation))
        {
            return;
        }

        split._pendingStarUpgrade = null;
        int actualCost = split.Card.BaseStarCost;
        if (actualCost != mutation.ExpectedVisibleCost)
        {
            split._unsplitStarCost = mutation.PreviousUnsplitCost;
        }
    }

    private void BeginDowngrade()
    {
        if (_internalWriteDepth > 0 || _pendingDowngrade != null || !HasCard)
        {
            return;
        }

        EnsureUnsplitSnapshot();
        var visibleDynamicValues = Card.DynamicVars.Values
            .Where(IsKnownGameplayNumericVar)
            .ToDictionary(value => value.Name, value => value.BaseValue,
                StringComparer.Ordinal);
        _pendingDowngrade = new DowngradeMutation(
            new Dictionary<string, decimal>(_unsplitDynamicValues!, StringComparer.Ordinal),
            visibleDynamicValues,
            _unsplitEnergyCost,
            Card.EnergyCost.CostsX
                ? null
                : Card.EnergyCost.GetWithModifiers(CostModifiers.None),
            _unsplitStarCost,
            Card.HasStarCostX || Card.BaseStarCost < 0 ? null : Card.BaseStarCost);
    }

    private void CompleteDowngradeTransition()
    {
        DowngradeMutation? mutation = _pendingDowngrade;
        if (mutation == null || !HasCard)
        {
            return;
        }

        var postDowngradeDynamicValues = Card.DynamicVars.Values
            .Where(IsKnownGameplayNumericVar)
            .ToDictionary(value => value.Name, value => value.BaseValue,
                StringComparer.Ordinal);
        int? postDowngradeEnergyCost = Card.EnergyCost.CostsX
            ? null
            : Card.EnergyCost.GetWithModifiers(CostModifiers.None);
        int? postDowngradeStarCost = Card.HasStarCostX || Card.BaseStarCost < 0
            ? null
            : Card.BaseStarCost;

        RunInternalWrite(() =>
        {
            foreach (DynamicVar value in Card.DynamicVars.Values)
            {
                if (!IsKnownGameplayNumericVar(value) ||
                    !postDowngradeDynamicValues.TryGetValue(value.Name,
                        out decimal postDowngradeValue))
                {
                    continue;
                }

                decimal visibleValue = SplitDynamicValue(postDowngradeValue);
                if (mutation.VisibleDynamicValues.TryGetValue(value.Name,
                        out decimal previousVisibleValue) &&
                    mutation.UnsplitDynamicValues.TryGetValue(value.Name,
                        out decimal previousUnsplitValue))
                {
                    // Remove only the split contribution that disappeared during
                    // downgrade. Permanent growth already applied to the visible
                    // half-card remains untouched.
                    visibleValue = previousVisibleValue +
                        SplitDynamicValue(postDowngradeValue) -
                        SplitDynamicValue(previousUnsplitValue);
                }

                value.BaseValue = visibleValue;
            }

            _unsplitDynamicValues = postDowngradeDynamicValues;
            Card.DynamicVars.RecalculateForUpgradeOrEnchant();

            _unsplitEnergyCost = postDowngradeEnergyCost;
            if (postDowngradeEnergyCost.HasValue)
            {
                int visibleEnergyCost = SplitEnergyCost(postDowngradeEnergyCost.Value);
                if (mutation.VisibleEnergyCost.HasValue &&
                    mutation.UnsplitEnergyCost.HasValue)
                {
                    visibleEnergyCost = mutation.VisibleEnergyCost.Value +
                        SplitEnergyCost(postDowngradeEnergyCost.Value) -
                        SplitEnergyCost(mutation.UnsplitEnergyCost.Value);
                }

                Card.EnergyCost.SetCustomBaseCost(visibleEnergyCost);
            }

            _unsplitStarCost = postDowngradeStarCost;
            if (postDowngradeStarCost.HasValue)
            {
                int visibleStarCost = SplitEnergyCost(postDowngradeStarCost.Value);
                if (mutation.VisibleStarCost.HasValue && mutation.UnsplitStarCost.HasValue)
                {
                    visibleStarCost = mutation.VisibleStarCost.Value +
                        SplitEnergyCost(postDowngradeStarCost.Value) -
                        SplitEnergyCost(mutation.UnsplitStarCost.Value);
                }

                SetBaseStarCost(Card, visibleStarCost);
            }
        });

        _pendingDowngrade = null;
    }

    private void CompleteDowngrade(Exception? exception)
    {
        DowngradeMutation? mutation = _pendingDowngrade;
        if (mutation == null)
        {
            return;
        }

        if (exception == null)
        {
            CompleteDowngradeTransition();
            return;
        }

        // If vanilla or another mod aborts the downgrade midway, keep the
        // enchantment's paired visible/unsplit state coherent. Restoration is
        // best-effort so an original exception is never masked by cleanup.
        try
        {
            RunInternalWrite(() =>
            {
                foreach (DynamicVar value in Card.DynamicVars.Values)
                {
                    if (IsKnownGameplayNumericVar(value) &&
                        mutation.VisibleDynamicValues.TryGetValue(value.Name,
                            out decimal visibleValue))
                    {
                        value.BaseValue = visibleValue;
                    }
                }

                _unsplitDynamicValues = new Dictionary<string, decimal>(
                    mutation.UnsplitDynamicValues, StringComparer.Ordinal);
                Card.DynamicVars.RecalculateForUpgradeOrEnchant();
                _unsplitEnergyCost = mutation.UnsplitEnergyCost;
                if (mutation.VisibleEnergyCost.HasValue && !Card.EnergyCost.CostsX)
                {
                    Card.EnergyCost.SetCustomBaseCost(mutation.VisibleEnergyCost.Value);
                }

                _unsplitStarCost = mutation.UnsplitStarCost;
                if (mutation.VisibleStarCost.HasValue && !Card.HasStarCostX)
                {
                    SetBaseStarCost(Card, mutation.VisibleStarCost.Value);
                }
            });
        }
        catch
        {
            // Preserve the exception that interrupted CardModel.DowngradeInternal.
        }
        finally
        {
            _pendingDowngrade = null;
        }
    }

    private void ApplyPendingSerializedState()
    {
        SplitSerializedState? state = _pendingSerializedState;
        if (state == null || !HasCard)
        {
            return;
        }

        RunInternalWrite(() =>
        {
            // Begin with values known by the currently running game/mod set,
            // then overlay saved names. A save made before a game update must
            // not erase newly introduced DynamicVars from the snapshot.
            var mergedUnsplitValues = new Dictionary<string, decimal>(
                StringComparer.Ordinal);
            foreach (DynamicVar value in Card.DynamicVars.Values)
            {
                if (!IsKnownGameplayNumericVar(value))
                {
                    continue;
                }

                decimal currentUnsplitValue =
                    _unsplitDynamicValues?.GetValueOrDefault(value.Name, value.BaseValue) ??
                    value.BaseValue;
                mergedUnsplitValues[value.Name] =
                    state.UnsplitDynamicValues.GetValueOrDefault(
                        value.Name, currentUnsplitValue);
                if (state.VisibleDynamicValues.TryGetValue(value.Name,
                        out decimal visibleValue))
                {
                    value.BaseValue = visibleValue;
                }
            }

            _unsplitDynamicValues = mergedUnsplitValues;
            Card.DynamicVars.RecalculateForUpgradeOrEnchant();
            _unsplitEnergyCost = state.UnsplitEnergyCost;
            if (state.VisibleEnergyCost.HasValue && !Card.EnergyCost.CostsX)
            {
                Card.EnergyCost.SetCustomBaseCost(state.VisibleEnergyCost.Value);
            }

            if (state.HasStarCostState)
            {
                _unsplitStarCost = state.UnsplitStarCost;
                if (state.VisibleStarCost.HasValue && !Card.HasStarCostX)
                {
                    SetBaseStarCost(Card, state.VisibleStarCost.Value);
                }
            }
        });
        _pendingSerializedState = null;
    }

    private string SerializeSplitState()
    {
        if (!HasCard || _unsplitDynamicValues == null)
        {
            return string.Empty;
        }

        var entries = new List<string>();
        foreach ((string name, decimal unsplitValue) in
                 _unsplitDynamicValues.OrderBy(pair => pair.Key, StringComparer.Ordinal))
        {
            if (!Card.DynamicVars.TryGetValue(name, out DynamicVar? value) ||
                !IsKnownGameplayNumericVar(value))
            {
                continue;
            }

            string encodedName = Convert.ToBase64String(Encoding.UTF8.GetBytes(name));
            entries.Add(string.Join(",",
                encodedName,
                unsplitValue.ToString("G29", CultureInfo.InvariantCulture),
                value.BaseValue.ToString("G29", CultureInfo.InvariantCulture)));
        }

        string unsplitEnergyCost =
            _unsplitEnergyCost?.ToString(CultureInfo.InvariantCulture) ?? string.Empty;
        string visibleEnergyCost = Card.EnergyCost.CostsX
            ? string.Empty
            : Card.EnergyCost.GetWithModifiers(CostModifiers.None)
                .ToString(CultureInfo.InvariantCulture);
        string unsplitStarCost =
            _unsplitStarCost?.ToString(CultureInfo.InvariantCulture) ?? string.Empty;
        string visibleStarCost = Card.HasStarCostX || Card.BaseStarCost < 0
            ? string.Empty
            : Card.BaseStarCost.ToString(CultureInfo.InvariantCulture);
        return string.Join("|", SerializedStateVersion,
            unsplitEnergyCost, visibleEnergyCost,
            unsplitStarCost, visibleStarCost,
            string.Join(";", entries));
    }

    private static SplitSerializedState? TryDeserializeSplitState(string? serialized)
    {
        if (string.IsNullOrEmpty(serialized))
        {
            return null;
        }

        string[] sections = serialized.Split('|');
        bool isVersion1 = sections.Length == 4 &&
            string.Equals(sections[0], "1", StringComparison.Ordinal);
        bool isVersion2 = sections.Length == 6 &&
            string.Equals(sections[0], SerializedStateVersion, StringComparison.Ordinal);
        if (!isVersion1 && !isVersion2)
        {
            return null;
        }

        int? unsplitEnergyCost = ParseNullableInt(sections[1]);
        int? visibleEnergyCost = ParseNullableInt(sections[2]);
        if ((sections[1].Length > 0 && !unsplitEnergyCost.HasValue) ||
            (sections[2].Length > 0 && !visibleEnergyCost.HasValue))
        {
            return null;
        }

        int? unsplitStarCost = null;
        int? visibleStarCost = null;
        int entriesSectionIndex = 3;
        if (isVersion2)
        {
            unsplitStarCost = ParseNullableInt(sections[3]);
            visibleStarCost = ParseNullableInt(sections[4]);
            if ((sections[3].Length > 0 && !unsplitStarCost.HasValue) ||
                (sections[4].Length > 0 && !visibleStarCost.HasValue))
            {
                return null;
            }

            entriesSectionIndex = 5;
        }

        var unsplitValues = new Dictionary<string, decimal>(StringComparer.Ordinal);
        var visibleValues = new Dictionary<string, decimal>(StringComparer.Ordinal);
        if (sections[entriesSectionIndex].Length > 0)
        {
            foreach (string entry in sections[entriesSectionIndex].Split(';'))
            {
                string[] fields = entry.Split(',');
                if (fields.Length != 3 || !TryDecodeName(fields[0], out string name) ||
                    !decimal.TryParse(fields[1], NumberStyles.Float,
                        CultureInfo.InvariantCulture, out decimal unsplitValue) ||
                    !decimal.TryParse(fields[2], NumberStyles.Float,
                        CultureInfo.InvariantCulture, out decimal visibleValue) ||
                    !unsplitValues.TryAdd(name, unsplitValue) ||
                    !visibleValues.TryAdd(name, visibleValue))
                {
                    return null;
                }
            }
        }

        return new SplitSerializedState(
            unsplitValues,
            visibleValues,
            unsplitEnergyCost,
            visibleEnergyCost,
            isVersion2,
            unsplitStarCost,
            visibleStarCost);
    }

    private static int? ParseNullableInt(string value)
    {
        if (value.Length == 0)
        {
            return null;
        }

        return int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture,
            out int parsed) ? parsed : null;
    }

    private static bool TryDecodeName(string encodedName, out string name)
    {
        try
        {
            name = Encoding.UTF8.GetString(Convert.FromBase64String(encodedName));
            return name.Length > 0;
        }
        catch (FormatException)
        {
            name = string.Empty;
            return false;
        }
    }

    private sealed class DynamicUpgradeMutation(
        ThingsSplit split,
        DynamicVar value,
        string name,
        decimal previousUnsplitValue,
        decimal expectedVisibleValue)
    {
        public ThingsSplit Split { get; } = split;
        public DynamicVar Value { get; } = value;
        public string Name { get; } = name;
        public decimal PreviousUnsplitValue { get; } = previousUnsplitValue;
        public decimal ExpectedVisibleValue { get; } = expectedVisibleValue;
        public bool WriteConsumed { get; set; }
    }

    private sealed class FullValueSetterMutation(
        ThingsSplit split,
        DynamicVar value,
        string name,
        decimal previousUnsplitValue,
        decimal previousVisibleValue,
        decimal intendedFullValue)
    {
        public ThingsSplit Split { get; } = split;
        public DynamicVar Value { get; } = value;
        public string Name { get; } = name;
        public decimal PreviousUnsplitValue { get; } = previousUnsplitValue;
        public decimal PreviousVisibleValue { get; } = previousVisibleValue;
        public decimal IntendedFullValue { get; } = intendedFullValue;
    }

    private sealed class EnergyUpgradeMutation(
        ThingsSplit split,
        CardEnergyCost energyCost,
        int previousUnsplitCost,
        int oldVisibleCost,
        int expectedVisibleCost)
    {
        public ThingsSplit Split { get; } = split;
        public CardEnergyCost EnergyCost { get; } = energyCost;
        public int PreviousUnsplitCost { get; } = previousUnsplitCost;
        public int OldVisibleCost { get; } = oldVisibleCost;
        public int ExpectedVisibleCost { get; } = expectedVisibleCost;
        public bool WriteConsumed { get; set; }
    }

    private sealed class StarUpgradeMutation(
        ThingsSplit split,
        int previousUnsplitCost,
        int oldVisibleCost,
        int expectedVisibleCost)
    {
        public ThingsSplit Split { get; } = split;
        public int PreviousUnsplitCost { get; } = previousUnsplitCost;
        public int OldVisibleCost { get; } = oldVisibleCost;
        public int ExpectedVisibleCost { get; } = expectedVisibleCost;
        public bool WriteConsumed { get; set; }
    }

    private sealed record DowngradeMutation(
        Dictionary<string, decimal> UnsplitDynamicValues,
        Dictionary<string, decimal> VisibleDynamicValues,
        int? UnsplitEnergyCost,
        int? VisibleEnergyCost,
        int? UnsplitStarCost,
        int? VisibleStarCost);

    private sealed record SplitSerializedState(
        Dictionary<string, decimal> UnsplitDynamicValues,
        Dictionary<string, decimal> VisibleDynamicValues,
        int? UnsplitEnergyCost,
        int? VisibleEnergyCost,
        bool HasStarCostState,
        int? UnsplitStarCost,
        int? VisibleStarCost);

    [HarmonyPatch(typeof(DynamicVar), nameof(DynamicVar.BaseValue), MethodType.Setter)]
    private static class DynamicVarBaseValuePatch
    {
        [HarmonyPrefix]
        [HarmonyPriority(Priority.Last)]
        private static void Prefix(
            DynamicVar __instance,
            AbstractModel? ____owner,
            [HarmonyArgument(0)] decimal value)
        {
            GetSplit(____owner)?.BeforeDynamicBaseValueWrite(__instance, value);
        }
    }

    [HarmonyPatch(typeof(DynamicVar), nameof(DynamicVar.UpgradeValueBy))]
    private static class DynamicVarUpgradePatch
    {
        [HarmonyPrefix]
        [HarmonyPriority(Priority.Last)]
        private static void Prefix(
            DynamicVar __instance,
            AbstractModel? ____owner,
            [HarmonyArgument(0)] ref decimal addend,
            out DynamicUpgradeMutation? __state)
        {
            __state = GetSplit(____owner)?.PrepareDynamicUpgrade(__instance, ref addend);
        }

        [HarmonyFinalizer]
        private static Exception? Finalizer(
            DynamicUpgradeMutation? __state,
            Exception? __exception)
        {
            CompleteDynamicUpgrade(__state, __exception);
            return __exception;
        }
    }

    [HarmonyPatch(typeof(TheScythe), "CurrentDamage", MethodType.Setter)]
    private static class TheScytheCurrentDamagePatch
    {
        [HarmonyPrefix]
        [HarmonyPriority(Priority.First)]
        private static void Prefix(
            TheScythe __instance,
            [HarmonyArgument(0)] int value,
            out FullValueSetterMutation? __state)
        {
            __state = (__instance.Enchantment as ThingsSplit)?
                .PrepareFullValueSetter("Damage", value);
        }

        [HarmonyPostfix]
        private static void Postfix(FullValueSetterMutation? __state)
        {
            CompleteFullValueSetter(__state);
        }
    }

    [HarmonyPatch(typeof(GeneticAlgorithm), "CurrentBlock", MethodType.Setter)]
    private static class GeneticAlgorithmCurrentBlockPatch
    {
        [HarmonyPrefix]
        [HarmonyPriority(Priority.First)]
        private static void Prefix(
            GeneticAlgorithm __instance,
            [HarmonyArgument(0)] int value,
            out FullValueSetterMutation? __state)
        {
            __state = (__instance.Enchantment as ThingsSplit)?
                .PrepareFullValueSetter("Block", value);
        }

        [HarmonyPostfix]
        private static void Postfix(FullValueSetterMutation? __state)
        {
            CompleteFullValueSetter(__state);
        }
    }

    [HarmonyPatch(typeof(SovereignBlade), "CurrentDamage", MethodType.Setter)]
    private static class SovereignBladeCurrentDamagePatch
    {
        [HarmonyPrefix]
        [HarmonyPriority(Priority.Last)]
        private static void Prefix(
            SovereignBlade __instance,
            [HarmonyArgument(0)] ref decimal value)
        {
            if (__instance.Enchantment is ThingsSplit split)
            {
                value = split.NormalizeStoredFullValue("Damage", value);
            }
        }
    }

    [HarmonyPatch(typeof(SovereignBlade), "CurrentRepeats", MethodType.Setter)]
    private static class SovereignBladeCurrentRepeatsPatch
    {
        [HarmonyPrefix]
        [HarmonyPriority(Priority.Last)]
        private static void Prefix(
            SovereignBlade __instance,
            [HarmonyArgument(0)] ref decimal value)
        {
            if (__instance.Enchantment is ThingsSplit split)
            {
                value = split.NormalizeStoredFullValue("Repeat", value);
            }
        }
    }

    [HarmonyPatch(typeof(CardEnergyCost), nameof(CardEnergyCost.UpgradeBy))]
    private static class EnergyCostUpgradePatch
    {
        [HarmonyPrefix]
        [HarmonyPriority(Priority.Last)]
        private static void Prefix(
            CardEnergyCost __instance,
            CardModel ____card,
            [HarmonyArgument(0)] ref int addend,
            out EnergyUpgradeMutation? __state)
        {
            __state = (____card.Enchantment as ThingsSplit)?
                .PrepareEnergyUpgrade(__instance, ref addend);
        }

        [HarmonyFinalizer]
        private static Exception? Finalizer(
            EnergyUpgradeMutation? __state,
            Exception? __exception)
        {
            CompleteEnergyUpgrade(__state, __exception);
            return __exception;
        }
    }

    [HarmonyPatch(typeof(CardEnergyCost), nameof(CardEnergyCost.SetCustomBaseCost))]
    private static class EnergyCostCustomBasePatch
    {
        [HarmonyPrefix]
        [HarmonyPriority(Priority.Last)]
        private static void Prefix(
            CardEnergyCost __instance,
            CardModel ____card,
            [HarmonyArgument(0)] int newBaseCost)
        {
            (____card.Enchantment as ThingsSplit)?
                .BeforeCustomEnergyCostWrite(__instance, newBaseCost);
        }
    }

    [HarmonyPatch(typeof(CardModel), nameof(CardModel.BaseStarCost), MethodType.Setter)]
    private static class BaseStarCostPatch
    {
        [HarmonyPrefix]
        [HarmonyPriority(Priority.Last)]
        private static void Prefix(
            CardModel __instance,
            [HarmonyArgument(0)] int value)
        {
            (__instance.Enchantment as ThingsSplit)?.BeforeBaseStarCostWrite(value);
        }
    }

    [HarmonyPatch(typeof(CardModel), "UpgradeStarCostBy")]
    private static class StarCostUpgradePatch
    {
        [HarmonyPrefix]
        [HarmonyPriority(Priority.Last)]
        private static void Prefix(
            CardModel __instance,
            [HarmonyArgument(0)] ref int addend,
            out StarUpgradeMutation? __state)
        {
            __state = (__instance.Enchantment as ThingsSplit)?
                .PrepareStarUpgrade(ref addend);
        }

        [HarmonyFinalizer]
        private static Exception? Finalizer(
            StarUpgradeMutation? __state,
            Exception? __exception)
        {
            CompleteStarUpgrade(__state, __exception);
            return __exception;
        }
    }

    [HarmonyPatch(typeof(CardModel), nameof(CardModel.ClearEnchantmentInternal))]
    private static class ClearEnchantmentPatch
    {
        [HarmonyPrefix]
        [HarmonyPriority(Priority.Last)]
        private static void Prefix(CardModel __instance)
        {
            (__instance.Enchantment as ThingsSplit)?.RestoreUnsplitValues();
        }
    }

    [HarmonyPatch(typeof(CardModel), nameof(CardModel.DowngradeInternal))]
    private static class CardDowngradePatch
    {
        [HarmonyPrefix]
        [HarmonyPriority(Priority.First)]
        private static void Prefix(CardModel __instance)
        {
            (__instance.Enchantment as ThingsSplit)?.BeginDowngrade();
        }

        [HarmonyFinalizer]
        private static Exception? Finalizer(CardModel __instance, Exception? __exception)
        {
            (__instance.Enchantment as ThingsSplit)?.CompleteDowngrade(__exception);
            return __exception;
        }
    }

    [HarmonyPatch(typeof(CardModel), nameof(CardModel.FromSerializable))]
    private static class CardDeserializationPatch
    {
        [HarmonyPostfix]
        [HarmonyPriority(Priority.First)]
        private static void Postfix(CardModel __result)
        {
            (__result.Enchantment as ThingsSplit)?.ApplyPendingSerializedState();
        }
    }
}
