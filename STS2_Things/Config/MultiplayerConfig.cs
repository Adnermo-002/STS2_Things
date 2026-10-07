using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Multiplayer.Game;

namespace STS2_Things.Config;

/// <summary>Session overrides never replace the local preferences written to disk.</summary>
public static class MultiplayerConfig
{
    private static INetGameService? _service;
    private static ThingsConfigSnapshotMessage? _snapshot;
    private static bool _initialized;
    private static readonly Dictionary<string, int> Indices = ThingsModConfig.Entries
        .Select((entry, index) => (entry.Key, index)).ToDictionary(pair => pair.Key, pair => pair.index);

    public static bool IsActive => _service is not null;
    public static bool IsHost => _service?.Type == NetGameType.Host;
    public static bool IsLocked => _snapshot?.Locked == true;
    public static bool HasSnapshot => _snapshot.HasValue;

    public static void Initialize()
    {
        if (_initialized) return;
        _initialized = true;
        ThingsModConfig.LocalChanged += OnLocalChanged;
    }

    public static bool CanEdit(string key) => !IsActive ||
        IsHost && (!IsLocked || key == ThingsModConfig.FeatureCustomBgmEnabled);

    public static object? GetOverride(string key)
    {
        if (_snapshot is not { } snapshot || !Indices.TryGetValue(key, out int index)) return null;
        return ThingsModConfig.Entries[index].Default is bool ? (object)(snapshot.Values[index] == 1) : snapshot.Values[index];
    }

    public static void Bind(INetGameService service, bool lockForLoadedRun = false)
    {
        Initialize();
        if (service.Type is not (NetGameType.Host or NetGameType.Client))
        {
            Clear();
            return;
        }
        if (ReferenceEquals(_service, service))
        {
            if (lockForLoadedRun && IsHost && !IsLocked) PrepareRun(service);
            return;
        }
        Clear();
        _service = service;
        service.RegisterMessageHandler<ThingsConfigSnapshotMessage>(Receive);
        service.Disconnected += OnDisconnected;
        if (service is INetHostGameService host)
        {
            host.ClientConnected += SendToJoiningPlayer;
            CaptureHost(lockForLoadedRun);
            foreach (ulong peer in host.NetHost?.ConnectedPeerIds ?? []) SendToJoiningPlayer(peer);
        }
        ThingsModConfig.NotifyEffectiveChanged();
    }

    public static void Clear()
    {
        if (_service is not { } service) return;
        _service = null;
        _snapshot = null;
        service.UnregisterMessageHandler<ThingsConfigSnapshotMessage>(Receive);
        service.Disconnected -= OnDisconnected;
        if (service is INetHostGameService host) host.ClientConnected -= SendToJoiningPlayer;
        ThingsModConfig.NotifyEffectiveChanged();
    }

    public static bool PrepareRun(INetGameService service)
    {
        Bind(service);
        if (!IsActive) return true;
        if (IsHost)
        {
            if (!IsLocked)
            {
                CaptureHost(locked: true);
                Broadcast();
                ThingsModConfig.NotifyEffectiveChanged();
            }
            return true;
        }
        if (IsLocked) return true;
        RejectIncompatibleSession("No final host configuration was received before run start.");
        return false;
    }

    public static void Detach(INetGameService? service)
    {
        if (ReferenceEquals(service, _service)) Clear();
    }

    private static void CaptureHost(bool locked)
    {
        int[] values = _snapshot is { Locked: true } old ? (int[])old.Values.Clone() :
            ThingsModConfig.Entries.Select(entry => Convert.ToInt32(ThingsModConfig.GetLocalValue(entry.Key))).ToArray();
        values[Indices[ThingsModConfig.FeatureCustomBgmEnabled]] =
            Convert.ToInt32(ThingsModConfig.GetLocalValue(ThingsModConfig.FeatureCustomBgmEnabled));
        _snapshot = new ThingsConfigSnapshotMessage
        {
            Version = ThingsConfigSnapshotMessage.Protocol,
            SchemaHash = ThingsConfigSnapshotMessage.Schema,
            Revision = (_snapshot?.Revision ?? 0) + 1,
            Locked = locked,
            Values = values,
        };
    }

    private static void OnLocalChanged()
    {
        if (!IsHost) return;
        CaptureHost(IsLocked);
        Broadcast();
    }

    private static void Broadcast()
    {
        if (_service is { IsConnected: true } service && _snapshot is { } snapshot)
            service.SendMessage(snapshot);
    }

    private static void SendToJoiningPlayer(ulong playerId)
    {
        if (_service is { IsConnected: true } service && _snapshot is { } snapshot)
            service.SendMessage(snapshot, playerId);
    }

    private static void Receive(ThingsConfigSnapshotMessage message, ulong senderId)
    {
        if (_service is not INetClientGameService client || client.NetClient?.HostNetId != senderId)
            return;
        if (!message.IsValid())
        {
            RejectIncompatibleSession("Host configuration protocol or values are incompatible.");
            return;
        }
        if (_snapshot is { } previous)
        {
            if (message.Revision <= previous.Revision) return;
            if (previous.Locked && (!message.Locked || message.Values.Where((value, index) =>
                    index != Indices[ThingsModConfig.FeatureCustomBgmEnabled] && value != previous.Values[index]).Any()))
            {
                RejectIncompatibleSession("Host attempted to change locked gameplay configuration.");
                return;
            }
        }
        _snapshot = message with { Values = (int[])message.Values.Clone() };
        ThingsModConfig.NotifyEffectiveChanged();
        Log.Info($"STS2_Things: host configuration applied (revision {message.Revision}, locked={message.Locked}).");
    }

    private static void RejectIncompatibleSession(string reason)
    {
        Log.Warn("STS2_Things: " + reason + " All players must use the same mod build.");
        _service?.Disconnect(NetError.ModMismatch);
        Clear();
    }

    private static void OnDisconnected(NetErrorInfo _) => Clear();
}
