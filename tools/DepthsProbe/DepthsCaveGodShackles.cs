using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Powers;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Encounters;
using STS2_Things.Monsters;

public partial class DepthsProbeNode
{
    private async Task VerifyCaveGodShackles()
    {
        foreach (int players in new[] { 1, 4 })
        foreach (bool left in new[] { false, true })
        foreach (int strength in new[] { 0, 4, 12 })
        {
            var b = await StrongBattle(ModelDb.Encounter<CaveGodBossEncounter>(), players);
            ThingsCaveGodHand survivor = left ? b.Monster<ThingsCaveGodLeftHand>() : b.Monster<ThingsCaveGodRightHand>();
            ThingsCaveGodHand broken = left ? b.Monster<ThingsCaveGodRightHand>() : b.Monster<ThingsCaveGodLeftHand>();
            if (strength != 0) await PowerCmd.Apply<StrengthPower>(Choice, survivor.Creature, strength, survivor.Creature, null);
            await PowerCmd.Apply<DarkShacklesPower>(Choice, survivor.Creature, 9, b.Players[0].Creature, null);
            await CreatureCmd.Kill(broken.Creature);
            bool targetable = survivor.ShouldAllowTargeting(survivor.Creature);
            await SideEnded(b, CombatSide.Enemy, b.Enemies);
            Assert(survivor.Creature.GetPowerAmount<StrengthPower>() == strength,
                $"Shackles on surviving stunned arm must restore baseline {strength}, got {survivor.Creature.GetPowerAmount<StrengthPower>()}");
            Assert(targetable && survivor.Creature.IsHittable, "Surviving arm is targetable during the initial exposure stun");
            int hp = survivor.Creature.CurrentHp;
            await CreatureCmd.Damage(Choice, survivor.Creature, 1, ValueProp.Unpowered, b.Players[0].Creature);
            Assert(survivor.Creature.CurrentHp == hp - 1, "Surviving arm actually receives attacks in the break turn");
            DeactivateSyntheticCombat();

            b = await StrongBattle(ModelDb.Encounter<CaveGodBossEncounter>(), players);
            broken = left ? b.Monster<ThingsCaveGodLeftHand>() : b.Monster<ThingsCaveGodRightHand>();
            if (strength != 0) await PowerCmd.Apply<StrengthPower>(Choice, broken.Creature, strength, broken.Creature, null);
            await PowerCmd.Apply<DarkShacklesPower>(Choice, broken.Creature, 9, b.Players[0].Creature, null);
            var old = broken.Creature.GetPower<DarkShacklesPower>()!;
            await CreatureCmd.Kill(broken.Creature);
            Assert(broken.Creature.GetPowerAmount<StrengthPower>() == strength, "Cleansing temporary loss preserves original positive strength");
            Assert(!broken.Creature.HasPower<DarkShacklesPower>() && old.Amount == 0, "Cleansed temporary-loss instance is retired");
            await old.AfterSideTurnEnd(Choice, CombatSide.Enemy, b.Enemies);
            Assert(broken.Creature.GetPowerAmount<StrengthPower>() == strength, "A stale temporary-loss callback cannot double-refund strength");
            Assert(!broken.ShouldAllowTargeting(broken.Creature), "Broken arm remains protected");
            DeactivateSyntheticCombat();
        }
        GD.Print("PASS Shackles restoration, positive-strength preservation, stale callbacks and same-turn surviving-arm attacks");
    }
}
