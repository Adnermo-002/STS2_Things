#!/usr/bin/env python3
"""Render linked-cutout extreme-pose QA before Spine integration."""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "linked_parts.generated.json"
OUT = ROOT / "extreme_pose_qa"

PIVOTS = {
    "torso": (650, 680),
    "head": (530, 515),
    "near_upper": (445, 615),
    "near_forearm": (390, 700),
    "near_hand": (315, 815),
    "far_upper": (790, 475),
    "far_forearm": (820, 575),
    "far_hand": (705, 525),
    "near_thigh": (525, 705),
    "near_shin": (540, 855),
    "near_boot": (545, 925),
    "far_thigh": (800, 720),
    "far_shin": (865, 860),
    "far_boot": (915, 925),
    "sack": (820, 410),
}

PARENT = {
    "torso": None,
    "head": "torso",
    "near_upper": "torso",
    "near_forearm": "near_upper",
    "near_hand": "near_forearm",
    "far_upper": "torso",
    "far_forearm": "far_upper",
    "far_hand": "far_forearm",
    "near_thigh": None,
    "near_shin": "near_thigh",
    "near_boot": "near_shin",
    "far_thigh": None,
    "far_shin": "far_thigh",
    "far_boot": "far_shin",
    "sack": "torso",
}

PART_BONE = {
    "cape_back": None,
    "loot_sack": "sack",
    "sack_knot": "sack",
    "sack_strap": "torso",
    "body_underpaint": None,
    "far_thigh": "far_thigh",
    "far_shin": "far_shin",
    "far_boot": "far_boot",
    "far_upper_arm": "far_upper",
    "far_shoulder_plate": "far_upper",
    "far_forearm": "far_forearm",
    "torso_core": "torso",
    "pelvis_waist_cloth": None,
    "near_thigh": "near_thigh",
    "near_shin": "near_shin",
    "near_boot": "near_boot",
    "hooded_head": "head",
    "eye_glow": "head",
    "near_upper_arm": "near_upper",
    "near_shoulder_plate": "near_upper",
    "near_forearm": "near_forearm",
    "dagger": "near_hand",
    "near_dagger_hand": "near_hand",
    "belt_and_pouch": None,
    "far_hand_strap_grip": "far_hand",
    "scarf_front": "head",
}

POSES = {
    "bind": {},
    "arm_limits": {
        "near_upper": 26,
        "near_forearm": -42,
        "near_hand": 18,
        "far_upper": -16,
        "far_forearm": 34,
        "far_hand": -12,
    },
    "leg_limits": {
        "near_thigh": 14,
        "near_shin": -28,
        "near_boot": 18,
        "far_thigh": -12,
        "far_shin": 24,
        "far_boot": -14,
    },
    "attack_contact": {
        "torso": 1.5,
        "head": -4,
        "near_upper": 20,
        "near_forearm": 32,
        "near_hand": -12,
        "far_upper": -5,
        "far_forearm": 8,
        "near_thigh": -4,
        "near_shin": 8,
        "far_thigh": 5,
        "far_shin": -8,
        "sack": -5,
    },
    "hurt_short": {
        "torso": -1.5,
        "head": -3,
        "near_upper": -4,
        "near_forearm": 6,
        "far_upper": -4,
        "far_forearm": 6,
        "sack": 3,
    },
}


def rotation(pivot: tuple[float, float], degrees_clockwise: float) -> np.ndarray:
    x, y = pivot
    radians = math.radians(degrees_clockwise)
    c, s = math.cos(radians), math.sin(radians)
    # Image coordinates have +y downward, so this matrix visually rotates in
    # the conventional clockwise direction for positive degrees.
    return np.array(
        [[c, -s, x - c * x + s * y], [s, c, y - s * x - c * y], [0, 0, 1]],
        np.float64,
    )


def global_matrices(angles: dict[str, float]) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}

    def resolve(name: str) -> np.ndarray:
        if name in result:
            return result[name]
        parent = PARENT[name]
        parent_matrix = np.eye(3) if parent is None else resolve(parent)
        local = rotation(PIVOTS[name], angles.get(name, 0.0))
        result[name] = parent_matrix @ local
        return result[name]

    for bone in PARENT:
        resolve(bone)
    return result


def alpha_over(dst: np.ndarray, src: np.ndarray) -> None:
    sa = src[:, :, 3:4].astype(np.float32) / 255.0
    da = dst[:, :, 3:4].astype(np.float32) / 255.0
    oa = sa + da * (1.0 - sa)
    rgb = src[:, :, :3] * sa + dst[:, :, :3] * da * (1.0 - sa)
    dst[:, :, :3] = np.where(oa > 0, rgb / np.maximum(oa, 1e-8), 0).astype(np.uint8)
    dst[:, :, 3:4] = np.clip(np.rint(oa * 255), 0, 255).astype(np.uint8)


def render_pose(manifest: dict, name: str, angles: dict[str, float]) -> tuple[np.ndarray, dict]:
    h = w = 1254
    matrices = global_matrices(angles)
    canvas = np.zeros((h, w, 4), np.uint8)
    for record in manifest["parts"]:
        image = np.array(Image.open(ROOT / record["file"]).convert("RGBA"))
        full = np.zeros((h, w, 4), np.uint8)
        x0, y0 = record["canvas_origin_xy"]
        full[y0:y0 + image.shape[0], x0:x0 + image.shape[1]] = image
        bone = PART_BONE[record["semantic"]]
        matrix = np.eye(3) if bone is None else matrices[bone]
        warped = cv2.warpAffine(
            full,
            matrix[:2],
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )
        alpha_over(canvas, warped)
    mask = (canvas[:, :, 3] > 24).astype(np.uint8)
    components, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    areas = sorted((int(stats[i, cv2.CC_STAT_AREA]) for i in range(1, components)), reverse=True)
    total = int(mask.sum())
    report = {
        "pose": name,
        "alpha_area": total,
        "connected_components": components - 1,
        "largest_component_ratio": (areas[0] / total) if total and areas else 0.0,
        "angles": angles,
    }
    return canvas, report


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    reports = []
    frames = []
    for name, angles in POSES.items():
        rgba, report = render_pose(manifest, name, angles)
        Image.fromarray(rgba, "RGBA").save(OUT / f"{name}.png")
        reports.append(report)
        frames.append((name, rgba))

    cell_w, cell_h = 420, 430
    board = Image.new("RGB", (cell_w * len(frames), cell_h), (27, 29, 34))
    draw = ImageDraw.Draw(board)
    font = ImageFont.load_default(size=18)
    for index, (name, rgba) in enumerate(frames):
        image = Image.fromarray(rgba, "RGBA")
        bbox = image.getchannel("A").getbbox()
        crop = image.crop(bbox)
        scale = min((cell_w - 24) / crop.width, (cell_h - 54) / crop.height)
        crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.Resampling.LANCZOS)
        x = index * cell_w + (cell_w - crop.width) // 2
        y = cell_h - 16 - crop.height
        board.paste(crop, (x, y), crop)
        draw.text((index * cell_w + 12, 10), name, fill=(245, 230, 145), font=font)
    board.save(OUT / "extreme_pose_contact.jpg", quality=94)
    (OUT / "extreme_pose_qa.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(f"THIEF_V7_EXTREME_POSES count={len(reports)} out={OUT}")
    for report in reports:
        print(json.dumps(report))


if __name__ == "__main__":
    main()
