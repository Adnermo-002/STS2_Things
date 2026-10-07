using System.Reflection;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Encounters;
using STS2_Things.Monsters;
using STS2_Things.Powers;

public partial class DepthsProbeNode
{
    private async Task VerifyFleetingEcho()
    {
        foreach (int count in new[] { 1, 4 })
        foreach (int asc in new[] { 0, 20 })
        {
            var b = await StrongBattle(ModelDb.Encounter<FleetingEchoWeak>(), count, asc);
            var echo = b.Monster<FleetingEcho>();
            var target = echo.Creature;
            Assert(b.Enemies.Length == 1 && b.Encounter.IsWeak, "One Echo in the weak pool.");
            Assert(target.GetPower<FleetingFadePower>()?.Amount == 5, "Timer is five for the whole party.");
            var source = b.Players[0].Creature;
            foreach (var p in b.Players) { p.Creature.SetMaxHpInternal(10000); p.Creature.SetCurrentHpInternal(10000); }
            for (int i = 0; i < 3; i++)
                await CreatureCmd.Damage(Choice, target, 4, ValueProp.Move, source);
            Assert(source.Block == 12, "Three four-damage hits produce twelve Block.");
            Assert(b.Players.Skip(1).All(p => p.Creature.Block == 0), "Other players receive no duplicated Block.");
            await CreatureCmd.Damage(Choice, target, 9, ValueProp.Unpowered, source);
            Assert(source.Block == 12, "Non-attack damage gives no Block.");
            await CreatureCmd.GainBlock(target, 5, ValueProp.Unpowered, null);
            await CreatureCmd.Damage(Choice, target, 8, ValueProp.Move, source);
            Assert(source.Block == 15, "Only three HP lost beyond the five Block are converted.");
            await PowerCmd.Apply<DexterityPower>(Choice, source, 10, source, null);
            await CreatureCmd.Damage(Choice, target, 5, ValueProp.Move, source);
            Assert(source.Block == 20, "Conversion does not add ten Dexterity a second time.");
            await PowerCmd.Remove<DexterityPower>(source);
            if (count > 1)
            {
                var other = b.Players[1].Creature;
                await CreatureCmd.Damage(Choice, target, 7, ValueProp.Move, other);
                Assert(other.Block == 7 && source.Block == 20, "Each player gets their own damage converted.");
            }
            // Native PetOwner is the route used by Osty and other summons.
            var pet = b.State.CreateCreature(ModelDb.Monster<MegaCrit.Sts2.Core.Models.Monsters.Osty>().ToMutable(), CombatSide.Player, null);
            pet.PetOwner = b.Players[0];b.State.AddCreature(pet);
            await CreatureCmd.Damage(Choice, target, 6, ValueProp.Move, pet);
            Assert(source.Block == 26 && pet.Block == 0, "Pet attacks protect their owning player.");
            target.SetCurrentHpInternal(3);
            // Native GainBlock intentionally stops once the final enemy dies.
            // Keep another enemy alive to verify lethal/overkill conversion
            // during an ongoing battle, without bypassing that native rule.
            var sentinel=b.State.CreateCreature(ModelDb.Monster<CrystalSnail>().ToMutable(),CombatSide.Enemy,"sentinel");
            b.State.AddCreature(sentinel);
            await CreatureCmd.Damage(Choice, target, 100, ValueProp.Move, source);
            Assert(source.Block == 29 && target.IsDead, $"Lethal hit converts three effective HP, excluding overkill. actual Block={source.Block}, HP={target.CurrentHp}, dead={target.IsDead}");
            DeactivateSyntheticCombat();

            b = await StrongBattle(ModelDb.Encounter<FleetingEchoWeak>(), count, asc, "echo-timer-"+count+"-"+asc);
            echo = b.Monster<FleetingEcho>();target = echo.Creature;
            foreach (var p in b.Players) { p.Creature.SetMaxHpInternal(10000); p.Creature.SetCurrentHpInternal(10000); }
            int[] expected = asc == 0 ? [26,31,36,41,46] : [30,35,40,45,50];
            for (int phase = 0; phase < 5; phase++)
            {
                int hp = b.Players[0].Creature.CurrentHp;
                b.State.CurrentSide = CombatSide.Enemy;
                await echo.PerformMove();
                Assert(hp - b.Players[0].Creature.CurrentHp == expected[phase], $"Expected Echo attack damage: players={count}, asc={asc}, phase={phase}, expected={expected[phase]}, actual={hp-b.Players[0].Creature.CurrentHp}, block={b.Players[0].Creature.Block}");
                if (phase < 4)
                {
                    Assert(target.IsAlive && target.GetPower<FleetingFadePower>()?.Amount == 4-phase, "Exactly one timer decrement per enemy action.");
                    echo.RollMove(b.Players.Select(p => p.Creature));
                }
            }
            Assert(target.IsDead && !b.State.Enemies.Contains(target), "Final attack resolves before native death removes the Echo.");
            DeactivateSyntheticCombat();
        }
        var loss = await StrongBattle(ModelDb.Encounter<FleetingEchoWeak>(),1,0,"echo-loss");
        var losingEcho=loss.Monster<FleetingEcho>();
        loss.Players[0].Creature.SetCurrentHpInternal(1);
        loss.State.CurrentSide=CombatSide.Enemy;
        await losingEcho.PerformMove();
        Assert(loss.Players[0].Creature.IsDead && losingEcho.Creature.IsAlive,
            "Player defeat does not also kill the surviving Echo.");
        Assert(losingEcho.Creature.GetPower<FleetingFadePower>()?.Amount==5,
            "Already ending combat does not continue the timer or create a second outcome.");
        DeactivateSyntheticCombat();
        GD.Print("PASS Fleeting Echo: 1/4 players, A0/A20, five attacks, owner-only Block, pets, lethal and overkill.");
        await RenderFleetingEcho();
    }

