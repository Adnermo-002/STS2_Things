using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Encounters;
using STS2_Things.Monsters;
using STS2_Things.Powers;

public partial class DepthsProbeNode
{
    private static async Task<Battle> ColumnBattle(int players=1,int ascension=0)
    {
        var b=await StrongBattle(ModelDb.Encounter<HumanFaceColumnEncounter>(),players,ascension,"column-rules");
        foreach(var c in b.Enemies)await c.Monster!.AfterAddedToRoom();
        foreach(var p in b.Players){p.Creature.SetMaxHpInternal(10000);p.Creature.SetCurrentHpInternal(10000);}
        return b;
    }
    private static HumanFaceColumn[] Discs(Battle b)=>b.Enemies.Select(c=>c.Monster).OfType<HumanFaceColumn>().OrderBy(c=>c.Level).ToArray();
    private static async Task HitColumn(Battle b,params HumanFaceColumn[] targets)=>
        await CreatureCmd.Damage(Choice,targets.Select(c=>c.Creature).ToArray(),99999,ValueProp.Unpowered,b.Players[0].Creature);

    private async Task VerifyColumnRules()
    {
        await VerifyColumnAttackBudget();
        foreach(int count in new[]{1,4})
        foreach(int asc in new[]{0,20})
        {
            var b=await ColumnBattle(count,asc);var original=Discs(b);
            var bottom=original[0];var middle=original[1];var top=original[2];
            string middleMove=middle.NextMove.Id;string topMove=top.NextMove.Id;
            await HitColumn(b,bottom);
            var alive=Discs(b);
            Assert(alive.Length==3 && alive[0]==middle && alive[1]==top,"Original identities fall to the correct slots.");
            Assert(middle.IsDizzy && !top.IsDizzy && !alive[2].IsDizzy,"Only the ORIGINAL middle disc is stunned.");
            Assert(top.NextMove.Id==topMove && alive[2].NextMove.Id=="KNOCK_MOVE","Top and replacement keep real announced actions.");
            Assert(alive.All(c=>c.RemainingLayers==5 && c.Creature.GetPower<HumanFaceColumnPower>()?.Amount==5),"Layer counter remains shared and loses exactly one.");
            b.State.CurrentSide=CombatSide.Enemy;
            await middle.PerformMove();middle.RollMove(b.Players.Select(p=>p.Creature));
            Assert(!middle.IsDizzy && middle.NextMove.Id==middleMove,"One stun action restores the interrupted move.");
            var priorMiddle=alive[1];var priorTop=alive[2];
            await HitColumn(b,middle);
            alive=Discs(b);
            Assert(alive[0]==priorMiddle && priorMiddle.IsDizzy && !priorTop.IsDizzy && !alive[2].IsDizzy,
                "Repeated bottom breaks stun the middle identity of each collapse only.");
            DeactivateSyntheticCombat();

            foreach(bool reverse in new[]{false,true})
            {
                b=await ColumnBattle(count,asc);original=Discs(b);top=original[2];
                await HitColumn(b,reverse?[original[1],original[0]]:[original[0],original[1]]);
                alive=Discs(b);
                Assert(alive.Length==3 && alive[0]==top && alive.All(c=>!c.IsDizzy),
                    "Simultaneous bottom/middle deaths do not transfer stun to top or replacements.");
                Assert(alive.All(c=>c.RemainingLayers==4) && alive.Count(c=>c.IsReplacement)==2,
                    "Two confirmations deduct two layers and add exactly two replacements.");
                DeactivateSyntheticCombat();
            }
            b=await ColumnBattle(count,asc);original=Discs(b);bottom=original[0];top=original[2];
            await HitColumn(b,original[1]);alive=Discs(b);
            Assert(alive[0]==bottom && alive[1]==top && alive.All(c=>!c.IsDizzy),
                "Breaking only a middle disc causes no bottom-break stun.");
            DeactivateSyntheticCombat();

            b=await ColumnBattle(count,asc);original=Discs(b);top=original[2];bottom=original[0];
            Assert(top.MinInitialHp==(asc==0?34:40) && top.MaxInitialHp==(asc==0?40:46),"Both reduced HP endpoints match the balance contract.");
            int hp=top.Creature.CurrentHp;
            await CreatureCmd.Damage(Choice,top.Creature,10,ValueProp.Move,b.Players[0].Creature);
            Assert(top.Creature.CurrentHp==hp,"Top immunity retained.");
            hp=original[1].Creature.CurrentHp;
            await CreatureCmd.Damage(Choice,original[1].Creature,10,ValueProp.Move,b.Players[0].Creature);
            Assert(hp-original[1].Creature.CurrentHp==5,"Middle half damage retained.");
            b.State.CurrentSide=CombatSide.Enemy;
            hp=b.Players[0].Creature.CurrentHp;await top.PerformMove();
            Assert(hp-b.Players[0].Creature.CurrentHp==8,"Knock fits the shared three-disc attack budget.");
            top.RollMove(b.Players.Select(p=>p.Creature));await top.PerformMove();
            Assert(b.Players.All(p=>p.Creature.GetPower<WeakPower>()?.Amount==1),"Rebuke applies one Weak to each player.");
            int block=bottom.Creature.Block;await bottom.PerformMove();
            int baseBlock=asc==0?10:14;
            Assert(count==1?bottom.Creature.Block-block==baseBlock:bottom.Creature.Block-block>=baseBlock,
                $"Seal reduced base Block and multiplayer uses native scaling. players={count}, gained={bottom.Creature.Block-block}");
            bottom.RollMove(b.Players.Select(p=>p.Creature));hp=b.Players[0].Creature.CurrentHp;
            await bottom.PerformMove();
            Assert(hp-b.Players[0].Creature.CurrentHp==8,"Rattle has two four-damage hits.");
            DeactivateSyntheticCombat();
        }
        GD.Print("PASS column rules: A0/A20, 1/4 players, eight-damage attacks, middle-only stun, AoE order and recovery.");
    }

