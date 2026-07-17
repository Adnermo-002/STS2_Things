#!/usr/bin/env python3
"""Extract and name the clean v8 image-generation donor sheet.

These files are donor geometry for hidden joint overlap and style reference.
They are not automatically approved as visible bind-pose pixels.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "02_part_sources/parts_sheet_candidate_01_revision_alpha.png"
OUT = ROOT / "03_clean_parts/generated_donor_parts"
MANIFEST = ROOT / "03_clean_parts/generated_donor_parts.json"
CONTACT = ROOT / "03_clean_parts/generated_donor_parts_contact.png"

# Expected centers are deliberately recorded in sheet pixels. Matching by center
# avoids depending on OpenCV component label order while still failing loudly if
# image generation changes the layout.
EXPECTED = {
    "hooded_head": (158, 149),
    "torso_core": (519, 156),
    "pelvis_coat": (789, 160),
    "belt_pouch": (1052, 160),
    "near_upper_arm": (149, 411),
    "near_forearm_hand_donor": (331, 427),
    "far_upper_arm": (561, 424),
    "far_forearm": (754, 437),
    "far_hand": (916, 476),
    "near_shoulder_plate": (1099, 357),
    "far_shoulder_plate": (1098, 491),
    "dagger": (97, 700),
    "near_thigh": (279, 696),
    "near_shin": (488, 699),
    "near_boot": (642, 716),
    "far_thigh": (837, 701),
    "far_shin": (984, 702),
    "far_boot": (1127, 733),
    "scarf_front": (159, 905),
    "scarf_rear": (409, 939),
    "cape_upper": (669, 991),
    "cape_middle": (933, 1030),
    "cape_tail": (1140, 1040),
    "loot_sack": (145, 1103),
    "sack_knot": (368, 1124),
    "sack_strap": (590, 1158),
}


def components(alpha: np.ndarray) -> list[dict[str, object]]:
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        (alpha > 32).astype(np.uint8), connectivity=8
    )
    result: list[dict[str, object]] = []
    for label in range(1, count):
        x, y, width, height, area = map(int, stats[label])
        if area < 30:
            continue
        result.append(
            {
                "label": label,
                "bbox": [x, y, width, height],
                "area": area,
                "center": [float(centroids[label][0]), float(centroids[label][1])],
                "mask": labels == label,
            }
        )
    return result


def crop_masked(
    rgba: np.ndarray, mask: np.ndarray, padding: int = 6
) -> tuple[np.ndarray, list[int]]:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise RuntimeError("empty component mask")
    x0 = max(0, int(xs.min()) - padding)
    y0 = max(0, int(ys.min()) - padding)
    x1 = min(rgba.shape[1], int(xs.max()) + 1 + padding)
    y1 = min(rgba.shape[0], int(ys.max()) + 1 + padding)
    crop = rgba[y0:y1, x0:x1].copy()
    local = mask[y0:y1, x0:x1]
    crop[~local] = (0, 0, 0, 0)
    return crop, [x0, y0, x1 - x0, y1 - y0]


def main() -> None:
    rgba = np.array(Image.open(SOURCE).convert("RGBA"))
    found = components(rgba[:, :, 3])
    if len(found) != 28:
        raise RuntimeError(f"expected 28 connected components, found {len(found)}")

    eyes = sorted((part for part in found if int(part["area"]) < 1000), key=lambda p: p["center"][0])
    if len(eyes) != 2:
        raise RuntimeError(f"expected two eye components, found {len(eyes)}")
    eye_mask = np.logical_or(eyes[0]["mask"], eyes[1]["mask"])
    remaining = [part for part in found if part not in eyes]

    assignments: dict[str, dict[str, object]] = {}
    for semantic, target in EXPECTED.items():
        if not remaining:
            raise RuntimeError(f"no component left for {semantic}")
        best = min(
            remaining,
            key=lambda part: math.hypot(
                float(part["center"][0]) - target[0],
                float(part["center"][1]) - target[1],
            ),
        )
        distance = math.hypot(
            float(best["center"][0]) - target[0],
            float(best["center"][1]) - target[1],
        )
        if distance > 30:
            raise RuntimeError(f"{semantic}: nearest component is {distance:.1f}px from expected center")
        assignments[semantic] = best
        remaining.remove(best)
    if remaining:
        raise RuntimeError(f"unassigned components: {len(remaining)}")

    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.png"):
        stale.unlink()

    records: list[dict[str, object]] = []
    ordered = ["eye_glow", *EXPECTED]
    for index, semantic in enumerate(ordered):
        if semantic == "eye_glow":
            mask = eye_mask
            source_area = int(mask.sum())
            source_center = [
                float(np.where(mask)[1].mean()),
                float(np.where(mask)[0].mean()),
            ]
        else:
            item = assignments[semantic]
            mask = item["mask"]
            source_area = int(item["area"])
            source_center = list(item["center"])
        crop, bbox = crop_masked(rgba, mask)
        filename = f"{index:02d}_{semantic}.png"
        Image.fromarray(crop, "RGBA").save(OUT / filename)
        records.append(
            {
                "index": index,
                "semantic": semantic,
                "file": f"generated_donor_parts/{filename}",
                "source_bbox": bbox,
                "source_center": source_center,
                "alpha_area": source_area,
                "approval": "donor_only_requires_joint_review",
            }
        )

    # Compact contact sheet for visual inspection. It intentionally uses a
    # checker background so holes and accidental green fringe remain visible.
    thumb_w, thumb_h = 250, 210
    cols = 5
    rows = math.ceil(len(records) / cols)
    canvas = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (36, 40, 47))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for record in records:
        image = Image.open(ROOT / "03_clean_parts" / record["file"]).convert("RGBA")
        image.thumbnail((thumb_w - 24, thumb_h - 48), Image.Resampling.LANCZOS)
        col = int(record["index"]) % cols
        row = int(record["index"]) // cols
        x = col * thumb_w + (thumb_w - image.width) // 2
        y = row * thumb_h + 30 + (thumb_h - 42 - image.height) // 2
        canvas.paste(image, (x, y), image)
        draw.text((col * thumb_w + 8, row * thumb_h + 6), str(record["semantic"]), fill=(235, 235, 235), font=font)
    canvas.save(CONTACT)

    manifest = {
        "schema_version": 1,
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "component_count": 28,
        "logical_part_count": len(records),
        "unmanifested_png_count": 0,
        "status": "generated_donor_only_not_bind_approved",
        "parts": records,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"THIEF_V8_DONOR_EXTRACT_PASS logical_parts={len(records)} components=28")


if __name__ == "__main__":
    main()
