using System.Collections;
using System.Reflection;
using System.Runtime.Loader;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Multiplayer.Messages.Game.Sync;
using MegaCrit.Sts2.Core.Multiplayer.Serialization;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Shops;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Config;

// Drives the native purchase wrapper and production bargain manager. Only the
// graphical minigame is replaced: full animations are covered in real clients.
// Network endpoints record actual native reward messages; this is not a LAN test.
public static class MerchantMultiplayerRegression
{
    private static readonly Assembly Mod = typeof(STS2_ThingsInit).Assembly;
    private static readonly Type Manager = Mod.GetType("STS2_Things.Features.MerchantBargain.MerchantBargainManager", true)!;
    private static readonly BindingFlags PrivateStatic = BindingFlags.Static | BindingFlags.NonPublic;
    private static NMerchantRoom? _room;
    private static bool _win = true;
    private static int _fights;
    private static int _assertions;
    private static readonly List<object> _sessions = [];

    public static async Task Run()
    {
        AssemblyLoadContext.Default.Resolving += ResolveDependency;
        TestMode.TurnOnInternal();
        InitializeModels();
        SaveManager.Instance.InitSettingsDataForTest();
        SaveManager.Instance.InitPrefsDataForTest();
        MultiplayerConfig.Clear();
        ThingsModConfig.Load();
        ThingsModConfig.SetValue(ThingsModConfig.FeatureMerchantBargainEnabled, true);
        var harmony = new Harmony("MerchantBargainProbe.NativeMultiplayer");
        foreach (string name in new[] {"MerchantEntryOnTryPurchaseWrapperPatch", "MerchantEntryCostPatch"})
            harmony.CreateClassProcessor(Mod.GetType("STS2_Things.Features.MerchantBargain." + name, true)!).Patch();
        harmony.Patch(AccessTools.PropertyGetter(typeof(NMerchantRoom), nameof(NMerchantRoom.Instance)),
            prefix: new HarmonyMethod(typeof(MerchantMultiplayerRegression), nameof(LocalRoom)));
        harmony.Patch(Manager.GetMethod("ResolveFightAndPurchaseAsync", PrivateStatic),
            prefix: new HarmonyMethod(typeof(MerchantMultiplayerRegression), nameof(ResolveWithoutAnimation)));
        try
        {
            foreach (int count in new[] {1, 2, 3, 4}) await Party(count);
            GD.Print($"Merchant multiplayer purchase regression: PASS ({_assertions} assertions; native 1–4 player inventories/messages)");
        }
        finally
        {
            harmony.UnpatchAll(harmony.Id);
            _room?.Inventory?.Free();
            _room?.Free();
            _room = null;
            LocalContext.NetId = null;
            MultiplayerConfig.Clear();
        }
    }

    private static bool LocalRoom(ref NMerchantRoom? __result) { __result = _room; return false; }
    private static bool ResolveWithoutAnimation(object[] __args, ref Task<bool> __result)
    {
        _fights++;
        __result = Resolve((MerchantEntry)__args[0], (MerchantInventory)__args[1], __args[3]);
        return false;
    }
    private static async Task<bool> Resolve(MerchantEntry entry, MerchantInventory inventory, object state)
    {
        object session = state.GetType().GetProperty("Session")!.GetValue(state)!;
        _sessions.Add(session);
        if (!_win)
        {
            session.GetType().GetMethod("MarkFightLost")!.Invoke(session, null);
            session.GetType().GetMethod("EndFight")!.Invoke(session, null);
            entry.InvokePurchaseFailed(PurchaseStatus.FailureGold);
            return false;
        }
        int price = inventory.Player.Gold;
        session.GetType().GetMethod("MarkFightWon")!.Invoke(session, [entry, price]);
        var result = (Task<bool>)Manager.GetMethod("PurchaseAtNegotiatedPriceAsync", PrivateStatic)!
            .Invoke(null, [entry, inventory, state, price])!;
        bool success = await result;
        session.GetType().GetMethod("EndFight")!.Invoke(session, null);
        return success;
    }

