using MegaCrit.Sts2.Core.Map;

namespace STS2_Things.Map;

public sealed class CrossroadRecord
{
    public int Row { get; set; }
    public int Left { get; set; }
    public int Right { get; set; }
    public int FromColumn { get; set; } = -1;
    public ulong Payer { get; set; }
    public bool IsOpen => FromColumn == Left || FromColumn == Right;
    public MapCoord A => new(Left, Row);
    public MapCoord B => new(Right, Row);
    public MapCoord From => new(FromColumn, Row);
    public MapCoord To => new(FromColumn == Left ? Right : Left, Row);
    public bool Touches(MapCoord coord) => coord == A || coord == B;
    public MapCoord Other(MapCoord coord) => coord == A ? B : A;
}

public sealed class CrossroadActPlan
{
    public int Act { get; set; }
    public ulong Fingerprint { get; set; }
    public List<CrossroadRecord> Roads { get; set; } = [];
    public List<MapCoord> History { get; set; } = [];
}

public static class CrossroadPlan
{
    public const int Price = 50;
    public const int MaxRoads = 3;

    // Only forward edges participate: opening a side road never changes its ID.
    public static ulong Fingerprint(ActMap map)
    {
        ulong hash = 14695981039346656037UL;
        void Add(int value) { unchecked { hash = (hash ^ (uint)value) * 1099511628211UL; } }
        Add(map.GetColumnCount()); Add(map.GetRowCount());
        foreach (MapPoint point in map.GetAllMapPoints().OrderBy(p => p.coord.row).ThenBy(p => p.coord.col))
        {
            Add(point.coord.col); Add(point.coord.row); Add((int)point.PointType);
            foreach (MapPoint child in point.Children.Where(c => c.coord.row > point.coord.row).OrderBy(c => c.coord.row).ThenBy(c => c.coord.col))
            { Add(child.coord.col); Add(child.coord.row); }
            Add(-1);
        }
        return hash;
    }

    public static List<CrossroadRecord> Generate(ActMap map, ulong seed, int act)
    {
        var candidates = new List<(CrossroadRecord road, int score, ulong tie)>();
        int rows = map.GetRowCount();
        for (int row = 2; row < rows - 2; row++)
        {
            var points = map.GetPointsInRow(row).OrderBy(p => p.coord.col).ToArray();
            for (int i = 0; i + 1 < points.Length; i++)
            {
                MapPoint a = points[i], b = points[i + 1];
                if (!Suitable(a) || !Suitable(b) || a.PointType == b.PointType || b.coord.col - a.coord.col > 3 ||
                    a.Children.Contains(b) || b.Children.Contains(a)) continue;
                int score = Value(a) + Value(b);
                if (score == 0) continue;
                var road = new CrossroadRecord { Row = row, Left = a.coord.col, Right = b.coord.col };
                ulong tie = Mix(seed ^ ((ulong)(uint)act << 40) ^ ((ulong)(uint)row << 24) ^ ((ulong)(uint)a.coord.col << 12) ^ (uint)b.coord.col);
                candidates.Add((road, score, tie));
            }
        }
        var selected = new List<CrossroadRecord>();
        // Spread opportunities over the act instead of filling the treasure row.
        for (int band = 0; band < 3; band++)
        {
            var pick = candidates.Where(c => Math.Min(2, (c.road.Row - 2) * 3 / Math.Max(1, rows - 4)) == band &&
                    selected.All(r => Math.Abs(r.Row - c.road.Row) >= 2))
                .OrderByDescending(c => c.score).ThenBy(c => c.tie).FirstOrDefault();
            if (pick.road != null) selected.Add(pick.road);
        }
        foreach (var candidate in candidates.OrderByDescending(c => c.score).ThenBy(c => c.tie))
        {
            if (selected.Count == MaxRoads) break;
            if (selected.All(r => Math.Abs(r.Row - candidate.road.Row) >= 2)) selected.Add(candidate.road);
        }
        return selected.OrderBy(r => r.Row).ThenBy(r => r.Left).ToList();
    }

    public static bool Suitable(MapPoint point) => point.PointType is not (MapPointType.Unassigned or MapPointType.Boss or MapPointType.Ancient) &&
        point.parents.Count > 0 && point.Children.Any(c => c.coord.row > point.coord.row);

    private static int Value(MapPoint point) => point.PointType switch
    {
        MapPointType.RestSite or MapPointType.Shop or MapPointType.Treasure => 5,
        MapPointType.Unknown => 4,
        _ => point.Children.Any(c => c.coord.row == point.coord.row + 1 && c.PointType == MapPointType.Elite) ? 4 : 0,
    };

    private static ulong Mix(ulong value)
    {
        unchecked
        {
            value += 0x9e3779b97f4a7c15UL;
            value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9UL;
            value = (value ^ (value >> 27)) * 0x94d049bb133111ebUL;
            return value ^ (value >> 31);
        }
    }
}
