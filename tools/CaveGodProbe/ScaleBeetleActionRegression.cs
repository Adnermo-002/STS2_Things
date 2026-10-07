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
using STS2_Things.Powers;
using STS2_Things.Visuals;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models.Singleton;
using MegaCrit.Sts2.Core.ValueProps;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;

public partial class CaveGodProbeNode
{
    private static string BeetleOutput(string root, string subdir)
    {
        var args = OS.GetCmdlineUserArgs();
        int index = Array.IndexOf(args, "--scale-beetle-output");
        return index >= 0 && index + 1 < args.Length ? args[index + 1]
            : Path.Combine(root, "build/scale-beetle-impact-20261003", subdir);
    }
    private static readonly List<(string kind,string clip,float time)> BeetleReleases=[];
    private static decimal BeetleBlockInput;
    private static void BeetleMoment(string kind)
    {
        if(ActionSprites.Length==0)return;
        using var track=new MegaSprite(ActionSprites[0]).GetAnimationState().GetCurrent(0);
        if(track!=null)BeetleReleases.Add((kind,track.GetAnimationName(),track.GetTrackTime()));
    }
    private static void RecordBeetlePower(PowerModel __instance)
    {
        if(__instance is ThingsScaleDownPower or ThingsScaleUpPower)BeetleMoment(__instance.GetType().Name);
    }
    private static void RecordBeetleBlock(Creature creature,decimal amount)
    {
        if(creature.Monster is not ThingsScaleBeetle)return;
        BeetleBlockInput=amount;BeetleMoment("block");
    }
    private static readonly List<object> BeetleHits = [];
    private static readonly List<float> BeetleHitTimes = [];
    private static readonly List<string> BeetleHitClips = [];
    private static int BeetleAttackCommands;
    // TestMode intentionally suppresses UI notifications; this harness adds a
    // real creature solely for its animation, not a complete combat HUD.
    private static bool SkipBeetleUiNotification() => false;
    private static bool SkipBeetleIntent(ref Task __result)
    {
        // This host has a creature and powers, but no complete combat HUD.
        __result=Task.CompletedTask;
        return false;
    }
    private static bool BeetleCreatureNode(Creature __instance, ref NCreature? __result)
    {
        if (__instance.Monster is not ThingsScaleBeetle) return true;
        __result = ActionRoom?.GetCreatureNode(__instance);
        return false;
    }
    private static void RecordBeetleAttack(AttackCommand __instance)
    {
        if (__instance.Attacker?.Monster is not ThingsScaleBeetle) return;
        BeetleAttackCommands++;
        __instance.BeforeDamage(() =>
        {
            var state = new MegaSprite(ActionSprites[0]).GetAnimationState();
            using var track = state.GetCurrent(0);
            float time = track!.GetTrackTime();
            string clip = track.GetAnimationName();
            BeetleHitTimes.Add(time); BeetleHitClips.Add(clip);
            BeetleHits.Add(new { clock = ActionClock, time, clip });
            return Task.CompletedTask;
        });
    }

