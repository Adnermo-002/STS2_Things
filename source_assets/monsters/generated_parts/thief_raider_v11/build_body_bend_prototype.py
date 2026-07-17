#!/usr/bin/env python3
"""Render full-character torso/pelvis hierarchy bend poses."""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
BASELINE = HERE / "00_reference" / "visible_baseline"
MANIFEST = BASELINE / "visible_baseline.manifest.json"
MASTER = HERE / "00_reference" / "locked_master.png"
TORSO_ROOT = HERE / "02_semantic_parts" / "context_reveals" / "torso_v01"
OUT = HERE / "03_bind_review" / "body_bend_v01"

SOURCE_WIDTH, SOURCE_HEIGHT = 534, 420
PAD_X, PAD_Y = 100, 50
WIDTH, HEIGHT = SOURCE_WIDTH + PAD_X * 2, SOURCE_HEIGHT + PAD_Y * 2
PIVOT = np.asarray([292.0 + PAD_X, 270.0 + PAD_Y], dtype=np.float32)

TORSO_GROUP = {
    "cape_back",
    "loot_sack",
    "bag_knot",
    "strap_back",
    "far_upper_arm",
    "far_forearm",
    "far_shoulder_plate",
    "torso_core",
    "scarf_back",
    "hooded_head",
    "eye_glow",
    "near_upper_arm",
    "near_forearm",
    "near_shoulder_plate",
    "dagger",
    "near_dagger_hand",
    "strap_front",
    "far_strap_hand",
    "scarf_front",
}

CASES = [
    {"name": "bind", "torso_deg": 0.0, "x": 0.0, "y": 0.0},
    {"name": "idle_inhale", "torso_deg": 0.45, "x": 0.0, "y": -0.5},
    {"name": "idle_exhale", "torso_deg": -0.35, "x": 0.0, "y": 0.35},
    {"name": "attack_windup", "torso_deg": 4.0, "x": 2.0, "y": -1.0},
    {"name": "attack_contact", "torso_deg": -7.0, "x": -4.0, "y": 1.0},
    {"name": "attack_recoil", "torso_deg": -2.5, "x": -1.0, "y": 0.5},
    {"name": "hurt_recoil", "torso_deg": 8.0, "x": 3.0, "y": 3.0},
]


def alpha_over(bottom: np.ndarray, top: np.ndarray) -> np.ndarray:
    image = Image.fromarray(bottom, "RGBA")
    image.alpha_composite(Image.fromarray(top, "RGBA"))
    return np.asarray(image, dtype=np.uint8)


def transform_matrix(angle_deg: float, x: float, y: float) -> np.ndarray:
    angle = math.radians(angle_deg)
    rotation = np.asarray([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]], dtype=np.float32)
    translation = PIVOT + np.asarray([x, y], dtype=np.float32) - rotation @ PIVOT
    return np.column_stack((rotation, translation)).astype(np.float32)


def warp(source: np.ndarray, case: dict) -> np.ndarray:
    if abs(case["torso_deg"]) < 1e-9 and abs(case["x"]) < 1e-9 and abs(case["y"]) < 1e-9:
        return source.copy()
    value = source.astype(np.float32)
    value[:, :, :3] *= value[:, :, 3:4] / 255.0
    posed = cv2.warpAffine(
        value,
        transform_matrix(case["torso_deg"], case["x"], case["y"]),
        (WIDTH, HEIGHT),
        cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )
    alpha = posed[:, :, 3]
    keep = alpha >= 16.0
    output = np.zeros(posed.shape, dtype=np.uint8)
    safe_alpha = np.maximum(alpha, 1.0)
    rgb = np.clip(posed[:, :, :3] * (255.0 / safe_alpha[:, :, None]), 0, 255)
    output[:, :, :3][keep] = np.round(rgb[keep]).astype(np.uint8)
    output[:, :, 3][keep] = np.clip(np.round(alpha[keep]), 0, 255).astype(np.uint8)
    return output


def padded(path: Path) -> np.ndarray:
    source = np.asarray(Image.open(path).convert("RGBA"), dtype=np.uint8)
    output = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    output[PAD_Y : PAD_Y + SOURCE_HEIGHT, PAD_X : PAD_X + SOURCE_WIDTH] = source
    return output


