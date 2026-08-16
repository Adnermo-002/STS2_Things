using System;
using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Encounters;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

public sealed class GravetideSlugBossEncounter : ModBossEncounter
{
    public const int CorpseSlugSlotCount = 6;
    public const string BossSlot = "gravetide_slug";

    private static readonly int[] OpeningSlotIndices = [0, 5];

    protected override string IconName => "gravetide_slug";

    public override RoomType RoomType => RoomType.Boss;

    public override IEnumerable<EncounterTag> Tags => [EncounterTag.Slugs];

    public override string CustomBgm =>
        "res://music/gravetide_slug/gravetide_slug_boss_theme.wav";

    public override bool HasScene => true;

    protected override bool HasCustomBackground => true;

    public override IEnumerable<string> ExtraAssetPaths =>
    [
        "res://images/ui/run_history/gravetide_slug_boss_encounter.png",
        "res://images/ui/run_history/gravetide_slug_boss_encounter_outline.png",
    ];

    public override IReadOnlyList<string> Slots =>
        [BossSlot, .. Enumerable.Range(0, CorpseSlugSlotCount).Select(GetCorpseSlugSlotName)];

    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
    [
        ModelDb.Monster<GravetideSlug>(),
        ModelDb.Monster<GravetideCorpseSlug>(),
        ModelDb.Monster<GravetideSlugCorpse>(),
    ];

    public static string GetCorpseSlugSlotName(int index)
    {
        if ((uint)index >= CorpseSlugSlotCount)
            throw new ArgumentOutOfRangeException(nameof(index));
        return $"gravetide_corpse_slug_{index + 1}";
    }

    /// <summary>
    /// Returns dedicated attendant slots in stable encounter order. A dead
    /// creature remains an occupied slot until its death/replacement sequence
    /// finishes, which prevents a summon from racing a corpse replacement.
    /// </summary>
    public static IReadOnlyList<string> GetVacantCorpseSlugSlots(ICombatState combatState)
    {
        return Enumerable.Range(0, CorpseSlugSlotCount)
            .Select(GetCorpseSlugSlotName)
            .Where(slot => !combatState.Enemies.Any(enemy =>
                string.Equals(enemy.SlotName, slot, StringComparison.Ordinal)))
            .ToArray();
    }

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        var boss = (GravetideSlug)ModelDb.Monster<GravetideSlug>().ToMutable();
        var attendants = Enumerable.Range(0, OpeningSlotIndices.Length)
            .Select(_ => (GravetideCorpseSlug)ModelDb.Monster<GravetideCorpseSlug>().ToMutable())
            .ToArray();

        int firstMove = Rng.NextInt(3);
        for (int index = 0; index < attendants.Length; index++)
            attendants[index].StarterMoveIndex = (firstMove + index) % 3;

        return
        [
            (boss, BossSlot),
            (attendants[0], GetCorpseSlugSlotName(OpeningSlotIndices[0])),
            (attendants[1], GetCorpseSlugSlotName(OpeningSlotIndices[1])),
        ];
    }
}
