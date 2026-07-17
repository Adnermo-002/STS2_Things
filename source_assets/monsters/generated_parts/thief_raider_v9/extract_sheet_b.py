#!/usr/bin/env python3
"""Extract and strictly classify v9 Sheet B limb donors."""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "01_generated_sheets/sheet_b_limbs_alpha.png"
OUT = ROOT / "02_extracted_donors/sheet_b"
MANIFEST = ROOT / "02_extracted_donors/sheet_b.manifest.json"
CONTACT = ROOT / "02_extracted_donors/sheet_b.contact.png"

EXPECTED = {
    "near_upper_arm": (159, 220),
    "near_forearm": (392, 230),
    "near_dagger_hand": (618, 254),
    "far_upper_arm": (913, 233),
    "far_forearm": (1167, 230),
    "far_strap_hand": (1400, 238),
    "near_shin": (249, 576),
    "near_thigh": (514, 553),
    "far_thigh": (928, 548),
    "far_shin": (1252, 574),
    "near_boot": (253, 852),
    "dagger": (720, 839),
    "far_boot": (1284, 852),
}

CLASSIFICATION = {
    "near_upper_arm": (
        "rejected_open_socket",
        ["distal end is a visible hollow sleeve tube"],
    ),
    "near_forearm": (
        "rejected_open_socket",
        ["wrist end is a visible hollow cuff/tube"],
    ),
    "near_dagger_hand": (
        "rejected_wrong_grip",
        ["closed fist does not preserve the reference dagger grip"],
    ),
    "far_upper_arm": (
        "rejected_open_socket",
        ["distal end is a visible hollow sleeve tube"],
    ),
    "far_forearm": (
        "rejected_open_socket",
        ["wrist end is a visible hollow cuff/tube"],
    ),
    "far_strap_hand": (
        "rejected_wrong_grip",
        ["closed fist does not preserve the reference strap grip"],
    ),
    "near_shin": (
        "donor_only_joint_review",
        ["may supply hidden knee/ankle fill; visible master pixels must cover it"],
    ),
    "near_thigh": (
        "donor_only_joint_review",
        ["solid volume is usable only beneath current-master visible pixels"],
    ),
    "far_thigh": (
        "donor_only_joint_review",
        ["solid volume is usable only beneath current-master visible pixels"],
    ),
    "far_shin": (
        "donor_only_joint_review",
        ["may supply hidden knee/ankle fill; visible master pixels must cover it"],
    ),
    "near_boot": (
        "rejected_open_boot",
        ["boot shaft is an explicit hollow opening"],
    ),
    "dagger": (
        "donor_only_identity_review",
        ["geometry is plausible but current-master blade remains the visible source"],
    ),
    "far_boot": (
        "rejected_open_boot",
        ["boot shaft is an explicit hollow opening"],
    ),
}


def _components(alpha: np.ndarray) -> list[dict[str, object]]:
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        (alpha > 32).astype(np.uint8), 8
    )
    found = []
    for label in range(1, count):
        x, y, width, height, area = map(int, stats[label])
        if area < 50:
            continue
        found.append(
            {
                "bbox": [x, y, width, height],
                "area": area,
                "center": [float(centroids[label][0]), float(centroids[label][1])],
                "mask": labels == label,
            }
        )
    return found


def _crop(rgba: np.ndarray, mask: np.ndarray, padding: int = 8) -> tuple[np.ndarray, list[int]]:
    ys, xs = np.where(mask)
    x0 = max(0, int(xs.min()) - padding)
    y0 = max(0, int(ys.min()) - padding)
    x1 = min(rgba.shape[1], int(xs.max()) + padding + 1)
    y1 = min(rgba.shape[0], int(ys.max()) + padding + 1)
    crop = rgba[y0:y1, x0:x1].copy()
    local = mask[y0:y1, x0:x1]
    crop[~local] = (0, 0, 0, 0)
    return crop, [x0, y0, x1 - x0, y1 - y0]


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def main() -> None:
    rgba = np.asarray(Image.open(SOURCE).convert("RGBA"), dtype=np.uint8)
    remaining = _components(rgba[:, :, 3])
    if len(remaining) != 13:
        raise RuntimeError(f"expected 13 generated parts, found {len(remaining)}")

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
        if distance > 20:
            raise RuntimeError(f"{semantic}: nearest component is {distance:.1f}px away")
        assignments[semantic] = best
        remaining.remove(best)
    if remaining:
        raise RuntimeError(f"unassigned components: {len(remaining)}")

    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.png"):
        stale.unlink()
    records = []
    for index, semantic in enumerate(EXPECTED):
        item = assignments[semantic]
        crop, bbox = _crop(rgba, item["mask"])
        filename = f"{index:02d}_{semantic}.png"
        Image.fromarray(crop, "RGBA").save(OUT / filename)
        status, warnings = CLASSIFICATION[semantic]
        records.append(
            {
                "index": index,
                "semantic": semantic,
                "file": f"{OUT.name}/{filename}",
                "source_bbox": bbox,
                "source_center": item["center"],
                "alpha_area": int(item["area"]),
                "status": status,
                "warnings": warnings,
                "allowed_use": (
                    "none" if status.startswith("rejected")
                    else "hidden_overlap_donor_only"
                ),
            }
        )

    tile_w, tile_h, cols = 300, 255, 4
    rows = math.ceil(len(records) / cols)
    contact = Image.new("RGB", (cols * tile_w, rows * tile_h), (30, 33, 39))
    draw = ImageDraw.Draw(contact)
    label_font, state_font = _font(17), _font(14)
    for record in records:
        donor = Image.open(ROOT / "02_extracted_donors" / record["file"]).convert("RGBA")
        donor.thumbnail((tile_w - 24, tile_h - 65), Image.Resampling.LANCZOS)
        index = int(record["index"])
        col, row = index % cols, index // cols
        x = col * tile_w + (tile_w - donor.width) // 2
        y = row * tile_h + 54 + (tile_h - 58 - donor.height) // 2
        contact.paste(donor, (x, y), donor)
        left, top = col * tile_w + 8, row * tile_h + 7
        draw.text((left, top), str(record["semantic"]), fill=(240, 240, 240), font=label_font)
        status = str(record["status"])
        color = (245, 184, 78) if status.startswith("donor") else (244, 92, 92)
        draw.text((left, top + 23), status, fill=color, font=state_font)
    contact.save(CONTACT)

    rejected = sum(str(record["status"]).startswith("rejected") for record in records)
    donor_only = len(records) - rejected
    manifest = {
        "schema_version": 1,
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "component_count": 13,
        "logical_part_count": len(records),
        "identity_source": "00_reference/current_master.png",
        "status": "rejected_as_complete_sheet",
        "summary": {"donor_only": donor_only, "rejected": rejected},
        "parts": records,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        "THIEF_V9_SHEET_B_EXTRACT_PASS "
        f"components=13 donor_only={donor_only} rejected={rejected}"
    )


if __name__ == "__main__":
    main()