def load_layers() -> tuple[list[dict], dict[str, np.ndarray], dict[str, np.ndarray]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    parts = {}
    for record in manifest["parts"]:
        crop = np.asarray(Image.open(BASELINE / record["file"]).convert("RGBA"), dtype=np.uint8)
        canvas = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
        x, y, width, height = map(int, record["source_bbox"])
        canvas[y + PAD_Y : y + PAD_Y + height, x + PAD_X : x + PAD_X + width] = crop
        parts[record["semantic"]] = canvas
    replacements = {
        "torso_core": padded(TORSO_ROOT / "torso_core_attachment.png"),
        "pelvis_tunic": padded(TORSO_ROOT / "pelvis_tunic_attachment.png"),
        "torso_back": padded(TORSO_ROOT / "torso_core_underpaint_back.png"),
        "pelvis_back": padded(TORSO_ROOT / "pelvis_tunic_underpaint_back.png"),
    }
    return manifest["parts"], parts, replacements


def render(records: list[dict], parts: dict[str, np.ndarray], replacements: dict[str, np.ndarray], case: dict) -> np.ndarray:
    result = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    result = alpha_over(result, warp(replacements["torso_back"], case))
    result = alpha_over(result, replacements["pelvis_back"])
    for record in sorted(records, key=lambda item: (int(item["z"]), int(item["index"]))):
        semantic = record["semantic"]
        if semantic == "torso_core":
            layer = replacements["torso_core"]
        elif semantic == "pelvis_tunic":
            layer = replacements["pelvis_tunic"]
        else:
            layer = parts[semantic]
        if semantic in TORSO_GROUP:
            layer = warp(layer, case)
        result = alpha_over(result, layer)
    return result


def bounds(frame: np.ndarray) -> list[int]:
    ys, xs = np.where(frame[:, :, 3] > 16)
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def make_contact(frames: list[tuple[dict, np.ndarray]], output: Path) -> None:
    cols, rows = 4, 2
    cell_w, cell_h = 560, 500
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (27, 31, 39, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (case, frame) in enumerate(frames):
        x, y = (index % cols) * cell_w, (index // cols) * cell_h
        draw.text((x + 10, y + 8), case["name"], fill=(242, 244, 248, 255), font=font)
        draw.text(
            (x + 10, y + 24),
            f"torso {case['torso_deg']:+.2f} / x {case['x']:+.1f} / y {case['y']:+.1f}",
            fill=(155, 216, 240, 255),
            font=font,
        )
        shown = Image.fromarray(frame, "RGBA")
        bbox = shown.getchannel("A").getbbox()
        if bbox:
            shown = shown.crop(bbox)
        scale = min(530 / max(1, shown.width), 420 / max(1, shown.height))
        shown = shown.resize((max(1, round(shown.width * scale)), max(1, round(shown.height * scale))), Image.Resampling.LANCZOS)
        sheet.alpha_composite(shown, (x + (cell_w - shown.width) // 2, y + 55 + (420 - shown.height) // 2))
    sheet.convert("RGB").save(output, quality=95)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records, parts, replacements = load_layers()
    master = padded(MASTER)
    frames = []
    audits = []
    for case in CASES:
        frame = render(records, parts, replacements, case)
        Image.fromarray(frame, "RGBA").save(OUT / f"{case['name']}.png")
        mismatch = int(np.any(frame != master, axis=2).sum()) if case["name"] == "bind" else None
        audits.append({**case, "alpha_bounds": bounds(frame), "bind_mismatch_pixels": mismatch})
        frames.append((case, frame))
    make_contact(frames, OUT / "full_character_contact.jpg")
    report = {
        "schema_version": 1,
        "status": "full_character_body_bend_visual_review_required",
        "pivot_xy_source": [292.0, 270.0],
        "cases": audits,
        "feet_static": True,
        "bind_exact_rgba": audits[0]["bind_mismatch_pixels"] == 0,
        "shipping_allowed": False,
        "steam_install_allowed": False,
        "next_gate": "waist_seam_review_then_combine_with_arm_topology",
    }
    if not report["bind_exact_rgba"]:
        raise RuntimeError(report)
    (OUT / "audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
