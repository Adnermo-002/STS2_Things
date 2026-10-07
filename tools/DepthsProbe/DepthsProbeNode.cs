using System.Reflection;
using System.Runtime.Loader;
using Godot;
using Godot.Bridge;
using MegaCrit.Sts2.Core.Achievements;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Acts;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Multiplayer.Serialization;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Saves.Runs;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Acts;
using STS2_Things.Config;
using STS2_Things.Encounters;
using STS2_Things.Monsters;

public partial class DepthsProbeNode : Node
{
    private static int _checks;
    private string _root = null!;
    private string _output = null!;
    private readonly List<Node> _resourceFixtures = [];
    public override void _Ready()
    {
        // Install dependency resolution before JIT touches the game's module initializer.
        AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency;
#if !STS2_V107_1
        EnsureRuntimeDependency("Sentry");
        EnsureRuntimeDependency("Sentry.Godot");
#endif
        _ = RunProbe();
    }

    private async Task RunProbe()
    {
        try
        {
            _root = Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "../.."));
            _output = System.Environment.GetEnvironmentVariable("THINGS_PROBE_OUTPUT") ?? Path.Combine(_root,"build/depths/verification");Directory.CreateDirectory(_output);
            TestMode.TurnOnInternal();
            ProjectSettings.LoadResourcePack("D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck");
            string package=System.Environment.GetEnvironmentVariable("THINGS_PROBE_PCK") ?? Path.Combine(_root,"build/depths/v111/STS2_Things.pck");
            Assert(ProjectSettings.LoadResourcePack(package),"Packaged mod mounted.");
            AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency;
            EnsureRuntimeDependency("System.IO.Hashing");
            RegisterSyntheticMod(typeof(Depths).Assembly);
            // Same order as the mod loader: initialize Harmony before ModelDb builds its caches.
            STS2_ThingsInit.Initialize();
            InitializeModelDb();
            Assert(OS.GetUserDataDir().Contains("Depths",StringComparison.OrdinalIgnoreCase),"Isolated probe user data.");
            ResetSettings();
            SaveManager.Instance.InitSettingsDataForTest();
            SaveManager.Instance.InitPrefsDataForTest();
            SaveManager.Instance.SettingsSave.Language="zhs";LocManager.Initialize();
            if(OS.GetCmdlineUserArgs().Contains("--cavegod-doom-only"))
            {
                await VerifyCaveGodDoom();await ReleaseProbeResources();
                GD.Print($"Depths CaveGod Doom probe: PASS ({_checks} assertions)");GetTree().Quit(0);return;
            }
            if(OS.GetCmdlineUserArgs().Contains("--native-migration-only"))
            {
                await VerifyNativeMigration();await ReleaseProbeResources();
                GD.Print($"Depths native migration probe: PASS ({_checks} assertions)");GetTree().Quit(0);return;
            }
            if(OS.GetCmdlineUserArgs().Contains("--column-tracks-only"))
            {
                await VerifyColumnTracks();await ReleaseProbeResources();
                GD.Print($"Depths column tracks probe: PASS ({_checks} assertions)");GetTree().Quit(0);return;
            }
            if(OS.GetCmdlineUserArgs().Contains("--balance-only"))
            {
                await SampleDepthsBalance();await ReleaseProbeResources();
                GD.Print($"Depths balance probe: PASS ({_checks} assertions)");GetTree().Quit(0);return;
            }
            if(OS.GetCmdlineUserArgs().Contains("--fleeting-echo-only"))
            {
                VerifyResources();
                await VerifyFleetingEcho();await ReleaseProbeResources();
                GD.Print($"Depths Fleeting Echo probe: PASS ({_checks} assertions)");GetTree().Quit(0);return;
            }
            if(OS.GetCmdlineUserArgs().Contains("--column-variants-only"))
            {
                await VerifyColumnCompanions();await ReleaseProbeResources();
                GD.Print($"Depths column variants probe: PASS ({_checks} assertions)");GetTree().Quit(0);return;
            }
            if(OS.GetCmdlineUserArgs().Contains("--column-rules-only"))
            {
                await VerifyColumnRules();await ReleaseProbeResources();
                GD.Print($"Depths column rules probe: PASS ({_checks} assertions)");GetTree().Quit(0);return;
            }
            if(OS.GetCmdlineUserArgs().Contains("--effects-only"))
            {
                await VerifySpongeSprayRendering();
                VerifyBorrowedDeathAudio();
                GD.Print($"Depths effects probe: PASS ({_checks} assertions)");GetTree().Quit(0);return;
            }
            if(OS.GetCmdlineUserArgs().Contains("--camp-only"))
            {
                VerifyResources();await RenderCampSeats();await ReleaseProbeResources();
                GD.Print($"Depths camp seating probe: PASS ({_checks} assertions)");GetTree().Quit(0);return;
            }
            VerifyCatalog();
            VerifyPoolsAndConfig();
            VerifyRoomsAndSaves();
            await VerifyNativeActProgression();
            VerifyResources();
            await VerifyColumnRules();
            await VerifyFleetingEcho();
            await VerifyStrongEncounters();
            await VerifySpongeSprayRendering();
            VerifyBorrowedDeathAudio();
            if(OS.GetCmdlineUserArgs().Contains("--variety-visual")) await RenderStrongVariety();
            if(OS.GetCmdlineUserArgs().Contains("--visual")) await RenderDepths();
            await ReleaseProbeResources();
            GD.Print($"Depths act probe: PASS ({_checks} assertions)");
            GetTree().Quit(0);
        }
        catch(Exception ex){GD.PushError(ex.ToString());GetTree().Quit(1);}
    }

    private static void ResetSettings() => ThingsModConfig.SetValues(
        ThingsModConfig.Entries.ToDictionary(entry=>entry.Key,entry=>(object?)entry.Default));
    private static void Assert(bool condition,string message){if(!condition)throw new Exception(message);_checks++;}

    private async Task ReleaseProbeResources()
    {
        await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        // These resources are instantiated off-tree. Flush pending material updates
        // before disposing their cache entries, especially on the older game runtime.
        RenderingServer.ForceDraw();
        // VisualShader schedules shader assignment when the off-tree scenes are
        // instantiated. Retain them until those updates have actually flushed.
        foreach (var node in _resourceFixtures) node.Free();
        _resourceFixtures.Clear();
        await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        RenderingServer.ForceDraw();
        var cache=MegaCrit.Sts2.Core.Assets.PreloadManager.Cache;
        cache.GetType().GetMethod("UnloadMissedCacheAssets")?.Invoke(cache,null);
        await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        GC.Collect();GC.WaitForPendingFinalizers();
        await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        RenderingServer.ForceDraw();
    }

    private static void VerifyCatalog()
    {
        var act=ModelDb.Act<Depths>();
        Assert(act.Index==1 && !act.IsDefault && act.IsUnlocked(UnlockState.all),"Alternate act two is unlocked.");
        Assert(ModelDb.Acts.Count(a=>a is Depths)==1,"One canonical Depths entry.");
        Assert(ModelDb.ActsByIndex[1].Any(a=>a is Depths) && ModelDb.ActsByIndex[1].Any(a=>a is Hive),"Hive and Depths share second-act slot.");
        Assert(ModelDb.ActsByIndex.Count==3 && ActModel.GetDefaultList()[1] is Hive,"Default route and three-act length preserved.");
        var rolled=new HashSet<Type>();
        for(int seed=0;seed<128;seed++)
        {
            var a=ActModel.GetRandomList(new RunRngSet($"depths-{seed}").UpFront,UnlockState.all,true).ToArray();
            var b=ActModel.GetRandomList(new RunRngSet($"depths-{seed}").UpFront,UnlockState.all,true).ToArray();
            Assert(a.Select(x=>x.Id).SequenceEqual(b.Select(x=>x.Id)),"Seeded chapter list is deterministic.");
            Assert(a.Length==3 && a[0] is Overgrowth or Underdocks && a[1] is Hive or Depths && a[2] is Glory,"Depths never replaces act 1 or 3.");
            rolled.Add(a[1].GetType());
        }
        Assert(rolled.SetEquals([typeof(Hive),typeof(Depths)]),"Both second acts roll organically.");
        Assert(act.Title.GetFormattedText()=="深处","Localized chapter title resolves.");
        GD.Print("PASS chapter registration, native random selection and localized title.");
    }

    private static void VerifyPoolsAndConfig()
    {
        var act=ModelDb.Act<Depths>();
        Assert(act.AllWeakEncounters.Select(e=>e.GetType()).ToHashSet().SetEquals([typeof(LanternFishWeak),typeof(SanguineLeechWeak),typeof(SpongeLeechWeak),typeof(SilkMothWeak),typeof(CaveMawWeak),typeof(SnailTrioWeak),typeof(HumanFaceColumnWeak),typeof(FleetingEchoWeak)]),"Eight weak encounter entries.");
        Assert(act.AllRegularEncounters.Select(e=>e.GetType()).ToHashSet().SetEquals(StrongRosterContracts.Keys),"Twelve independent regular encounter entries.");
        Assert(act.AllEliteEncounters.Select(e=>e.GetType()).ToHashSet().SetEquals([
            typeof(DecimillipedeElite),typeof(EntomancerElite),typeof(InfestedPrismsElite),typeof(MycorrhizalTwinsElite),typeof(ReverseSalamanderElite),typeof(RadioJellyfishElite)]),"Depths has three custom elites and three vanilla elites.");
        Assert(act.AllBossEncounters.Single() is CaveGodBossEncounter,"Depths defaults to Cave God.");
        Assert(ModelDb.Act<Hive>().AllBossEncounters.Any(e=>e is CaveGodBossEncounter),"Cave God remains in Hive.");
        Assert(!ModelDb.Act<Hive>().AllEncounters.Any(e=>e is LanternFishWeak or LanternFishEncounter or SanguineLeechWeak or SanguineLeechEncounter or SpongeLeechWeak or SpongeLeechEncounter or SilkMothWeak or SilkMothEncounter or CaveMawWeak or CaveMawEncounter or SnailTrioWeak),"Custom hallway pools belong only to Depths.");
        var run=CreateRun("pair-contract");
        foreach(var (canonical,count,phases) in new[]{(ModelDb.Encounter<LanternFishWeak>() as EncounterModel,2,new[]{0,1}),
            (ModelDb.Encounter<LanternFishEncounter>(),3,new[]{0,1,3})})
        {
            var encounter=canonical.ToMutable();encounter.GenerateMonstersWithSlots(run);
            Assert(encounter.MonstersWithSlots.Count==count,"Correct fish count.");
            Assert(encounter.MonstersWithSlots.Select(x=>((LanternFish)x.Item1).OpeningPhase).SequenceEqual(phases),"Opening moves stagger.");
            Assert(encounter.Slots.Count==count && encounter.MonstersWithSlots.All(x=>encounter.Slots.Contains(x.Item2!)),"All creature slots resolve.");
            Assert(encounter.RoomType==RoomType.Monster && encounter.IsWeak==(count==2),"Native weak/regular classification.");
        }
        ThingsModConfig.SetValue(ThingsModConfig.BossCaveGodEnabled,false);
        Assert(!act.AllBossEncounters.Any(e=>e is CaveGodBossEncounter) && act.AllBossEncounters.Any(),"Disabled shared boss has a playable fallback.");
        ResetSettings();ThingsModConfig.SetValue(ThingsModConfig.BossBowlbugProgenitorForced,true);
        Assert(act.AllBossEncounters.Single() is CaveGodBossEncounter,"Hive-only force does not replace Depths boss.");
        ResetSettings();
        GD.Print("PASS 2/3 fish pools, native elites, shared Cave God and config isolation.");
    }

    private static RunState CreateRun(string seed,int players=1,int ascension=0)
    {
        var party=Enumerable.Range(1,players).Select(i=>Player.CreateForNewRun<Ironclad>(UnlockState.all,(ulong)i)).ToList();
        return RunState.CreateForNewRun(party,[ModelDb.Act<Overgrowth>().ToMutable(),ModelDb.Act<Depths>().ToMutable(),ModelDb.Act<Glory>().ToMutable()],[],GameMode.Standard,ascension,seed);
    }

    private void VerifyRoomsAndSaves()
    {
        var weakSeen=new HashSet<ModelId>();
        var regularSeen=new HashSet<ModelId>();
        for(int players=1;players<=4;players++)
        for(int seed=0;seed<16;seed++)
        {
            var run=CreateRun($"rooms-{seed}",players);run.CurrentActIndex=1;
            var act=run.Act;act.GenerateRooms(run.Rng.UpFront,UnlockState.all,players>1);
            var save=act.ToSave();
            weakSeen.UnionWith(save.SerializableRooms.NormalEncounterIds.Take(2));
            regularSeen.UnionWith(save.SerializableRooms.NormalEncounterIds.Skip(2));
            Assert(save.SerializableRooms.NormalEncounterIds.Count==(players==1?14:13),"Native room count.");
            Assert(save.SerializableRooms.NormalEncounterIds.Take(2).All(id=>act.AllWeakEncounters.Any(e=>e.Id==id)),"First two encounters use the weak pool.");
            Assert(save.SerializableRooms.NormalEncounterIds.Skip(2).All(id=>act.AllRegularEncounters.Any(e=>e.Id==id)),"Later encounters use the regular pool.");
            Assert(save.SerializableRooms.NormalEncounterIds.Skip(2).Distinct().Count()==save.SerializableRooms.NormalEncounterIds.Count-2,"Regular entries do not repeat before the twelve-entry bag is exhausted.");
            Assert(save.SerializableRooms.EliteEncounterIds.Count==15 && save.SerializableRooms.AncientId!=null,"Elite and ancient room sets complete.");
            var map=act.CreateMap(run,false);
            Assert(map.startMapPoints.Count>0 && map.GetAllMapPoints().Any(p=>p.PointType==MapPointType.RestSite),"Native map contains traversable starts and camps.");
            Assert(map.BossMapPoint.PointType==MapPointType.Boss,"Native boss destination exists.");
            act.MarkRoomVisited(RoomType.Monster);
            save=act.ToSave();save.SavedMap=SerializableActMap.FromActMap(map);
            var writer=new PacketWriter{WarnOnGrow=false};save.Serialize(writer);
            var reader=new PacketReader();reader.Reset(writer.Buffer);
            var restored=new SerializableActModel();restored.Deserialize(reader);
            var loaded=ActModel.FromSave(restored);
            Assert(loaded.ToSave().SerializableRooms.NormalEncounterIds.SequenceEqual(save.SerializableRooms.NormalEncounterIds),"Save/load preserves the entire encounter queue, including new IDs.");
            Assert(loaded is Depths && loaded.BossEncounter is CaveGodBossEncounter,"Native binary act snapshot rehydrates Depths and boss.");
            Assert(loaded.ToSave().SerializableRooms.NormalEncountersVisited==1,"Visited encounter index survives reload.");
            Assert(loaded.PullNextEncounter(RoomType.Monster).IsWeak,"Reload continues remaining weak encounter.");
            Assert(new SavedActMap(restored.SavedMap!).GetRowCount()==map.GetRowCount(),"Saved map restores geometry.");
            if(seed==0 && players==1)System.IO.File.WriteAllBytes(Path.Combine(_output,"depths-act.snapshot"),writer.Buffer.Take(writer.BytePosition).ToArray());
        }
        Assert(weakSeen.Contains(ModelDb.Encounter<SpongeLeechWeak>().Id),"Native room generation actually rolls the mixed sponge weak encounter.");
        Assert(regularSeen.Contains(ModelDb.Encounter<SpongeLeechEncounter>().Id),"Native room generation actually rolls the mixed sponge regular encounter.");
        Assert(weakSeen.Contains(ModelDb.Encounter<SilkMothWeak>().Id),"Native room generation rolls the moth weak encounter.");
        Assert(regularSeen.Contains(ModelDb.Encounter<SilkMothEncounter>().Id),"Native room generation rolls the moth regular encounter.");
        Assert(regularSeen.SetEquals(ModelDb.Act<Depths>().AllRegularEncounters.Select(e=>e.Id)),"All twelve regular encounters roll organically.");
        Assert(weakSeen.SetEquals(ModelDb.Act<Depths>().AllWeakEncounters.Select(e=>e.Id)),"All seven weak encounters remain reachable.");
        GD.Print("PASS 64 native 1-4 player room sets, twelve-entry bags, generated maps and binary save/load round trips.");
    }

    private async Task VerifyNativeActProgression()
    {
        var run=CreateRun("native-depths-progression");
        RunManager.Instance.SetUpTest(run,new NetSingleplayerGameService(),shouldSave:false);
        RunManager.Instance.GenerateRooms();
        await RunManager.Instance.SetActInternal(0);
        Assert(run.Act is Overgrowth && run.Map!=null,"Native first act initialized.");
        await RunManager.Instance.SetActInternal(1);
        Assert(run.Act is Depths && run.CurrentActIndex==1 && run.Map!=null,"Native first-to-second progression reaches Depths.");
        AchievementsHelper.CheckForDefeatedAllEnemiesAchievement(run.Act,run.Players[0]);
        await RunManager.Instance.SetActInternal(2);
        Assert(run.Act is Glory,"Native progression continues into original third act.");
        GD.Print("PASS RunManager initializes acts 1 -> Depths -> Glory without replacing vanilla act logic.");
    }

    private void VerifyResources()
    {
        var status=GDExtensionManager.LoadExtension(Path.Combine(_root,"addons/spine/spine_godot_extension.gdextension"));
        Assert(status is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded,"Spine loaded.");
        ScriptManagerBridge.LookupScriptsInAssembly(typeof(ActModel).Assembly);
        foreach(string title in new[]{"depths","lantern_fish_encounter","lantern_fish_weak"})
        {
            using var directory=DirAccess.Open($"res://scenes/backgrounds/{title}/layers");
            Assert(directory!=null,$"Background directory {title}.");
            var paths=directory!.GetFiles().Where(n=>n.Contains("_bg_00_") && n.EndsWith(".tscn",StringComparison.Ordinal)).ToArray();
            Assert(paths.Length==(title=="depths"?8:1),$"Act variants and fish-specific scene are separate: {title}: {string.Join(',',directory.GetFiles())}.");
            if(title!="depths")Assert(paths.Single().Contains("cave_riverbend"),"Fish stay at the riverbank.");
            foreach(string name in paths)
            {
                var layer=GD.Load<PackedScene>($"res://scenes/backgrounds/{title}/layers/{name}").Instantiate<Control>();
                Assert(layer.HasMeta("depths_variant") && layer.GetChildCount()>=3,"Atomic composition includes art, ambience and foreground.");
                _resourceFixtures.Add(layer);
            }
        }
        var act=ModelDb.Act<Depths>();
        Assert(act.MapTopBg.GetWidth()==2036 && act.MapMidBg.GetHeight()==1440 && act.MapBotBg.GetHeight()==1440,"Native map textures load.");
        var rest=act.CreateRestSiteBackground();Assert(rest.HasNode("%RestSiteLighting"),"Camp exposes native lighting contract.");_resourceFixtures.Add(rest);
        Assert(ResourceLoader.Exists(act.ChestSpineResourcePath),"Chest resource exists.");
        var backgrounds=new HashSet<string>();
        for(int seed=0;seed<128;seed++)
        {
            var bg=act.GenerateBackgroundAssets(new RunRngSet($"bg-{seed}").UpFront);
            Assert(bg.BgLayers.Count==1 && bg.FgLayer!=null,"Native generator chooses one whole cave.");
            backgrounds.Add(bg.BgLayers[0]);
        }
        Assert(backgrounds.Count==8,"Every variant is reachable.");
        GD.Print("PASS packaged chapter/background/camp/map asset contracts and all eight choices.");
    }

}
