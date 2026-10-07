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
        var b=await StrongBattle(ModelDb.Encounter<HumanFaceColumnWeak>(),players,ascension,"column-rules");
        foreach(var c in b.Enemies)await c.Monster!.AfterAddedToRoom();
        foreach(var p in b.Players){p.Creature.SetMaxHpInternal(10000);p.Creature.SetCurrentHpInternal(10000);}
        return b;
    }
    private static HumanFaceColumn[] Discs(Battle b)=>b.Enemies.Select(c=>c.Monster).OfType<HumanFaceColumn>().OrderBy(c=>c.Level).ToArray();
    private static async Task HitColumn(Battle b,params HumanFaceColumn[] targets)=>
        await CreatureCmd.Damage(Choice,targets.Select(c=>c.Creature).ToArray(),99999,ValueProp.Unpowered,b.Players[0].Creature);

    private async Task VerifyColumnRules()
    {
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
            Assert(top.MinInitialHp==(asc==0?40:46) && top.MaxInitialHp==(asc==0?46:52),"Both HP endpoints doubled.");
            int hp=top.Creature.CurrentHp;
            await CreatureCmd.Damage(Choice,top.Creature,10,ValueProp.Move,b.Players[0].Creature);
            Assert(top.Creature.CurrentHp==hp,"Top immunity retained.");
            hp=original[1].Creature.CurrentHp;
            await CreatureCmd.Damage(Choice,original[1].Creature,10,ValueProp.Move,b.Players[0].Creature);
            Assert(hp-original[1].Creature.CurrentHp==5,"Middle half damage retained.");
            b.State.CurrentSide=CombatSide.Enemy;
            hp=b.Players[0].Creature.CurrentHp;await top.PerformMove();
            Assert(hp-b.Players[0].Creature.CurrentHp==10,"Knock fits the shared three-disc attack budget.");
            top.RollMove(b.Players.Select(p=>p.Creature));await top.PerformMove();
            Assert(b.Players.All(p=>p.Creature.GetPower<WeakPower>()?.Amount==2),"Rebuke applies two Weak to each player.");
            int block=bottom.Creature.Block;await bottom.PerformMove();
            int baseBlock=asc==0?14:18;
            Assert(count==1?bottom.Creature.Block-block==baseBlock:bottom.Creature.Block-block>=baseBlock,
                $"Seal base Block doubled and multiplayer uses native scaling. players={count}, gained={bottom.Creature.Block-block}");
            bottom.RollMove(b.Players.Select(p=>p.Creature));hp=b.Players[0].Creature.CurrentHp;
            await bottom.PerformMove();
            Assert(hp-b.Players[0].Creature.CurrentHp==10,"Rattle has two five-damage hits.");
            DeactivateSyntheticCombat();
        }
        GD.Print("PASS column rules: A0/A20, 1/4 players, ten-damage attacks, middle-only stun, AoE order and recovery.");
    }
}
