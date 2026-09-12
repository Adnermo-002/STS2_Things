using System.Collections;
using System.IO;
using System.Reflection;
using System.Runtime.Loader;
using Godot;
using Godot.Bridge;
using HarmonyLib;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Acts;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using STS2_Things;
using STS2_Things.Encounters;
using STS2_Things.Monsters;
using STS2_Things.Visuals;
using ReflectionMethodInfo = System.Reflection.MethodInfo;
using ReflectionPropertyInfo = System.Reflection.PropertyInfo;

public partial class LivingRockProbeNode : Node
{
    private const string CreatureScenePath = "res://scenes/creature_visuals/living_rock.tscn";
    private static Assembly ImplementationAssembly => typeof(STS2_ThingsInit).Assembly;

    public override async void _Ready()
    {
        try
        {
            string[] args = OS.GetCmdlineUserArgs();
            bool render = args.Length == 2 && args[1] == "render";
            bool visualOnly = args.Length == 2 && args[1] == "visual";
            Assert(args.Length == 1 || render || visualOnly,
                "Usage: LivingRockProbe ABSOLUTE_PCK [render|visual]");
            Assert(ProjectSettings.LoadResourcePack(args[0], replaceFiles: true),
                $"Could not mount PCK: {args[0]}");

            AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency;
            EnsureRuntimeDependency("Sentry.Godot");
            ScriptManagerBridge.LookupScriptsInAssembly(ImplementationAssembly);
            if (render)
            {
                await RenderLayeredScene();
                GD.Print("Living Rock layered render: PASS");
                GetTree().Quit(0);
                return;
            }
            if (visualOnly)
            {
                await VerifyVisualStateMachine();
                GD.Print("Living Rock visual behavior probe: PASS");
                GetTree().Quit(0);
                return;
            }
            InitializeModelDb();
            VerifyModelAndEncounterContract();
            await VerifyVisualStateMachine();
            GD.Print("Living Rock behavior probe: PASS");
            GetTree().Quit(0);
        }
        catch (Exception exception)
        {
            GD.PushError(exception.ToString());
            GetTree().Quit(1);
        }
        finally
        {
            ClearRunContext();
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

        Type? assemblyInfo = typeof(ModelDb).Assembly.GetType(
            "MegaCrit.Sts2.Core.Modding.AssemblyInfo");
        assemblyInfo?.GetMethod("Init", BindingFlags.Public | BindingFlags.Static)?
            .Invoke(null, null);
        typeof(ModelDb).GetMethod("ResetForTest", BindingFlags.Public | BindingFlags.Static)?
            .Invoke(null, null);

        ReflectionMethodInfo init = typeof(ModelDb).GetMethods(BindingFlags.Public | BindingFlags.Static)
            .Single(method => method.Name == "Init");
        init.Invoke(null, init.GetParameters().Length == 0 ? null : [modelTypes]);

        Type serializationCache = typeof(ModelDb).Assembly.GetType(
            "MegaCrit.Sts2.Core.Multiplayer.Serialization.ModelIdSerializationCache",
            throwOnError: true)!;
        serializationCache.GetMethod("Init", BindingFlags.Public | BindingFlags.Static)!
            .Invoke(null, null);
        typeof(ModelDb).GetMethod("InitIds", BindingFlags.Public | BindingFlags.Static)!
            .Invoke(null, null);

        try
        {
            new Harmony("STS2_Things.LivingRockProbe").PatchAll(ImplementationAssembly);
        }
        catch (PlatformNotSupportedException exception)
        {
            GD.PushWarning($"Harmony patching skipped on this probe runtime: {exception.Message}");
        }
        catch (HarmonyException exception) when (exception.InnerException is PlatformNotSupportedException)
        {
            GD.PushWarning($"Harmony patching skipped on this probe runtime: {exception.InnerException!.Message}");
        }
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
        manifestType.GetField("name")?.SetValue(manifest, "STS2_Things Living Rock Probe");
        manifestType.GetField("affectsGameplay")?.SetValue(manifest, true);
        modType.GetField("path")!.SetValue(mod, "probe://STS2_Things");
        modType.GetField("manifest")!.SetValue(mod, manifest);
        modType.GetField("state")!.SetValue(mod,
            Enum.Parse(modType.GetField("state")!.FieldType, "Loaded"));

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
        typeof(ModManager).GetProperty(nameof(ModManager.State),
                BindingFlags.Public | BindingFlags.Static)!
            .SetValue(null, ModManagerState.Initialized);
    }

    private static void VerifyModelAndEncounterContract()
    {
        using (SetRunAscension(0))
        {
            ThingsLivingRock normal = (ThingsLivingRock)ModelDb.Monster<ThingsLivingRock>().ToMutable();
            normal.SetUpForCombat();
            Assert(normal.Id.Entry == "THINGS_LIVING_ROCK", "Living Rock ModelId drifted.");
            Assert(normal.MinInitialHp == 220 && normal.MaxInitialHp == 220,
                "Living Rock normal HP is not 220.");
            Assert(GetPunchDamage(normal, "LEFT_PUNCH_MOVE") == 12 &&
                   GetPunchDamage(normal, "RIGHT_PUNCH_MOVE") == 12,
                "Living Rock normal punch damage is not 12.");
            AssertFixedPunchCycle(normal);
        }

        using (SetRunAscension((int)AscensionLevel.DeadlyEnemies))
        {
            ThingsLivingRock ascended = (ThingsLivingRock)ModelDb.Monster<ThingsLivingRock>().ToMutable();
            ascended.SetUpForCombat();
            Assert(ascended.MinInitialHp == 230 && ascended.MaxInitialHp == 230,
                "Living Rock high-ascension HP is not 230.");
            Assert(GetPunchDamage(ascended, "LEFT_PUNCH_MOVE") == 14 &&
                   GetPunchDamage(ascended, "RIGHT_PUNCH_MOVE") == 14,
                "Living Rock high-ascension punch damage is not 14.");
        }

        var encounter = (LivingRockBossEncounter)ModelDb.Encounter<LivingRockBossEncounter>().ToMutable();
        Assert(encounter.RoomType == RoomType.Boss, "Living Rock encounter is not a boss room.");
        Assert(encounter.HasScene, "Living Rock encounter does not expose its centered layout scene.");
        ReflectionPropertyInfo customBackgroundProperty = typeof(EncounterModel).GetProperty(
                "HasCustomBackground",
                BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingMemberException(typeof(EncounterModel).FullName, "HasCustomBackground");
        Assert((bool)(customBackgroundProperty.GetValue(encounter) ?? false),
            "Living Rock encounter does not expose its custom cliff background.");
        Assert(encounter.Slots.SequenceEqual([LivingRockBossEncounter.BossSlot]),
            "Living Rock encounter does not expose exactly one body slot.");
        Assert(encounter.AllPossibleMonsters.Single() is ThingsLivingRock,
            "Living Rock encounter does not expose the Living Rock body model.");

        Assert(HiveEncounterContains("GenerateAllEncounters", typeof(LivingRockBossEncounter)),
            "Hive normal encounter catalog omits Living Rock.");
        Assert(HiveEncounterContains("get_BossDiscoveryOrder", typeof(LivingRockBossEncounter)),
            "Hive boss discovery catalog omits Living Rock.");
    }

    private static int GetPunchDamage(ThingsLivingRock monster, string moveId)
    {
        MoveState move = (MoveState)monster.MoveStateMachine!.States[moveId];
        var intent = move.Intents.OfType<AttackIntent>().Single();
        return (int)(intent.DamageCalc?.Invoke()
            ?? throw new InvalidOperationException($"{moveId} has no damage calculator."));
    }

    private static void AssertFixedPunchCycle(ThingsLivingRock monster)
    {
        MoveState left = (MoveState)monster.MoveStateMachine!.States["LEFT_PUNCH_MOVE"];
        MoveState right = (MoveState)monster.MoveStateMachine.States["RIGHT_PUNCH_MOVE"];
        Assert(ReferenceEquals(left.FollowUpState, right) && ReferenceEquals(right.FollowUpState, left),
            "Living Rock punch state machine is not LEFT_PUNCH -> RIGHT_PUNCH -> LEFT_PUNCH.");
    }

    private static bool HiveEncounterContains(string methodName, Type encounterType)
    {
        var hive = ModelDb.Act<Hive>();
        ReflectionMethodInfo method = typeof(Hive).GetMethod(
                methodName,
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
            ?? throw new MissingMethodException(typeof(Hive).FullName, methodName);
        IEnumerable<EncounterModel> results = (IEnumerable<EncounterModel>)(method.Invoke(hive, null)
            ?? throw new InvalidOperationException($"Hive.{methodName} returned null."));
        return results.Any(encounter => encounter.GetType() == encounterType);
    }

    private async Task VerifyVisualStateMachine()
    {
        var scene = ResourceLoader.Load<PackedScene>(CreatureScenePath);
        Assert(scene != null, "Could not load the Living Rock creature scene from the mounted PCK.");
        var visual = scene!.Instantiate<NCaveGodVisuals>();
        AddChild(visual);
        try
        {
            await VerifyImmediateIdleFrontLayers(visual);
            MegaAnimationState state = await WaitForAnimationState(visual);
            MegaSkeleton skeleton = visual.SpineBody?.GetSkeleton()
                ?? throw new InvalidOperationException("Living Rock Spine skeleton is unavailable.");

            await VerifyVisualCase(visual, state, skeleton,
                NCaveGodVisuals.RightToLeftAnimation,
                NCaveGodVisuals.LeftPunchTrigger,
                expectsRewind: false,
                NCaveGodVisuals.LeftPunchAnimation,
                NCaveGodVisuals.LeftToRightAnimation);
            await VerifyVisualCase(visual, state, skeleton,
                NCaveGodVisuals.LeftToRightAnimation,
                NCaveGodVisuals.LeftPunchTrigger,
                expectsRewind: true,
                NCaveGodVisuals.LeftPunchAnimation,
                NCaveGodVisuals.LeftToRightAnimation);
            await VerifyVisualCase(visual, state, skeleton,
                NCaveGodVisuals.LeftToRightAnimation,
                NCaveGodVisuals.RightPunchTrigger,
                expectsRewind: false,
                NCaveGodVisuals.RightPunchAnimation,
                NCaveGodVisuals.RightToLeftAnimation);
            await VerifyVisualCase(visual, state, skeleton,
                NCaveGodVisuals.RightToLeftAnimation,
                NCaveGodVisuals.RightPunchTrigger,
                expectsRewind: true,
                NCaveGodVisuals.RightPunchAnimation,
                NCaveGodVisuals.RightToLeftAnimation);
        }
        finally
        {
            visual.QueueFree();
        }
    }

    private async Task RenderLayeredScene()
    {
        SubViewport viewport = new SubViewport
        {
            Size = new Vector2I(1920, 1080),
            RenderTargetUpdateMode = SubViewport.UpdateMode.Always,
            TransparentBg = false
        };
        AddChild(viewport);
        Node2D stage = new Node2D();
        viewport.AddChild(stage);
        AddTextureLayer(stage, "res://images/backgrounds/living_rock_generated_bg.png", -2, Vector2.Zero);
        AddTextureLayer(stage, "res://images/backgrounds/living_rock_generated_ground.png", 1,
            new Vector2(0f, 60f));
        PackedScene scene = ResourceLoader.Load<PackedScene>(CreatureScenePath)
            ?? throw new InvalidOperationException("Could not load Living Rock scene for render.");
        NCaveGodVisuals creature = scene.Instantiate<NCaveGodVisuals>();
        creature.Position = new Vector2(960f, 820f);
        stage.AddChild(creature);
        AddTextureLayer(stage, "res://images/backgrounds/living_rock_generated_fg.png", 3,
            new Vector2(0f, 60f));
        await WaitForIdleRenderFrame(creature);
        await SaveLayeredFrame(viewport, "living-rock-layered-immediate-idle.png");
        for (int frame = 0; frame < 120; frame++)
            await ProcessFrame();
        await SaveLayeredFrame(viewport, "living-rock-layered-idle.png");
    }

    private static void AddTextureLayer(Node2D stage, string path, int zIndex, Vector2 position)
    {
        TextureRect rect = new TextureRect
        {
            Texture = ResourceLoader.Load<Texture2D>(path),
            Position = position,
            Size = new Vector2(1920f, 1080f),
            ExpandMode = TextureRect.ExpandModeEnum.IgnoreSize,
            StretchMode = TextureRect.StretchModeEnum.KeepAspectCovered,
            MouseFilter = Control.MouseFilterEnum.Ignore,
            ZIndex = zIndex
        };
        stage.AddChild(rect);
    }

    private async Task WaitForIdleRenderFrame(NCaveGodVisuals visual)
    {
        for (int frame = 0; frame < 240; frame++)
        {
            if (visual.CurrentPhase == "Idle")
            {
                await ProcessFrame();
                return;
            }
            await ProcessFrame();
        }
        throw new InvalidOperationException("Living Rock render did not reach its idle pose.");
    }

    private static async Task SaveLayeredFrame(SubViewport viewport, string name)
    {
        await Task.Yield();
        Image? image = viewport.GetTexture().GetImage();
        if (image == null)
            throw new InvalidOperationException("Layered render viewport did not produce an image.");
        string path = ProjectSettings.GlobalizePath($"res://../../build/verification/living-rock-occlusion-ground-20260820-v8/{name}");
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        Error error = image.SavePng(path);
        if (error != Error.Ok)
            throw new InvalidOperationException($"Could not save layered render frame {name}: {error}");
    }

    private async Task VerifyImmediateIdleFrontLayers(NCaveGodVisuals visual)
    {
        Vector2 initialPosition = visual.Position;
        MegaAnimationState? state = null;
        for (int frame = 0; frame < 12; frame++)
        {
            state = visual.SpineBody?.TryGetAnimationState();
            if (state != null && visual.CurrentPhase == "Idle")
                break;
            await ProcessFrame();
        }
        if (state == null || visual.CurrentPhase != "Idle")
        {
            throw new InvalidOperationException(
                "Living Rock did not enter Idle immediately; an arrival phase is still running.");
        }
        Assert(state.GetCurrentAnimationName(0) == NCaveGodVisuals.LeftToRightAnimation,
            "Living Rock did not start with the left-to-right idle animation.");
        Assert(visual.Position.IsEqualApprox(initialPosition),
            "Living Rock moved vertically during initialization.");

        Node2D main = visual.GetNode<Node2D>("Visuals");
        Node2D left = visual.GetNode<Node2D>("ArmFrontLeft");
        Node2D right = visual.GetNode<Node2D>("ArmFrontRight");
        Node2D face = visual.GetNodeOrNull<Node2D>("FaceFront")
            ?? throw new InvalidOperationException("Living Rock scene lacks a FaceFront layer.");
        Vector2 expectedScale = new(1.05f, 1.05f);
        Assert(main.Scale.IsEqualApprox(expectedScale)
               && left.Scale.IsEqualApprox(expectedScale)
               && right.Scale.IsEqualApprox(expectedScale)
               && face.Scale.IsEqualApprox(expectedScale),
            "Living Rock body, face, and hand layers are not all at the requested 1.05 scale.");
        FieldInfo leftSlotsField = typeof(NCaveGodVisuals).GetField(
                "LeftArmSlots", BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new MissingFieldException(typeof(NCaveGodVisuals).FullName, "LeftArmSlots");
        FieldInfo rightSlotsField = typeof(NCaveGodVisuals).GetField(
                "RightArmSlots", BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new MissingFieldException(typeof(NCaveGodVisuals).FullName, "RightArmSlots");
        var leftSlots = (ISet<string>?)leftSlotsField.GetValue(null)
            ?? throw new InvalidOperationException("Living Rock left foreground slot set is unavailable.");
        var rightSlots = (ISet<string>?)rightSlotsField.GetValue(null)
            ?? throw new InvalidOperationException("Living Rock right foreground slot set is unavailable.");
        Assert(leftSlots.SetEquals(["arm1_2", "arm1_3"]),
            "Living Rock left foreground layer still exposes a body-connected upper arm slot.");
        Assert(rightSlots.SetEquals(["arm2_2", "arm2_3"]),
            "Living Rock right foreground layer still exposes a body-connected upper arm slot.");
        Assert(main.ZIndex == -1, "Living Rock body is not behind the ground layer.");
        Assert(left.ZIndex == 4 && right.ZIndex == 4 && face.ZIndex == 4,
            "Living Rock face and hand layers are not all above the ground.");
    }

    private async Task<MegaAnimationState> WaitForAnimationState(NCaveGodVisuals visual)
    {
        for (int frame = 0; frame < 720; frame++)
        {
            if (frame % 60 == 0)
            {
                GD.Print($"IDLE_TRACE frame={frame} phase={visual.CurrentPhase} animation={visual.SpineBody?.TryGetAnimationState()?.GetCurrentAnimationName(0)}");
            }
            MegaAnimationState? state = visual.SpineBody?.TryGetAnimationState();
            if (state != null && visual.CurrentPhase == "Idle" &&
                state.GetCurrentAnimationName(0) == NCaveGodVisuals.LeftToRightAnimation)
                return state;
            await ProcessFrame();
        }
        throw new InvalidOperationException("Living Rock Spine animation state did not initialize.");
    }

    private async Task VerifyVisualCase(
        NCaveGodVisuals visual,
        MegaAnimationState state,
        MegaSkeleton skeleton,
        string currentIdle,
        string trigger,
        bool expectsRewind,
        string expectedPunch,
        string expectedIdle)
    {
        state.SetAnimation(currentIdle, loop: false, trackId: 0);
        SetTrackTime(state, skeleton, 2.5f);
        await ProcessFrame();

        visual.TriggerPunch(trigger);
        float initialTrackTime = GetTrackTime(state);
        if (expectsRewind)
        {
            float previous = initialTrackTime;
            bool decreased = false;
            for (int frame = 0; frame < 8; frame++)
            {
                await ProcessFrame();
                float current = GetTrackTime(state);
                Assert(current <= previous + 0.0001f,
                    $"{trigger} rewind increased track time.");
                decreased |= current < previous - 0.0001f;
                previous = current;
            }
            Assert(decreased, $"{trigger} did not decrement track time during rewind.");
        }
        else
        {
            await ProcessFrame();
            await ProcessFrame();
            Assert(GetTrackTime(state) >= initialTrackTime - 0.0001f,
                $"{trigger} natural-complete path rewound the idle track.");
            SetTrackTime(state, skeleton, GetAnimationEnd(state));
        }

        await WaitForAnimation(state, expectedPunch, 240);
        SetTrackTime(state, skeleton, GetAnimationEnd(state));
        await WaitForAnimation(state, expectedIdle, 240);
    }

    private async Task WaitForAnimation(MegaAnimationState state, string expected, int frameLimit)
    {
        for (int frame = 0; frame < frameLimit; frame++)
        {
            if (state.GetCurrentAnimationName(0) == expected)
                return;
            await ProcessFrame();
        }
        throw new InvalidOperationException($"Living Rock never transitioned to {expected}.");
    }

    private async Task ProcessFrame()
    {
        await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
    }

    private static float GetTrackTime(MegaAnimationState state)
    {
        MegaTrackEntry? track = state.GetCurrent(0);
        if (track == null)
            return 0f;
#if !STS2_V107_1
        using (track)
            return track.GetTrackTime();
#else
        return track.GetTrackTime();
#endif
    }

    private static float GetAnimationEnd(MegaAnimationState state)
    {
        MegaTrackEntry? track = state.GetCurrent(0);
        if (track == null)
            throw new InvalidOperationException("Living Rock animation track is missing.");
#if !STS2_V107_1
        using (track)
            return track.GetAnimationEnd();
#else
        return track.GetAnimationEnd();
#endif
    }

    private static void SetTrackTime(MegaAnimationState state, MegaSkeleton skeleton, float time)
    {
        MegaTrackEntry? track = state.GetCurrent(0);
        if (track == null)
            throw new InvalidOperationException("Living Rock animation track is missing.");
#if !STS2_V107_1
        using (track)
            track.SetTrackTime(time);
#else
        track.SetTrackTime(time);
#endif
        state.Update(0f);
        state.Apply(skeleton);
    }

    private static IDisposable SetRunAscension(int level)
    {
        RunManager manager = RunManager.Instance;
        ReflectionPropertyInfo stateProperty = typeof(RunManager).GetProperty(
                "State", BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingMemberException(typeof(RunManager).FullName, "State");
        ReflectionPropertyInfo ascensionProperty = typeof(RunManager).GetProperty(
                nameof(RunManager.AscensionManager), BindingFlags.Instance | BindingFlags.Public)
            ?? throw new MissingMemberException(typeof(RunManager).FullName, nameof(RunManager.AscensionManager));
        object? oldState = stateProperty.GetValue(manager);
        object? oldAscension = ascensionProperty.GetValue(manager);
        RunState state = RunState.CreateForTest(ascensionLevel: level, seed: "LIVING_ROCK_PROBE");
        stateProperty.SetValue(manager, state);
        ascensionProperty.SetValue(manager, new AscensionManager(level));
        return new RunContext(manager, stateProperty, ascensionProperty, oldState, oldAscension);
    }

    private static void ClearRunContext()
    {
        RunManager manager = RunManager.Instance;
        typeof(RunManager).GetProperty("State", BindingFlags.Instance | BindingFlags.NonPublic)
            ?.SetValue(manager, null);
    }

    private static void EnsureRuntimeDependency(string assemblyName)
    {
        if (AppDomain.CurrentDomain.GetAssemblies().Any(assembly =>
                string.Equals(assembly.GetName().Name, assemblyName, StringComparison.Ordinal)))
        {
            return;
        }

        string path = FindRuntimeDependencyPath(assemblyName)
            ?? throw new FileNotFoundException($"Could not locate runtime dependency {assemblyName}.dll.");
        AssemblyLoadContext.Default.LoadFromAssemblyPath(path);
    }

    private static Assembly? ResolveRuntimeDependency(
        AssemblyLoadContext context,
        AssemblyName assemblyName)
    {
        if (string.IsNullOrWhiteSpace(assemblyName.Name))
            return null;
        string? path = FindRuntimeDependencyPath(assemblyName.Name);
        return path == null ? null : context.LoadFromAssemblyPath(path);
    }

    private static string? FindRuntimeDependencyPath(string assemblyName)
    {
        string projectRoot = ProjectSettings.GlobalizePath("res://");
        string? assemblyDirectory = Path.GetDirectoryName(typeof(LivingRockProbeNode).Assembly.Location);
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
            throw new InvalidOperationException(message);
    }

    private sealed class RunContext(
        RunManager manager,
        ReflectionPropertyInfo stateProperty,
        ReflectionPropertyInfo ascensionProperty,
        object? oldState,
        object? oldAscension) : IDisposable
    {
        public void Dispose()
        {
            stateProperty.SetValue(manager, oldState);
            ascensionProperty.SetValue(manager, oldAscension);
        }
    }
}
