"""Detect detached painted pieces in the real Spine render probe (without VFX)."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frames", type=Path)
    args = parser.parse_args()
    files = sorted(args.frames.glob("*.png"))
    if not files:
        parser.error("no rendered frames found")
    report = json.loads((args.frames / "report.json").read_text(encoding="utf-8"))
    if report.get("key") != "origin_fogmog" or report.get("frames") != len(files):
        parser.error("incomplete or wrong-character render report")
    failures = []
    for file in files:
        image = cv2.imread(str(file))
        if image is None:
            parser.error(f"cannot read {file}")
        # The probe background/shadow is dark; all opaque painted limbs are brighter.
        # Small antialiased eye highlights are permitted, detached claws are not.
        mask = (image.max(axis=2) > 85).astype(np.uint8)
        _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        pieces = sorted(stats[1:], key=lambda row: -row[4])
        if not pieces or pieces[0][4] < 5000:
            parser.error(f"missing visible subject in {file.name}")
        detached = [row.tolist() for row in pieces[1:] if row[4] >= 64]
        if detached:
            failures.append((file.name, detached))
    for name, pieces in failures[:12]:
        print(f"DETACHED {name}: x,y,w,h,area={pieces}")
    print(f"FOGMOG_RENDER_{'FAIL' if failures else 'PASS'} "
          f"frames={len(files)} detached_frames={len(failures)}")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
