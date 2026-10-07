using System.Reflection;
using System.Runtime.Loader;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Multiplayer;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Saves;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.Unlocks;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Acts;
using STS2_Things.Cards;
using STS2_Things.Encounters;
using STS2_Things.Monsters;

public partial class SanguineLeechProbeNode : Node
{
    private static readonly ThrowingPlayerChoiceContext Choice = new();
    private static int _checks;
    private string _root = null!;
    public override void _Ready()
    {
        AssemblyLoadContext.Default.Resolving += ResolveRuntimeDependency;
        _ = RunProbe();
    }
    private async Task RunProbe()
    {
        try
        {
            _root = Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"), "../.."));
            TestMode.TurnOnInternal();
            ProjectSettings.LoadResourcePack("D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck");
            string pack=System.Environment.GetEnvironmentVariable("THINGS_PROBE_PCK")
                ?? Path.Combine(_root,"build/sanguine_leech/v111/STS2_Things.pck");
            if (File.Exists(pack)) ProjectSettings.LoadResourcePack(pack);
            SaveManager.Instance.InitSettingsDataForTest();
            SaveManager.Instance.InitPrefsDataForTest();
            SaveManager.Instance.SettingsSave.Language = "eng";
            LocManager.Initialize();
            InitializeModelDb();
            VerifyPools();
            await VerifyOpeningHand();
            await VerifyParasite();
            await VerifyMoves();
            await VerifyHandOverflow();
            if (OS.GetCmdlineUserArgs().Contains("--visual")) await RenderProbe();
            DeactivateSyntheticCombat();
            GD.Print($"Sanguine Leech probe: PASS ({_checks} assertions)");
            GetTree().Quit();
        }
        catch (Exception ex) { GD.PushError(ex.ToString()); GetTree().Quit(1); }
    }

    private static Fixture Scenario(bool weak = false, int players = 1, int ascension = 0)
    {
        DeactivateSyntheticCombat();
        var party = Enumerable.Range(1,players).Select(i => Player.CreateForNewRun<Ironclad>(UnlockState.all,(ulong)i)).ToList();
        var run = RunState.CreateForNewRun(party, ActModel.GetDefaultList().Select(a=>a.ToMutable()).ToList(),[],GameMode.Standard,ascension,"leech-native-probe");
        run.CurrentActIndex = 1;
        typeof(RunManager).GetProperty("State",BindingFlags.NonPublic|BindingFlags.Instance)!.SetValue(RunManager.Instance,run);
        typeof(RunManager).GetProperty("AscensionManager")!.SetValue(RunManager.Instance,new AscensionManager(ascension));
        typeof(RunManager).GetProperty("NetService")!.SetValue(RunManager.Instance,new NetSingleplayerGameService());
        EncounterModel encounter = (weak ? ModelDb.Encounter<SanguineLeechWeak>() as EncounterModel : ModelDb.Encounter<SanguineLeechEncounter>()).ToMutable();
        run.AppendToMapPointHistory(MapPointType.Monster,RoomType.Monster,encounter.Id);
        var room = new CombatRoom(encounter,run);run.PushRoom(room);
        foreach (var p in party) {p.ResetCombatState();room.CombatState.AddPlayer(p);p.PopulateCombatState(run.Rng.Shuffle,room.CombatState);}
        encounter.GenerateMonstersWithSlots(run);
        foreach (var (monster,slot) in encounter.MonstersWithSlots)
        {
            var entity=room.CombatState.CreateCreature(monster,CombatSide.Enemy,slot);
            room.CombatState.AddCreature(entity);monster.SetUpForCombat();
        }
        room.CombatState.CurrentSide=CombatSide.Player;
        ActivateSyntheticCombat(room.CombatState);
        return new(run,room,party,encounter);
    }

