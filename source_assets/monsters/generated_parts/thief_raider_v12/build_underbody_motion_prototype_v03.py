#!/usr/bin/env python3
"""Render hierarchical rigid-part motion from the v03 semantic attachments."""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
SEG = HERE / "02_semantic_parts" / "underbody_context_v03" / "segmentation_v01"
MANIFEST = SEG / "segmentation_review.json"
SOURCE = HERE / "02_semantic_parts" / "underbody_context_v03" / "underbody_context_candidate_v03_alpha.png"
OUT = HERE / "03_bind_review" / "underbody_motion_v03"

WIDTH, HEIGHT = 1536, 1024
PELVIS_PIVOT = (795.0, 595.0)
TORSO_PIVOT = (795.0, 595.0)

PART_PARENT = {
    "pelvis": "pelvis",
    "torso": "torso",
    "hooded_head": "head",
    "near_upper_arm": "near_upper_arm",
    "near_forearm": "near_forearm",
    "near_hand": "near_hand",
    "far_upper_arm": "far_upper_arm",
    "far_forearm": "far_forearm",
    "far_hand": "far_hand",
    "near_thigh": "near_thigh",
    "near_boot": "near_boot",
    "far_thigh": "far_thigh",
    "far_boot": "far_boot",
}

DEFAULT = {
    "root_x": 0.0, "root_y": 0.0, "root_angle": 0.0,
    "pelvis_angle": 0.0, "pelvis_x": 0.0, "pelvis_y": 0.0,
    "torso_angle": 0.0, "torso_x": 0.0, "torso_y": 0.0, "torso_sx": 1.0, "torso_sy": 1.0,
    "head_angle": 0.0,
    "near_upper_angle": 0.0, "near_forearm_angle": 0.0, "near_hand_angle": 0.0,
    "far_upper_angle": 0.0, "far_forearm_angle": 0.0, "far_hand_angle": 0.0,
    "near_thigh_angle": 0.0, "near_boot_angle": 0.0,
    "far_thigh_angle": 0.0, "far_boot_angle": 0.0,
}

CASES = [
    ("bind", {}),
    ("idle_inhale", {"torso_angle": -0.55, "torso_y": -0.8, "torso_sx": 1.002, "torso_sy": 1.004}),
    ("idle_exhale", {"torso_angle": 0.4, "torso_y": 0.5, "torso_sx": 0.999, "torso_sy": 0.998}),
    ("attack_windup", {
        "root_x": 12.0, "pelvis_angle": 1.5, "torso_angle": 4.5,
        "near_upper_angle": -17.0, "near_forearm_angle": 22.0, "near_hand_angle": -4.0,
        "far_upper_angle": -1.5, "far_forearm_angle": 2.0,
    }),
    ("attack_contact", {
        "root_x": -30.0, "pelvis_angle": -2.5, "torso_angle": -7.0,
        "near_upper_angle": 30.0, "near_forearm_angle": -16.0, "near_hand_angle": 3.0,
        "far_upper_angle": 2.0, "far_forearm_angle": -3.0,
        "near_thigh_angle": -2.0, "near_boot_angle": 2.0,
    }),
    ("attack_recoil", {
        "root_x": -7.0, "pelvis_angle": -0.8, "torso_angle": -2.0,
        "near_upper_angle": 11.0, "near_forearm_angle": -7.0, "near_hand_angle": 1.0,
    }),
    ("hurt_recoil", {
        "root_x": 17.0, "root_y": 2.0, "pelvis_angle": 2.0, "torso_angle": 7.0,
        "near_upper_angle": -8.0, "near_forearm_angle": 10.0,
        "far_upper_angle": -5.0, "far_forearm_angle": 7.0,
        "near_thigh_angle": 2.0, "far_thigh_angle": -2.0,
    }),
    ("die_anticipation", {
        "root_y": -5.0, "pelvis_angle": 2.0, "torso_angle": 5.0,
        "near_upper_angle": -5.0, "near_forearm_angle": 7.0,
    }),
    ("die_collapse", {
        "root_x": -20.0, "root_y": 35.0, "root_angle": -48.0,
        "pelvis_angle": -4.0, "torso_angle": -10.0,
        "near_upper_angle": 15.0, "near_forearm_angle": 12.0, "near_hand_angle": 5.0,
        "far_upper_angle": -8.0, "far_forearm_angle": 10.0, "far_hand_angle": -4.0,
        "near_thigh_angle": 8.0, "near_boot_angle": -10.0,
        "far_thigh_angle": -7.0, "far_boot_angle": 11.0,
    }),
]

