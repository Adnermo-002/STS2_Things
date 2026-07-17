#!/usr/bin/env python3
"""Key and audit the focused twelve-part image-generation pass."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from extract_semantic_parts_v01 import chroma_to_rgba, sha256


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "01_imagegen_boards" / "focused_body_parts_candidate_v02_chroma.png"
OUT = HERE / "02_semantic_parts" / "focused_body_parts_v02"

PARTS = [
    {"name": "torso_cloth", "id": 1, "verdict": "reject", "note": "Painted black neck and shoulder cavities; reads as an empty shirt."},
    {"name": "pelvis_tunic", "id": 4, "verdict": "reject", "note": "Painted black waist cavity; missing solid hidden torso/hip volume."},
    {"name": "near_upper_arm", "id": 2, "verdict": "reject", "note": "Large black sleeve port at elbow and capsule-like shoulder cap."},
    {"name": "far_upper_arm", "id": 3, "verdict": "reject", "note": "Large black sleeve port at elbow and capsule-like shoulder cap."},
    {"name": "near_forearm", "id": 5, "verdict": "reject", "note": "Large black sleeve port; both endpoints lack tapered underlap."},
    {"name": "far_forearm", "id": 6, "verdict": "reject", "note": "Large black sleeve port; both endpoints lack tapered underlap."},
    {"name": "near_empty_grip_hand", "id": 7, "verdict": "donor", "note": "Independent empty grip; perspective and palette are usable donors."},
    {"name": "far_empty_grip_hand", "id": 8, "verdict": "donor", "note": "Independent empty grip; perspective and palette are usable donors."},
    {"name": "near_thigh", "id": 9, "verdict": "reject", "note": "Pillow-like bent tube with no controlled hip/knee underlap."},
    {"name": "far_thigh", "id": 10, "verdict": "reject", "note": "Pillow-like bent tube with no controlled hip/knee underlap."},
    {"name": "near_shin", "id": 11, "verdict": "reject", "note": "Generic tapered tube; endpoints and silhouette do not match the crouched bind pose."},
    {"name": "far_shin", "id": 12, "verdict": "reject", "note": "Generic tapered tube; endpoints and silhouette do not match the crouched bind pose."},
]


def crop_component(rgba: np.ndarray, labels: np.ndarray, component_id: int, padding: int = 10) -> tuple[np.ndarray, list[int]]:
    owned = labels == component_id
    ys, xs = np.where(owned)
    if not len(xs):
        raise RuntimeError(component_id)
    x0, y0 = max(0, int(xs.min()) - padding), max(0, int(ys.min()) - padding)
    x1, y1 = min(rgba.shape[1], int(xs.max()) + 1 + padding), min(rgba.shape[0], int(ys.max()) + 1 + padding)
    crop = rgba[y0:y1, x0:x1].copy()
    own_crop = owned[y0:y1, x0:x1]
    crop[~own_crop] = 0
    return crop, [x0, y0, x1, y1]


def dark_cavity_pixels(crop: np.ndarray) -> int:
    rgb = crop[:, :, :3].astype(np.float32)
    alpha = crop[:, :, 3] > 128
    luminance = rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722
    # Body cloth is dark, so only count near-black pockets, not normal charcoal.
    return int(((luminance < 17.0) & alpha).sum())


def make_contact(records: list[dict]) -> None:
    cols, cell_w, cell_h = 4, 380, 330
    rows = 3
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (26, 30, 38, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    colors = {"donor": (64, 210, 120, 255), "reject": (235, 76, 76, 255)}
    for index, record in enumerate(records):
        x, y = (index % cols) * cell_w, (index // cols) * cell_h
        color = colors[record["verdict"]]
        draw.rectangle((x + 4, y + 4, x + cell_w - 5, y + cell_h - 5), outline=color, width=3)
        draw.text((x + 12, y + 10), f'{index:02d} {record["name"]}', fill=(245, 247, 250, 255), font=font)
        draw.text((x + 12, y + 28), f'{record["verdict"].upper()}  near-black={record["near_black_pixels"]}', fill=color, font=font)
        part = Image.open(OUT / record["file"]).convert("RGBA")
        scale = min(330 / max(1, part.width), 245 / max(1, part.height), 1.35)
        shown = part.resize((max(1, round(part.width * scale)), max(1, round(part.height * scale))), Image.Resampling.LANCZOS)
        sheet.alpha_composite(shown, (x + (cell_w - shown.width) // 2, y + 62 + (245 - shown.height) // 2))
    sheet.convert("RGB").save(OUT / "focused_body_parts_contact.jpg", quality=96)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source = np.asarray(Image.open(SOURCE).convert("RGBA"), dtype=np.uint8)
    keyed = chroma_to_rgba(source)
    Image.fromarray(keyed, "RGBA").save(OUT / "focused_body_parts_candidate_v02_alpha.png")
    mask = (keyed[:, :, 3] > 24).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    significant = [i for i in range(1, count) if int(stats[i, cv2.CC_STAT_AREA]) >= 100]
    if significant != list(range(1, 13)):
        raise RuntimeError(significant)

    records = []
    for index, spec in enumerate(PARTS):
        crop, bbox = crop_component(keyed, labels, spec["id"])
        filename = f"{index:02d}_{spec['name']}.png"
        Image.fromarray(crop, "RGBA").save(OUT / filename)
        records.append({**spec, "file": filename, "source_bbox": bbox, "near_black_pixels": dark_cavity_pixels(crop)})
    make_contact(records)
    report = {
        "schema_version": 1,
        "source_sha256": sha256(SOURCE),
        "status": "failed_body_part_visual_gate_hands_donor_only",
        "verdict_counts": {"donor": 2, "reject": 10},
        "parts": records,
        "production_rig_allowed": False,
        "shipping_allowed": False,
        "steam_install_allowed": False,
        "next_gate": "full_character_context_reveal_without_armor_then_semantic_masking",
    }
    (OUT / "focused_body_parts_review.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
