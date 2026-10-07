// Share the native combat/ModelDb harness with the other boss checks.
using System.Reflection;
using System.Text.Json;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Commands.Builders;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.Settings;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Encounters;
using STS2_Things.Monsters;

public partial class CaveGodProbeNode
{
    private static string FogmogOutput(string root, string subdir)
    {
        var args = OS.GetCmdlineUserArgs();
        int index = Array.IndexOf(args, "--fogmog-output");
        return index >= 0 && index + 1 < args.Length ? args[index + 1]
            : Path.Combine(root, "build/origin-fogmog-impact-20261003", subdir);
    }
    private static readonly List<object> FogmogHits = [];
    private static readonly List<float> FogmogHitTimes = [];
    private static readonly List<string> FogmogHitClips = [];
    private static int FogmogAttackCommands;
    // TestMode intentionally suppresses UI notifications; this harness adds a
    // real creature solely for its animation, not a complete combat HUD.
    private static bool SkipFogmogUiNotification() => false;
    private static bool FogmogCreatureNode(Creature __instance, ref NCreature? __result)
    {
        if (__instance.Monster is not OriginFogmog) return true;
        __result = ActionRoom?.GetCreatureNode(__instance);
        return false;
    }
    private static void RecordFogmogAttack(AttackCommand __instance)
    {
        if (__instance.Attacker?.Monster is not OriginFogmog) return;
        FogmogAttackCommands++;
        __instance.BeforeDamage(() =>
        {
            var state = new MegaSprite(ActionSprites[0]).GetAnimationState();
            using var track = state.GetCurrent(0);
            float time = track!.GetTrackTime();
            string clip = track.GetAnimationName();
            FogmogHitTimes.Add(time); FogmogHitClips.Add(clip);
            FogmogHits.Add(new { clock = ActionClock, time, clip });
            return Task.CompletedTask;
        });
    }

