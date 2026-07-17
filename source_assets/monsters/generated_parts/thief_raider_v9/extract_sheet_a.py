#!/usr/bin/env python3
"""Extract and classify the first v9 image-generated donor sheet.

The generated pixels are donor material for hidden joint extensions only.  The
visible bind pose remains owned by ``00_reference/current_master.png``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "01_generated_sheets/sheet_a_core_alpha.png"
OUT = ROOT / "02_extracted_donors/sheet_a"
MANIFEST = ROOT / "02_extracted_donors/sheet_a.manifest.json"
CONTACT = ROOT / "02_extracted_donors/sheet_a.contact.png"


# Centers are in the 1405x1119 generated sheet.  The two eyes are merged into
# one logical glow attachment after component extraction.
EXPECTED = {
    "head_scarf_composite": (246, 237),
    "torso_costume_composite": (666, 249),
    "far_shoulder_plate": (1236, 232),
    "near_shoulder_plate": (995, 235),
    "scarf_front": (1121, 556),
    "pelvis_skirt": (243, 585),
    "belt_and_pouch": (756, 625),
    "sack_and_strap_composite": (1154, 909),
    "near_upper_arm": (227, 888),
    "far_upper_arm": (668, 896),
}

CLASSIFICATION = {
    "eye_glow": ("candidate", []),
    "head_scarf_composite": (
        "needs_local_split",
        ["front scarf is fused to the hooded head"],
    ),
    "torso_costume_composite": (
        "rejected_visible_source",
        [
            "scarf, harness, belts and rear cloth are fused to the torso",
            "both arm interfaces are visibly hollow sockets",
        ],
    ),
    "far_shoulder_plate": ("candidate", []),
    "near_shoulder_plate": ("candidate", []),
    "scarf_front": ("candidate", []),
    "pelvis_skirt": ("candidate", []),
    "belt_and_pouch": ("candidate", []),
    "sack_and_strap_composite": (
        "needs_local_split",
        ["sack and strap are fused; independent inertia controls need two pieces"],
    ),
    "near_upper_arm": ("candidate_joint_review", []),
    "far_upper_arm": ("candidate_joint_review", []),
}


def _components(alpha: np.ndarray) -> list[dict[str, object]]:
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        (alpha > 32).astype(np.uint8), connectivity=8
    )
    found: list[dict[str, object]] = []
    for label in range(1, count):
        x, y, width, height, area = map(int, stats[label])
        if area < 50:
            continue
        found.append(
            {
                "label": label,
                "bbox": [x, y, width, height],
                "area": area,
                "center": [float(centroids[label][0]), float(centroids[label][1])],
                "mask": labels == label,
            }
        )
    return found


def _crop(rgba: np.ndarray, mask: np.ndarray, padding: int = 8) -> tuple[np.ndarray, list[int]]:
    ys, xs = np.where(mask)
    if not len(xs):
        raise RuntimeError("empty donor mask")
    x0 = max(0, int(xs.min()) - padding)
    y0 = max(0, int(ys.min()) - padding)
    x1 = min(rgba.shape[1], int(xs.max()) + padding + 1)
    y1 = min(rgba.shape[0], int(ys.max()) + padding + 1)
    result = rgba[y0:y1, x0:x1].copy()
    local_mask = mask[y0:y1, x0:x1]
    result[~local_mask] = (0, 0, 0, 0)
    return result, [x0, y0, x1 - x0, y1 - y0]


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def main() -> None:
    rgba = np.asarray(Image.open(SOURCE).convert("RGBA"), dtype=np.uint8)
    found = _components(rgba[:, :, 3])
    if len(found) != 12:
        raise RuntimeError(f"expected 12 sheet components, found {len(found)}")

    eye_components = [item for item in found if int(item["area"]) < 1000]
    if len(eye_components) != 2:
        raise RuntimeError(f"expected two eye components, found {len(eye_components)}")
    eye_mask = np.logical_or(eye_components[0]["mask"], eye_components[1]["mask"])
    remaining = [item for item in found if item not in eye_components]

    assignments: dict[str, dict[str, object]] = {}
    for semantic, target in EXPECTED.items():
        best = min(
            remaining,
            key=lambda item: math.hypot(
                float(item["center"][0]) - target[0],
                float(item["center"][1]) - target[1],
            ),
        )
        distance = math.hypot(
            float(best["center"][0]) - target[0],
            float(best["center"][1]) - target[1],
        )
        if distance > 24:
            raise RuntimeError(f"{semantic}: closest component is {distance:.1f}px away")
        assignments[semantic] = best
        remaining.remove(best)
    if remaining:
        raise RuntimeError(f"unassigned generated components: {len(remaining)}")

    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.png"):
        stale.unlink()

    ordered = ["eye_glow", *EXPECTED]
    records: list[dict[str, object]] = []
    for index, semantic in enumerate(ordered):
        if semantic == "eye_glow":
            mask = eye_mask
            center = [
                float(np.where(mask)[1].mean()),
                float(np.where(mask)[0].mean()),
            ]
            area = int(mask.sum())
        else:
            item = assignments[semantic]
            mask = item["mask"]
            center = list(item["center"])
            area = int(item["area"])
        crop, bbox = _crop(rgba, mask)
        filename = f"{index:02d}_{semantic}.png"
        Image.fromarray(crop, "RGBA").save(OUT / filename)
        status, warnings = CLASSIFICATION[semantic]
        records.append(
            {
                "index": index,
                "semantic": semantic,
                "file": f"sheet_a/{filename}",
                "source_bbox": bbox,
                "source_center": center,
                "alpha_area": area,
                "status": status,
                "warnings": warnings,
                "allowed_use": "hidden_overlap_donor_only",
            }
        )

    tile_w, tile_h = 310, 255
    columns = 4
    rows = math.ceil(len(records) / columns)
    contact = Image.new("RGB", (columns * tile_w, rows * tile_h), (30, 33, 39))
    draw = ImageDraw.Draw(contact)
    label_font = _font(17)
    state_font = _font(14)
    for record in records:
        donor = Image.open(ROOT / "02_extracted_donors" / record["file"]).convert("RGBA")
        donor.thumbnail((tile_w - 24, tile_h - 65), Image.Resampling.LANCZOS)
        col = int(record["index"]) % columns
        row = int(record["index"]) // columns
        x = col * tile_w + (tile_w - donor.width) // 2
        y = row * tile_h + 54 + (tile_h - 58 - donor.height) // 2
        contact.paste(donor, (x, y), donor)
        left = col * tile_w + 8
        top = row * tile_h + 7
        draw.text((left, top), str(record["semantic"]), fill=(240, 240, 240), font=label_font)
        status = str(record["status"])
        color = (92, 224, 145) if status.startswith("candidate") else (245, 184, 78)
        if status.startswith("rejected"):
            color = (244, 92, 92)
        draw.text((left, top + 23), status, fill=color, font=state_font)
    contact.save(CONTACT)

    manifest = {
        "schema_version": 1,
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "component_count": 12,
        "logical_part_count": len(records),
        "identity_source": "00_reference/current_master.png",
        "policy": "donor pixels never replace visible bind-pose master pixels",
        "status": "partially_salvageable_not_bind_ready",
        "parts": records,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        "THIEF_V9_SHEET_A_EXTRACT_PASS "
        f"components={len(found)} logical_parts={len(records)}"
    )


if __name__ == "__main__":
    main()
