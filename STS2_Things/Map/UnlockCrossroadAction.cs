using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Gold;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Multiplayer.Serialization;
using MegaCrit.Sts2.Core.Runs;
using STS2_Things.Modifiers;

namespace STS2_Things.Map;

public enum CrossroadPurchaseResult { Purchased, AlreadyOpen, Stale, NotAtRoad, InsufficientGold }

public static class Crossroads
{
    public static event Action<IRunState>? Changed;
    public static ThingsCrossroads? Ledger(IRunState run) => run.Modifiers.OfType<ThingsCrossroads>().FirstOrDefault();

    public static async Task<CrossroadPurchaseResult> Purchase(Player payer, int act, ulong fingerprint, MapCoord from, MapCoord to, int quotedPrice)
    {
        if (payer.RunState is not RunState run || !run.Players.Contains(payer)) return CrossroadPurchaseResult.Stale;
        if (run.CurrentActIndex != act || quotedPrice != CrossroadPlan.Price || run.Map == null ||
            CrossroadPlan.Fingerprint(run.Map) != fingerprint) return CrossroadPurchaseResult.Stale;
        if (run.CurrentMapCoord != from || run.VisitedMapCoords.Contains(to)) return CrossroadPurchaseResult.NotAtRoad;
        var ledger = Ledger(run);
        var plan = ledger?.EnsurePlan(run, run.Map, act);
        var road = plan?.Roads.FirstOrDefault(r => r.Touches(from) && r.Other(from) == to);
        if (road == null) return CrossroadPurchaseResult.Stale;
        if (road.IsOpen) return CrossroadPurchaseResult.AlreadyOpen;
        if (run.Map.GetPoint(from) is not { } source || run.Map.GetPoint(to) is not { } destination ||
            source.Children.Contains(destination) || destination.Children.Contains(source)) return CrossroadPurchaseResult.Stale;
        if (payer.Gold < CrossroadPlan.Price) return CrossroadPurchaseResult.InsufficientGold;

        // Native gold spending is synchronous. Reserve before yielding so two
        // confirmed requests cannot charge twice or open a reverse cycle.
        road.FromColumn = from.col;
        road.Payer = payer.NetId;
        await PlayerCmd.LoseGold(CrossroadPlan.Price, payer, GoldLossType.Spent);
        source.AddChildPoint(destination);
        ledger!.Commit();
        Changed?.Invoke(run);
        return CrossroadPurchaseResult.Purchased;
    }
}

public sealed class UnlockCrossroadAction(Player player, int act, ulong fingerprint, MapCoord from, MapCoord to, int price) : GameAction
{
    public override ulong OwnerId => player.NetId;
    public override GameActionType ActionType => GameActionType.NonCombat;
    protected override async Task ExecuteAction() =>
        await Crossroads.Purchase(player, act, fingerprint, from, to, price);
    public override INetAction ToNetAction() => new NetUnlockCrossroadAction { Act = act, Fingerprint = fingerprint, From = from, To = to, Price = price };
}

public struct NetUnlockCrossroadAction : INetAction, IPacketSerializable
{
    public int Act;
    public ulong Fingerprint;
    public MapCoord From;
    public MapCoord To;
    public int Price;
    public GameAction ToGameAction(Player player) => new UnlockCrossroadAction(player, Act, Fingerprint, From, To, Price);
    public void Serialize(PacketWriter writer)
    { writer.WriteInt(Act); writer.WriteULong(Fingerprint); writer.Write(From); writer.Write(To); writer.WriteInt(Price); }
    public void Deserialize(PacketReader reader)
    { Act = reader.ReadInt(); Fingerprint = reader.ReadULong(); From = reader.Read<MapCoord>(); To = reader.Read<MapCoord>(); Price = reader.ReadInt(); }
}
