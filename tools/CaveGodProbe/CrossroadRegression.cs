using System.Reflection;
using System.Text.Json;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Multiplayer.Serialization;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves.Runs;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Map;
using STS2_Things.Modifiers;

public sealed class CrossroadFixtureMap : ActMap
{
    protected override MapPoint?[,] Grid { get; } = new MapPoint?[7, 15];
    public override MapPoint StartingMapPoint { get; } = new(3, 0) { PointType = MapPointType.Ancient };
    public override MapPoint BossMapPoint { get; } = new(3, 15) { PointType = MapPointType.Boss };
    public CrossroadFixtureMap()
    {
        for(int row=1;row<15;row++)
        foreach(int col in new[]{0,2,4,6})
        {
            var type=row switch {3=>col<3?MapPointType.Shop:MapPointType.RestSite,
                7=>col<3?MapPointType.Treasure:MapPointType.Unknown,
                10=>col<3?MapPointType.Unknown:MapPointType.RestSite,11=>MapPointType.Elite,14=>MapPointType.RestSite,_=>MapPointType.Monster};
            Grid[col,row]=new MapPoint(col,row){PointType=type};
        }
        foreach(int col in new[]{0,2,4,6})
        {
            StartingMapPoint.AddChildPoint(Grid[col,1]!);
            for(int row=1;row<14;row++)Grid[col,row]!.AddChildPoint(Grid[col,row+1]!);
            Grid[col,14]!.AddChildPoint(BossMapPoint);
        }
    }
}

public partial class CaveGodProbeNode
{
    private static void VerifyCrossroadSaveFiltering()
    {
        var options=new JsonSerializerOptions{IncludeFields=true,IgnoreReadOnlyProperties=true};
        foreach(var type in new[]{MapPointType.Treasure,MapPointType.RestSite,MapPointType.Shop,
            MapPointType.Unknown,MapPointType.Monster,MapPointType.Elite})
        {
            var run=RunState.CreateForTest(seed:$"same-room-road-{type}");
            var map=new CrossroadFixtureMap();run.Map=map;
            var same=new CrossroadRecord{Row=7,Left=0,Right=2};
            map.GetPoint(same.A)!.PointType=type;map.GetPoint(same.B)!.PointType=type;
            var useful=new CrossroadRecord{Row=3,Left=2,Right=4};
            var history=new List<MapCoord>{map.StartingMapPoint.coord,useful.A};
            var old=new ThingsCrossroads.Ledger{Acts=[new CrossroadActPlan{Act=0,Fingerprint=CrossroadPlan.Fingerprint(map),
                Roads=[useful,same],History=history}]};
            var ledger=Crossroads.Ledger(run)!;ledger.Data=JsonSerializer.Serialize(old,options);
            var filtered=ledger.EnsurePlan(run,map,0)!;
            Assert(filtered.Roads.Count==1&&filtered.Roads[0].A==useful.A&&filtered.Roads[0].B==useful.B,
                $"Saved locked {type}-to-{type} road was not removed, or a useful road was changed");
            Assert(filtered.History.SequenceEqual(history),"Filtering roads changed visit history");
            string once=ledger.Data;ledger.EnsurePlan(run,map,0);
            Assert(ledger.Data==once,"Saved route filtering is not idempotent");
            var restored=(ThingsCrossroads)ModifierModel.FromSerializable(ledger.ToSerializable());
            Assert(restored.EnsurePlan(run,map,0)!.Roads.Count==1,"Removed route returned after native save reload");

            same.FromColumn=same.Left;same.Payer=42;
            ledger.Data=JsonSerializer.Serialize(old,options);
            var paid=ledger.EnsurePlan(run,map,0)!;
            Assert(paid.Roads.Any(r=>r.A==same.A&&r.IsOpen&&r.From==same.From&&r.Payer==42),"Filtering removed a previously paid road");
            Assert(map.GetPoint(same.From)!.Children.Contains(map.GetPoint(same.To)!),"Previously paid road did not remain traversable");
            AssertAcyclic(map);

            // No same-type fallback just to fill the three-road quota.
            var uniform=new CrossroadFixtureMap();
            foreach(var point in uniform.GetAllMapPoints())point.PointType=type;
            Assert(CrossroadPlan.Generate(uniform,run.Rng.Seed,0).Count==0,$"Uniform {type} map still generated same-type roads");
        }
    }