    private static (CombatState state, OriginFogmog boss) FogmogScenario(int count)
    {
        var players = Enumerable.Range(1,count).Select(i=>Player.CreateForNewRun<Ironclad>(UnlockState.all,(ulong)i)).ToArray();
        var run = RunState.CreateForTest(players, seed:"fogmog-actions");
        typeof(RunManager).GetProperty("State",BindingFlags.NonPublic|BindingFlags.Instance)!.SetValue(RunManager.Instance,run);
        typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance,new MegaCrit.Sts2.Core.Entities.Ascension.AscensionManager(0));
        var room = new CombatRoom(ModelDb.Encounter<OriginFogmogBossEncounter>().ToMutable(),run);
        run.PushRoom(room);
        foreach(var player in players)
        {
            player.ResetCombatState();room.CombatState.AddPlayer(player);
            player.Creature.SetMaxHpInternal(10000);player.Creature.SetCurrentHpInternal(10000);
        }
        var boss=Add<OriginFogmog>(room.CombatState,"fogmog");
        ActivateSyntheticCombat(room.CombatState);
        return (room.CombatState,boss);
    }

    private async Task VerifyFogmogActions()
    {
        string root=Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"),"../.."));
        string output=FogmogOutput(root,"actions");
        Directory.CreateDirectory(output);
        MegaCrit.Sts2.Core.Localization.LocManager.Initialize();
        SaveManager.Instance.InitPrefsDataForTest();
        var status=GDExtensionManager.LoadExtension(Path.Combine(root,"addons/spine/spine_godot_extension.gdextension"));
        Assert(status is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded,"Spine unavailable");
        var room=new CaveGodProbeRoom();AddChild(room);ActionRoom=room;
        var nodes=(List<NCreature>)typeof(NCombatRoom).GetField("_creatureNodes",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(room)!;
        var harmony=new Harmony("OriginFogmog.MotionProbe");
        harmony.Patch(AccessTools.PropertyGetter(typeof(NCombatRoom),nameof(NCombatRoom.Instance)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(ActionRoomGetter)));
        harmony.Patch(AccessTools.Method(typeof(Cmd),nameof(Cmd.Wait),[typeof(float),typeof(CancellationToken),typeof(bool)]),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(ActionWait)));
        harmony.Patch(AccessTools.Method(typeof(Cmd),nameof(Cmd.CustomScaledWait)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(ActionScaledWait)));
        harmony.Patch(AccessTools.Method(typeof(AttackCommand),nameof(AttackCommand.Execute)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(RecordFogmogAttack)));
        harmony.Patch(AccessTools.Method(CombatManager.Instance.StateTracker.GetType(),"NotifyCombatStateChanged"),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(SkipFogmogUiNotification)));
        harmony.Patch(AccessTools.Method(typeof(Creature),nameof(Creature.GetCreatureNode)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(FogmogCreatureNode)));
        var results=new List<object>();
        try
        {
            foreach(int count in new[]{1,2,4})
            foreach(var mode in new[]{FastModeType.Normal,FastModeType.Fast,FastModeType.Instant})
            {
                var (state,boss)=FogmogScenario(count);
                var node=GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
                typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(node,boss.Creature);
                var visuals=GD.Load<PackedScene>("res://scenes/creature_visuals/origin_fogmog.tscn").Instantiate<NCreatureVisuals>();
                typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(node,visuals);
                ActionRoom=null;
                nodes.Add(node);room.AddChild(node);
                for(int i=0;i<3;i++) await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
                ActionRoom=room;
                var sprite=visuals.GetNode<Node2D>("Visuals");
                sprite.Call("set_update_mode",ClassDB.ClassGetIntegerConstant("SpineConstant","UpdateMode_Manual"));
                ActionSprites=[sprite];
                var animator=(CreatureAnimator)typeof(NCreature).GetField("_spineAnimator",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(node)!;
                Assert(animator.HasTrigger("Headbutt")&&animator.HasTrigger("Triple"),"Dedicated Fogmog triggers missing");
                SaveManager.Instance.PrefsSave.FastMode=mode;
                foreach(var (method,clip,expected,damage) in new[]{
                    ("SwipeMove","attack",new[]{.64f},10m),
                    ("SwipeBlockMove","attack",new[]{.64f},12m),
                    ("HeadbuttMove","headbutt",new[]{.80f},15m),
                    ("TripleMove","triple_attack",new[]{.48f,.94f,1.40f},18m)})
                {
                    animator.SetTrigger("Idle");AdvanceAction(.3);
                    ActionClock=0;FogmogHits.Clear();FogmogHitTimes.Clear();FogmogHitClips.Clear();FogmogAttackCommands=0;
                    var health=state.PlayerCreatures.Select(c=>c.CurrentHp).ToArray();
                    await (Task)typeof(OriginFogmog).GetMethod(method,BindingFlags.Instance|BindingFlags.NonPublic)!.Invoke(boss,[state.PlayerCreatures.ToArray()])!;
                    Assert(FogmogAttackCommands==1,"Multi-hit must remain one native attack command");
                    Assert(FogmogHitTimes.Count==expected.Length,$"{method} wrong hit count");
                    for(int i=0;i<expected.Length;i++)
                        Assert(FogmogHitClips[i]==clip&&Math.Abs(FogmogHitTimes[i]-expected[i])<.025,$"{method}/{mode}: damage at {FogmogHitClips[i]}@{FogmogHitTimes[i]:F3}; expected {clip}@{expected[i]:F3}");
                    for(int i=0;i<health.Length;i++) Assert(health[i]-state.PlayerCreatures.ElementAt(i).CurrentHp==damage,$"{method}: damage changed");
                    using var finished = new MegaSprite(sprite).GetAnimationState().GetCurrent(0);
                    Assert(finished == null || finished.GetAnimationName() == "idle_loop" ||
                        (finished.GetAnimationName() == clip && finished.GetTrackTime() >= finished.GetAnimationEnd() - .001f),
                        $"{method}/{mode}: move finished before the return steps");
                    results.Add(new {count,mode=mode.ToString(),method,hits=FogmogHits.ToArray()});
                }
                // Native particle events: the new cloud starts at the release and
                // stops immediately if another animation interrupts the exhale.
                animator.SetTrigger("PowerUp");AdvanceAction(.75);
                var cloud=sprite.GetNode<GpuParticles2D>("ThrustSlotNode/ThrustParticles");
                Assert(cloud.Emitting,"PowerUp release did not emit spores");
                await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
                var direction=((ParticleProcessMaterial)cloud.ProcessMaterial).Direction;
                Vector2 worldDirection=(cloud.GlobalTransform*new Vector2(direction.X,direction.Y)-cloud.GlobalPosition).Normalized();
                Assert(worldDirection.Y<-.5f,$"Spore cloud points down: {worldDirection}");
                Assert((cloud.GlobalPosition-sprite.GlobalPosition).Y < -350,"Spore socket is not on the cap");
                animator.SetTrigger("Hit");AdvanceAction(0);
                Assert(!cloud.Emitting,"Interrupted spore cloud kept emitting");
                animator.SetTrigger("Summon");AdvanceAction(.85);
                var dust = sprite.GetNode<GpuParticles2D>("DustSlotNode/DustLeftParticles");
                Assert(cloud.Emitting && !dust.Emitting,"Jump release emitted landing dust in midair");
                AdvanceAction(.38);
                Assert(dust.Emitting,"Summon landing did not emit dust");
                animator.SetTrigger("Hit");AdvanceAction(0);
                Assert(!cloud.Emitting && !dust.Emitting,"Interrupted landing VFX kept emitting");
                nodes.Clear();ActionRoom=null;node.QueueFree();ActionSprites=[];
                await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
                DeactivateSyntheticCombat();
            }
        }
        finally
        {
            harmony.UnpatchAll(harmony.Id);ActionRoom=null;ActionSprites=[];room.QueueFree();
        }
        File.WriteAllText(Path.Combine(output,"measurements.json"),JsonSerializer.Serialize(results,new JsonSerializerOptions{WriteIndented=true}));
        GD.Print("OriginFogmog action regression: PASS (36 move/mode/player scenarios)");
    }

    private async Task RenderFogmogPreview()
    {
        string root=Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"),"../.."));
        string output=FogmogOutput(root,"preview");
        Directory.CreateDirectory(output);
        SaveManager.Instance.InitPrefsDataForTest();
        GDExtensionManager.LoadExtension(Path.Combine(root,"addons/spine/spine_godot_extension.gdextension"));
        var viewport=new SubViewport {Size=new Vector2I(1000,650),Disable3D=true,RenderTargetUpdateMode=SubViewport.UpdateMode.Always};
        AddChild(viewport);
        viewport.AddChild(new ColorRect {Size=new Vector2(1000,650),Color=new Color("20242a")});
        var visuals=GD.Load<PackedScene>("res://scenes/creature_visuals/origin_fogmog.tscn").Instantiate<NCreatureVisuals>();
        visuals.Position=new Vector2(510,580);visuals.Scale=Vector2.One*.8f;viewport.AddChild(visuals);
        for(int i=0;i<5;i++) await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        var sprite=visuals.GetNode<Node2D>("Visuals");
        sprite.Call("set_update_mode",ClassDB.ClassGetIntegerConstant("SpineConstant","UpdateMode_Manual"));
        var skeleton=sprite.Call("get_skeleton").AsGodotObject();
        var state=sprite.Call("get_animation_state").AsGodotObject();
        foreach(string name in new[]{"idle_loop","attack","headbutt","triple_attack","summon","power_up","hurt"})
        {
            state.Call("clear_tracks");skeleton.Call("set_to_setup_pose");
            foreach(var path in new[]{"ThrustSlotNode/ThrustParticles","DustSlotNode/DustLeftParticles","DustSlotNode/DustRightParticles"})
            {
                var emitter=sprite.GetNode<GpuParticles2D>(path);emitter.Restart();emitter.Emitting=false;
            }
            var entry=state.Call("set_animation",name,false,0).AsGodotObject();entry.Call("set_mix_duration",0f);
            float duration=entry.Call("get_animation_end").AsSingle();
            float previous=0;
            for(int frame=0;frame<=(int)Math.Ceiling(duration*30);frame++)
            {
                float time=Math.Min(frame/30f,duration);
                sprite.Call("update_skeleton",time-previous);previous=time;
                await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
                RenderingServer.ForceDraw(false);
                using var image=viewport.GetTexture().GetImage();
                image.Resize(800,520,Image.Interpolation.Lanczos);
                image.SavePng(Path.Combine(output,$"{name}_{frame:D3}.png"));
            }
        }
        viewport.QueueFree();
        await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        GD.Print("OriginFogmog preview: PASS (native scene, spores, 30 fps)");
    }
}
