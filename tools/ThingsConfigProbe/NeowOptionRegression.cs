using System.Reflection;
using Godot;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Models.Modifiers;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Modifiers;
using STS2_Things.Config;
using STS2_Things.Relics;

internal static class NeowOptionRegression
{
    public static async Task Run()
    {
        string nativePck = System.Environment.GetEnvironmentVariable("STS2_NEOW_NATIVE_PCK")
            ?? throw new InvalidOperationException("STS2_NEOW_NATIVE_PCK must name the native game pack.");
        Require(ProjectSettings.LoadResourcePack(nativePck, replaceFiles: false), "Native localization pack did not load.");
        SaveManager.Instance.InitSettingsDataForTest();
        SaveManager.Instance.InitPrefsDataForTest();
        SaveManager.Instance.SettingsSave.Language = "eng";
        LocManager.Initialize();
        Player player = Player.CreateForNewRun<Ironclad>(UnlockState.all, 1);
        RunState run = RunState.CreateForTest([player], seed: "NEOW_CROSSROADS_REGRESSION");
        Require(run.Modifiers.OfType<ThingsCrossroads>().Count() == 1,
            "Normal run creation must attach the saved crossroads ledger.");
        var neow = (Neow)ModelDb.Event<Neow>().ToMutable();
        MethodInfo begin = typeof(EventModel).GetMethods(BindingFlags.Public | BindingFlags.Instance)
            .Single(method => method.Name == nameof(EventModel.BeginEvent));
        object?[] args = begin.GetParameters().Select(parameter => parameter.ParameterType == typeof(Player)
            ? (object)player : parameter.ParameterType == typeof(bool) ? false : null).ToArray();
        await (Task)begin.Invoke(neow, args)!;
        GD.Print($"NEOW_OPTIONS modifiers={string.Join(',', run.Modifiers.Select(m => m.Id))} " +
                 $"choices={neow.CurrentOptions.Count} relics={neow.CurrentOptions.Count(o => o.Relic != null)} finished={neow.IsFinished}");
        Require(neow.CurrentOptions.Count == 3 && neow.CurrentOptions.All(option => option.Relic != null),
            "NEOW_OPTIONS_MISSING: a standard run must offer three starting relic choices, not only Proceed.");
        Require(!neow.IsFinished, "Neow must wait for a relic choice.");

        int checkedChoices = 1;
        string[] configKeys = [ThingsModConfig.NeowRelicCurseRemoverEnabled,
            ThingsModConfig.NeowRelicWhiteFlagEnabled, ThingsModConfig.NeowRelicMagicGloveEnabled];
        Type[] relicTypes = [typeof(ThingsCurseRemover), typeof(ThingsWhiteFlag), typeof(ThingsMagicGlove)];
        try
        {
            // Compare against the real native event without the internal ledger.
            // Each player's RNG and the configured relic pool must remain identical.
            foreach (int mask in Enumerable.Range(0, 8))
            foreach (int players in new[] { 1, 4 })
            {
                for (int i = 0; i < configKeys.Length; i++)
                    ThingsModConfig.SetValue(configKeys[i], (mask & (1 << i)) != 0);
                var withLedger = CreateRun(players, $"neow-{mask}-{players}");
                var native = CreateRun(players, $"neow-{mask}-{players}");
                typeof(RunState).GetProperty(nameof(RunState.Modifiers))!.SetValue(native, Array.Empty<ModifierModel>());
                foreach (int slot in Enumerable.Range(0, players))
                {
                    Neow actual = await Start(withLedger.Players[slot]);
                    Neow expected = await Start(native.Players[slot]);
                    Require(actual.CurrentOptions.Count == 3 && !actual.IsFinished,
                        $"Starting choices missing for mask={mask}, players={players}, slot={slot}.");
                    Require(actual.CurrentOptions.Select(o => o.Relic?.Id).SequenceEqual(expected.CurrentOptions.Select(o => o.Relic?.Id)),
                        "The route ledger changed the native seeded relic selection.");
                    Require(actual.InitialDescription.LocEntryKey == expected.InitialDescription.LocEntryKey,
                        "The route ledger selected the custom-run greeting.");
                    var pool = actual.AllPossibleOptions.Select(o => o.Relic?.GetType()).ToArray();
                    for (int i = 0; i < relicTypes.Length; i++)
                        Require(pool.Contains(relicTypes[i]) == ((mask & (1 << i)) != 0),
                            $"Neow relic switch failed: {configKeys[i]}.");
                    checkedChoices++;
                }
                Require(withLedger.Modifiers.OfType<ThingsCrossroads>().Count() == 1,
                    "Generating Neow options removed the saved route ledger.");
            }

            // Genuine custom rules must retain their original Neow branch, even
            // when a rule itself does not offer a Neow choice (Vintage).
            foreach (ModifierModel rule in new ModifierModel[] { ModelDb.Modifier<Specialized>(), ModelDb.Modifier<Vintage>() })
            {
                var withLedger = CreateRun(1, "neow-custom", rule.ToMutable());
                var native = CreateRun(1, "neow-custom", rule.ToMutable());
                typeof(RunState).GetProperty(nameof(RunState.Modifiers))!.SetValue(native,
                    native.Modifiers.Where(m => m is not ThingsCrossroads).ToArray());
                Neow actual = await Start(withLedger.Players[0]);
                Neow expected = await Start(native.Players[0]);
                Require(actual.CurrentOptions.Select(o => o.TextKey).SequenceEqual(expected.CurrentOptions.Select(o => o.TextKey)) &&
                    actual.IsFinished == expected.IsFinished && actual.InitialDescription.LocEntryKey == expected.InitialDescription.LocEntryKey,
                    $"Real custom-rule behavior changed: {rule.Id}.");
                checkedChoices++;
            }

            var restoredLedger = (ThingsCrossroads)ModifierModel.FromSerializable(run.Modifiers.Single().ToSerializable());
            var restoredRun = CreateRun(1, "neow-restored", restoredLedger);
            string savedData = restoredLedger.Data;
            Neow restored = await Start(restoredRun.Players[0]);
            Require(restored.CurrentOptions.Count == 3 && !restored.IsFinished && restoredLedger.Data == savedData,
                "A deserialized ledger suppressed Neow or was changed by option generation.");
            checkedChoices++;
        }
        finally
        {
            foreach (string key in configKeys) ThingsModConfig.SetValue(key, true);
        }
        GD.Print($"NEOW_REGRESSION_PASS cases={checkedChoices}; native choices, 1/4 players, 8 relic-switch combinations, custom rules, restored ledger");
    }

    private static RunState CreateRun(int players, string seed, params ModifierModel[] modifiers) =>
        RunState.CreateForTest(Enumerable.Range(1, players)
            .Select(i => Player.CreateForNewRun<Ironclad>(UnlockState.all, (ulong)i)).ToArray(),
            modifiers: modifiers, seed: seed);

    private static async Task<Neow> Start(Player player)
    {
        var neow = (Neow)ModelDb.Event<Neow>().ToMutable();
        MethodInfo begin = typeof(EventModel).GetMethods(BindingFlags.Public | BindingFlags.Instance)
            .Single(method => method.Name == nameof(EventModel.BeginEvent));
        object?[] args = begin.GetParameters().Select(parameter => parameter.ParameterType == typeof(Player)
            ? (object)player : parameter.ParameterType == typeof(bool) ? false : null).ToArray();
        await (Task)begin.Invoke(neow, args)!;
        return neow;
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
}
