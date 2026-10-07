using System.Security.Cryptography;
using System.Text;
using Godot;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Multiplayer.Connection;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Multiplayer.Serialization;
using MegaCrit.Sts2.Core.Multiplayer.Transport;
using STS2_Things.Config;

public struct ConfigNetworkProbeMessage : INetMessage
{
    public string Text;
    public bool ShouldBroadcast => false;
    public NetTransferMode Mode => NetTransferMode.Reliable;
    public LogLevel LogLevel => LogLevel.Debug;
    public bool ShouldBuffer => false;
    public void Serialize(PacketWriter writer) => writer.WriteString(Text);
    public void Deserialize(PacketReader reader) => Text = reader.ReadString();
}

/// <summary>Three separate Godot processes, connected through the actual ENet/game codec.</summary>
public partial class ConfigNetworkLiveProbe : Node
{
    private INetGameService? _service;
    private string _role = "";
    private string _output = "";
    private ushort _port;
    private string _localFile = "";
    private readonly HashSet<ulong> _joined = [];
    private readonly HashSet<ulong> _digests = [];
    private readonly HashSet<ulong> _music = [];
    private string _digest = "";
    private bool _rejoining;
    private bool _finished;
    private double _elapsed;

    private static PeerVersionInfo Version => new()
    {
        version = "v0.111.0", idDatabaseHash = ModelIdSerializationCache.Hash,
        gameplayAffectingMods = ["STS2_Things-1.11.0", "ConfigNetworkProbe"], otherMods = [],
    };

    public override void _Ready()
    {
        try
        {
            string[] args = OS.GetCmdlineUserArgs();
            _role = args[1];
            _port = ushort.Parse(args[2]);
            _output = args[3];
            MessageTypes.Initialize();
            if (_role == "host") StartHost(); else _ = Connect();
        }
        catch (Exception error) { Fail(error); }
    }

    private void StartHost()
    {
        ThingsModConfig.SetValue(ThingsModConfig.BossOnlyModBosses, true);
        ThingsModConfig.SetValue(ThingsModConfig.BossOriginFogmogForced, true);
        ThingsModConfig.SetValue(ThingsModConfig.EncounterSoulRoesWeightPercent, 10);
        ThingsModConfig.SetValue(ThingsModConfig.EventMedusaEnabled, false);
        ThingsModConfig.SetValue(ThingsModConfig.EncounterQuirkyHopperEnabled, false);
        ThingsModConfig.SetValue(ThingsModConfig.NeowRelicWhiteFlagEnabled, false);
        ThingsModConfig.SetValue(ThingsModConfig.FeatureCustomBgmEnabled, false);
        var host = new NetHostGameService(Version);
        if (host.StartENetHost(_port, 4) is { } error) throw new Exception(error.ToString());
        _service = host;
        MultiplayerConfig.Bind(host);
        host.RegisterMessageHandler<ConfigNetworkProbeMessage>(HandleHost);
        host.ClientConnected += id =>
        {
            host.SetPeerReadyForBroadcasting(id);
            // Bind registered its snapshot callback first; this marker must arrive later.
            Send(_digests.Count == 2 ? "rejoin" : "preview", id);
        };
        File.WriteAllText(Path.Combine(_output, "host-ready"), "ready");
    }

    private async Task Connect()
    {
        try
        {
            ThingsModConfig.SetValue(ThingsModConfig.BossOriginFogmogEnabled, false);
            ThingsModConfig.SetValue(ThingsModConfig.BossScaleBeetleWeightPercent, _role == "client2" ? 0 : 1000);
            ThingsModConfig.SetValue(ThingsModConfig.EncounterSoulRoesWeightPercent, 1000);
            ThingsModConfig.Save();
            _localFile = File.ReadAllText(ThingsModConfig.ConfigPath);
            var client = new NetClientGameService(Version);
            _service = client;
            // The production JoinFlow constructor attaches configuration before connecting.
            _ = new JoinFlow(client);
            client.RegisterMessageHandler<ConfigNetworkProbeMessage>(HandleClient);
            var initializer = new ENetClientConnectionInitializer(_role == "client2" ? 3UL : 2UL, "127.0.0.1", _port);
            if (await initializer.Connect(client) is { } error) throw new Exception(error.ToString());
        }
        catch (Exception error) { Fail(error); }
    }