    private static void VerifyPools()
    {
        var depths=ModelDb.Act<Depths>();
        Assert(depths.AllWeakEncounters.Any(e=>e is SanguineLeechWeak),"Leech pair in Depths weak pool.");
        Assert(depths.AllRegularEncounters.Any(e=>e is SanguineLeechEncounter),"Leech trio in Depths regular pool.");
        Assert(depths.AllWeakEncounters.Any(e=>e is LanternFishWeak) && depths.AllRegularEncounters.Any(e=>e is LanternFishEncounter),"Existing fish encounters retained.");
        foreach(bool weak in new[]{true,false})
        {
            var s=Scenario(weak);int expected=weak?2:3;
            Assert(s.Leeches.Length==expected && s.Encounter.IsWeak==weak,"Correct encounter size/classification.");
            Assert(s.Encounter.Slots.Count==expected && s.Leeches.All(l=>l.Creature.SlotName!=null),"Every leech has a slot.");
            string[] cycle=["SIP_MOVE","INFEST_MOVE","SIP_AGAIN_MOVE","CURL_MOVE"];
            foreach (var l in s.Leeches)
            {
                Assert(l.MinInitialHp==34 && l.MaxInitialHp==38,"A0 HP range.");
                for(int turn=0;turn<8;turn++)
                {
                    var move=l.MoveStateMachine!.RollMove([s.Player.Creature],l.Creature,s.Run.Rng.MonsterAi);
                    Assert(move.Id==cycle[(l.OpeningPhase+turn)%4],"Deterministic staggered cycle.");
                    l.MoveStateMachine.OnMovePerformed(move);
                }
            }
        }
        var high=Scenario(ascension:20);
        Assert(high.Leeches.All(l=>l.MinInitialHp==38 && l.MaxInitialHp==42),"Tough-enemy HP range.");
        GD.Print("PASS pools, counts, HP and staggered move state machines.");
    }

