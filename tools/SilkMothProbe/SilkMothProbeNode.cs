using System.Reflection;
using System.Runtime.Loader;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Powers;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Afflictions;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Acts;
using STS2_Things.Afflictions;
using STS2_Things.Cards;
using STS2_Things.Encounters;
using STS2_Things.Monsters;
using STS2_Things.Powers;

public partial class SilkMothProbeNode : Node
{
    private static readonly ThrowingPlayerChoiceContext Choice=new();
    private static int _checks;
    private string _root=null!;
    public override void _Ready(){AssemblyLoadContext.Default.Resolving+=ResolveRuntimeDependency;_ = RunProbe();}
    private async Task RunProbe()
    {
        try
        {
            _root=Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"),"../.."));
            TestMode.TurnOnInternal();
            ProjectSettings.LoadResourcePack("D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck");
            string pack=System.Environment.GetEnvironmentVariable("THINGS_PROBE_PCK")??Path.Combine(_root,"build/silk_moth/v111/STS2_Things.pck");
            if(File.Exists(pack)) Assert(ProjectSettings.LoadResourcePack(pack),"Shipping PCK mounts.");
            SaveManager.Instance.InitSettingsDataForTest();SaveManager.Instance.InitPrefsDataForTest();
            SaveManager.Instance.SettingsSave.Language="eng";LocManager.Initialize();InitializeModelDb();LocManager.Initialize();
            await VerifyPoolsAndMoves();
            await VerifyDelayedLink();
            await VerifyCleanup();
            await VerifyEligibilityAndMultiplayer();
            if(OS.GetCmdlineUserArgs().Contains("--visual"))await RenderProbe();
            DeactivateSyntheticCombat();GD.Print($"Silk Moth probe: PASS ({_checks} assertions)");GetTree().Quit(0);
        }
        catch(Exception exception){GD.PushError(exception.ToString());GetTree().Quit(1);}
    }

