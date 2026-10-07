using System.Reflection;
using Godot;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Acts;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Multiplayer.Game.Lobby;
using MegaCrit.Sts2.Core.Multiplayer.Serialization;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Config;

public static class MultiplayerConfigChecks
{
    public static void Run()
    {
        typeof(MessageTypes).GetMethod("Initialize")?.Invoke(null, null);
        MultiplayerConfig.Clear();
        Reset();
        ThingsModConfig.SetValue(ThingsModConfig.BossOnlyModBosses, true);
        ThingsModConfig.SetValue(ThingsModConfig.BossOriginFogmogWeightPercent, 900);
        ThingsModConfig.SetValue(ThingsModConfig.EncounterSoulRoesWeightPercent, 10);
        ThingsModConfig.SetValue(ThingsModConfig.EncounterQuirkyHopperEnabled, false);
        ThingsModConfig.SetValue(ThingsModConfig.EventBackroomsEnabled, false);
        ThingsModConfig.SetValue(ThingsModConfig.NeowRelicWhiteFlagEnabled, false);
        var (host, hostWire) = ConfigNetworkFake.Host();
        var listener = DispatchProxy.Create<IStartRunLobbyListener, ConfigSilentListener>();
        var lobby = new StartRunLobby(GameMode.Standard, host, listener, 4);
        Assert(MultiplayerConfig.IsHost && !MultiplayerConfig.IsLocked, "Host lobby was not attached by its constructor.");
        ThingsModConfig.SetValue(ThingsModConfig.FeatureCustomBgmEnabled, false);
        var preview = (ThingsConfigSnapshotMessage)hostWire.Sent.Last();
        Assert(MultiplayerConfig.PrepareRun(host), "Host could not prepare run.");
        var final = (ThingsConfigSnapshotMessage)hostWire.Sent.Last();
        Assert(final.Locked && final.IsValid(), "Host did not send a final valid snapshot.");
        string hostRooms = Rooms();
        ThingsModConfig.SetValue(ThingsModConfig.BossOnlyModBosses, false);
        Assert(ThingsModConfig.GetBool(ThingsModConfig.BossOnlyModBosses), "Host changed gameplay after start.");
        ThingsModConfig.SetValue(ThingsModConfig.FeatureCustomBgmEnabled, true);
        var music = (ThingsConfigSnapshotMessage)hostWire.Sent.Last();
        Assert(music.Revision > final.Revision, "Host music change was not published.");
        lobby.CleanUp(false);
        Assert(MultiplayerConfig.IsActive, "Lobby-to-run transition cleared host configuration.");
        MultiplayerConfig.Clear();

        Reset();
        ThingsModConfig.SetValue(ThingsModConfig.BossOriginFogmogEnabled, false);
        ThingsModConfig.SetValue(ThingsModConfig.BossScaleBeetleWeightPercent, 0);
        ThingsModConfig.Save();
        string localFile = File.ReadAllText(ThingsModConfig.ConfigPath);
        var local = ThingsModConfig.Entries.ToDictionary(entry => entry.Key, entry => ThingsModConfig.GetValue(entry.Key));
        var (client, clientWire) = ConfigNetworkFake.Peer();
        AttachJoin(client);
        Assert(MultiplayerConfig.IsActive && !MultiplayerConfig.HasSnapshot, "Client was not attached before joining.");
        clientWire.Deliver(RoundTrip(preview), sender: 999);
        Assert(!MultiplayerConfig.HasSnapshot, "A non-host changed client configuration.");
        clientWire.Deliver(RoundTrip(preview));
        Assert(!ThingsModConfig.GetBool(ThingsModConfig.FeatureCustomBgmEnabled), "Lobby snapshot not applied.");
        clientWire.Deliver(RoundTrip(final));
        Assert(MultiplayerConfig.PrepareRun(client), "Client did not accept the final host snapshot.");
        Assert(hostRooms == Rooms(), "Host and client generated different bosses, elites, events or RNG states.");
        ThingsModConfig.SetValue(ThingsModConfig.BossOnlyModBosses, false);
        ThingsModConfig.SetValue(ThingsModConfig.FeatureCustomBgmEnabled, true);
        Assert(ThingsModConfig.GetBool(ThingsModConfig.BossOnlyModBosses) &&
               !ThingsModConfig.GetBool(ThingsModConfig.FeatureCustomBgmEnabled), "Client overrode host settings.");
        ThingsModConfig.Save();
        ThingsModConfig.Load();
        Assert(File.ReadAllText(ThingsModConfig.ConfigPath) == localFile && hostRooms == Rooms(),
            "Session settings replaced local preferences or local reload replaced host settings.");
        clientWire.Deliver(RoundTrip(music));
        Assert(ThingsModConfig.GetBool(ThingsModConfig.FeatureCustomBgmEnabled), "Host music did not update client.");
        clientWire.Deliver(RoundTrip(final));
        Assert(ThingsModConfig.GetBool(ThingsModConfig.FeatureCustomBgmEnabled), "Stale packet rolled back settings.");
        MultiplayerConfig.Clear();
        Assert(ThingsModConfig.Entries.All(entry => Equals(local[entry.Key], ThingsModConfig.GetValue(entry.Key))),
            "Leaving did not restore every local setting.");

        // Rejoin/load receives the same frozen host snapshot before restoring a run.
        var (rejoin, rejoinWire) = ConfigNetworkFake.Peer();
        AttachJoin(rejoin);
        rejoinWire.Deliver(RoundTrip(music));
        Assert(MultiplayerConfig.PrepareRun(rejoin) && Rooms() == hostRooms, "Rejoin did not restore the active host configuration.");
        var illegal = music with { Revision = music.Revision + 1, Values = (int[])music.Values.Clone() };
        illegal.Values[1] = 0;
        rejoinWire.Deliver(RoundTrip(illegal));
        Assert(rejoinWire.DisconnectReason == NetError.ModMismatch && !MultiplayerConfig.IsActive,
            "A gameplay change after start was accepted.");
        var (missing, missingWire) = ConfigNetworkFake.Peer();
        AttachJoin(missing);
        Assert(!MultiplayerConfig.PrepareRun(missing) && missingWire.DisconnectReason == NetError.ModMismatch,
            "Missing host configuration silently fell back to local settings.");
        var (invalid, invalidWire) = ConfigNetworkFake.Peer();
        AttachJoin(invalid);
        invalidWire.Deliver(music with { Version = 999 });
        Assert(invalidWire.DisconnectReason == NetError.ModMismatch, "Incompatible protocol was accepted.");
        Assert(!(music with { SchemaHash = 0 }).IsValid(), "Incompatible schema was accepted.");
        Assert(!(music with { Values = [] }).IsValid(), "Truncated snapshot was accepted.");
        MultiplayerConfig.Clear();
        var (loadedHost, _) = ConfigNetworkFake.Host();
        MultiplayerConfig.Bind(loadedHost);
        MultiplayerConfig.Bind(loadedHost, lockForLoadedRun: true);
        Assert(MultiplayerConfig.IsLocked, "A reused host service did not lock when resuming a saved run.");
        MultiplayerConfig.Clear();
        Reset();
        ThingsModConfig.Save();
        GD.Print("Multiplayer config: PASS (authority, packet codec, deterministic rooms, locking, music, rejoin, cleanup, local-file isolation)");
    }

