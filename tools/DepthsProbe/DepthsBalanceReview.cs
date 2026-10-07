using System.Text.Json;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Hooks;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Acts;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using STS2_Things.Acts;
using STS2_Things.Monsters;
using STS2_Things.Powers;
using MegaCrit.Sts2.Core.HoverTips;

public partial class DepthsProbeNode
{
    // An unmitigated trajectory, not a victory-rate simulation. No player
    // cards are played and no enemy is killed. Actual draw/end-turn hooks still
    // apply, so leaving Parasitism alone intentionally includes its growth.
    private async Task SampleDepthsBalance()
    {
        var custom = ModelDb.Act<Depths>().AllWeakEncounters
            .Concat(ModelDb.Act<Depths>().AllRegularEncounters)
            .Concat(ModelDb.Act<Depths>().AllEliteEncounters.Where(e => e.GetType().Assembly == typeof(Depths).Assembly)).ToArray();
        EncounterModel[] reference = [
            ModelDb.Encounter<BowlbugsWeak>(), ModelDb.Encounter<ThievingHopperWeak>(), ModelDb.Encounter<TunnelerWeak>(),
            ModelDb.Encounter<BowlbugsNormal>(), ModelDb.Encounter<ChompersNormal>(), ModelDb.Encounter<HunterKillerNormal>(),
            ModelDb.Encounter<EntomancerElite>(), ModelDb.Encounter<InfestedPrismsElite>(),
        ];
        var records = new List<object>();
        foreach (var canonical in custom.Concat(reference))
        foreach (int ascension in new[] { 0, 20 })
        foreach (int players in new[] { 1, 4 })
        {
            var b = await StrongBattle(canonical, players, ascension, "depths-balance-" + canonical.Id.Entry);
            foreach (var creature in b.Enemies) await creature.Monster!.AfterAddedToRoom();
            foreach (var creature in b.Enemies)
            {
                if (creature.Monster is ReverseSalamander salamander && creature.GetPower<ReverseCurrentPower>() is { } reflux)
                {
                    string text = reflux.HoverTips.OfType<HoverTip>().First().Description;
                    Assert(text.Contains($"[blue]{salamander.GrowthAmount}[/blue]"),
                        "Native Reflux tooltip displays the actual A0/A20 Strength gift.");
                }
                if (creature.Monster is RadioJellyfish && creature.GetPower<RadioReceptionPower>() is { } reception)
                {
                    string text = reception.HoverTips.OfType<HoverTip>().First().Description;
                    Assert(text.Contains("[blue]1[/blue]"), "Native Reception tooltip displays one point per opening stack.");
                }
            }
            foreach (var player in b.Players) { player.Creature.SetMaxHpInternal(10000); player.Creature.SetCurrentHpInternal(10000); }
            var roster = b.Enemies.Select(c => new { monster = c.Monster!.Id.Entry, hp = c.MaxHp,
                baseMin = c.Monster.MinInitialHp, baseMax = c.Monster.MaxInitialHp, block = c.Block }).ToArray();
            var turns = new List<object>();
            for (int turn = 1; turn <= 8 && b.Enemies.Length > 0; turn++)
            {
                b.State.RoundNumber = turn;
                b.State.CurrentSide = CombatSide.Player;
                foreach (var player in b.Players)
                {
                    await player.Creature.AfterTurnStart(CombatSide.Player);
                    await PlayerCmd.SetEnergy(3, player);
                    await CardPileCmd.Draw(Choice, 5, player);
                    await Hook.AfterPlayerTurnStart(b.State, Choice, player);
                }
                await SideEnding(b, CombatSide.Player, b.Players.Select(p => p.Creature).ToArray());
                foreach (var player in b.Players) await EndPlayer(b, player);
                await SideEnded(b, CombatSide.Player, b.Players.Select(p => p.Creature).ToArray());
                b.State.CurrentSide = CombatSide.Enemy;
                var participants = b.Enemies;
                int[] hp = b.Players.Select(p => p.Creature.CurrentHp).ToArray();
                var moves = new List<object>();
                foreach (var creature in participants)
                {
                    if (!creature.IsAlive) continue;
                    await creature.AfterTurnStart(CombatSide.Enemy);
                    var monster = creature.Monster!;
                    int intent = monster.NextMove.Intents.OfType<AttackIntent>().Sum(i => i.GetTotalDamage([b.Players[0].Creature], creature));
                    Assert(intent >= 0, "Nonnegative native attack intent");
                    string id = monster.NextMove.Id;
                    int before = b.Players[0].Creature.CurrentHp;
                    await monster.PerformMove();
                    moves.Add(new { monster = monster.Id.Entry, move = id, intent,
                        actualDamageToFirstPlayer = before - b.Players[0].Creature.CurrentHp,
                        strengthAfter = creature.GetPower<StrengthPower>()?.Amount ?? 0, blockAfter = creature.Block });
                }
                await SideEnding(b, CombatSide.Enemy, participants);
                await SideEnded(b, CombatSide.Enemy, participants);
                turns.Add(new { turn, damageByPlayer = b.Players.Select((p, i) => hp[i] - p.Creature.CurrentHp).ToArray(), moves });
                b.State.CurrentSide = CombatSide.Player;
                foreach (var creature in b.Enemies) creature.Monster!.RollMove(b.Players.Select(p => p.Creature));
            }
            Assert(b.Players.All(p => p.Creature.IsAlive), "Measurement fixture stays alive");
            records.Add(new { encounter = canonical.Id.Entry, source = canonical.GetType().Assembly == typeof(Depths).Assembly ? "depths" : "native",
                kind = canonical.RoomType.ToString(), weak = canonical.IsWeak, ascension, players, roster, turns });
            DeactivateSyntheticCombat();
        }
        File.WriteAllText(Path.Combine(_output, "balance-trajectories.json"), JsonSerializer.Serialize(records, new JsonSerializerOptions { WriteIndented = true }));
        Godot.GD.Print($"PASS {records.Count} native balance trajectories: A0/A20, 1/4 players; eight unmitigated turns, not win rates.");
    }
}
