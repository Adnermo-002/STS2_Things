using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using STS2_Things.Encounters;
using STS2_Things.Monsters;

public partial class DepthsProbeNode
{
    private async Task VerifyCaveGodDoom()
    {
        foreach (int players in new[] { 1, 4 })
        {
            var b = await StrongBattle(ModelDb.Encounter<CaveGodBossEncounter>(), players);
            var body = b.Monster<ThingsCaveGodBody>();
            var left = b.Monster<ThingsCaveGodLeftHand>();
            var right = b.Monster<ThingsCaveGodRightHand>();
            foreach (var arm in new ThingsCaveGodHand[] { left, right })
                await PowerCmd.Apply<DoomPower>(Choice, arm.Creature, arm.Creature.CurrentHp,
                    b.Players[0].Creature, null);
            b.State.CurrentSide = CombatSide.Enemy;
            GD.Print($"DOOM dual arms {players}p: begin");
            // Dispatch the complete native hook batch. Calling DoomKill alone
            // misses the stale second Doom listener captured before cleansing.
            var kill = SideEnding(b, CombatSide.Enemy, b.Enemies);
            Assert(await Task.WhenAny(kill, Task.Delay(3000)) == kill, "Dual-arm Doom must finish rather than stall the turn");
            await kill;
            Assert(body.IsWeakPhase, "Doom opens the core");
            Assert(left.Creature.IsAlive && right.Creature.IsAlive, "Both recoverable arms stay alive after Doom death prevention");
            Assert(!left.Creature.HasPower<DoomPower>() && !right.Creature.HasPower<DoomPower>(), "Both defeated arms cleanse Doom");
            for (int turn = 0; turn < 4; turn++)
            {
                foreach (var creature in b.Enemies.ToArray()) await creature.Monster!.PerformMove();
                foreach (var creature in b.Enemies.ToArray()) creature.Monster!.RollMove(b.Players.Select(p => p.Creature));
            }
            Assert(!body.IsWeakPhase && left.Creature.CurrentHp == left.Creature.MaxHp && right.Creature.CurrentHp == right.Creature.MaxHp,
                "The core exposure ends and both arms resume at full HP");
            DeactivateSyntheticCombat();
            GD.Print($"DOOM dual arms {players}p: completed and recovered");
        }
    }
}
