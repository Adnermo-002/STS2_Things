using System.Reflection;
using System.Runtime.Loader;
using Godot;
using MegaCrit.Sts2.Core.Debug;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Events;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;

// Exercises the real ModManager against the exact workshop directory. There is
// deliberately no reference to an implementation DLL and no injected model list.
public partial class UnifiedStartupProbeNode : Node
{
    public override async void _Ready()
    {
        try
        {
            AssemblyLoadContext.Default.Resolving += ResolveDependency;
            TestMode.TurnOnInternal();
            string[] args = OS.GetCmdlineUserArgs();
            Require(args.Length >= 3, "Expected package directory, native PCK, and target.");
            Require(OS.GetUserDataDir().Contains("Things Unified Startup Probe", StringComparison.Ordinal),
                "Startup probe must use isolated user data.");
            Require(ProjectSettings.LoadResourcePack(args[1]), "Native resource pack failed to mount.");
            SaveManager.Instance.InitSettingsDataForTest();
            SaveManager.Instance.InitPrefsDataForTest();
            SaveManager.Instance.SettingsSave.Language = "eng";
            ModManager.ResetForTests();
            // V111 deliberately skips DLL/PCK loading in native test mode.
            // Keep real startup behavior until all initialization has completed.
            TestMode.IsOn = false;
            Require(SemanticVersion.TryFromString(args[2] == "v107.1" ? "v0.107.1" : "v0.111.0", out var version),
                "Invalid target version.");
            await ModManager.Initialize(new PackageFileIo(args[0]),
                new ModSettings { PlayerAgreedToModLoading = true }, version);
            var mods = ModManager.GetLoadedMods().ToArray();
            Require(mods.Length == 1 && mods[0].manifest?.id == "STS2_Things" &&
                (mods[0].errors == null || mods[0].errors!.Count == 0),
                "Native ModManager failed to initialize the published package.");
            Type bootstrap = AppDomain.CurrentDomain.GetAssemblies()
                .Single(a => a.GetName().Name == "STS2_Things.Bootstrap")
                .GetType("STS2_Things.Bootstrap.UnifiedBootstrap", true)!;
            Require((string?)bootstrap.GetProperty("SelectedTarget")!.GetValue(null) == args[2],
                "Published bootstrap selected the wrong game version.");
            Type[] modTypes = ReflectionHelper.ModTypes;
            Require(modTypes.Any(t => t.FullName == "STS2_Things.Acts.Depths"), "Depths was not discovered.");
            Type? assemblyInfo = typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Modding.AssemblyInfo");
            assemblyInfo?.GetMethod("Init")?.Invoke(null, null);
            MethodInfo init = typeof(ModelDb).GetMethods().Single(m => m.Name == "Init");
            Type[] models = AbstractModelSubtypes.All.Concat(modTypes.Where(t => !t.IsAbstract &&
                typeof(AbstractModel).IsAssignableFrom(t))).Distinct().ToArray();
            init.Invoke(null, init.GetParameters().Length == 0 ? null : [models]);
            typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Multiplayer.Serialization.ModelIdSerializationCache", true)!
                .GetMethod("Init")!.Invoke(null, null);
            typeof(ModelDb).GetMethod("InitIds")!.Invoke(null, null);
            foreach (string name in new[] { "MegaCrit.Sts2.Core.Multiplayer.Serialization.MessageTypes", "MegaCrit.Sts2.Core.GameActions.Multiplayer.ActionTypes" })
                typeof(ModelDb).Assembly.GetType(name)?.GetMethod("Initialize")?.Invoke(null, null);
            ModelDb.Preload();
            typeof(OneTimeInitialization).GetMethod("PrewarmJit", BindingFlags.NonPublic | BindingFlags.Static)!
                .Invoke(null, null);
            GD.Print($"UNIFIED_STARTUP_LOAD_PASS target={args[2]} models={models.Length}");
            TestMode.TurnOnInternal();
            if (!args.Contains("--load-only"))
            {
                LocManager.Initialize();
                ActModel depths = ModelDb.Acts.Single(a => a.GetType().Name == "Depths").ToMutable();
                var nativeEvents = ModelDb.AllEvents.Where(e => e.GetType().Assembly == typeof(ActModel).Assembly)
                    .Select(e => e.Id).ToHashSet();
                Require(depths.AllEvents.Any() && depths.AllEvents.All(e => !nativeEvents.Contains(e.Id)),
                    "Depths still inherits native regular events.");
                depths.GenerateRooms(new MegaCrit.Sts2.Core.Random.Rng(1729), UnlockState.all);
                var savedDepths = depths.ToSave();
                Require(savedDepths.SerializableRooms.EventIds.Count > 0 &&
                    savedDepths.SerializableRooms.EventIds.All(id => !nativeEvents.Contains(id)),
                    "Native shared events leaked into the generated Depths pool.");
                ActModel hive = ModelDb.Act<MegaCrit.Sts2.Core.Models.Acts.Hive>().ToMutable();
                hive.GenerateRooms(new MegaCrit.Sts2.Core.Random.Rng(1729), UnlockState.all);
                Require(hive.ToSave().SerializableRooms.EventIds.Any(nativeEvents.Contains),
                    "Removing Depths events affected Hive.");
                savedDepths.SerializableRooms.EventIds.Insert(0, ModelDb.AllSharedEvents.First().Id);
                savedDepths.SerializableRooms.EventsVisited = 0;
                ActModel restoredDepths = ActModel.FromSave(savedDepths);
                var eventPlayer = Player.CreateForNewRun<Ironclad>(UnlockState.all, 1);
                var eventRun = RunState.CreateForTest([eventPlayer], seed: "DEPTHS_EVENTS_RESTORE");
                Require(!nativeEvents.Contains(restoredDepths.PullNextEvent(eventRun).Id) &&
                    restoredDepths.ToSave().SerializableRooms.EventIds.All(id => !nativeEvents.Contains(id)),
                    "Saved native events survived the Depths draw policy.");
                GD.Print($"UNIFIED_STARTUP_DEPTHS_EVENTS_PASS count={depths.AllEvents.Count()} generated=clean restored=clean hive=preserved");
                Player player = Player.CreateForNewRun<Ironclad>(UnlockState.all, 1);
                RunState run = RunState.CreateForTest([player], seed: "NEOW_PUBLISHED_STARTUP");
                var neow = (Neow)ModelDb.Event<Neow>().ToMutable();
                MethodInfo begin = typeof(EventModel).GetMethods().Single(m => m.Name == "BeginEvent");
                object?[] values = begin.GetParameters().Select(p => p.ParameterType == typeof(Player)
                    ? (object)player : p.ParameterType == typeof(bool) ? false : null).ToArray();
                await (Task)begin.Invoke(neow, values)!;
                Require(neow.CurrentOptions.Count == 3 && neow.CurrentOptions.All(o => o.Relic != null) && !neow.IsFinished,
                    "Published package skipped Neow's three starting relic choices.");
                Require(run.Modifiers.Any(m => m.GetType().Name == "ThingsCrossroads"), "Route ledger disappeared.");
                GD.Print($"UNIFIED_STARTUP_NEOW_PASS choices={neow.CurrentOptions.Count}");
                // The reported save has Neow marked pre-finished without a
                // chosen reward. New-run-only probes do not exercise this path.
                run.AppendToMapPointHistory(MegaCrit.Sts2.Core.Map.MapPointType.Ancient,
                    MegaCrit.Sts2.Core.Rooms.RoomType.Event, neow.Id);
                var resumed = (Neow)ModelDb.Event<Neow>().ToMutable();
                resumed.DebugOption = "BOOMING_CONCH";
                object?[] resumeValues = begin.GetParameters().Select(p => p.ParameterType == typeof(Player)
                    ? (object)player : p.ParameterType == typeof(bool) ? true : null).ToArray();
                await (Task)begin.Invoke(resumed, resumeValues)!;
                Require(resumed.CurrentOptions.Count == 3 && resumed.CurrentOptions.All(o => o.Relic != null) && !resumed.IsFinished,
                    "Unrewarded pre-finished Neow must restore its three relic choices.");
                GD.Print("UNIFIED_STARTUP_NEOW_RESUME_PASS");
                var reward = resumed.CurrentOptions.Single(o => o.Relic is MegaCrit.Sts2.Core.Models.Relics.BoomingConch);
                int relicCount = player.Relics.Count;
                await reward.Chosen();
                Require(player.Relics.Count == relicCount + 1 && player.Relics.Any(r => r.Id == reward.Relic!.Id),
                    "Restored Neow did not grant the selected native relic.");
                await reward.Chosen();
                Require(player.Relics.Count == relicCount + 1, "Repeated selection duplicated the relic.");
                var awarded = (Neow)ModelDb.Event<Neow>().ToMutable();
                await (Task)begin.Invoke(awarded, resumeValues)!;
                Require(awarded.IsFinished && awarded.CurrentOptions.All(o => o.Relic == null),
                    "A rewarded opening must not reopen Neow.");
                GD.Print("UNIFIED_STARTUP_NEOW_AWARD_PASS grant=1 repeat=0 resume=0");
                foreach (string guard in new[] { "chosen", "later-floor", "later-act", "custom-rule" })
                {
                    Player protectedPlayer = Player.CreateForNewRun<Ironclad>(UnlockState.all, 1);
                    RunState protectedRun = RunState.CreateForTest([protectedPlayer], seed: "NEOW_GUARD");
                    protectedRun.AppendToMapPointHistory(MegaCrit.Sts2.Core.Map.MapPointType.Ancient,
                        MegaCrit.Sts2.Core.Rooms.RoomType.Event, neow.Id);
                    if (guard == "chosen")
                        protectedRun.CurrentMapPointHistoryEntry!.GetEntry(protectedPlayer.NetId).AncientChoices.Add(
                            new MegaCrit.Sts2.Core.Runs.History.AncientChoiceHistoryEntry(reward.Title, true));
                    if (guard == "later-floor")
                        protectedRun.AppendToMapPointHistory(MegaCrit.Sts2.Core.Map.MapPointType.Monster,
                            MegaCrit.Sts2.Core.Rooms.RoomType.Monster, null);
                    if (guard == "later-act") protectedRun.CurrentActIndex = 1;
                    if (guard == "custom-rule") protectedRun.AddModifierDebug(ModelDb.Modifier<MegaCrit.Sts2.Core.Models.Modifiers.Vintage>().ToMutable());
                    var protectedEvent = (Neow)ModelDb.Event<Neow>().ToMutable();
                    object?[] protectedValues = begin.GetParameters().Select(p => p.ParameterType == typeof(Player)
                        ? (object)protectedPlayer : p.ParameterType == typeof(bool) ? true : null).ToArray();
                    await (Task)begin.Invoke(protectedEvent, protectedValues)!;
                    Require(protectedEvent.IsFinished && protectedEvent.CurrentOptions.All(o => o.Relic == null),
                        $"Neow recovery bypassed the {guard} guard.");
                }
                GD.Print("UNIFIED_STARTUP_NEOW_GUARDS_PASS cases=4");
            }
            GD.Print("Unified startup probe: PASS");
            GetTree().Quit();
        }
        catch (Exception error)
        {
            GD.PushError(error.ToString());
            GetTree().Quit(1);
        }
    }

