#!/usr/bin/env python3
"""Assemble generated semantic accessories on the continuous v03 underbody."""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
PARTS = HERE / "02_semantic_parts" / "semantic_parts_v01"
UNDERBODY = HERE / "02_semantic_parts" / "underbody_context_v03" / "underbody_context_candidate_v03_alpha.png"
MASTER = HERE / "00_reference" / "locked_master.png"
OUT = HERE / "03_bind_review" / "accessory_layout_v04"
WIDTH, HEIGHT = 1536, 1024

PLACEMENTS = {
    "cape_far": {"file": "24_cape_tail_far.png", "anchor": (24, 18), "target": (850, 310), "angle": -7.0, "scale": 0.95},
    "cape_near": {"file": "23_cape_tail_near.png", "anchor": (30, 18), "target": (900, 345), "angle": -1.0, "scale": 1.02},
    "loot_sack": {"file": "18_loot_sack.png", "anchor": (118, 22), "target": (1030, 300), "angle": 3.0, "scale": 1.00},
    "sack_rope": {"file": "21_sack_rope.png", "anchor": (95, 20), "target": (900, 265), "angle": -18.0, "scale": 0.58},
    "dagger": {"file": "28_dagger.png", "anchor": (174, 44), "target": (444, 728), "angle": 7.0, "scale": 1.02},
    "scarf": {"file": "03_scarf_tube_front.png", "anchor": (101, 78), "target": (642, 416), "angle": -4.0, "scale": 0.90},
    "shoulder_far": {"file": "06_shoulder_plate_far.png", "anchor": (72, 58), "target": (850, 326), "angle": 23.0, "scale": 0.82},
    "shoulder_near": {"file": "07_shoulder_plate_near.png", "anchor": (68, 58), "target": (606, 440), "angle": 18.0, "scale": 0.74},
    "forearm_near": {"file": "14_forearm_plate_near.png", "anchor": (43, 61), "target": (525, 603), "angle": 36.0, "scale": 0.82},
    "forearm_far": {"file": "15_forearm_plate_far.png", "anchor": (43, 61), "target": (922, 433), "angle": 56.0, "scale": 0.78},
    "belt": {"file": "22_belt.png", "anchor": (100, 70), "target": (792, 598), "angle": 0.0, "scale": 1.02},
    "pouch": {"file": "20_pouch.png", "anchor": (68, 67), "target": (908, 603), "angle": 2.0, "scale": 0.82},
}

BACKGROUND_ORDER = ["cape_far", "loot_sack", "cape_near", "scarf_back", "belt_back", "dagger"]
FOREGROUND_ORDER = ["belt_front", "pouch", "sack_rope", "shoulder_far", "shoulder_near", "forearm_far", "forearm_near", "far_hand_retop", "scarf_front"]


def matrix_for(spec: dict) -> np.ndarray:
    ax, ay = spec["anchor"]
    tx, ty = spec["target"]
    angle = math.radians(spec["angle"])
    scale = float(spec["scale"])
    c, s = math.cos(angle) * scale, math.sin(angle) * scale
    return np.asarray([[c, -s, tx - c * ax + s * ay], [s, c, ty - s * ax - c * ay]], dtype=np.float32)


