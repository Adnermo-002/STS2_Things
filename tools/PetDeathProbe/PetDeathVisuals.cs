using System.Reflection;
using Godot;
using Godot.Bridge;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Monsters;

public partial class DepthsProbeNode
{
    private static NCombatRoom? _visualRoom;
    private static bool SupplyVisualRoom(ref NCombatRoom? __result)
    { __result=_visualRoom;return false; }
    private static bool SkipUiStateGuard()=>false;
    private static DepthsProbeNode? _timingHost;
    private static bool NativeDeathDelay(float seconds,CancellationToken cancelToken,bool ignoreCombatEnd,ref Task __result)
    {
        __result=_timingHost!.AwaitRealFrames(Math.Min(Math.Max(seconds,0),.08),cancelToken);return false;
    }
    private async Task AwaitRealFrames(double seconds,CancellationToken cancelToken)
    {
        if(seconds<=0 || cancelToken.IsCancellationRequested)return;
        await ToSignal(GetTree().CreateTimer(seconds),SceneTreeTimer.SignalName.Timeout);
    }

    private async Task VerifyPetDeathVisuals()
    {
        var extension=GDExtensionManager.LoadExtension(Path.Combine(_root,"addons/spine/spine_godot_extension.gdextension"));
        Assert(extension is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded,"Spine runtime");
        ScriptManagerBridge.LookupScriptsInAssembly(typeof(ModelDb).Assembly);
        var loaderType=typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Assets.AtlasResourceLoader");
        var loader=loaderType==null?null:(ResourceFormatLoader)Activator.CreateInstance(loaderType)!;
        if(loader!=null)ResourceLoader.AddResourceFormatLoader(loader,true);
        var host=new Harmony("PetDeathProbe.VisualHost");
        host.Patch(AccessTools.PropertyGetter(typeof(NCombatRoom),nameof(NCombatRoom.Instance)),
            prefix:new HarmonyMethod(typeof(DepthsProbeNode),nameof(SupplyVisualRoom)));
        host.Patch(AccessTools.Method(typeof(CombatStateTracker),"NotifyCombatStateChanged"),
            prefix:new HarmonyMethod(typeof(DepthsProbeNode),nameof(SkipUiStateGuard)));
        _timingHost=this;
        host.Patch(AccessTools.Method(typeof(Cmd),nameof(Cmd.Wait),[typeof(float),typeof(CancellationToken),typeof(bool)]),
            prefix:new HarmonyMethod(typeof(DepthsProbeNode),nameof(NativeDeathDelay)));
        var b=await Battle(2);
        foreach(var p in b.Run.Players)await OstyCmd.Summon(Choice,p,3,null);
        var view=new SubViewport{Size=new Vector2I(1200,700),Disable3D=true,RenderTargetUpdateMode=SubViewport.UpdateMode.Always};
        AddChild(view);
        var scene=new Control();view.AddChild(scene);
        var room=new NCombatRoom();
        typeof(NCombatRoom).GetProperty(nameof(NCombatRoom.SceneContainer))!.SetValue(room,scene);
        var ui=new NCombatUi();typeof(NCombatRoom).GetProperty(nameof(NCombatRoom.Ui))!.SetValue(room,ui);
        var nodes=(List<NCreature>)typeof(NCombatRoom).GetField("_creatureNodes",BindingFlags.NonPublic|BindingFlags.Instance)!.GetValue(room)!;
        _visualRoom=room;
        NCreature Add(Creature entity,Vector2 position)
        {
            var node=GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
            typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(node,entity);
            var visuals=entity.Monster?.CreateVisuals() ?? entity.Player!.Character.CreateVisuals();
            typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(node,visuals);
            node.Position=position;nodes.Add(node);scene.AddChild(node);return node;
        }
        for(int i=0;i<b.Run.Players.Count;i++)
        {
            var p=b.Run.Players[i];Add(p.Creature,new Vector2(220+400*i,480));
            Add(p.Osty!,new Vector2(400+400*i,405));
        }
        var pets=b.Run.Players.Select(p=>p.Osty!).ToArray();
        for(int cycle=0;cycle<24;cycle++)
        {
            if(cycle>0)foreach(var p in b.Run.Players)await OstyCmd.Summon(Choice,p,3,null);
            foreach(var p in b.Run.Players){p.Creature.SetCurrentHpInternal(p.Creature.MaxHp);}
            await CreatureCmd.Damage(Choice,b.Run.Players.Select(p=>p.Creature).ToArray(),8,
                ValueProp.Move,b.Room.CombatState.Enemies.First());
            Assert(pets.All(p=>room.GetCreatureNode(p)!.DeathAnimationTask is { IsCompleted:false }),
                "Both death animations overlap asynchronously");
            foreach(var p in pets)
            {
                var node=room.GetCreatureNode(p)!;
                Assert(node.DeathAnimationTask!=null,"Lethal attacks entered the native pet death animation");
                await node.DeathAnimationTask!;
                Assert(!node.DeathAnimationTask.IsFaulted,"Native Osty death task completed without a fault");
            }
        }
        RenderingServer.ForceDraw();
        string output=System.Environment.GetEnvironmentVariable("THINGS_PROBE_OUTPUT")!;
        Directory.CreateDirectory(output);
        using(var image=view.GetTexture().GetImage())image.SavePng(Path.Combine(output,"two-osty-dead.png"));
        GD.Print("PET_DEATH_VISUAL_PASS 24 cycles, 48 overlapping native pet death animations");
        _visualRoom=null;
        foreach(var n in nodes)n.QueueFree();
        nodes.Clear();view.QueueFree();room.Free();ui.Free();
        await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        host.UnpatchAll(host.Id);
        if(loader!=null)ResourceLoader.RemoveResourceFormatLoader(loader);
    }
}
