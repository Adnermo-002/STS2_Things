#!/usr/bin/env python3
"""Extract the four v8 three-quarter core replacement pieces."""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "02_part_sources/three_quarter_core_replacements_alpha.png"
OUT = ROOT / "03_clean_parts/core_replacements"
MANIFEST = ROOT / "03_clean_parts/core_replacements.json"
EXPECTED = {
    "torso_three_quarter": (350, 350),
    "rear_scarf_ribbon": (930, 430),
    "pelvis_three_quarter": (360, 870),
    "belt_three_quarter": (930, 900),
}


def main() -> None:
    rgba = np.array(Image.open(SOURCE).convert("RGBA"))
    mask = (rgba[:, :, 3] > 32).astype(np.uint8)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    components = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < 200:
            continue
        components.append(
            {
                "label": label,
                "area": area,
                "center": (float(centroids[label][0]), float(centroids[label][1])),
            }
        )
    if len(components) != 4:
        raise RuntimeError(f"expected four core components, found {len(components)}")

    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.png"):
        stale.unlink()
    remaining = list(components)
    records = []
    for index, (semantic, target) in enumerate(EXPECTED.items()):
        item = min(remaining, key=lambda c: math.hypot(c["center"][0] - target[0], c["center"][1] - target[1]))
        remaining.remove(item)
        component = labels == int(item["label"])
        ys, xs = np.where(component)
        pad = 6
        x0, y0 = max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad)
        x1 = min(rgba.shape[1], int(xs.max()) + 1 + pad)
        y1 = min(rgba.shape[0], int(ys.max()) + 1 + pad)
        crop = rgba[y0:y1, x0:x1].copy()
        local = component[y0:y1, x0:x1]
        crop[~local] = (0, 0, 0, 0)
        filename = f"{index:02d}_{semantic}.png"
        Image.fromarray(crop, "RGBA").save(OUT / filename)
        records.append(
            {
                "index": index,
                "semantic": semantic,
                "file": f"core_replacements/{filename}",
                "source_bbox": [x0, y0, x1 - x0, y1 - y0],
                "alpha_area": int(item["area"]),
            }
        )
    MANIFEST.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": SOURCE.relative_to(ROOT).as_posix(),
                "part_count": 4,
                "status": "three_quarter_core_draft",
                "parts": records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("THIEF_V8_CORE_REPLACEMENTS_PASS parts=4")


if __name__ == "__main__":
    main()
