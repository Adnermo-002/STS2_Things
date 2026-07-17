#!/usr/bin/env python3
"""Extract the 26 semantic Thief Raider v7 donor pieces from the chroma-key sheet.

The sheet is used only as a hidden-overlap/style donor. Visible bind pixels remain
owned by the coherent master once semantic masks are authored.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "parts_sheet_candidate_01_alpha.png"
OUT = ROOT / "donor_parts"
MANIFEST = ROOT / "donor_parts.generated.json"

SEMANTICS = [
    "hooded_head",
    "cape_upper",
    "cape_mid",
    "cape_tail",
    "scarf_front",
    "torso_core",
    "loot_sack",
    "pelvis_waist_cloth",
    "sack_knot",
    "sack_strap_free",
    "belt_and_pouch",
    "near_upper_arm",
    "far_upper_arm",
    "far_hand_strap_grip",
    "far_forearm",
    "near_forearm",
    "near_dagger_hand",
    "near_shoulder_plate",
    "far_shoulder_plate",
    "dagger",
    "far_thigh",
    "near_thigh",
    "far_shin",
    "near_shin",
    "far_boot",
    "near_boot",
]


def main() -> None:
    rgba = np.array(Image.open(SOURCE).convert("RGBA"))
    alpha = rgba[:, :, 3]
    mask = (alpha > 32).astype(np.uint8)
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask, 8)
    components = []
    for label in range(1, count):
        x, y, w, h, area = map(int, stats[label])
        if area >= 200:
            components.append((label, x, y, w, h, area, centers[label]))
    components.sort(key=lambda item: (item[2], item[1]))
    if len(components) != len(SEMANTICS):
        raise SystemExit(
            f"Expected {len(SEMANTICS)} semantic pieces, got {len(components)}"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    pad = 12
    height, width = alpha.shape
    for index, (component, x, y, w, h, area, center) in enumerate(components):
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(width, x + w + pad), min(height, y + h + pad)
        crop = rgba[y0:y1, x0:x1].copy()
        owned = labels[y0:y1, x0:x1] == component
        crop[~owned] = 0
        semantic = SEMANTICS[index]
        filename = f"{index:02d}_{semantic}.png"
        Image.fromarray(crop, "RGBA").save(OUT / filename)
        records.append(
            {
                "index": index,
                "semantic": semantic,
                "file": f"donor_parts/{filename}",
                "sheet_bbox_xywh": [x, y, w, h],
                "crop_origin_xy": [x0, y0],
                "alpha_area": area,
                "centroid_xy": [round(float(center[0]), 3), round(float(center[1]), 3)],
                "usage": "hidden_overlap_and_style_donor_only",
            }
        )

    manifest = {
        "schema_version": 1,
        "source": SOURCE.name,
        "component_count": len(records),
        "selection": "connected components sorted by top then left; semantic names manually verified",
        "bind_contract": "Visible bind pixels must come from master_candidate_01_alpha.png; these pieces fill hidden overlap only.",
        "parts": records,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"THIEF_V7_DONORS_PASS parts={len(records)} manifest={MANIFEST}")


if __name__ == "__main__":
    main()