    private static void AttachJoin(INetClientGameService service)
    {
        if (typeof(JoinFlow).GetConstructor([typeof(INetClientGameService)]) is { } constructor)
            constructor.Invoke([service]);
        else
            MultiplayerConfig.Bind(service);
    }

    private static ThingsConfigSnapshotMessage RoundTrip(ThingsConfigSnapshotMessage message)
    {
#if STS2_V107_1
        var bus = new NetMessageBus();
#else
        var bus = new NetMessageBus(new PacketReader(), new PacketWriter());
#endif
        byte[] bytes = bus.SerializeMessage(1, message, out int length)[..length];
        Assert(bus.TryDeserializeMessage(bytes, out var decoded, out var sender) && sender == 1,
            "Native message bus could not round-trip configuration.");
        return (ThingsConfigSnapshotMessage)decoded!;
    }

    public static string Rooms()
    {
        var parts = new List<string>();
        foreach (ActModel model in new ActModel[] { ModelDb.Act<Overgrowth>(), ModelDb.Act<Underdocks>(), ModelDb.Act<Hive>() })
        {
            ActModel act = model.ToMutable();
            var rng = new Rng(319);
            act.GenerateRooms(rng, UnlockState.all, isMultiplayer: true);
            act.ApplyDiscoveryOrderModifications(UnlockState.all);
            parts.Add(act.BossEncounter.Id.ToString());
            parts.AddRange(act.AllEvents.Select(entry => entry.Id.ToString()));
            for (int i = 0; i < 15; i++)
            {
                parts.Add(act.PullNextEncounter(RoomType.Elite).Id.ToString());
                act.MarkRoomVisited(RoomType.Elite);
            }
            parts.Add(rng.NextInt().ToString());
        }
        return string.Join("|", parts);
    }

    private static void Reset() => ThingsModConfig.SetValues(ThingsModConfig.Entries.ToDictionary(entry => entry.Key, entry => (object?)entry.Default));
    private static void Assert(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException("Multiplayer config probe: " + message);
    }
}