    private static async Task VerifyOpeningHand()
    {
        foreach (bool weak in new[]{true,false})
        {
            var s=Scenario(weak,players:2);
            int deck=s.Player.Deck.Cards.Count;
            await Hook.BeforeCombatStart(s.Run,s.Room.CombatState);
            foreach(var p in s.Players)
            {
                Assert(p.PlayerCombatState!.Hand.Cards.OfType<LeechParasite>().Count()==s.Leeches.Length,"Each leech generates one opening parasite directly in hand.");
                Assert(!p.PlayerCombatState.DrawPile.Cards.OfType<LeechParasite>().Any(),"Opening parasites never enter the draw pile.");
                var method=typeof(CombatManager).GetMethod("SetupPlayerTurn",BindingFlags.Instance|BindingFlags.NonPublic)!;
                var ctx=new HookPlayerChoiceContext(p,p.NetId,GameActionType.Combat);
                object?[] args=method.GetParameters().Length==3
                    ? [typeof(CombatManager).GetField("_turnState",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(CombatManager.Instance),p,ctx]
                    : [p,ctx];
                await (Task)method.Invoke(CombatManager.Instance,args)!;
                Assert(p.PlayerCombatState.Hand.Cards.OfType<LeechParasite>().Count()==s.Leeches.Length,"Normal opening draws retain the directly generated parasites.");
                Assert(p.PlayerCombatState.Hand.Cards.Count==5+s.Leeches.Length,"Five normal opening cards are drawn in addition to the parasites.");
                Assert(p.Deck.Cards.Count==deck && !p.Deck.Cards.OfType<LeechParasite>().Any(),"Permanent deck unchanged.");
            }
        }
        GD.Print("PASS direct opening hand, full normal opening draw, two/three parasites and temporary deck ownership.");
    }

    private static LeechParasite Parasite(Fixture s,Player? player=null,PileType pile=PileType.Hand)
    {
        player??=s.Player;
        var card=s.Room.CombatState.CreateCard<LeechParasite>(player);
        pile.GetPile(player).AddInternal(card,silent:true);
        return card;
    }
    private static async Task EndHand(Fixture s,Player? player=null)
    {
        player??=s.Player;
        var method=typeof(CombatManager).GetMethod("DoTurnEnd",BindingFlags.Instance|BindingFlags.NonPublic)!;
        object?[] args=method.GetParameters().Length==3
            ? [typeof(CombatManager).GetField("_turnState",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(CombatManager.Instance),player,Choice]
            : [player,Choice];
        await (Task)method.Invoke(CombatManager.Instance,args)!;
    }
    private static async Task VerifyParasite()
    {
        foreach(int players in new[]{1,2,4})
        {
            var s=Scenario(players:players);var card=Parasite(s);
            Assert(card.Type==CardType.Status && card.EnergyCost.Canonical==1 && card.MaxUpgradeLevel==0,"Status cost/upgrade rules.");
            Assert(!card.Keywords.Contains(CardKeyword.Innate) && card.Keywords.Contains(CardKeyword.Exhaust),"Parasite has Exhaust and no Innate keyword.");
            await EndHand(s);
            Assert(s.Leeches.All(l=>l.Creature.GetPower<RegenPower>()?.Amount==2 && l.Creature.GetPower<StrengthPower>()?.Amount==2),
                $"Exactly two native buffs with {players} players: "+string.Join(",",s.Leeches.Select(l=>$"{l.Creature.GetPower<RegenPower>()?.Amount}/{l.Creature.GetPower<StrengthPower>()?.Amount}")));
            Assert(s.Player.PlayerCombatState!.DiscardPile.Cards.Contains(card),"Native end-turn moves status through Play into Discard, without exhausting.");
            Parasite(s);Parasite(s);await EndHand(s);
            Assert(s.Leeches.All(l=>l.Creature.GetPower<RegenPower>()?.Amount==6 && l.Creature.GetPower<StrengthPower>()?.Amount==6),"Two simultaneous retained statuses stack independently.");
            Parasite(s,pile:PileType.Draw);await EndHand(s);
            Assert(s.Leeches.All(l=>l.Creature.GetPower<StrengthPower>()?.Amount==6),"Off-hand statuses never feed.");
        }
        {
            var s=Scenario();var card=Parasite(s);var pc=s.Player.PlayerCombatState!;
            pc.Energy=3;
            await card.SpendResources();
            Assert(pc.Energy==2,"Removing a parasite costs one energy.");
            await CardCmd.AutoPlay(Choice,card,null,skipCardPileVisuals:true);
            Assert(pc.ExhaustPile.Cards.Contains(card) && !pc.Hand.Cards.Contains(card),"Native play exhausts the status.");
            await EndHand(s);
            Assert(s.Leeches.All(l=>l.Creature.GetPower<StrengthPower>()==null),"Played parasite does not feed.");
            var discard=Parasite(s);await CardCmd.Discard(Choice,discard);
            await EndHand(s);
            Assert(s.Leeches.All(l=>l.Creature.GetPower<StrengthPower>()==null),"Discarding before turn end prevents feeding.");
        }
        {
            var s=Scenario();var card=Parasite(s);var state=s.Room.CombatState;
            var other=state.CreateCreature(ModelDb.Monster<LeafSlimeS>().ToMutable(),CombatSide.Enemy,null);
            state.AddCreature(other);other.Monster!.SetUpForCombat();
            await CreatureCmd.Kill(s.Leeches[0].Creature);
            await EndHand(s);
            Assert(s.Leeches[0].Creature.GetPower<RegenPower>()==null,"Dead leech not resurrected/fed.");
            Assert(other.GetPower<RegenPower>()==null && other.GetPower<StrengthPower>()==null,"Unrelated enemies do not receive buffs.");
            Assert(s.Leeches.Skip(1).All(l=>l.Creature.GetPower<StrengthPower>()?.Amount==2),"Other living leeches are fed.");
            var living=s.Leeches[1].Creature;
            living.SetCurrentHpInternal(living.MaxHp-10);
            state.CurrentSide=CombatSide.Enemy;
            foreach(var names in new[]{new[]{"BeforeSideTurnEnd","BeforeTurnEnd"},new[]{"AfterSideTurnEnd","AfterTurnEnd"}})
            {
                var hook=names.Select(name=>typeof(Hook).GetMethod(name,BindingFlags.Public|BindingFlags.Static)).First(m=>m!=null)!;
                await (Task)hook.Invoke(null,[state,CombatSide.Enemy,new[]{living}])!;
            }
            Assert(living.CurrentHp==living.MaxHp-8 && living.GetPower<RegenPower>()?.Amount==1,"Native Regen heals and decrements at enemy turn end.");
        }
        GD.Print("PASS fixed buff amounts, living-leech filter, play/discard counterplay and native Regeneration.");
    }

    private static async Task VerifyMoves()
    {
        foreach(int ascension in new[]{0,20})
        {
            var s=Scenario(ascension:ascension);var l=s.Leeches[0];var enemy=l.Creature;
            enemy.SetCurrentHpInternal(enemy.MaxHp-12);int playerHp=s.Player.Creature.CurrentHp;
            await ((MoveState)l.MoveStateMachine!.States["SIP_MOVE"]).PerformMove([s.Player.Creature]);
            int damage=ascension==0?7:8;
            Assert(s.Player.Creature.CurrentHp==playerHp-damage,"Native siphon damage and ascension.");
            Assert(enemy.CurrentHp==enemy.MaxHp-12+damage,"Siphon heals actual life damage.");
            await CreatureCmd.GainBlock(s.Player.Creature,50,ValueProp.Unpowered,null);
            int hp=enemy.CurrentHp;playerHp=s.Player.Creature.CurrentHp;
            await ((MoveState)l.MoveStateMachine.States["SIP_MOVE"]).PerformMove([s.Player.Creature]);
            Assert(enemy.CurrentHp==hp && s.Player.Creature.CurrentHp==playerHp,"Full block prevents both damage and lifesteal.");
            await ((MoveState)l.MoveStateMachine.States["CURL_MOVE"]).PerformMove([s.Player.Creature]);
            Assert(enemy.Block==8,"Curl grants eight block.");
            int parasites=s.Player.PlayerCombatState!.Hand.Cards.OfType<LeechParasite>().Count();
            await ((MoveState)l.MoveStateMachine.States["INFEST_MOVE"]).PerformMove([s.Player.Creature]);
            Assert(s.Player.PlayerCombatState.Hand.Cards.OfType<LeechParasite>().Count()==parasites+1,"Infest generates one temporary status directly in hand.");
        }
        GD.Print("PASS native moves, ascension, healing and full-block prevention.");
    }

    private static async Task VerifyHandOverflow()
    {
        var s=Scenario(players:2);
        var full=s.Players[0];var open=s.Players[1];
        for(int i=0;i<CardPile.MaxCardsInHand;i++)
            await CardPileCmd.AddGeneratedCardToCombat(s.Room.CombatState.CreateCard<StrikeIronclad>(full),PileType.Hand,null);
        await PowerCmd.Apply<STS2_Things.Powers.SpongeRinsePower>(Choice,open.Creature,1,s.Leeches[0].Creature,null);
        var move=(MoveState)s.Leeches[0].MoveStateMachine!.States["INFEST_MOVE"];
        await move.PerformMove(s.Players.Select(p=>p.Creature));
        Assert(full.PlayerCombatState!.Hand.Cards.Count==CardPile.MaxCardsInHand,"Infest respects the native full-hand limit.");
        Assert(full.PlayerCombatState.DiscardPile.Cards.OfType<LeechParasite>().Count()==1,"Full-hand parasite goes to discard using the native overflow rule.");
        Assert(open.PlayerCombatState!.Hand.Cards.OfType<LeechParasite>().Count()==1,"Another player's free hand still receives the parasite.");
        Assert(s.Players.All(p=>!p.PlayerCombatState!.DrawPile.Cards.OfType<LeechParasite>().Any()),"Neither normal delivery nor overflow sends parasites to the draw pile.");
        Assert(open.Creature.GetPower<STS2_Things.Powers.SpongeRinsePower>()?.Amount==1,"Direct hand generation is not a draw and does not consume Rinsed.");
        GD.Print("PASS native hand generation, multiplayer ownership, overflow and draw-only Rinsed semantics.");
    }

    private static void Assert(bool condition,string message) { if(!condition)throw new Exception(message);_checks++; }
    private sealed record Fixture(RunState Run, CombatRoom Room, List<Player> Players, EncounterModel Encounter)
    {
        public Player Player=>Players[0];
        public SanguineLeech[] Leeches=>Encounter.MonstersWithSlots.Select(m=>(SanguineLeech)m.Item1).ToArray();
    }
}