    private void HandleHost(ConfigNetworkProbeMessage message, ulong sender)
    {
        try
        {
            if (message.Text == "preview-ok")
            {
                _joined.Add(sender);
                if (_joined.Count == 2)
                {
                    Assert(MultiplayerConfig.PrepareRun(_service!), "Host did not freeze configuration.");
                    _digest = Digest();
                    Send("start");
                }
            }
            else if (message.Text.StartsWith("rooms:"))
            {
                Assert(message.Text[6..] == _digest, "Independent process generated different rooms/RNG.");
                _digests.Add(sender);
                if (_digests.Count == 2)
                {
                    Assert(ThingsModConfig.GetBool(ThingsModConfig.BossOnlyModBosses), "Client changed host settings.");
                    ThingsModConfig.SetValue(ThingsModConfig.FeatureCustomBgmEnabled, true);
                    Send("music");
                }
            }
            else if (message.Text == "music-ok")
            {
                _music.Add(sender);
                if (_music.Count == 2) Send("reconnect", 3);
            }
            else if (message.Text == "rejoin-ok")
            {
                Send("finish");
                _ = FinishHostAfterFlush();
            }
        }
        catch (Exception error) { Fail(error); }
    }

    private void HandleClient(ConfigNetworkProbeMessage message, ulong sender)
    {
        try
        {
            if (message.Text == "preview")
            {
                Assert(MultiplayerConfig.HasSnapshot && !MultiplayerConfig.IsLocked, "Initial host snapshot arrived too late.");
                Send("preview-ok");
            }
            else if (message.Text == "start")
            {
                Assert(MultiplayerConfig.IsLocked && MultiplayerConfig.PrepareRun(_service!), "Run start overtook final snapshot.");
                ThingsModConfig.SetValue(ThingsModConfig.BossOnlyModBosses, false);
                Assert(ThingsModConfig.GetBool(ThingsModConfig.BossOnlyModBosses), "Client overrode host settings.");
                ThingsModConfig.Save();
                Assert(File.ReadAllText(ThingsModConfig.ConfigPath) == _localFile, "Client local preferences were overwritten.");
                _digest = Digest();
                Send("rooms:" + _digest);
            }
            else if (message.Text == "music")
            {
                Assert(ThingsModConfig.GetBool(ThingsModConfig.FeatureCustomBgmEnabled), "Host music update was not delivered.");
                Assert(Digest() == _digest, "Music update changed gameplay/RNG.");
                Send("music-ok");
            }
            else if (message.Text == "reconnect") _rejoining = true;
            else if (message.Text == "rejoin")
            {
                Assert(MultiplayerConfig.IsLocked && Digest() == _digest, "Reconnect missed active host settings.");
                Send("rejoin-ok");
            }
            else if (message.Text == "finish") Finish();
        }
        catch (Exception error) { Fail(error); }
    }

    public override void _Process(double delta)
    {
        if (_finished) return;
        try
        {
            _elapsed += delta;
            if (_elapsed > 30) throw new TimeoutException("Network probe timed out.");
            _service?.Update();
            if (_rejoining)
            {
                _rejoining = false;
                _service!.Disconnect(NetError.Quit);
                MultiplayerConfig.Clear();
                Assert(!ThingsModConfig.GetBool(ThingsModConfig.BossOnlyModBosses), "Disconnect did not restore local settings.");
                _ = ReconnectAfterClose();
            }
        }
        catch (Exception error) { Fail(error); }
    }

    private async Task ReconnectAfterClose()
    {
        await ToSignal(GetTree().CreateTimer(0.3), SceneTreeTimer.SignalName.Timeout);
        await Connect();
    }

    private async Task FinishHostAfterFlush()
    {
        await ToSignal(GetTree().CreateTimer(0.5), SceneTreeTimer.SignalName.Timeout);
        Finish();
    }

    private void Send(string text, ulong? target = null)
    {
        var message = new ConfigNetworkProbeMessage { Text = text };
        if (target is { } id) _service!.SendMessage(message, id); else _service!.SendMessage(message);
    }

    private void Finish()
    {
        if (_finished) return;
        _finished = true;
        _service?.Disconnect(NetError.Quit);
        MultiplayerConfig.Clear();
        if (_role != "host") Assert(File.ReadAllText(ThingsModConfig.ConfigPath) == _localFile, "Cleanup changed preferences.");
        File.WriteAllText(Path.Combine(_output, _role + ".result"), "PASS " + _digest);
        GD.Print("ENet config probe: PASS " + _role + " " + _digest);
        GetTree().Quit(0);
    }

    private void Fail(Exception error)
    {
        _finished = true;
        GD.PushError(error.ToString());
        GetTree().Quit(1);
    }

    private static string Digest() => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(MultiplayerConfigChecks.Rooms())));
    private static void Assert(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
}