    private static Assembly? ResolveDependency(AssemblyLoadContext context, AssemblyName name)
    {
        string candidate = Path.Combine(ProjectSettings.GlobalizePath("res://"), ".godot", "mono", "temp", "bin", "Debug", name.Name + ".dll");
        return File.Exists(candidate) ? context.LoadFromAssemblyPath(candidate) : null;
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    // Only the directory discovery is redirected. Native loading reads the
    // actual manifest, bootstrap and PCK. No user mod or save directory is read.
    private sealed class PackageFileIo(string packageDirectory) : IModManagerFileIo
    {
        private readonly string _package = Path.GetFullPath(packageDirectory);
        private readonly string _virtualRoot = Path.Combine(Path.GetDirectoryName(OS.GetExecutablePath())!, "mods");
        private bool IsPackage(string path) => Path.GetFullPath(path).StartsWith(_package + Path.DirectorySeparatorChar,
            StringComparison.OrdinalIgnoreCase);
        public string[] GetFilesAt(string path) => path == _package ? Directory.GetFiles(_package) : [];
        public string[] GetDirectoriesAt(string path) => path == _virtualRoot ? [_package] : [];
        public bool FileExists(string path) => IsPackage(path) && File.Exists(path);
        public bool DirectoryExists(string path) => path == _virtualRoot || path == _package;
        public Stream OpenStream(string path, Godot.FileAccess.ModeFlags mode) =>
            IsPackage(path) && mode == Godot.FileAccess.ModeFlags.Read ? File.OpenRead(path) : throw new InvalidOperationException("Unexpected probe file access.");
        public void MakeDirRecursive(string path) => throw new InvalidOperationException("Unexpected probe directory write.");
        public Error CopyFile(string sourcePath, string destinationPath) => throw new InvalidOperationException("Unexpected probe file write.");
    }
}