def warp(source: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    value = source.astype(np.float32)
    value[:, :, :3] *= value[:, :, 3:4] / 255.0
    result = cv2.warpAffine(value, matrix, (WIDTH, HEIGHT), cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    alpha = np.clip(result[:, :, 3], 0.0, 255.0)
    output = np.zeros_like(result, dtype=np.uint8)
    keep = alpha >= 1.0
    safe = np.maximum(alpha, 1.0)
    rgb = np.clip(result[:, :, :3] * (255.0 / safe[:, :, None]), 0.0, 255.0)
    output[:, :, :3][keep] = np.round(rgb[keep]).astype(np.uint8)
    output[:, :, 3][keep] = np.round(alpha[keep]).astype(np.uint8)
    return output


def alpha_over(bottom: np.ndarray, top: np.ndarray) -> np.ndarray:
    image = Image.fromarray(bottom, "RGBA")
    image.alpha_composite(Image.fromarray(top, "RGBA"))
    return np.asarray(image, dtype=np.uint8)


def split_horizontal(source: np.ndarray, split_y: int, overlap: int = 8) -> tuple[np.ndarray, np.ndarray]:
    back = source.copy()
    front = source.copy()
    yy = np.arange(source.shape[0])[:, None]
    back[np.broadcast_to(yy > split_y + overlap, source.shape[:2])] = 0
    front[np.broadcast_to(yy < split_y - overlap, source.shape[:2])] = 0
    return back, front


def load_layers() -> tuple[dict[str, np.ndarray], dict[str, dict]]:
    raw = {name: np.asarray(Image.open(PARTS / spec["file"]).convert("RGBA"), dtype=np.uint8) for name, spec in PLACEMENTS.items()}
    layers: dict[str, np.ndarray] = {}
    specs: dict[str, dict] = {}
    for name, source in raw.items():
        if name == "scarf":
            back, front = split_horizontal(source, 76, 10)
            layers["scarf_back"], layers["scarf_front"] = back, front
            specs["scarf_back"] = specs["scarf_front"] = PLACEMENTS[name]
        elif name == "belt":
            back, front = split_horizontal(source, 62, 8)
            layers["belt_back"], layers["belt_front"] = back, front
            specs["belt_back"] = specs["belt_front"] = PLACEMENTS[name]
        else:
            layers[name] = source
            specs[name] = PLACEMENTS[name]
    return layers, specs


def render() -> tuple[np.ndarray, dict[str, np.ndarray]]:
    base = np.asarray(Image.open(UNDERBODY).convert("RGBA"), dtype=np.uint8)
    layers, specs = load_layers()
    warped = {name: warp(source, matrix_for(specs[name])) for name, source in layers.items()}
    # Repaint the generated empty grip above the rope so the fingers visibly
    # wrap around it instead of the rope being pasted over the hand.
    hand_crop = np.asarray(Image.open(HERE / "02_semantic_parts" / "underbody_context_v03" / "segmentation_v01" / "08_far_hand_visible.png").convert("RGBA"), dtype=np.uint8)
    far_hand_retop = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    far_hand_retop[366:535, 724:888] = hand_crop
    warped["far_hand_retop"] = far_hand_retop
    result = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    for name in BACKGROUND_ORDER:
        result = alpha_over(result, warped[name])
    result = alpha_over(result, base)
    for name in FOREGROUND_ORDER:
        result = alpha_over(result, warped[name])
    return result, warped


def make_contact(composite: np.ndarray, warped: dict[str, np.ndarray]) -> None:
    master = Image.open(MASTER).convert("RGBA")
    underbody = Image.open(UNDERBODY).convert("RGBA")
    panels = [("LOCKED MASTER / IDENTITY", master), ("V03 CONTINUOUS UNDERBODY", underbody), ("V04 GENERATED ACCESSORY ASSEMBLY", Image.fromarray(composite, "RGBA"))]
    sheet = Image.new("RGBA", (1800, 720), (26, 30, 38, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (label, image) in enumerate(panels):
        x = index * 600
        draw.text((x + 12, 10), label, fill=(244, 246, 250, 255), font=font)
        bbox = image.getchannel("A").getbbox()
        if bbox:
            image = image.crop(bbox)
        scale = min(550 / max(1, image.width), 620 / max(1, image.height))
        image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
        sheet.alpha_composite(image, (x + (600 - image.width) // 2, 58 + (620 - image.height) // 2))
    sheet.convert("RGB").save(OUT / "accessory_bind_contact.jpg", quality=96)

    debug = Image.fromarray(composite, "RGBA")
    d = ImageDraw.Draw(debug)
    for name, spec in PLACEMENTS.items():
        x, y = spec["target"]
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(255, 50, 50, 255), outline=(255, 255, 255, 255), width=2)
        d.text((x + 8, y - 7), name, fill=(255, 255, 255, 255), font=font)
    debug.save(OUT / "accessory_anchor_debug.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    composite, warped = render()
    Image.fromarray(composite, "RGBA").save(OUT / "accessory_bind.png")
    for name, layer in warped.items():
        Image.fromarray(layer, "RGBA").save(OUT / f"layer_{name}.png")
    make_contact(composite, warped)
    report = {
        "schema_version": 1,
        "status": "accessory_bind_visual_review_required",
        "placements": PLACEMENTS,
        "background_order": BACKGROUND_ORDER,
        "foreground_order": FOREGROUND_ORDER,
        "shipping_allowed": False,
        "steam_install_allowed": False,
        "next_gate": "placement_scale_draw_order_review",
    }
    (OUT / "layout_review.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
