using Godot;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Multiplayer.Connection;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Multiplayer.Messages.Game.Checksums;

public partial class DepthsProbeNode
{
    private async Task VerifyLoopback()
    {
        MegaCrit.Sts2.Core.Multiplayer.Serialization.MessageTypes.Initialize();
        var host=new NetHostGameService(PeerVersionInfo.LocalDefault());
        var client=new NetClientGameService(PeerVersionInfo.LocalDefault());
        var received=new List<NetChecksumData>();
        host.RegisterMessageHandler<ChecksumDataMessage>((message,_)=>received.Add(message.checksumData));
        try
        {
            Assert(host.StartENetHost(19243,1)==null,"Native ENet host starts");
            var connect=new ENetClientConnectionInitializer(2,"127.0.0.1",19243).Connect(client);
            ulong deadline=Time.GetTicksMsec()+10000;
            while(!connect.IsCompleted || !client.IsConnected || host.ConnectedPeers.Count==0)
            {
                host.Update();client.Update();
                Assert(Time.GetTicksMsec()<deadline,"Native host/client connection finishes");
                await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            }
            Assert(await connect==null,"Native version/mod handshake accepts both peers");
            var b=await Battle(2);
            foreach(var p in b.Run.Players)await MegaCrit.Sts2.Core.Commands.OstyCmd.Summon(Choice,p,3,null);
            using var tracker=new ChecksumTracker(host,b.Run);
            for(int i=0;i<8;i++)
            {
                await MegaCrit.Sts2.Core.Commands.DamageCmd.Attack(8).FromMonster(b.Room.CombatState.Enemies.First().Monster!).Execute(Choice);
                var expected=tracker.GenerateChecksum("pet-death-loopback-"+i,null);
                client.SendMessage(new ChecksumDataMessage{checksumData=expected});
                deadline=Time.GetTicksMsec()+3000;
                while(received.Count<=i)
                {
                    host.Update();client.Update();
                    Assert(Time.GetTicksMsec()<deadline,"Post-death checksum arrives at the host");
                    await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
                }
                Assert(received[i].id==expected.id && received[i].checksum==expected.checksum,
                    "Reliable native checksum packet survives summon deaths");
                foreach(var p in b.Run.Players)await MegaCrit.Sts2.Core.Commands.OstyCmd.Summon(Choice,p,3,null);
            }
            GD.Print("PET_DEATH_ENET_PASS real loopback connection, eight post-death native checksums received");
        }
        finally
        {
            client.Disconnect(NetError.Quit,true);host.Disconnect(NetError.Quit,true);
        }
    }
}
