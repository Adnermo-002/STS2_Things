using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using STS2_Things.Acts;
using STS2_Things.Afflictions;
using STS2_Things.Encounters;
using STS2_Things.Monsters;
using STS2_Things.Powers;

public partial class SilkMothProbeNode
{
    private static async Task VerifyGreatMoth()
    {
        Assert(ModelDb.Act<Depths>().AllRegularEncounters.Any(e=>e is SilkMothTrio),"Moth trio joins the strong pool.");
        Assert(!ModelDb.Act<Depths>().AllWeakEncounters.Any(e=>e is SilkMothTrio),"Trio does not leak into weak pool.");
        Assert(ModelDb.Power<SilkThreadPower>().StackType==PowerStackType.Counter,"Native layered duration.");
        foreach(int count in new[]{1,2,4}) foreach(int asc in new[]{0,20})
        {
            var s=await Scenario(players:count,ascension:asc,trio:true);
            var moths=s.Room.CombatState.Enemies.Select(c=>c.Monster).OfType<SilkMoth>().ToArray();
            Assert(moths.Length==3 && moths[1] is GreatSilkMoth,"Small / great / small production roster.");
            Assert(moths.Select(m=>m.OpeningPhase).SequenceEqual(new[]{1,0,2}),"Three distinct opening phases.");
            Assert(moths[1].MinInitialHp==(asc==0?58:66),"Great moth's deliberate endurance.");
            foreach(var p in s.Players){p.Creature.SetMaxHpInternal(10000);p.Creature.SetCurrentHpInternal(10000);}
            for(int round=0;round<9;round++)
            {
                int index=round%3==0?1:round%3==1?2:0;
                Assert(moths.Count(m=>m.NextMove.Id=="WEAVE_MOVE")==1 && moths[index].NextMove.Id=="WEAVE_MOVE", "Caster turns remain staggered through three complete cycles.");
                foreach(var m in moths){await m.PerformMove();m.RollMove(s.Players.Select(p=>p.Creature));}
                Assert(s.Players.All(p=>p.Creature.GetPower<SilkThreadPower>()!.Amount<=2),"Repeated casts never accumulate unbounded duration.");
            }
        }
        foreach(bool playFirst in new[]{false,true})
        {
            var s=await Scenario(trio:true);await BasicHand(s);
            var great=s.Room.CombatState.Enemies.Select(c=>c.Monster).OfType<GreatSilkMoth>().Single();
            await great.PerformMove();var power=s.Player.Creature.GetPower<SilkThreadPower>()!;
            Assert(power.Amount==2 && power.IsPending,"Great moth grants two pending turns.");
            await Begin(s);Assert(power.HasLivePair,"First player turn binds exactly one pair.");
            var first=power.FirstCard!;var second=power.SecondCard!;
            Assert(s.Player.PlayerCombatState!.AllCards.Count(c=>c.Affliction is SilkLead or SilkBound)==2,"Two layers never bind four cards at once.");
            if(playFirst)
            {
                await CardCmd.AutoPlay(Choice,first,first.TargetType==TargetType.AnyEnemy?great.Creature:null,skipCardPileVisuals:true);
                Assert(power.Amount==1 && second.CanPlay(),"Unlocking first turn consumes one layer only.");
            }
            await power.BeforeSideTurnEnd(Choice,CombatSide.Player,s.Players.Select(p=>p.Creature));
            Assert(power.Amount==1 && power.IsPending,"First turn leaves one layer ready for the next turn.");
            Assert(s.Player.PlayerCombatState!.AllCards.All(c=>c.Affliction is not SilkLead and not SilkBound),"Current turn's marks retire fully.");
            await BasicHand(s);await Begin(s);
            Assert(power.HasLivePair && power.Amount==1,"Second player turn independently selects a pair.");
            await power.BeforeSideTurnEnd(Choice,CombatSide.Player,s.Players.Select(p=>p.Creature));
            Assert(s.Player.Creature.GetPower<SilkThreadPower>()==null,"Exactly two player turns exhaust the duration.");
        }
        Godot.GD.Print("PASS great moth strong roster, nine-turn stagger, 1/2/4 players, cap and two distinct binding turns.");
    }
}
