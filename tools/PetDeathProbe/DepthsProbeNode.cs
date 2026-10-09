using System.Reflection;
using System.Runtime.Loader;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.Multiplayer.Serialization;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Monsters;
using STS2_Things.Acts;

public partial class DepthsProbeNode : Node
{
    private static readonly ThrowingPlayerChoiceContext Choice=new();
    private static int _checks;
    private string _root=null!;
    private static void Assert(bool pass,string text)
    { if(!pass)throw new InvalidOperationException(text);_checks++; }
    private static bool HostMode(ref NetGameType __result){__result=NetGameType.Host;return false;}

    public override void _Ready()
    {
        AssemblyLoadContext.Default.Resolving+=ResolveRuntimeDependency;
#if !STS2_V107_1
        EnsureRuntimeDependency("Sentry");EnsureRuntimeDependency("Sentry.Godot");
#endif
        _=Run();
    }

    private async Task Run()
    {
        try
        {
            _root=Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"),"../.."));
            TestMode.TurnOnInternal();
            Assert(ProjectSettings.LoadResourcePack("D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck"),"Native PCK mount");
            Assert(ProjectSettings.LoadResourcePack(System.Environment.GetEnvironmentVariable("THINGS_PROBE_PCK")!),"Mod PCK mount");
            EnsureRuntimeDependency("System.IO.Hashing");
            RegisterSyntheticMod(typeof(LanternFish).Assembly);
            typeof(LanternFish).Assembly.GetTypes().Single(t=>t.Name=="STS2_ThingsInit")
                .GetMethod("Initialize",BindingFlags.Public|BindingFlags.Static)!.Invoke(null,null);
            InitializeModelDb();
            SaveManager.Instance.InitSettingsDataForTest();SaveManager.Instance.InitPrefsDataForTest();
            SaveManager.Instance.SettingsSave.Language="eng";LocManager.Initialize();
            if(OS.GetCmdlineUserArgs().Contains("--host"))
                new Harmony("PetDeathProbe.HostMode").Patch(AccessTools.PropertyGetter(typeof(NetSingleplayerGameService),nameof(NetSingleplayerGameService.Type)),
                    prefix:new HarmonyMethod(typeof(DepthsProbeNode),nameof(HostMode)));
            foreach(int count in new[]{2,4})
            {
                var b=await Battle(count);
                foreach(var p in b.Run.Players)await OstyCmd.Summon(Choice,p,3,null);
                var pets=b.Run.Players.Select(p=>p.Osty!).ToArray();
                Assert(pets.Length==count && pets.Distinct().Count()==count,"Separate Osty per player");
                var attacker=b.Room.CombatState.Enemies.First().Monster!;
                await DamageCmd.Attack(8).FromMonster(attacker).Execute(Choice);
                GD.Print("PET_DEATH_STATE "+System.Text.Json.JsonSerializer.Serialize(b.Run.Players.Select(p=>new{
                    id=p.NetId,hp=p.Creature.CurrentHp,pet=p.Osty?.CurrentHp,alive=p.IsOstyAlive,pets=p.PlayerCombatState!.Pets.Count})));
                foreach(var p in b.Run.Players)
                {
                    Assert(!p.IsOstyAlive && p.PlayerCombatState!.Pets.Count==1,"Dead Osty remains available for native revival");
                    Assert(p.Creature.IsAlive && p.Creature.CurrentHp==p.Creature.MaxHp-5,"Overkill reaches the correct owner");
                }
                foreach(var p in b.Run.Players)await OstyCmd.Summon(Choice,p,4,null);
                Assert(b.Run.Players.All(p=>p.IsOstyAlive),"All dead Osty can be revived");
                foreach(var p in b.Run.Players)
                    await CreatureCmd.Damage(Choice,p.Creature,7,ValueProp.Move,attacker.Creature);
                Assert(b.Run.Players.All(p=>!p.IsOstyAlive && p.Creature.IsAlive),"Sequential group strikes kill each summon without killing an owner");
                GD.Print("PET_DEATH_NATIVE_PASS players="+count+" sequence=aoe,revive,group-strikes");
            }
            if(OS.GetCmdlineUserArgs().Contains("--matrix"))await VerifyEncounterMatrix();
            await VerifyNetworkState();
            if(OS.GetCmdlineUserArgs().Contains("--loopback"))await VerifyLoopback();
            if(OS.GetCmdlineUserArgs().Contains("--visual"))await VerifyPetDeathVisuals();
            DeactivateSyntheticCombat();
            GD.Print("Pet death probe: PASS ("+_checks+" assertions)");
            GetTree().Quit(0);
        }
        catch(Exception e){GD.PushError(e.ToString());GetTree().Quit(1);}
    }