    private static async Task VerifyColumnAttackBudget()
    {
        foreach (int players in new[] { 1, 4 })
        foreach (int asc in new[] { 0, 20 })
        {
            var b = await ColumnBattle(players, asc);
            var totals = new List<int>();
            b.State.CurrentSide = CombatSide.Enemy;
            for (int turn = 0; turn < 8; turn++)
            {
                if (turn == 4)
                {
                    b.State.CurrentSide = CombatSide.Player;
                    await HitColumn(b, Discs(b)[0]);
                    // A synthetic damage call does not run the native enemy
                    // turn setup that announces newly summoned creatures.
                    foreach (var disc in Discs(b))
                        if (disc.NextMove.Id == "UNSET_MOVE") disc.RollMove(b.Players.Select(p => p.Creature));
                    b.State.CurrentSide = CombatSide.Enemy;
                }
                var before = b.Players.Select(p => p.Creature.CurrentHp).ToArray();
                foreach (var disc in Discs(b)) await disc.PerformMove();
                var damage = b.Players.Select((p, i) => before[i] - p.Creature.CurrentHp).ToArray();
                Assert(damage.All(value => value is >= 0 and <= 30), "Whole column stays within thirty damage per player, including collapse and replacement");
                if (turn < 4) Assert(damage.All(value => value is >= 8 and <= 16), "Intact column deals eight to sixteen damage per turn");
                totals.Add(damage.Max());
                foreach (var disc in Discs(b)) disc.RollMove(b.Players.Select(p => p.Creature));
            }
            foreach (string id in new[] { "KNOCK_MOVE", "RATTLE_MOVE" })
            {
                foreach (var disc in Discs(b)) disc.SetMoveImmediate(
                    (MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.MoveState)disc.MoveStateMachine!.States[id], forceTransition: true);
                var before = b.Players.Select(p => p.Creature.CurrentHp).ToArray();
                foreach (var disc in Discs(b)) await disc.PerformMove();
                Assert(b.Players.Select((p, i) => before[i] - p.Creature.CurrentHp).All(value => value == 24), "Three aligned column attacks total twenty-four damage");
            }
            GD.Print($"COLUMN TOTAL {players}p A{asc}: {string.Join(',', totals)}; aligned peak=24");
            DeactivateSyntheticCombat();
        }
    }
}