    private static async Task<Fixture> Scenario(bool weak=false,int players=1,int ascension=0)
    {
        DeactivateSyntheticCombat();
        var party=Enumerable.Range(1,players).Select(i=>Player.CreateForNewRun<Ironclad>(UnlockState.all,(ulong)i)).ToList();
        var run=RunState.CreateForNewRun(party,ActModel.GetDefaultList().Select(a=>a.ToMutable()).ToList(),[],GameMode.Standard,ascension,"silk-moth-probe");
        run.CurrentActIndex=1;
        typeof(RunManager).GetProperty("State",BindingFlags.NonPublic|BindingFlags.Instance)!.SetValue(RunManager.Instance,run);
        typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance,new AscensionManager(ascension));
        typeof(RunManager).GetProperty("NetService")!.SetValue(RunManager.Instance,new NetSingleplayerGameService());
        EncounterModel encounter=(weak?ModelDb.Encounter<SilkMothWeak>() as EncounterModel:ModelDb.Encounter<SilkMothEncounter>()).ToMutable();
        run.AppendToMapPointHistory(MapPointType.Monster,RoomType.Monster,encounter.Id);
        var room=new CombatRoom(encounter,run);run.PushRoom(room);
        foreach(var player in party){player.ResetCombatState();room.CombatState.AddPlayer(player);player.PopulateCombatState(run.Rng.Shuffle,room.CombatState);}
        encounter.GenerateMonstersWithSlots(run);
        foreach(var(monster,slot) in encounter.MonstersWithSlots)
        {
            var entity=room.CombatState.CreateCreature(monster,CombatSide.Enemy,slot);room.CombatState.AddCreature(entity);
            monster.SetUpForCombat();monster.RollMove(party.Select(p=>p.Creature));
        }
        room.CombatState.CurrentSide=CombatSide.Player;ActivateSyntheticCombat(room.CombatState);
        await Hook.BeforeCombatStart(run,room.CombatState);
        foreach(var player in party)await PlayerCmd.SetEnergy(3,player);
        return new(run,room,party,encounter);
    }

    private static async Task<T> Hand<T>(Fixture s,Player? owner=null) where T:CardModel
    {
        var card=s.Room.CombatState.CreateCard<T>(owner??s.Player);
        await CardPileCmd.Add(card,PileType.Hand,CardPilePosition.Bottom,null,false);return card;
    }
    private static async Task BasicHand(Fixture s,Player? owner=null)
    {
        await Hand<StrikeIronclad>(s,owner);await Hand<DefendIronclad>(s,owner);
        await Hand<Bash>(s,owner);await Hand<Anger>(s,owner);
    }
    private static async Task<SilkThreadPower> Apply(Fixture s,Player? player=null)
    {
        return (await PowerCmd.Apply<SilkThreadPower>(Choice,(player??s.Player).Creature,1,s.Moth.Creature,null))!;
    }
    private static Task Begin(Fixture s,Player? player=null)=>Hook.AfterPlayerTurnStart(s.Room.CombatState,Choice,player??s.Player);
    private static async Task<(Fixture,SilkThreadPower)> BoundScenario()
    {
        var s=await Scenario();await BasicHand(s);var power=await Apply(s);await Begin(s);
        Assert(power.HasLivePair,"Native start-of-turn hook forms pair.");return(s,power);
    }

    private static async Task VerifyPoolsAndMoves()
    {
        var act=ModelDb.Act<Depths>();
        Assert(act.AllWeakEncounters.Any(e=>e is SilkMothWeak),"Moth weak pool.");
        Assert(act.AllRegularEncounters.Any(e=>e is SilkMothEncounter),"Moth strong pool.");
        foreach(bool weak in new[]{true,false})
        foreach(int players in new[]{1,2,4})
        {
            var s=await Scenario(weak,players);
            Assert(s.Encounter.MonstersWithSlots.Count==(weak?2:3),"One moth and one/two leeches.");
            Assert(s.Encounter.IsWeak==weak,"Native pool category.");
            Assert(s.Moth.MinInitialHp==36 && s.Moth.MaxInitialHp==40,"Base HP range.");
            Assert(s.Encounter.MonstersWithSlots.All(e=>s.Encounter.Slots.Contains(e.Item2!)),"All slots exist.");
            foreach(var player in s.Players)
                Assert(player.PlayerCombatState!.Hand.Cards.OfType<LeechParasite>().Count()==(weak?1:2),"Native direct-hand parasite count.");
            Assert(s.Moth.NextMove.Id=="WEAVE_MOVE" && s.Moth.NextMove.Intents.Single() is CardDebuffIntent,"Queen's native card-debuff intention.");
            await s.Moth.PerformMove();
            Assert(s.Players.All(p=>p.Creature.GetPower<SilkThreadPower>() is { IsPending:true,Type:PowerType.Buff }),"Weave grants pending player Buff to every player.");
            s.Moth.RollMove(s.Players.Select(p=>p.Creature));
            Assert(s.Moth.NextMove.Id=="SWOOP_MOVE" && s.Moth.NextMove.Intents.Single() is SingleAttackIntent,"Swoop follows weave.");
            int hp=s.Player.Creature.CurrentHp;await s.Moth.PerformMove();
            Assert(s.Player.Creature.CurrentHp==hp-7,"Swoop native damage.");
            s.Moth.RollMove(s.Players.Select(p=>p.Creature));
            Assert(s.Moth.NextMove.Intents.Single() is MultiAttackIntent,"Native multi-hit intent.");
            hp=s.Player.Creature.CurrentHp;await s.Moth.PerformMove();Assert(s.Player.Creature.CurrentHp==hp-8,"Two flutter hits.");
            s.Moth.RollMove(s.Players.Select(p=>p.Creature));Assert(s.Moth.NextMove.Id=="WEAVE_MOVE","Repeating cycle.");
        }
        var tough=await Scenario(ascension:20);Assert(tough.Moth.MinInitialHp==40 && tough.Moth.MaxInitialHp==44,"Ascension HP.");
        GD.Print("PASS weak/strong pools, multiplayer targets, native intents, damage and cycle.");
    }

    private static async Task VerifyDelayedLink()
    {
        var s=await Scenario();await BasicHand(s);var power=await Apply(s);
        Assert(power.IsPending && power.FirstCard==null && power.SecondCard==null,"Applying the buff does not bind the old hand.");
        await CardPileCmd.Draw(Choice,1,s.Player,fromHandDraw:true);
        Assert(power.IsPending && !s.Player.PlayerCombatState!.Hand.Cards.Any(c=>c.Affliction is SilkLead or SilkBound),"Drawing cards alone never binds mid-draw.");
        await Begin(s);Assert(power.HasLivePair && !power.IsPending,"Binds after full start-of-turn draw.");
        var first=power.FirstCard!;var second=power.SecondCard!;
        Assert(!ReferenceEquals(first,second) && first.CanPlay(),"Two distinct cards, first starts playable.");
        int firstCost=first.EnergyCost.GetAmountToSpend(),secondCost=second.EnergyCost.GetAmountToSpend();
        Assert(!second.CanPlay(out var reason,out var preventer) && reason.HasFlag(UnplayableReason.BlockedByHook) && preventer==power,"Native playability names the power as preventer.");
        await CardCmd.AutoPlay(Choice,first,first.TargetType==TargetType.AnyEnemy?s.Moth.Creature:null,skipCardPileVisuals:true);
        Assert(s.Player.Creature.GetPower<SilkThreadPower>()==null && second.CanPlay(),"Playing first unlocks second via native hooks.");
        Assert(first.Affliction==null && second.Affliction==null,"Both affliction marks clear.");
        Assert(first.EnergyCost.GetAmountToSpend()==firstCost && second.EnergyCost.GetAmountToSpend()==secondCost,"No discount or cost mutation.");
        foreach(var card in s.Player.PlayerCombatState!.AllCards)Assert(card.Affliction is not SilkLead and not SilkBound,"No cloned orphan marks.");
        var(auto,automatic)=await BoundScenario();var locked=automatic.SecondCard!;
        int plays=CombatManager.Instance.History.CardPlaysStarted.Count();
        await CardCmd.AutoPlay(Choice,locked,locked.TargetType==TargetType.AnyEnemy?auto.Moth.Creature:null,skipCardPileVisuals:true);
        Assert(CombatManager.Instance.History.CardPlaysStarted.Count()==plays,"Failed native autoplay cannot execute the locked card.");
        Assert(locked.Pile?.Type==PileType.Discard && auto.Player.Creature.GetPower<SilkThreadPower>()==null,"Native failed autoplay discards the card and therefore breaks the link.");
        GD.Print("PASS delayed activation, visible native lock, autoplay guard, unlock and unchanged costs.");
    }

    private static async Task VerifyCleanup()
    {
        foreach(bool first in new[]{true,false})
        foreach(bool exhaust in new[]{true,false})
        {
            var(s,power)=await BoundScenario();var card=(first?power.FirstCard:power.SecondCard)!;
            if(exhaust)await CardCmd.Exhaust(Choice,card,skipVisuals:true);
            else await CardPileCmd.Add(card,PileType.Discard,CardPilePosition.Bottom,null,false);
            Assert(s.Player.Creature.GetPower<SilkThreadPower>()==null,"Moving either linked card breaks link.");
            Assert(s.Player.PlayerCombatState!.AllCards.All(c=>c.Affliction is not SilkLead and not SilkBound),"Moving either card removes both native marks.");
        }
        var(ended,ending)=await BoundScenario();
#if STS2_V107_1
        await ending.BeforeSideTurnEnd(Choice,CombatSide.Player,ended.Players.Select(p=>p.Creature));
#else
        await Hook.BeforeSideTurnEnd(ended.Room.CombatState,CombatSide.Player,ended.Players.Select(p=>p.Creature));
#endif
        Assert(ended.Player.Creature.GetPower<SilkThreadPower>()==null,"Turn-end clears unplayed pair, including retained cards.");
        var(dead,death)=await BoundScenario();
        await CreatureCmd.Damage(Choice,dead.Moth.Creature,999,ValueProp.Unpowered,dead.Player.Creature);
        Assert(dead.Player.Creature.GetPower<SilkThreadPower>()==null,"Killing last moth clears active link.");
        var pending=await Scenario();await Apply(pending);
        await CreatureCmd.Damage(Choice,pending.Moth.Creature,999,ValueProp.Unpowered,pending.Player.Creature);
        Assert(pending.Player.Creature.GetPower<SilkThreadPower>()==null,"Killing last moth clears pending buff.");
        var(cleansed,clean)=await BoundScenario();CardCmd.ClearAffliction(clean.FirstCard!);
        Assert(clean.SecondCard!.CanPlay(),"External removal of first affliction releases lock immediately.");
        await PowerCmd.Remove(clean);
        Assert(cleansed.Player.PlayerCombatState!.Hand.Cards.All(c=>c.Affliction==null),"Native buff removal clears remaining mark.");
        GD.Print("PASS discard, exhaust, retained-turn-end, active/pending death and external cleanse.");
    }

    private static async Task VerifyEligibilityAndMultiplayer()
    {
        var scarce=await Scenario();await Hand<StrikeIronclad>(scarce);var single=await Apply(scarce);await Begin(scarce);
        Assert(scarce.Player.Creature.GetPower<SilkThreadPower>()==null,"Insufficient cards cancels cleanly.");
        var none=await Scenario();await Hand<Bash>(none);await Hand<Bash>(none);await PlayerCmd.SetEnergy(0,none.Player);await Apply(none);await Begin(none);
        Assert(none.Player.Creature.GetPower<SilkThreadPower>()==null,"No playable starting card cannot trap the hand.");
        var filtered=await Scenario();var wound=await Hand<Wound>(filtered);var parasite=await Hand<LeechParasite>(filtered);
        var curse=await Hand<Doubt>(filtered);var x=await Hand<Whirlwind>(filtered);var old=await Hand<StrikeIronclad>(filtered);
        await CardCmd.Afflict<Bound>(old,1);await Hand<StrikeIronclad>(filtered);await Hand<DefendIronclad>(filtered);
        var p=await Apply(filtered);await Begin(filtered);
        Assert(p.HasLivePair,"Two eligible cards still bind with other hand types present.");
        Assert(new CardModel[]{wound,parasite,curse,x,old}.All(c=>!ReferenceEquals(c,p.FirstCard)&&!ReferenceEquals(c,p.SecondCard)),"Statuses, curses, X and existing afflictions excluded.");
        Assert(old.Affliction is Bound,"Existing native affliction preserved.");
        var ids=new List<string>();
        for(int run=0;run<2;run++){var f=await Scenario();await BasicHand(f);var q=await Apply(f);await Begin(f);ids.Add(q.FirstCard!.Id+"/"+q.SecondCard!.Id);}
        Assert(ids[0]==ids[1],"Same seed yields same card order.");
        var multi=await Scenario(players:2);
        foreach(var player in multi.Players){await BasicHand(multi,player);await Apply(multi,player);}
        await Begin(multi,multi.Players[0]);
        Assert(multi.Players[0].Creature.GetPower<SilkThreadPower>()!.HasLivePair && multi.Players[1].Creature.GetPower<SilkThreadPower>()!.IsPending,"Per-player start timing.");
        await Begin(multi,multi.Players[1]);
        var a=multi.Players[0].Creature.GetPower<SilkThreadPower>()!;var b=multi.Players[1].Creature.GetPower<SilkThreadPower>()!;
        var aFirst=a.FirstCard!;await CardCmd.AutoPlay(Choice,aFirst,aFirst.TargetType==TargetType.AnyEnemy?multi.Moth.Creature:null,skipCardPileVisuals:true);
        Assert(multi.Players[0].Creature.GetPower<SilkThreadPower>()==null && b.HasLivePair,"One player's unlock cannot clear another player's pair.");
        Assert(b.FirstCard!.Owner==multi.Players[1] && b.SecondCard!.Owner==multi.Players[1],"Pair always belongs to owning player.");
        GD.Print("PASS eligible-card filter, scarce hands, original afflictions, deterministic RNG and multiplayer isolation.");
    }

    private static void Assert(bool condition,string text){if(!condition)throw new Exception(text);_checks++;}
    private sealed record Fixture(RunState Run,CombatRoom Room,List<Player> Players,EncounterModel Encounter)
    { public Player Player=>Players[0];public SilkMoth Moth=>Encounter.MonstersWithSlots.Select(e=>e.Item1).OfType<SilkMoth>().Single(); }
}