    private static void AssertAcyclic(ActMap map)
    {
        var active=new HashSet<MapPoint>();var done=new HashSet<MapPoint>();
        void Visit(MapPoint point)
        {
            if(done.Contains(point))return;
            Assert(active.Add(point),"A horizontal route introduced a map cycle");
            foreach(var child in point.Children)Visit(child);
            active.Remove(point);done.Add(point);
        }
        foreach(var point in map.GetAllMapPoints())Visit(point);
    }

    private async Task VerifyCrossroads()
    {
        string root=Path.GetFullPath(Path.Combine(ProjectSettings.GlobalizePath("res://"),"../.."));
        string output=Path.Combine(root,"build/crossroads-20261003");Directory.CreateDirectory(output);
        var harmony=new Harmony("Things.Crossroads.Probe");
        foreach(var name in new[]{"CrossroadRunPatch","CrossroadHistoryRecordPatch","CrossroadHistoryLookupPatch","CrossroadFreeTravelPatch"})
            harmony.CreateClassProcessor(ImplementationAssembly.GetType("STS2_Things.Map."+name,true)!).Patch();
        ActionTypes.Initialize();
        var results=new List<object>();
        try
        {
            // Real native map generation across seeded acts, separate from the
            // hand-built transaction fixture below.
            var generated=new List<object>();
            for(int seed=0;seed<120;seed++)
            {
                var run=RunState.CreateForTest(seed:$"crossroads-{seed}");
                for(int act=0;act<run.Acts.Count;act++)
                {
                    var map=run.Acts[act].CreateMap(run,false);
                    var first=CrossroadPlan.Generate(map,run.Rng.Seed,act);
                    var again=CrossroadPlan.Generate(map,run.Rng.Seed,act);
                    Assert(JsonSerializer.Serialize(first)==JsonSerializer.Serialize(again),"Route generation is not deterministic");
                    Assert(first.Count<=3&&first.Select(r=>r.Row).Distinct().Count()==first.Count,"Too many routes or duplicate rows");
                    foreach(var road in first)
                    {
                        var a=map.GetPoint(road.A)!;var b=map.GetPoint(road.B)!;
                        Assert(a.PointType!=b.PointType,$"Seed {seed}, act {act}: generated a {a.PointType}-to-{b.PointType} road");
                        Assert(road.Left<road.Right&&road.Right-road.Left<=3&&road.Row>=2,"Invalid horizontal span");
                        Assert(a.PointType is MapPointType.RestSite or MapPointType.Shop or MapPointType.Treasure or MapPointType.Unknown ||
                            b.PointType is MapPointType.RestSite or MapPointType.Shop or MapPointType.Treasure or MapPointType.Unknown ||
                            a.Children.Concat(b.Children).Any(c=>c.PointType==MapPointType.Elite),"Route misses every preferred destination");
                    }
                    generated.Add(new{seed,act,roads=first.Select(r=>new{r.Row,r.Left,r.Right}).ToArray()});
                }
            }
            VerifyCrossroadSaveFiltering();
            foreach(int count in new[]{1,2,4})
            foreach(bool fromRight in new[]{false,true})
            {
                var players=Enumerable.Range(1,count).Select(i=>Player.CreateForNewRun<Ironclad>(UnlockState.all,(ulong)i)).ToArray();
                var run=RunState.CreateForTest(players,seed:"paid-roads");
                var ledger=Crossroads.Ledger(run) ?? throw new InvalidOperationException("Route ledger was not attached to the run");
                var map=new CrossroadFixtureMap();run.Map=map;
                var plan=ledger.EnsurePlan(run,map,0)!;
                Assert(plan.Roads.Count==3,"Fixture must expose three separate opportunities");
                var road=plan.Roads[0];var from=fromRight?road.B:road.A;var to=road.Other(from);
                run.AddVisitedMapCoord(map.StartingMapPoint.coord);
                run.AddVisitedMapCoord(from);
                foreach(var player in players)player.Gold=125;
                var payer=players[^1];
                Assert(await Crossroads.Purchase(payer,0,plan.Fingerprint,from,to,1)==CrossroadPurchaseResult.Stale,"Client changed the price");
                Assert(await Crossroads.Purchase(payer,0,plan.Fingerprint+1,from,to,50)==CrossroadPurchaseResult.Stale,"Stale map accepted");
                payer.Gold=49;
                Assert(await Crossroads.Purchase(payer,0,plan.Fingerprint,from,to,50)==CrossroadPurchaseResult.InsufficientGold,"Insufficient gold accepted");
                Assert(!road.IsOpen&&payer.Gold==49,"Rejected purchase mutated the route or gold");payer.Gold=125;
                var action=new NetUnlockCrossroadAction{Act=0,Fingerprint=plan.Fingerprint,From=from,To=to,Price=50};
                Assert(action.ToId()>=0,"Native action discovery missed the unlock action");
                var writer=new PacketWriter();action.Serialize(writer);var reader=new PacketReader();reader.Reset(writer.Buffer);
                var decoded=new NetUnlockCrossroadAction();decoded.Deserialize(reader);
                Assert(decoded.Act==action.Act&&decoded.Fingerprint==action.Fingerprint&&decoded.From==from&&decoded.To==to&&decoded.Price==50,"Action packet changed");
                var nativeAction=decoded.ToGameAction(payer);nativeAction.OnEnqueued(_=>{},1);await nativeAction.Execute();
                Assert(nativeAction.Exception==null&&road.IsOpen,"Native unlock action failed");
                Assert(payer.Gold==75&&players.Where(p=>p!=payer).All(p=>p.Gold==125),"Someone other than the initiator paid");
                Assert(await Crossroads.Purchase(payer,0,plan.Fingerprint,from,to,50)==CrossroadPurchaseResult.AlreadyOpen,"Duplicate purchase was not idempotent");
                Assert(payer.Gold==75,"Duplicate purchase charged again");
                Assert(map.GetPoint(from)!.Children.Contains(map.GetPoint(to)!),"Paid edge missing");AssertAcyclic(map);
                var fingerprint=CrossroadPlan.Fingerprint(map);Assert(fingerprint==plan.Fingerprint,"Opening a route changed its map identity");

                var saved=ledger.ToSerializable();writer.Reset();saved.Serialize(writer);reader.Reset(writer.Buffer);
                var restoredData=new SerializableModifier();restoredData.Deserialize(reader);
                var restored=(ThingsCrossroads)ModifierModel.FromSerializable(restoredData);
                var regenerated=new CrossroadFixtureMap();restored.Bind(run);restored.EnsurePlan(run,regenerated,0);
                Assert(regenerated.GetPoint(from)!.Children.Contains(regenerated.GetPoint(to)!),"Reload/regeneration lost the paid edge");
                var nativeSavedMap=new SavedActMap(SerializableActMap.FromActMap(map));
                restored.EnsurePlan(run,nativeSavedMap,0);AssertAcyclic(nativeSavedMap);
                run.AddVisitedMapCoord(to);
                Assert(await Crossroads.Purchase(payer,0,plan.Fingerprint,to,from,50)==CrossroadPurchaseResult.NotAtRoad,"Reverse travel allowed reward farming");
                Assert(ledger.HistoryIndex(new MapLocation(to,0))==2,"Same-row room history did not retain visit order");
                results.Add(new{count,fromRight,gold=payer.Gold,from=from.ToString(),to=to.ToString(),serializedBytes=writer.BytePosition});
            }
            File.WriteAllText(Path.Combine(output,"generation.json"),JsonSerializer.Serialize(generated,new JsonSerializerOptions{WriteIndented=true}));
            File.WriteAllText(Path.Combine(output,"transactions.json"),JsonSerializer.Serialize(results,new JsonSerializerOptions{WriteIndented=true}));
            GD.Print($"CROSSROADS_RULES_PASS maps={generated.Count} transactions={results.Count}; different-room routes only, six same-type save migrations/paid-edge preservation, deterministic routes, native actions, payer-only gold, save/network roundtrip, no cycles/revisits");
        }
        finally{harmony.UnpatchAll(harmony.Id);}
    }
}
