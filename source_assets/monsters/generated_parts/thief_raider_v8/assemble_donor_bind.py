#!/usr/bin/env python3
"""Assemble the v8 image-generated semantic parts into a clean bind candidate.

This is the direct image-to-image cutout route requested by the user. It does
not use master ownership fragments. The coherent master is a pose/style guide;
all assembled pixels come from the generated semantic donor sheet.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
MASTER = ROOT / "01_master_candidates/candidate_01_alpha.png"
DONOR_MANIFEST = ROOT / "03_clean_parts/generated_donor_parts.json"
CORE_MANIFEST = ROOT / "03_clean_parts/core_replacements.json"
OUT = ROOT / "03_clean_parts/donor_bind_candidate_01.png"
COMPARE = ROOT / "03_clean_parts/donor_bind_candidate_01_compare.png"
REPORT = ROOT / "03_clean_parts/donor_bind_candidate_01.json"
RIG_PARTS = ROOT / "04_rig/parts_bind"
RIG_MANIFEST = ROOT / "04_rig/donor_bind_parts.json"
CANVAS = (1254, 1254)

# back-to-front: (semantic, center x/y, uniform scale, PIL rotation degrees)
PLACEMENTS = (
    ("cape_middle", (920, 585), 0.78, -9.0),
    ("cape_upper", (845, 540), 0.92, -10.0),
    ("sack_strap", (735, 420), 1.00, -18.0),
    ("loot_sack", (875, 425), 1.10, 0.0),
    ("sack_knot", (865, 330), 0.80, 0.0),
    ("far_boot", (905, 935), 1.15, 4.0),
    ("far_shin", (855, 835), 0.92, 22.0),
    ("far_thigh", (775, 745), 1.05, 18.0),
    ("near_boot", (535, 935), 1.18, -2.0),
    ("near_shin", (535, 835), 0.92, -3.0),
    ("near_thigh", (530, 735), 1.06, -8.0),
    ("pelvis_three_quarter", (640, 720), 0.82, 3.0),
    ("torso_three_quarter", (625, 550), 0.80, 7.0),
    ("far_upper_arm", (780, 510), 0.98, 18.0),
    ("near_upper_arm", (430, 590), 0.95, -24.0),
    ("hooded_head", (495, 355), 1.36, 12.0),
    ("scarf_front", (515, 480), 1.22, 4.0),
    ("far_shoulder_plate", (445, 525), 0.68, -10.0),
    ("near_shoulder_plate", (735, 425), 1.02, 8.0),
    ("near_forearm_hand_donor", (345, 710), 1.05, -30.0),
    ("far_forearm", (750, 570), 0.96, 55.0),
    ("dagger", (225, 835), 1.05, -68.0),
    ("far_hand", (645, 585), 0.94, 5.0),
    ("belt_pouch", (650, 650), 1.17, 1.0),
    ("eye_glow", (445, 410), 1.00, 2.0),
)


def load_parts() -> dict[str, Image.Image]:
    raw = json.loads(DONOR_MANIFEST.read_text(encoding="utf-8"))
    result: dict[str, Image.Image] = {}
    for record in raw["parts"]:
        result[record["semantic"]] = Image.open(
            ROOT / "03_clean_parts" / record["file"]
        ).convert("RGBA")
    core = json.loads(CORE_MANIFEST.read_text(encoding="utf-8"))
    for record in core["parts"]:
        result[record["semantic"]] = Image.open(
            ROOT / "03_clean_parts" / record["file"]
        ).convert("RGBA")
    return result


def transformed(image: Image.Image, scale: float, angle: float) -> Image.Image:
    width = max(1, round(image.width * scale))
    height = max(1, round(image.height * scale))
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    return image.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)


def main() -> None:
    parts = load_parts()
    missing = sorted({placement[0] for placement in PLACEMENTS} - set(parts))
    if missing:
        raise RuntimeError(f"missing donor parts: {missing}")

    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    RIG_PARTS.mkdir(parents=True, exist_ok=True)
    for stale in RIG_PARTS.glob("*.png"):
        stale.unlink()
    placement_records = []
    for index, (semantic, center, scale, angle) in enumerate(PLACEMENTS):
        image = transformed(parts[semantic], scale, angle)
        x = round(center[0] - image.width / 2)
        y = round(center[1] - image.height / 2)
        canvas.alpha_composite(image, (x, y))
        filename = f"{index:02d}_{semantic}.png"
        image.save(RIG_PARTS / filename)
        placement_records.append(
            {
                "index": index,
                "semantic": semantic,
                "center_xy": list(center),
                "scale": scale,
                "rotation_degrees": angle,
                "placed_bbox": [x, y, image.width, image.height],
                "texture": f"parts_bind/{filename}",
            }
        )
    canvas.save(OUT)

    master = Image.open(MASTER).convert("RGBA")
    bg = Image.new("RGB", (CANVAS[0] * 2, CANVAS[1] + 70), (31, 34, 40))
    left = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    left.alpha_composite(master)
    bg.paste(left, (0, 70), left)
    bg.paste(canvas, (CANVAS[0], 70), canvas)
    draw = ImageDraw.Draw(bg)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 30)
    except OSError:
        font = ImageFont.load_default()
    draw.text((24, 20), "V8 MASTER GUIDE", fill=(240, 240, 240), font=font)
    draw.text((CANVAS[0] + 24, 20), "V8 DIRECT GENERATED-PART ASSEMBLY", fill=(240, 240, 240), font=font)
    bg.save(COMPARE)

    master_rgba = np.array(master)
    bind_rgba = np.array(canvas)
    ma = master_rgba[:, :, 3] > 8
    ba = bind_rgba[:, :, 3] > 8
    intersection = int((ma & ba).sum())
    union = int((ma | ba).sum())
    report = {
        "schema_version": 1,
        "status": "direct_donor_bind_draft_requires_visual_review",
        "source": DONOR_MANIFEST.relative_to(ROOT).as_posix(),
        "placement_count": len(placement_records),
        "alpha_iou_to_master_guide": intersection / max(1, union),
        "alpha_area_ratio_to_master": int(ba.sum()) / max(1, int(ma.sum())),
        "placements": placement_records,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    RIG_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    RIG_MANIFEST.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "canvas": list(CANVAS),
                "bind_image": OUT.relative_to(ROOT).as_posix(),
                "part_count": len(placement_records),
                "status": "direct_generated_part_bind_draft",
                "parts": placement_records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"THIEF_V8_DONOR_BIND_DRAFT parts={len(placement_records)} "
        f"iou={report['alpha_iou_to_master_guide']:.4f} "
        f"area_ratio={report['alpha_area_ratio_to_master']:.4f}"
    )


if __name__ == "__main__":
    main()