    private static async Task Party(int count)
    {
        var players = Enumerable.Range(1, count).Select(i => Player.CreateForNewRun<Ironclad>(UnlockState.all, (ulong)i)).ToList();
        var run = RunState.CreateForNewRun(players, ActModel.GetDefaultList().Select(a => a.ToMutable()).ToList(), [],
            GameMode.Standard, 0, "merchant-bargain-party-" + count);
        typeof(RunManager).GetProperty("State", PrivateStatic | BindingFlags.Instance)!
            .SetValue(RunManager.Instance, run);
        run.PushRoom(new MerchantRoom());
        run.AppendToMapPointHistory(MapPointType.Shop, RoomType.Shop, null);
        var inventories = players.Select(p => new MerchantInventory(p)).ToArray();
        var entries = players.Select(p => new MerchantRelicEntry(ModelDb.Relic<Anchor>().ToMutable(), p)).ToArray();
        for (int i = 0; i < count; i++)
        {
            typeof(MerchantEntry).GetField("_cost", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(entries[i], 120);
            typeof(Player).GetProperty(nameof(Player.Gold))!.SetValue(players[i], 110);
            inventories[i].AddRelicEntry(entries[i]);
        }
        _win = true;
        int fightStart = _fights;
        for (int local = 0; local < count; local++)
        {
            LocalContext.NetId = players[local].NetId;
            var (service, wire) = local == 0 ? HostEndpoint(players[local].NetId) : ClientEndpoint(players[local].NetId);
            typeof(RunManager).GetProperty(nameof(RunManager.NetService))!.SetValue(RunManager.Instance, service);
            var buffer = new RunLocationTargetedMessageBuffer(service);
            using var sync = new RewardSynchronizer(buffer, service, run, players[local].NetId);
            typeof(RunManager).GetProperty(nameof(RunManager.RewardSynchronizer))!.SetValue(RunManager.Instance, sync);
            SetUi(inventories[local]);
            int before = _fights;
            // An off-screen peer's inventory must not accumulate local clicks.
            for (int remote = local + 1; remote < count; remote++)
                for (int attempt = 0; attempt < 4; attempt++)
                    Require(!await entries[remote].OnTryPurchaseWrapper(inventories[remote]), "Off-screen peer follows native insufficient-gold flow");
            for (int attempt = 1; attempt < 5; attempt++)
                Require(!await entries[local].OnTryPurchaseWrapper(inventories[local]), "First four eligible native clicks fail normally");
            Require(_fights == before && players[local].Gold == 110 && entries[local].IsStocked, "No early fight or purchase");
            Require(await entries[local].OnTryPurchaseWrapper(inventories[local]), "Fifth eligible native click starts bargain and native purchase");
            Require(_fights == before + 1 && players[local].Gold == 0 && !entries[local].IsStocked, "One fight and one purchase for this player");
            Require(players[local].Relics.Count(r => r.Id == ModelDb.Relic<Anchor>().Id) == 1, "Native relic reward obtained once");
            var gold = wire.Sent.OfType<GoldLostMessage>().ToArray();
            Require(gold.Length == 1 && gold[0].goldLost == 110, "Native sync sends negotiated gold amount once");
            Require(wire.Sent.OfType<RewardObtainedMessage>().Count() == 1, "Native reward synchronizer sends one obtained relic");
            Require(!_sessions[^1].Equals(_sessions.Take(_sessions.Count - 1).LastOrDefault()), "Personal inventories have distinct bargain sessions");
            for (int other = local + 1; other < count; other++)
                Require(players[other].Gold == 110 && entries[other].IsStocked, "Other players' gold and inventory unchanged");
            // The one-shop offer cannot be spent again, including on a different stock slot.
            var otherEntry = new MerchantRelicEntry(ModelDb.Relic<Anchor>().ToMutable(), players[local]);
            for (int attempt = 0; attempt < 5; attempt++) await otherEntry.OnTryPurchaseWrapper(inventories[local]);
            Require(_fights == before + 1, "Winning consumes only this player's shop bargain");
            Require(entries[local].Cost == 120, "Temporary negotiated price removed after native purchase");
            string shopsState = RngState(players[local].PlayerRng.Shops);
            var stream1 = (Rng)Manager.GetMethod("CreateFightRng", PrivateStatic)!.Invoke(null, [players[local]])!;
            var stream2 = (Rng)Manager.GetMethod("CreateFightRng", PrivateStatic)!.Invoke(null, [players[local]])!;
            Require(Enumerable.Range(0, 12).All(_ => stream1.NextInt(3) == stream2.NextInt(3)), "Same player/floor produces deterministic independent fight stream");
            Require(RngState(players[local].PlayerRng.Shops) == shopsState, "Fight RNG does not consume native shop RNG");
        }
        Require(_fights == fightStart + count, "Each party member can bargain independently");

        // A fresh shop inventory gets a fresh personal offer, including on loss.
        var loser = players[0];
        typeof(Player).GetProperty(nameof(Player.Gold))!.SetValue(loser, 110);
        var losingInventory = new MerchantInventory(loser);
        var losingEntry = new MerchantRelicEntry(ModelDb.Relic<Anchor>().ToMutable(), loser);
        typeof(MerchantEntry).GetField("_cost", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(losingEntry, 120);
        LocalContext.NetId = loser.NetId;
        SetUi(losingInventory);
        _win = false;
        int prior = _fights;
        for (int attempt = 0; attempt < 5; attempt++) await losingEntry.OnTryPurchaseWrapper(losingInventory);
        Require(_fights == prior + 1 && loser.Gold == 110 && losingEntry.IsStocked, "Loss consumes offer without taking gold or stock");
        for (int attempt = 0; attempt < 5; attempt++) await losingEntry.OnTryPurchaseWrapper(losingInventory);
        Require(_fights == prior + 1, "Lost fight cannot retrigger in the same personal shop");
    }

    private static (INetGameService, ConfigNetworkFake) HostEndpoint(ulong id)
    {
        var (service, wire) = ConfigNetworkFake.Host(); wire.Id = id; return (service, wire);
    }
    private static (INetGameService, ConfigNetworkFake) ClientEndpoint(ulong id)
    {
        var (service, wire) = ConfigNetworkFake.Peer(); wire.Id = id; return (service, wire);
    }
    private static void SetUi(MerchantInventory inventory)
    {
        _room?.Inventory?.Free(); _room?.Free();
        _room = new NMerchantRoom();
        var ui = new NMerchantInventory();
        typeof(NMerchantRoom).GetProperty(nameof(NMerchantRoom.Inventory))!.SetValue(_room, ui);
        typeof(NMerchantInventory).GetProperty(nameof(NMerchantInventory.Inventory))!.SetValue(ui, inventory);
        typeof(NMerchantInventory).GetProperty(nameof(NMerchantInventory.IsOpen))!.SetValue(ui, true);
    }
    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
        _assertions++;
    }

    private static string RngState(Rng rng)
    {
#if STS2_V107_1
        return rng.Counter.ToString(System.Globalization.CultureInfo.InvariantCulture);
#else
        return System.Text.Json.JsonSerializer.Serialize(rng.ToSerializable(),
            new System.Text.Json.JsonSerializerOptions { IncludeFields = true });
#endif
    }

    private static Assembly? ResolveDependency(AssemblyLoadContext context, AssemblyName name)
    {
        string file = Path.Combine(Path.GetDirectoryName(typeof(MerchantBargainProbeNode).Assembly.Location)!, name.Name + ".dll");
        return File.Exists(file) ? context.LoadFromAssemblyPath(file) : null;
    }
    private static void InitializeModels()
    {
        var types = Mod.GetTypes();
        typeof(ReflectionHelper).GetField("_modTypes", PrivateStatic)!.SetValue(null, types);
        var game = typeof(ModManager).Assembly;
        Type modType = game.GetType("MegaCrit.Sts2.Core.Modding.Mod", true)!;
        Type manifestType = game.GetType("MegaCrit.Sts2.Core.Modding.ModManifest", true)!;
        object manifest = Activator.CreateInstance(manifestType)!;
        manifestType.GetField("id")!.SetValue(manifest, "STS2_Things");
        manifestType.GetField("name")!.SetValue(manifest, "STS2 Things Merchant Probe");
        object mod = Activator.CreateInstance(modType)!;
        modType.GetField("manifest")!.SetValue(mod, manifest);
        modType.GetField("path")!.SetValue(mod, "probe://merchant");
        var state = modType.GetField("state")!; state.SetValue(mod, Enum.Parse(state.FieldType, "Loaded"));
        if (modType.GetField("assemblies")?.GetValue(mod) is IList assemblies) assemblies.Add(Mod);
        else modType.GetField("assembly")!.SetValue(mod, Mod);
        var mods = (IList)typeof(ModManager).GetField("_mods", PrivateStatic)!.GetValue(null)!; mods.Clear(); mods.Add(mod);
        var managerState = typeof(ModManager).GetProperty("State");
        if (managerState != null) managerState.SetValue(null, Enum.Parse(managerState.PropertyType, "Initialized"));
        game.GetType("MegaCrit.Sts2.Core.Modding.AssemblyInfo")?.GetMethod("Init")?.Invoke(null, null);
        Type[] models = AbstractModelSubtypes.All.Concat(types.Where(t => !t.IsAbstract && typeof(AbstractModel).IsAssignableFrom(t))).Distinct().ToArray();
        MethodInfo init = typeof(ModelDb).GetMethods().Single(m => m.Name == "Init");
        init.Invoke(null, init.GetParameters().Length == 0 ? null : [models]);
        game.GetType("MegaCrit.Sts2.Core.Multiplayer.Serialization.ModelIdSerializationCache", true)!.GetMethod("Init")!.Invoke(null, null);
        typeof(ModelDb).GetMethod("InitIds")!.Invoke(null, null);
        MessageTypes.Initialize();
    }
}