    private static async Task<(RunState Run,CombatRoom Room)> Battle(int count,EncounterModel? canonical=null)
    {
        DeactivateSyntheticCombat();
        var party=Enumerable.Range(1,count).Select(i=>Player.CreateForNewRun<Necrobinder>(UnlockState.all,(ulong)i)).ToList();
        var run=RunState.CreateForNewRun(party,ActModel.GetDefaultList().Select(a=>a.ToMutable()).ToList(),[],GameMode.Standard,0,"pet-death-fixed-seed");
        typeof(RunManager).GetProperty("State",BindingFlags.NonPublic|BindingFlags.Instance)!.SetValue(RunManager.Instance,run);
        typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance,new AscensionManager(0));
        typeof(RunManager).GetProperty("NetService")!.SetValue(RunManager.Instance,new NetSingleplayerGameService());
        var encounter=(canonical??ModelDb.Encounter<LouseProgenitorNormal>()).ToMutable();
        run.AppendToMapPointHistory(MapPointType.Monster,RoomType.Monster,encounter.Id);
        var room=new CombatRoom(encounter,run);run.PushRoom(room);
        foreach(var p in party)
        { p.ResetCombatState();room.CombatState.AddPlayer(p);p.PopulateCombatState(run.Rng.Shuffle,room.CombatState); }
        encounter.GenerateMonstersWithSlots(run);
        foreach(var (monster,slot) in encounter.MonstersWithSlots)
        { var c=room.CombatState.CreateCreature(monster,CombatSide.Enemy,slot);room.CombatState.AddCreature(c);monster.SetUpForCombat();monster.RollMove(party.Select(p=>p.Creature)); }
        room.CombatState.CurrentSide=CombatSide.Player;ActivateSyntheticCombat(room.CombatState);
        foreach(var c in room.CombatState.Enemies.ToArray())await c.AfterAddedToRoom();
        return (run,room);
    }

    private async Task VerifyEncounterMatrix()
    {
        foreach(var canonical in ModelDb.Act<Depths>().AllEncounters.Where(e=>e.RoomType!=RoomType.Boss))
        {
            var b=await Battle(2,canonical);
            foreach(var p in b.Run.Players){p.Creature.SetMaxHpInternal(10000);p.Creature.SetCurrentHpInternal(10000);}
        await Hook.BeforeCombatStart(b.Run,b.Room.CombatState);
            for(int round=0;round<4;round++)
            {
                foreach(var p in b.Run.Players)
                {
                    if(p.IsOstyAlive)await CreatureCmd.Kill(p.Osty!,force:true);
                    await OstyCmd.Summon(Choice,p,1,null);
                }
                foreach(var monster in b.Room.CombatState.Enemies.Where(c=>c.IsAlive).Select(c=>c.Monster!).ToArray())
                {
                    await monster.PerformMove();monster.RollMove(b.Run.Players.Select(p=>p.Creature));
                }
                await CreatureCmd.Damage(Choice,b.Run.Players.Select(p=>p.Creature).ToArray(),1,ValueProp.Move,b.Room.CombatState.Enemies.First(c=>c.IsAlive));
                Assert(b.Run.Players.All(p=>!p.IsOstyAlive),"All summons can die with the encounter's actual powers");
            }
            GD.Print("PET_DEATH_ENCOUNTER_PASS "+canonical.Id.Entry);
        }
        var generic=await Battle(2);
        foreach(var p in generic.Run.Players)for(int i=0;i<2;i++)await PlayerCmd.AddPet<BowlbugRock>(p);
        var doomed=generic.Run.Players.SelectMany(p=>p.PlayerCombatState!.Pets).ToArray();
        await CreatureCmd.Damage(Choice,doomed,999,ValueProp.Unpowered,generic.Room.CombatState.Enemies.First());
        Assert(generic.Run.Players.All(p=>p.PlayerCombatState!.Pets.Count==0),"Multiple removable summons retire from the correct owners");
        Assert(generic.Run.Players.All(p=>p.Creature.IsAlive),"Direct summon deaths preserve every owner");
        GD.Print("PET_DEATH_GENERIC_PASS four independently owned removable pets");
    }

    private static byte[] NetworkState(RunState run)
    {
        var snapshot=NetFullCombatState.FromRun(run,null);
        var writer=new PacketWriter();writer.Write(snapshot);writer.ZeroByteRemainder();
        return writer.Buffer.Take(writer.BytePosition).ToArray();
    }

    private async Task VerifyNetworkState()
    {
        var packets=new List<byte[]>();
        foreach(ulong localId in new ulong[]{1,2})
        {
            var b=await Battle(2);
            LocalContext.NetId=localId;
            var net=RunManager.Instance.NetService;
            typeof(RunManager).GetProperty("PlayerChoiceSynchronizer")!.SetValue(RunManager.Instance,new PlayerChoiceSynchronizer(net,b.Run));
            typeof(RunManager).GetProperty("RewardsSetSynchronizer")!.SetValue(RunManager.Instance,new RewardsSetSynchronizer(new RunLocationTargetedMessageBuffer(net),net,b.Run,localId));
            foreach(var p in b.Run.Players)await OstyCmd.Summon(Choice,p,3,null);
            for(int i=0;i<8;i++)
            {
                await DamageCmd.Attack(8).FromMonster(b.Room.CombatState.Enemies.First().Monster!).Execute(Choice);
                byte[] packet=NetworkState(b.Run);
                if(localId==1)packets.Add(packet);
                else Assert(packet.SequenceEqual(packets[i]),"Host/client native state packets match after multiple summon deaths");
                foreach(var p in b.Run.Players)await OstyCmd.Summon(Choice,p,3,null);
            }
        }
        GD.Print("PET_DEATH_NETWORK_PASS eight identical native state packets after kill/revive loops");
    }
}
