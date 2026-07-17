using System;
using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

/// <summary>
///     SoulRoes 精英遭遇
///     SoulRoes → "soul_roes"
///     SoulRoe  → "soul_roe_1" ~ "soul_roe_8"
///     .tscn 场景中的 Marker2D 节点名必须与此一致。
/// </summary>
public sealed class SoulRoesEncounter : EncounterModel
{
    public const int SoulRoeSlotCount = 8;
    private const string SoulRoesSlot = "soul_roes";

    public override RoomType RoomType => RoomType.Elite;

    public override bool HasScene => true;

    public override IReadOnlyList<string> Slots =>
        [SoulRoesSlot, .. Enumerable.Range(0, SoulRoeSlotCount).Select(GetSoulRoeSlotName)];

    public override IEnumerable<MonsterModel> AllPossibleMonsters => new MonsterModel[]
    {
        ModelDb.Monster<SoulRoes>(),
        ModelDb.Monster<SoulRoe>()
    };

    public static string GetSoulRoeSlotName(int index)
    {
        if ((uint)index >= SoulRoeSlotCount)
            throw new ArgumentOutOfRangeException(nameof(index));
        return $"soul_roe_{index + 1}";
    }

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        return new (MonsterModel, string?)[]
        {
            (ModelDb.Monster<SoulRoes>().ToMutable(), SoulRoesSlot)
        };
    }
}