    private static (CombatState state, ThingsScaleBeetle boss) BeetleScenario(int count)
    {
        var players = Enumerable.Range(1,count).Select(i=>Player.CreateForNewRun<Ironclad>(UnlockState.all,(ulong)i)).ToArray();
        var run = RunState.CreateForTest(players, seed:"scale-beetle-actions");
        typeof(RunManager).GetProperty("State",BindingFlags.NonPublic|BindingFlags.Instance)!.SetValue(RunManager.Instance,run);
        typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance,new MegaCrit.Sts2.Core.Entities.Ascension.AscensionManager(0));
        var room = new CombatRoom(ModelDb.Encounter<ScaleBeetleBossEncounter>().ToMutable(),run);
        run.PushRoom(room);
        foreach(var player in players)
        {
            player.ResetCombatState();room.CombatState.AddPlayer(player);
            player.Creature.SetMaxHpInternal(10000);player.Creature.SetCurrentHpInternal(10000);
        }
        var boss=Add<ThingsScaleBeetle>(room.CombatState,"scale-beetle");
        ActivateSyntheticCombat(room.CombatState);
        return (room.CombatState,boss);
    }

    private async Task VerifyBeetleActions()
    {
        string root=Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"),"../.."));
        string output=BeetleOutput(root,"actions");
        Directory.CreateDirectory(output);
        MegaCrit.Sts2.Core.Localization.LocManager.Initialize();
        SaveManager.Instance.InitPrefsDataForTest();
        var status=GDExtensionManager.LoadExtension(Path.Combine(root,"addons/spine/spine_godot_extension.gdextension"));
        Assert(status is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded,"Spine unavailable");
        var room=new CaveGodProbeRoom();AddChild(room);ActionRoom=room;
        var nodes=(List<NCreature>)typeof(NCombatRoom).GetField("_creatureNodes",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(room)!;
        var harmony=new Harmony("ThingsScaleBeetle.MotionProbe");
        harmony.Patch(AccessTools.PropertyGetter(typeof(NCombatRoom),nameof(NCombatRoom.Instance)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(ActionRoomGetter)));
        harmony.Patch(AccessTools.Method(typeof(Cmd),nameof(Cmd.Wait),[typeof(float),typeof(CancellationToken),typeof(bool)]),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(ActionWait)));
        harmony.Patch(AccessTools.Method(typeof(Cmd),nameof(Cmd.CustomScaledWait)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(ActionScaledWait)));
        harmony.Patch(AccessTools.Method(typeof(AttackCommand),nameof(AttackCommand.Execute)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(RecordBeetleAttack)));
        harmony.Patch(AccessTools.Method(CombatManager.Instance.StateTracker.GetType(),"NotifyCombatStateChanged"),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(SkipBeetleUiNotification)));
        harmony.Patch(AccessTools.Method(typeof(Creature),nameof(Creature.GetCreatureNode)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(BeetleCreatureNode)));
        harmony.Patch(AccessTools.Method(typeof(NCreature),nameof(NCreature.UpdateIntent)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(SkipBeetleIntent)));
        harmony.Patch(AccessTools.Method(typeof(PowerModel),nameof(PowerModel.ApplyInternal)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(RecordBeetlePower)));
        harmony.Patch(AccessTools.Method(typeof(PowerModel),nameof(PowerModel.SetAmount)),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(RecordBeetlePower)));
        harmony.Patch(AccessTools.Method(typeof(CreatureCmd),nameof(CreatureCmd.GainBlock),[typeof(Creature),typeof(decimal),typeof(ValueProp),typeof(CardPlay),typeof(bool)]),prefix:new HarmonyMethod(typeof(CaveGodProbeNode),nameof(RecordBeetleBlock)));
        var results=new List<object>();
        foreach(var power in new PowerModel[]{ModelDb.Power<ThingsScaleBeetlePower>(),ModelDb.Power<ThingsScaleUpPower>(),ModelDb.Power<ThingsScaleDownPower>()})
            Assert(ResourceLoader.Exists(power.PackedIconPath)&&power.Icon!=null,"Beetle power HUD icon missing");
        try
        {
            foreach(int count in new[]{1,2,4})
            foreach(var mode in new[]{FastModeType.Normal,FastModeType.Fast,FastModeType.Instant})
            {
                var (state,boss)=BeetleScenario(count);
                var node=GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
                typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(node,boss.Creature);
                var visuals=GD.Load<PackedScene>("res://scenes/creature_visuals/things_scale_beetle.tscn").Instantiate<NCreatureVisuals>();
                typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(node,visuals);
                ActionRoom=null;
                nodes.Add(node);room.AddChild(node);
                for(int i=0;i<3;i++) await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
                ActionRoom=room;
                var sprite=visuals.GetNode<Node2D>("Visuals");
                sprite.Call("set_update_mode",ClassDB.ClassGetIntegerConstant("SpineConstant","UpdateMode_Manual"));
                ActionSprites=[sprite];
                var animator=(CreatureAnimator)typeof(NCreature).GetField("_spineAnimator",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(node)!;
                Assert(animator.HasTrigger("Whip")&&animator.HasTrigger("Molt"),"Dedicated Beetle triggers missing");
                SaveManager.Instance.PrefsSave.FastMode=mode;
                await PowerCmd.Apply<ThingsScaleBeetlePower>(new ThrowingPlayerChoiceContext(),boss.Creature,1m,boss.Creature,null,silent:true);
                foreach(var (method,clip,expected,damage) in new[]{
                    ("BiteMove","attack",new[]{.68f},12m),
                    ("WhipMove","whip",new[]{.60f,1.12f,1.68f},12m)})
                {
                    animator.SetTrigger("Idle");AdvanceAction(.3);
                    ActionClock=0;BeetleHits.Clear();BeetleHitTimes.Clear();BeetleHitClips.Clear();BeetleAttackCommands=0;
                    var health=state.PlayerCreatures.Select(c=>c.CurrentHp).ToArray();
                    await (Task)typeof(ThingsScaleBeetle).GetMethod(method,BindingFlags.Instance|BindingFlags.NonPublic)!.Invoke(boss,[state.PlayerCreatures.ToArray()])!;
                    Assert(BeetleAttackCommands==1,"Multi-hit must remain one native attack command");
                    Assert(BeetleHitTimes.Count==expected.Length,$"{method} wrong hit count");
                    for(int i=0;i<expected.Length;i++)
                        Assert(BeetleHitClips[i]==clip&&Math.Abs(BeetleHitTimes[i]-expected[i])<.025,$"{method}/{mode}: damage at {BeetleHitClips[i]}@{BeetleHitTimes[i]:F3}; expected {clip}@{expected[i]:F3}");
                    for(int i=0;i<health.Length;i++) Assert(health[i]-state.PlayerCreatures.ElementAt(i).CurrentHp==damage,$"{method}: damage changed");
                    using var finished = new MegaSprite(sprite).GetAnimationState().GetCurrent(0);
                    Assert(finished == null || finished.GetAnimationName() == "idle_loop" ||
                        (finished.GetAnimationName() == clip && finished.GetTrackTime() >= finished.GetAnimationEnd() - .001f),
                        $"{method}/{mode}: move finished before the return steps");
                    results.Add(new {count,mode=mode.ToString(),method,hits=BeetleHits.ToArray()});
                }
                foreach(var (method,clip,moment) in new[]{("ReconstructMove","cast",.76f),("MoltMove","molt",.80f)})
                {
                    animator.SetTrigger("Idle");AdvanceAction(.3);
                    ActionClock=0;BeetleReleases.Clear();BeetleBlockInput=0;
                    await (Task)typeof(ThingsScaleBeetle).GetMethod(method,BindingFlags.Instance|BindingFlags.NonPublic)!.Invoke(boss,[state.PlayerCreatures.ToArray()])!;
                    string cue=clip=="cast"?nameof(ThingsScaleDownPower):"block";
                    var release=BeetleReleases.First(r=>r.kind==cue);
                    Assert(release.clip==clip&&Math.Abs(release.time-moment)<.025,$"{method}/{mode}: release was {release.clip}@{release.time}");
                    int expectedScale=clip=="cast"?15:30;
                    Assert(boss.Creature.GetPowerAmount<ThingsScaleUpPower>()==expectedScale,"ScaleUp stacks changed");
                    foreach(var player in state.PlayerCreatures)Assert(player.GetPowerAmount<ThingsScaleDownPower>()==35,"Player ScaleDown stacks changed (passive hits plus reconstruct)");
                    if(clip=="molt")
                    {
                        decimal factor=count<=2?count:count*MultiplayerScalingModel.GetMultiplayerScaling(state.Encounter,state.RunState.CurrentActIndex);
                        Assert(BeetleBlockInput==14&&boss.Creature.Block==(int)(14*factor),"Molt block was not scaled exactly once by the game");
                    }
                    using var finished=new MegaSprite(sprite).GetAnimationState().GetCurrent(0);
                    Assert(finished==null||finished.GetAnimationName()=="idle_loop"||
                        (finished.GetAnimationName()==clip&&finished.GetTrackTime()>=finished.GetAnimationEnd()-.001f),"Cast/molt recovery was cut off");
                    results.Add(new {count,mode=mode.ToString(),method,releases=BeetleReleases.Select(r=>new{r.kind,r.clip,r.time}).ToArray(),scale=expectedScale,block=boss.Creature.Block});
                }
                var motion=sprite.GetNode<NThingsScaleBeetleMotion>("MotionTiming");
                animator.SetTrigger("Whip");motion.AllowBeat(1);AdvanceAction(1.2);
                using(var held=new MegaSprite(sprite).GetAnimationState().GetCurrent(0))
                    Assert(held!=null&&Math.Abs(held.GetTrackTime()-.88f)<.012f,"Whip did not hold the next windup while damage hooks were pending");
                animator.SetTrigger("Hit");motion.FinishCombo();AdvanceAction(.2);
                using(var reaction=new MegaSprite(sprite).GetAnimationState().GetCurrent(0))
                    Assert(reaction!=null&&reaction.GetAnimationName()=="hurt"&&reaction.GetTrackTime()>.19f,"Interrupted combo froze the reaction");
                animator.SetTrigger("Whip");AdvanceAction(1.8);
                using(var preview=new MegaSprite(sprite).GetAnimationState().GetCurrent(0))
                    Assert(preview!=null&&preview.GetTrackTime()>1.79f,"Uncontrolled preview was paused by a gameplay gate");
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
        GD.Print("ThingsScaleBeetle action regression: PASS (36 move/mode/player scenarios)");
    }

}
