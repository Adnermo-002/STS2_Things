using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Monsters;
using MegaCrit.Sts2.Core.Rooms;
using STS2_Things.Monsters;

namespace STS2_Things.Encounters;

/// <summary>
///     劫掠队 — 3 个随机劫掠者 + 1 个劫掠者窃贼
/// </summary>
public sealed class RaidParty : EncounterModel
{
    // ModelDb 尚未初始化时不能在静态字段初始化器中查询模型。
    private static IReadOnlyList<MonsterModel> RaiderPool =>
    [
        ModelDb.Monster<AxeRubyRaider>(),
        ModelDb.Monster<AssassinRubyRaider>(),
        ModelDb.Monster<BruteRubyRaider>(),
        ModelDb.Monster<CrossbowRubyRaider>(),
        ModelDb.Monster<TrackerRubyRaider>()
    ];

    public override RoomType RoomType => RoomType.Elite;

    public override bool HasScene => true;

    public override IReadOnlyList<string> Slots => new[]
    {
        "thief_raider", "raider_1", "raider_2", "raider_3", "raider_4", "raider_5"
    };

    public override IEnumerable<MonsterModel> AllPossibleMonsters =>
        RaiderPool.Append(ModelDb.Monster<ThiefRaider>());

    protected override IReadOnlyList<(MonsterModel, string?)> GenerateMonsters()
    {
        var list = new List<(MonsterModel, string?)>();
        var raiderPool = RaiderPool;

        // 先加劫掠者（让 ThiefRaider 能给他们上虚弱）
        var picked = new HashSet<MonsterModel>();
        for (var i = 0; i < 3; i++)
        {
            var candidates = raiderPool.Where(r => !picked.Contains(r)).ToList();
            var raider = candidates[Rng.NextInt(candidates.Count)];
            picked.Add(raider);
            list.Add((raider.ToMutable(), $"raider_{i + 1}"));
        }

        // ThiefRaider 最后加
        list.Add((ModelDb.Monster<ThiefRaider>().ToMutable(), "thief_raider"));

        return list;
    }
}
