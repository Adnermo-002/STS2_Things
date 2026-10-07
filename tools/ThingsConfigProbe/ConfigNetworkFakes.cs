using System.Reflection;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Multiplayer.Serialization;
using MegaCrit.Sts2.Core.Multiplayer.Transport;

public class ConfigNetworkFake : DispatchProxy
{
    public NetGameType Kind;
    public ulong Id;
    public bool Connected = true;
    public NetClient? Client;
    public readonly List<INetMessage> Sent = [];
    public readonly Dictionary<Type, Delegate> Handlers = [];
    public NetError? DisconnectReason;
    private readonly Dictionary<string, Delegate?> _events = [];

    public static (INetHostGameService Service, ConfigNetworkFake Fake) Host()
    {
        INetHostGameService service = Create<INetHostGameService, ConfigNetworkFake>();
        var fake = (ConfigNetworkFake)(object)service;
        fake.Kind = NetGameType.Host;
        fake.Id = 1;
        return (service, fake);
    }

    public static (INetClientGameService Service, ConfigNetworkFake Fake) Peer()
    {
        INetClientGameService service = Create<INetClientGameService, ConfigNetworkFake>();
        var fake = (ConfigNetworkFake)(object)service;
        fake.Kind = NetGameType.Client;
        fake.Id = 2;
        fake.Client = new ConfigFakeTransport(service as INetClientHandler ?? Create<INetClientHandler, ConfigSilentListener>());
        return (service, fake);
    }

    public void Deliver(INetMessage message, ulong sender = 1) => Handlers[message.GetType()].DynamicInvoke(message, sender);

    protected override object? Invoke(MethodInfo? method, object?[]? args)
    {
        args ??= [];
        string name = method!.Name;
        if (name == "get_Type") return Kind;
        if (name == "get_NetId") return Id;
        if (name == "get_NetClient") return Client;
        if (name == "get_IsConnected") return Connected;
        if (name == "get_ConnectedPeers") return new List<NetClientData>();
        if (name == "SendMessage") { Sent.Add((INetMessage)args[0]!); return null; }
        if (name == "RegisterMessageHandler")
        {
            Type type = method.GetGenericArguments()[0];
            Handlers[type] = Delegate.Combine(Handlers.GetValueOrDefault(type), (Delegate)args[0]!)!;
            return null;
        }
        if (name == "UnregisterMessageHandler")
        {
            Type type = method.GetGenericArguments()[0];
            Delegate? remaining = Delegate.Remove(Handlers.GetValueOrDefault(type), (Delegate)args[0]!);
            if (remaining is null) Handlers.Remove(type); else Handlers[type] = remaining;
            return null;
        }
        if (name.StartsWith("add_"))
        {
            _events[name[4..]] = Delegate.Combine(_events.GetValueOrDefault(name[4..]), (Delegate?)args[0]);
            return null;
        }
        if (name.StartsWith("remove_"))
        {
            _events[name[7..]] = Delegate.Remove(_events.GetValueOrDefault(name[7..]), (Delegate?)args[0]);
            return null;
        }
        if (name == "Disconnect")
        {
            DisconnectReason = (NetError)args[0]!;
            Connected = false;
            return null;
        }
        return method.ReturnType == typeof(void) || !method.ReturnType.IsValueType
            ? null : Activator.CreateInstance(method.ReturnType);
    }
}

public class ConfigSilentListener : DispatchProxy
{
    protected override object? Invoke(MethodInfo? method, object?[]? args) =>
        method!.ReturnType == typeof(void) || !method.ReturnType.IsValueType
            ? null : Activator.CreateInstance(method.ReturnType);
}

public sealed class ConfigFakeTransport(INetClientHandler handler) : NetClient(handler)
{
    public override bool IsConnected => true;
    public override ulong NetId => 2;
    public override ulong HostNetId => 1;
    public override void Update() { }
    public override void SendMessageToHost(byte[] bytes, int length, NetTransferMode mode, int channel = 0) { }
    public override void DisconnectFromHost(NetError reason, bool now = false) { }
    public override string? GetRawLobbyIdentifier() => "config-probe";
}
