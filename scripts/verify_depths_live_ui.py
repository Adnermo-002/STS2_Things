"""Check captured native power hitboxes against the resting hand and end-turn UI.

Input comes from Workbench's actual scene tree, not source layout assumptions.
Only settled player-turn captures with no hovered/dragged card should be used.
"""
import argparse
import json
from pathlib import Path


def overlap_fraction(rect, other):
    x, y, w, h = rect
    ox, oy, ow, oh = other
    area = max(0, min(x + w, ox + ow) - max(x, ox)) * max(
        0, min(y + h, oy + oh) - max(y, oy)
    )
    return area / (w * h) if w > 0 and h > 0 else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captures", nargs="+", type=Path)
    args = parser.parse_args()
    failures = []
    count = 0
    for path in args.captures:
        capture = json.loads(path.read_text(encoding="utf-8-sig"))
        blockers = capture["cards"] + [capture["end_turn"]]
        for power in capture["powers"]:
            count += 1
            for blocker in blockers:
                fraction = overlap_fraction(power["rect"], blocker["rect"])
                if fraction > 0.1:
                    failures.append({"capture": str(path), "power": power["path"],
                                     "blocker": blocker["path"], "covered": round(fraction, 3)})
    print(json.dumps({"checked_power_hitboxes": count, "failures": failures}, indent=2))
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