    private async Task RenderFleetingEcho()
    {
        Type? atlasType=typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Assets.AtlasResourceLoader");
        ResourceFormatLoader? atlas=atlasType==null?null:(ResourceFormatLoader)Activator.CreateInstance(atlasType)!;
        if(atlas!=null)ResourceLoader.AddResourceFormatLoader(atlas,true);
        var b = await StrongBattle(ModelDb.Encounter<FleetingEchoWeak>());
        var entity = b.Monster<FleetingEcho>().Creature;
        var view = new SubViewport { Size = new Vector2I(900,650), Disable3D = true,
            TransparentBg = false, RenderTargetUpdateMode = SubViewport.UpdateMode.Always };
        AddChild(view);
        var creature = GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
        typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(creature,entity);
        typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(creature,entity.Monster!.CreateVisuals());
        creature.Position = new Vector2(450,540);view.AddChild(creature);
        await creature.UpdateIntent([b.Players[0].Creature]);creature.IntentContainer.Modulate=Colors.White;
        await ToSignal(GetTree().CreateTimer(.5),SceneTreeTimer.SignalName.Timeout);
        foreach (var (clip,time) in new[] { ("idle_loop",1f),("attack",.52f),("sweep",.58f),
                     ("grasp",.62f),("pulse",.64f),("scatter",.70f),("hurt",.12f),("die",1.15f) })
        {
            var state = creature.Visuals.SpineBody!.GetAnimationState();
            state.SetAnimation(clip,false,0);
            var entry=state.GetCurrent(0);
            using var scope=(object?)entry as IDisposable;
            if(entry==null)throw new Exception("Missing clip: "+clip);
            entry.SetMixDuration(0);entry.SetTrackTime(time);
            creature.Visuals.SpineBody.BoundObject.Call("update_skeleton",0f);
            await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
            await ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
            using var im=view.GetTexture().GetImage();
            Assert(im.SavePng(Path.Combine(_output,"echo-"+clip+".png"))==Error.Ok,"Native pose captured: "+clip);
        }
        if(System.Environment.GetEnvironmentVariable("THINGS_ECHO_CAPTURE_ANIMATION")=="1")
        {
            creature.IntentContainer.Visible=false;
            var state=creature.Visuals.SpineBody!.GetAnimationState();
            state.SetTimeScale(0);
            foreach(var (clip,duration) in new[]{("idle_loop",3f),("grasp",1.5f),("scatter",1.65f),("die",1.9f)})
            {
                string folder=Path.Combine(_output,"motion",clip);Directory.CreateDirectory(folder);
                state.SetAnimation(clip,false,0);
                int count=(int)Math.Ceiling(duration*20);
                for(int i=0;i<=count;i++)
                {
                    var entry=state.GetCurrent(0);using var scope=(object?)entry as IDisposable;
                    if(entry==null)throw new Exception("Missing animation capture entry");
                    entry.SetMixDuration(0);entry.SetTrackTime(Math.Min(duration,i/20f));
                    creature.Visuals.SpineBody.BoundObject.Call("update_skeleton",0f);
                    await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
                    await ToSignal(RenderingServer.Singleton,RenderingServer.SignalName.FramePostDraw);
                    using var frame=view.GetTexture().GetImage();
                    Assert(frame.SavePng(Path.Combine(folder,$"{i:D3}.png"))==Error.Ok,"Native animation frame "+clip+" "+i);
                }
            }
        }
        view.QueueFree();await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        if(atlas!=null)ResourceLoader.RemoveResourceFormatLoader(atlas);
        DeactivateSyntheticCombat();
    }
}
