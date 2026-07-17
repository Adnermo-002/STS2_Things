#!/usr/bin/env python3
"""Remove the generated chroma plate and audit every connected semantic part.

This script deliberately distinguishes a usable texture donor from a production
attachment.  A clean connected component is not automatically considered a
riggable body part.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "01_imagegen_boards" / "semantic_parts_candidate_v01_chroma.png"
OUT = HERE / "02_semantic_parts" / "semantic_parts_v01"

# OpenCV connected-component ids for this immutable generated plate.  Grouping
# the two eyes keeps them as one Spine attachment while retaining transparency.
PARTS = [
    {"name": "hooded_head", "ids": [1], "verdict": "donor", "note": "Identity-preserving hood; face cavity is intentional."},
    {"name": "torso_fused_arms", "ids": [2], "verdict": "reject", "note": "Both sleeves are fused into the torso and the neck is a hollow port."},
    {"name": "scarf_tube_back", "ids": [3], "verdict": "reject", "note": "Closed hollow tube instead of separate front/back cloth attachments."},
    {"name": "scarf_tube_front", "ids": [4], "verdict": "reject", "note": "Closed hollow tube instead of separate front/back cloth attachments."},
    {"name": "pelvis_tunic_ring", "ids": [5], "verdict": "inspect", "note": "Useful painted donor, but upper opening and hidden waist volume need replacement."},
    {"name": "eye_glow", "ids": [6, 7], "verdict": "donor", "note": "Two disconnected eye sprites grouped as one attachment."},
    {"name": "shoulder_plate_far", "ids": [8], "verdict": "donor", "note": "Clean solid armor attachment."},
    {"name": "shoulder_plate_near", "ids": [9], "verdict": "donor", "note": "Clean solid armor attachment."},
    {"name": "plain_arm_bent", "ids": [10], "verdict": "inspect", "note": "Potential cloth donor; joint ends and role remain ambiguous."},
    {"name": "arm_bracer_composite_a", "ids": [11], "verdict": "reject", "note": "Cloth, leather and plate are fused; no independent elbow/wrist chain."},
    {"name": "arm_bracer_composite_b", "ids": [12], "verdict": "reject", "note": "Cloth, leather and plate are fused; no independent elbow/wrist chain."},
    {"name": "arm_bracer_composite_c", "ids": [13], "verdict": "reject", "note": "Cloth, leather and plate are fused; no independent elbow/wrist chain."},
    {"name": "rope_hand_composite", "ids": [14], "verdict": "inspect", "note": "Good hand identity donor; rope and cuff must be separated before rigging."},
    {"name": "dagger_hand_composite", "ids": [15], "verdict": "reject", "note": "Hand, dagger and cuff are fused although a separate dagger exists."},
    {"name": "forearm_plate_near", "ids": [16], "verdict": "donor", "note": "Clean solid armor attachment."},
    {"name": "forearm_plate_far", "ids": [17], "verdict": "donor", "note": "Clean solid armor attachment."},
    {"name": "leg_boot_composite_a", "ids": [18], "verdict": "reject", "note": "Thigh, shin and boot form one rigid sticker."},
    {"name": "leg_composite_b", "ids": [19], "verdict": "reject", "note": "Thigh and shin are fused and the ankle end is ambiguous."},
    {"name": "loot_sack", "ids": [20], "verdict": "donor", "note": "Clean accessory attachment."},
    {"name": "leg_boot_composite_c", "ids": [21], "verdict": "reject", "note": "Lower leg and boot are fused; knee/ankle cannot articulate."},
    {"name": "pouch", "ids": [22], "verdict": "donor", "note": "Clean accessory attachment."},
    {"name": "sack_rope", "ids": [23], "verdict": "donor", "note": "Clean rope donor; split into front/back paths at rig stage."},
    {"name": "belt", "ids": [24], "verdict": "donor", "note": "Clean accessory attachment."},
    {"name": "cape_tail_near", "ids": [25], "verdict": "donor", "note": "Clean cloth attachment with intentional tears."},
    {"name": "cape_tail_far", "ids": [26], "verdict": "donor", "note": "Clean cloth attachment with intentional tears."},
    {"name": "boot_near", "ids": [27], "verdict": "donor", "note": "Solid boot; ankle underlap still needs checkerboard verification."},
    {"name": "boot_far", "ids": [28], "verdict": "donor", "note": "Solid boot; ankle underlap still needs checkerboard verification."},
    {"name": "sack_knot", "ids": [29], "verdict": "donor", "note": "Clean accessory attachment."},
    {"name": "dagger", "ids": [30], "verdict": "donor", "note": "Clean weapon attachment."},
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def chroma_to_rgba(source: np.ndarray) -> np.ndarray:
    """Key the green plate and remove green contamination from antialiased edges."""
    rgb = source[:, :, :3].astype(np.float32)
    dominance = rgb[:, :, 1] - np.maximum(rgb[:, :, 0], rgb[:, :, 2])
    alpha = np.clip((150.0 - dominance) / 110.0, 0.0, 1.0)
    alpha[alpha < 0.035] = 0.0
    alpha[alpha > 0.965] = 1.0

    background_pixels = rgb[dominance > 190.0]
    background = np.median(background_pixels, axis=0) if len(background_pixels) else np.asarray([4.0, 250.0, 4.0])
    safe = np.maximum(alpha[:, :, None], 0.035)
    foreground = (rgb - (1.0 - alpha[:, :, None]) * background[None, None, :]) / safe
    foreground = np.clip(foreground, 0.0, 255.0)

    output = np.zeros((*source.shape[:2], 4), dtype=np.uint8)
    keep = alpha > 0.0
    output[:, :, :3][keep] = np.round(foreground[keep]).astype(np.uint8)
    output[:, :, 3] = np.round(alpha * 255.0).astype(np.uint8)
    return output


def crop_group(rgba: np.ndarray, labels: np.ndarray, ids: list[int], padding: int = 10) -> tuple[np.ndarray, list[int]]:
    owned = np.isin(labels, ids)
    ys, xs = np.where(owned)
    if not len(xs):
        raise RuntimeError(f"component group missing: {ids}")
    x0, y0 = max(0, int(xs.min()) - padding), max(0, int(ys.min()) - padding)
    x1, y1 = min(rgba.shape[1], int(xs.max()) + 1 + padding), min(rgba.shape[0], int(ys.max()) + 1 + padding)
    crop = rgba[y0:y1, x0:x1].copy()
    owned_crop = owned[y0:y1, x0:x1]
    crop[~owned_crop] = 0
    return crop, [x0, y0, x1, y1]


def make_contact(records: list[dict], output: Path) -> None:
    cols, cell_w, cell_h = 5, 330, 260
    rows = (len(records) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (26, 30, 38, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    colors = {"donor": (64, 210, 120, 255), "inspect": (245, 184, 64, 255), "reject": (235, 76, 76, 255)}
    for index, record in enumerate(records):
        x, y = (index % cols) * cell_w, (index // cols) * cell_h
        color = colors[record["verdict"]]
        draw.rectangle((x + 4, y + 4, x + cell_w - 5, y + cell_h - 5), outline=color, width=3)
        draw.text((x + 12, y + 10), f'{index:02d} {record["name"]}', fill=(245, 247, 250, 255), font=font)
        draw.text((x + 12, y + 27), record["verdict"].upper(), fill=color, font=font)
        part = Image.open(OUT / record["file"]).convert("RGBA")
        scale = min(292 / max(1, part.width), 185 / max(1, part.height), 1.6)
        shown = part.resize((max(1, round(part.width * scale)), max(1, round(part.height * scale))), Image.Resampling.LANCZOS)
        sheet.alpha_composite(shown, (x + (cell_w - shown.width) // 2, y + 55 + (185 - shown.height) // 2))
    sheet.convert("RGB").save(output, quality=96)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source = np.asarray(Image.open(SOURCE).convert("RGBA"), dtype=np.uint8)
    keyed = chroma_to_rgba(source)
    Image.fromarray(keyed, "RGBA").save(OUT / "semantic_parts_candidate_v01_alpha.png")

    component_mask = (keyed[:, :, 3] > 24).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(component_mask, connectivity=8)
    significant = [i for i in range(1, count) if int(stats[i, cv2.CC_STAT_AREA]) >= 50]
    expected = sorted({component_id for part in PARTS for component_id in part["ids"]})
    if significant != expected:
        raise RuntimeError({"significant_components": significant, "expected": expected})

    records = []
    for index, spec in enumerate(PARTS):
        crop, bbox = crop_group(keyed, labels, spec["ids"])
        filename = f"{index:02d}_{spec['name']}.png"
        Image.fromarray(crop, "RGBA").save(OUT / filename)
        records.append({**spec, "file": filename, "source_bbox": bbox, "opaque_pixels": int((crop[:, :, 3] > 128).sum())})

    make_contact(records, OUT / "semantic_parts_contact.jpg")
    verdict_counts = {key: sum(record["verdict"] == key for record in records) for key in ("donor", "inspect", "reject")}
    report = {
        "schema_version": 1,
        "source": str(SOURCE.relative_to(HERE)).replace("\\", "/"),
        "source_sha256": sha256(SOURCE),
        "status": "donor_board_only_focused_regeneration_required",
        "verdict_counts": verdict_counts,
        "parts": records,
        "production_rig_allowed": False,
        "shipping_allowed": False,
        "steam_install_allowed": False,
        "next_gate": "focused_solid_torso_arm_leg_generation",
    }
    (OUT / "semantic_parts_review.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