JOINTS = {
    "near_shoulder": (655.0, 395.0, "torso"),
    "near_elbow": (570.0, 545.0, "near_upper_arm"),
    "near_wrist": (465.0, 690.0, "near_forearm"),
    "far_shoulder": (820.0, 300.0, "torso"),
    "far_elbow": (950.0, 405.0, "far_upper_arm"),
    "far_wrist": (855.0, 465.0, "far_forearm"),
    "waist": (795.0, 595.0, "pelvis"),
    "near_knee": (655.0, 715.0, "near_thigh"),
    "far_knee": (980.0, 715.0, "far_thigh"),
}


def translation(x: float, y: float) -> np.ndarray:
    return np.asarray([[1.0, 0.0, x], [0.0, 1.0, y], [0.0, 0.0, 1.0]], dtype=np.float32)


def around(pivot: tuple[float, float], angle: float = 0.0, sx: float = 1.0, sy: float = 1.0, x: float = 0.0, y: float = 0.0) -> np.ndarray:
    px, py = pivot
    radians = math.radians(angle)
    c, s = math.cos(radians), math.sin(radians)
    rotate_scale = np.asarray([[c * sx, -s * sy, 0.0], [s * sx, c * sy, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
    return translation(x, y) @ translation(px, py) @ rotate_scale @ translation(-px, -py)


def params(overrides: dict) -> dict:
    value = DEFAULT.copy()
    value.update(overrides)
    return value


def bone_matrices(p: dict) -> dict[str, np.ndarray]:
    root = translation(p["root_x"], p["root_y"]) @ around((800.0, 820.0), p["root_angle"])
    pelvis = root @ around(PELVIS_PIVOT, p["pelvis_angle"], x=p["pelvis_x"], y=p["pelvis_y"])
    torso = pelvis @ around(TORSO_PIVOT, p["torso_angle"], p["torso_sx"], p["torso_sy"], p["torso_x"], p["torso_y"])
    head = torso @ around((650.0, 390.0), p["head_angle"])

    near_upper = torso @ around((655.0, 395.0), p["near_upper_angle"])
    near_forearm = near_upper @ around((570.0, 545.0), p["near_forearm_angle"])
    near_hand = near_forearm @ around((465.0, 690.0), p["near_hand_angle"])
    far_upper = torso @ around((820.0, 300.0), p["far_upper_angle"])
    far_forearm = far_upper @ around((950.0, 405.0), p["far_forearm_angle"])
    far_hand = far_forearm @ around((855.0, 465.0), p["far_hand_angle"])

    near_thigh = pelvis @ around((730.0, 620.0), p["near_thigh_angle"])
    near_boot = near_thigh @ around((655.0, 715.0), p["near_boot_angle"])
    far_thigh = pelvis @ around((865.0, 620.0), p["far_thigh_angle"])
    far_boot = far_thigh @ around((980.0, 715.0), p["far_boot_angle"])
    return {
        "root": root, "pelvis": pelvis, "torso": torso, "head": head,
        "near_upper_arm": near_upper, "near_forearm": near_forearm, "near_hand": near_hand,
        "far_upper_arm": far_upper, "far_forearm": far_forearm, "far_hand": far_hand,
        "near_thigh": near_thigh, "near_boot": near_boot,
        "far_thigh": far_thigh, "far_boot": far_boot,
    }


def load_full_canvas(record: dict) -> np.ndarray:
    crop = np.asarray(Image.open(SEG / record["attachment_file"]).convert("RGBA"), dtype=np.uint8)
    x0, y0, x1, y1 = map(int, record["source_bbox"])
    canvas = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    canvas[y0:y1, x0:x1] = crop
    return canvas


def warp_rgba(source: np.ndarray, matrix: np.ndarray, bind: bool = False) -> np.ndarray:
    if bind or np.allclose(matrix, np.eye(3), atol=1e-8):
        return source.copy()
    value = source.astype(np.float32)
    value[:, :, :3] *= value[:, :, 3:4] / 255.0
    warped = cv2.warpAffine(
        value,
        matrix[:2],
        (WIDTH, HEIGHT),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )
    alpha = np.clip(warped[:, :, 3], 0.0, 255.0)
    output = np.zeros_like(warped, dtype=np.uint8)
    keep = alpha >= 1.0
    safe = np.maximum(alpha, 1.0)
    rgb = np.clip(warped[:, :, :3] * (255.0 / safe[:, :, None]), 0.0, 255.0)
    output[:, :, :3][keep] = np.round(rgb[keep]).astype(np.uint8)
    output[:, :, 3][keep] = np.round(alpha[keep]).astype(np.uint8)
    return output


def alpha_over(bottom: np.ndarray, top: np.ndarray) -> np.ndarray:
    image = Image.fromarray(bottom, "RGBA")
    image.alpha_composite(Image.fromarray(top, "RGBA"))
    return np.asarray(image, dtype=np.uint8)


def render(records: dict[str, dict], canvases: dict[str, np.ndarray], p: dict, bind: bool = False) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    matrices = bone_matrices(p)
    frame = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    for name in json.loads(MANIFEST.read_text(encoding="utf-8"))["draw_order"]:
        matrix = matrices[PART_PARENT[name]]
        frame = alpha_over(frame, warp_rgba(canvases[name], matrix, bind=bind))
    return frame, matrices


def internal_holes(frame: np.ndarray) -> int:
    solid = (frame[:, :, 3] > 8).astype(np.uint8)
    inverse = (1 - solid).astype(np.uint8)
    flood = inverse.copy()
    mask = np.zeros((HEIGHT + 2, WIDTH + 2), dtype=np.uint8)
    cv2.floodFill(flood, mask, (0, 0), 2)
    return int((flood == 1).sum())


def checker(width: int, height: int, cell: int = 12) -> Image.Image:
    yy, xx = np.mgrid[0:height, 0:width]
    pattern = ((xx // cell + yy // cell) % 2).astype(np.uint8)
    rgb = np.where(pattern[:, :, None] == 0, np.asarray([91, 103, 119]), np.asarray([133, 146, 164])).astype(np.uint8)
    alpha = np.full((height, width, 1), 255, dtype=np.uint8)
    return Image.fromarray(np.concatenate([rgb, alpha], axis=2), "RGBA")


def transformed_point(point: tuple[float, float], matrix: np.ndarray) -> tuple[float, float]:
    result = matrix @ np.asarray([point[0], point[1], 1.0], dtype=np.float32)
    return float(result[0]), float(result[1])


def make_joint_review(name: str, frame: np.ndarray, matrices: dict[str, np.ndarray]) -> None:
    cols, rows, cell = 3, 3, 300
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (26, 30, 38, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (joint_name, (px, py, bone_name)) in enumerate(JOINTS.items()):
        x, y = (index % cols) * cell, (index // cols) * cell
        center = transformed_point((px, py), matrices[bone_name])
        half = 70
        x0, y0 = round(center[0] - half), round(center[1] - half)
        crop = Image.fromarray(frame, "RGBA").crop((x0, y0, x0 + half * 2, y0 + half * 2))
        bg = checker(half * 2, half * 2, 8)
        bg.alpha_composite(crop)
        shown = bg.resize((260, 260), Image.Resampling.NEAREST)
        sheet.alpha_composite(shown, (x + 20, y + 30))
        draw.text((x + 10, y + 8), joint_name, fill=(244, 246, 250, 255), font=font)
    sheet.convert("RGB").save(OUT / f"{name}_joint_checker.jpg", quality=96)


def make_contact(rendered: list[tuple[str, np.ndarray]]) -> None:
    cols, rows, cell_w, cell_h = 3, 3, 540, 470
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (26, 30, 38, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (name, frame) in enumerate(rendered):
        x, y = (index % cols) * cell_w, (index // cols) * cell_h
        draw.text((x + 10, y + 8), name, fill=(244, 246, 250, 255), font=font)
        image = Image.fromarray(frame, "RGBA")
        bbox = image.getchannel("A").getbbox()
        if bbox:
            image = image.crop(bbox)
        scale = min(500 / max(1, image.width), 410 / max(1, image.height))
        image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
        sheet.alpha_composite(image, (x + (cell_w - image.width) // 2, y + 42 + (410 - image.height) // 2))
    sheet.convert("RGB").save(OUT / "full_character_motion_contact.jpg", quality=96)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = {record["name"]: record for record in manifest["parts"]}
    canvases = {name: load_full_canvas(record) for name, record in records.items()}
    source = np.asarray(Image.open(SOURCE).convert("RGBA"), dtype=np.uint8)
    rendered = []
    audits = []
    for name, overrides in CASES:
        p = params(overrides)
        frame, matrices = render(records, canvases, p, bind=name == "bind")
        Image.fromarray(frame, "RGBA").save(OUT / f"{name}.png")
        mismatch = int(np.any(frame != source, axis=2).sum()) if name == "bind" else None
        holes = internal_holes(frame)
        audits.append({"name": name, "params": p, "bind_mismatch_pixels": mismatch, "internal_transparent_holes": holes})
        rendered.append((name, frame))
        if name in {"attack_windup", "attack_contact", "hurt_recoil", "die_collapse"}:
            make_joint_review(name, frame, matrices)
    make_contact(rendered)
    report = {
        "schema_version": 1,
        "status": "hierarchical_motion_visual_review_required",
        "rig": "root -> pelvis -> torso/limbs -> forearm/boot -> hand; hood follows torso during this gate",
        "cases": audits,
        "bind_exact_rgba": audits[0]["bind_mismatch_pixels"] == 0,
        "production_rig_allowed": False,
        "shipping_allowed": False,
        "steam_install_allowed": False,
        "next_gate": "joint_checker_review_then_accessory_assembly",
    }
    if not report["bind_exact_rgba"]:
        raise RuntimeError(report)
    (OUT / "motion_review.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
