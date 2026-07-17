#!/usr/bin/env python3
"""Render a padded, weighted-motion gate for Thief Raider v13.

The bind pose is reconstructed exclusively from locked-master ownership.  At
moving poses, continuous generated cloth underpaint follows two-bone weighted
meshes beneath exact visible overlays, preventing exposed rectangular cuts and
shoulder/elbow/knee holes.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
SOURCE_DIR = HERE / "02_semantic_parts" / "master_mesh_sources_v01"
BASELINE = HERE.parent / "thief_raider_v11" / "00_reference" / "visible_baseline"
MANIFEST = BASELINE / "visible_baseline.manifest.json"
MASTER = HERE / "00_reference" / "thief_raider_locked_master.png"
UNDER = SOURCE_DIR / "generated_hidden_underpaint"
OUT = HERE / "03_bind_review" / "weighted_motion_v02"

SOURCE_W, SOURCE_H = 534, 420
PAD_X, PAD_Y = 190, 150
WIDTH, HEIGHT = SOURCE_W + PAD_X * 2, SOURCE_H + PAD_Y * 2
ROOT_PIVOT = np.asarray([PAD_X + 290.0, PAD_Y + 285.0], dtype=np.float32)


CHAINS = {
    "near_arm": {
        "joints": [(169.0, 230.0), (139.0, 281.0), (116.0, 329.0)],
        "underpaint": UNDER / "near_arm_underpaint.png",
        "blend_radius": 22.0,
    },
    "far_arm": {
        "joints": [(332.0, 155.0), (367.0, 198.0), (301.0, 192.0)],
        "underpaint": UNDER / "far_arm_underpaint.png",
        "blend_radius": 24.0,
    },
    "near_leg": {
        "joints": [(221.0, 278.0), (214.0, 330.0), (220.0, 369.0)],
        "underpaint": UNDER / "near_leg_underpaint.png",
        "blend_radius": 20.0,
    },
    "far_leg": {
        "joints": [(354.0, 282.0), (382.0, 335.0), (398.0, 370.0)],
        "underpaint": UNDER / "far_leg_underpaint.png",
        "blend_radius": 20.0,
    },
}

for chain in CHAINS.values():
    chain["joints"] = [
        np.asarray([x + PAD_X, y + PAD_Y], dtype=np.float32)
        for x, y in chain["joints"]
    ]


DEFAULT = {
    "root_x": 0.0,
    "root_y": 0.0,
    "root_angle": 0.0,
    "root_sx": 1.0,
    "root_sy": 1.0,
    "head": 0.0,
    "scarf": 0.0,
    "cape": 0.0,
    "sack": 0.0,
    "pouch": 0.0,
    "near_arm_upper": 0.0,
    "near_arm_lower": 0.0,
    "near_arm_end": 0.0,
    "far_arm_upper": 0.0,
    "far_arm_lower": 0.0,
    "far_arm_end": 0.0,
    "near_leg_upper": 0.0,
    "near_leg_lower": 0.0,
    "near_leg_end": 0.0,
    "far_leg_upper": 0.0,
    "far_leg_lower": 0.0,
    "far_leg_end": 0.0,
}


CASES = [
    ("bind", {}),
    (
        "idle_inhale",
        {
            "root_y": -0.7,
            "root_angle": -0.25,
            "root_sx": 1.001,
            "root_sy": 1.004,
            "head": 0.35,
            "scarf": -0.35,
            "cape": -0.8,
            "sack": 0.25,
            "near_arm_upper": -0.7,
            "near_arm_lower": 0.8,
            "far_arm_upper": 0.4,
            "far_arm_lower": -0.5,
        },
    ),
    (
        "idle_exhale",
        {
            "root_y": 0.45,
            "root_angle": 0.18,
            "root_sx": 0.9995,
            "root_sy": 0.998,
            "head": -0.25,
            "scarf": 0.25,
            "cape": 0.55,
            "sack": -0.18,
            "near_arm_upper": 0.5,
            "near_arm_lower": -0.55,
            "far_arm_upper": -0.3,
            "far_arm_lower": 0.35,
        },
    ),
    (
        "attack_windup",
        {
            "root_x": 4.0,
            "root_y": 1.0,
            "root_angle": 2.0,
            "head": -1.4,
            "scarf": -2.2,
            "cape": -4.0,
            "sack": -2.0,
            "near_arm_upper": 9.0,
            "near_arm_lower": -6.0,
            "near_arm_end": -2.0,
            "far_arm_upper": -2.0,
            "far_arm_lower": 3.0,
            "near_leg_upper": 2.0,
            "near_leg_lower": -2.0,
            "far_leg_upper": -1.0,
            "far_leg_lower": 1.2,
        },
    ),
    (
        "attack_contact",
        {
            "root_x": -12.0,
            "root_angle": -3.0,
            "head": 1.5,
            "scarf": 2.8,
            "cape": 5.0,
            "sack": 2.5,
            "pouch": 1.8,
            "near_arm_upper": -14.0,
            "near_arm_lower": 6.0,
            "near_arm_end": 1.0,
            "far_arm_upper": 2.0,
            "far_arm_lower": -3.0,
            "near_leg_upper": -2.0,
            "near_leg_lower": 2.0,
            "far_leg_upper": -4.0,
            "far_leg_lower": 5.0,
        },
    ),
    (
        "attack_recoil",
        {
            "root_x": -4.0,
            "root_y": 0.5,
            "root_angle": -1.1,
            "head": 0.5,
            "scarf": 1.0,
            "cape": 1.8,
            "sack": 0.8,
            "near_arm_upper": -5.0,
            "near_arm_lower": 2.0,
            "far_arm_upper": 0.8,
            "far_arm_lower": -1.0,
        },
    ),
    (
        "hurt_recoil",
        {
            "root_x": 8.0,
            "root_y": -2.0,
            "root_angle": 4.5,
            "head": -5.0,
            "scarf": -3.0,
            "cape": -6.0,
            "sack": -4.0,
            "pouch": -2.0,
            "near_arm_upper": 4.0,
            "near_arm_lower": -3.0,
            "far_arm_upper": -6.0,
            "far_arm_lower": 7.0,
            "near_leg_upper": 2.0,
            "near_leg_lower": -2.0,
            "far_leg_upper": -2.0,
            "far_leg_lower": 2.5,
        },
    ),
    (
        "die_knee_buckle",
        {
            "root_y": 14.0,
            "root_angle": 6.0,
            "head": -7.0,
            "scarf": -4.0,
            "cape": -5.0,
            "sack": -4.0,
            "near_arm_upper": 8.0,
            "near_arm_lower": 8.0,
            "far_arm_upper": -8.0,
            "far_arm_lower": 10.0,
            "near_leg_upper": 10.0,
            "near_leg_lower": -18.0,
            "far_leg_upper": -8.0,
            "far_leg_lower": 14.0,
        },
    ),
    (
        "die_ground_settle",
        {
            "root_x": -15.0,
            "root_y": 90.0,
            "root_angle": -78.0,
            "head": 12.0,
            "scarf": 16.0,
            "cape": 22.0,
            "sack": 15.0,
            "pouch": 10.0,
            "near_arm_upper": 18.0,
            "near_arm_lower": 24.0,
            "near_arm_end": 8.0,
            "far_arm_upper": -18.0,
            "far_arm_lower": 25.0,
            "near_leg_upper": 55.0,
            "near_leg_lower": -70.0,
            "near_leg_end": 15.0,
            "far_leg_upper": 42.0,
            "far_leg_lower": -55.0,
            "far_leg_end": 12.0,
        },
    ),
]


def translation(x: float, y: float) -> np.ndarray:
    return np.asarray([[1.0, 0.0, x], [0.0, 1.0, y], [0.0, 0.0, 1.0]], dtype=np.float32)


def around(point: np.ndarray, angle: float = 0.0, sx: float = 1.0, sy: float = 1.0) -> np.ndarray:
    radians = math.radians(angle)
    c, s = math.cos(radians), math.sin(radians)
    local = np.asarray(
        [[c * sx, -s * sy, 0.0], [s * sx, c * sy, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float32,
    )
    return translation(float(point[0]), float(point[1])) @ local @ translation(-float(point[0]), -float(point[1]))


def root_matrix(p: dict) -> np.ndarray:
    return translation(p["root_x"], p["root_y"]) @ around(
        ROOT_PIVOT, p["root_angle"], p["root_sx"], p["root_sy"]
    )


def chain_matrices(chain: dict, upper_deg: float, lower_deg: float, end_deg: float) -> dict[str, np.ndarray]:
    start, middle, end = chain["joints"]
    upper = around(start, upper_deg)
    lower = upper @ around(middle, lower_deg)
    endpoint = lower @ around(end, end_deg)
    plate = around(start, upper_deg * 0.28)
    return {"upper": upper, "lower": lower, "end": endpoint, "plate": plate}


def project_segment(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> tuple[float, float]:
    vector = end - start
    denom = max(1e-6, float(np.dot(vector, vector)))
    t = float(np.clip(np.dot(point - start, vector) / denom, 0.0, 1.0))
    nearest = start + vector * t
    return t, float(np.linalg.norm(point - nearest))


def smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def lower_weight(point: np.ndarray, chain: dict) -> float:
    start, middle, end = chain["joints"]
    upper_t, upper_d = project_segment(point, start, middle)
    lower_t, lower_d = project_segment(point, middle, end)
    upper_len = float(np.linalg.norm(middle - start))
    lower_len = float(np.linalg.norm(end - middle))
    if upper_d <= lower_d:
        distance = upper_t * upper_len
    else:
        distance = upper_len + lower_t * lower_len
    radius = float(chain["blend_radius"])
    chain_weight = smoothstep((distance - (upper_len - radius)) / (radius * 2.0))
    nearest_weight = upper_d * upper_d / max(1e-5, upper_d * upper_d + lower_d * lower_d)
    return float(np.clip(chain_weight * 0.82 + nearest_weight * 0.18, 0.0, 1.0))


def deform_point(point: np.ndarray, chain: dict, upper_deg: float, lower_deg: float) -> np.ndarray:
    matrices = chain_matrices(chain, upper_deg, lower_deg, 0.0)
    weight = lower_weight(point, chain)
    angle = upper_deg + lower_deg * weight
    rotation = around(chain["joints"][0], angle)
    # Blend hierarchical translations while preserving local cross-section.
    upper_t = matrices["upper"][:2, 2]
    lower_t = matrices["lower"][:2, 2]
    blended = rotation @ np.asarray([point[0], point[1], 1.0], dtype=np.float32)
    blended[:2] += (lower_t - upper_t) * weight
    return blended[:2]


def warp_mesh(source: np.ndarray, chain: dict, upper_deg: float, lower_deg: float, root: np.ndarray) -> np.ndarray:
    alpha = source[:, :, 3]
    ys, xs = np.where(alpha > 2)
    if not len(xs):
        return np.zeros_like(source)
    margin, step = 12, 5
    left = max(0, int(xs.min()) - margin)
    right = min(WIDTH - 1, int(xs.max()) + margin)
    top = max(0, int(ys.min()) - margin)
    bottom = min(HEIGHT - 1, int(ys.max()) + margin)
    grid_x = list(range(left, right, step)) + [right]
    grid_y = list(range(top, bottom, step)) + [bottom]
    map_x = np.full((HEIGHT, WIDTH), -1.0, dtype=np.float32)
    map_y = np.full((HEIGHT, WIDTH), -1.0, dtype=np.float32)
    for yi in range(len(grid_y) - 1):
        for xi in range(len(grid_x) - 1):
            corners = np.asarray(
                [
                    [grid_x[xi], grid_y[yi]],
                    [grid_x[xi + 1], grid_y[yi]],
                    [grid_x[xi + 1], grid_y[yi + 1]],
                    [grid_x[xi], grid_y[yi + 1]],
                ],
                dtype=np.float32,
            )
            posed = []
            for point in corners:
                local = deform_point(point, chain, upper_deg, lower_deg)
                final = root @ np.asarray([local[0], local[1], 1.0], dtype=np.float32)
                posed.append(final[:2])
            posed = np.asarray(posed, dtype=np.float32)
            for tri in ((0, 1, 2), (0, 2, 3)):
                src_tri = corners[list(tri)]
                dst_tri = posed[list(tri)]
                dx, dy, dw, dh = cv2.boundingRect(dst_tri)
                l, t = max(0, dx), max(0, dy)
                r, b = min(WIDTH, dx + dw), min(HEIGHT, dy + dh)
                if l >= r or t >= b:
                    continue
                local_tri = dst_tri - np.asarray([dx, dy], dtype=np.float32)
                tri_mask = np.zeros((dh, dw), dtype=np.uint8)
                cv2.fillConvexPoly(tri_mask, np.round(local_tri).astype(np.int32), 255, cv2.LINE_8)
                inverse = cv2.getAffineTransform(dst_tri.astype(np.float32), src_tri.astype(np.float32))
                yy, xx = np.indices((b - t, r - l), dtype=np.float32)
                wx, wy = xx + l, yy + t
                sx = inverse[0, 0] * wx + inverse[0, 1] * wy + inverse[0, 2]
                sy = inverse[1, 0] * wx + inverse[1, 1] * wy + inverse[1, 2]
                take = tri_mask[t - dy : b - dy, l - dx : r - dx] > 0
                map_x[t:b, l:r][take] = sx[take]
                map_y[t:b, l:r][take] = sy[take]
    premultiplied = source.astype(np.float32)
    premultiplied[:, :, :3] *= premultiplied[:, :, 3:4] / 255.0
    warped = cv2.remap(
        premultiplied,
        map_x,
        map_y,
        cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )
    return finish_warp(warped)


def finish_warp(warped: np.ndarray) -> np.ndarray:
    alpha = np.clip(warped[:, :, 3], 0.0, 255.0)
    result = np.zeros_like(warped, dtype=np.uint8)
    keep = alpha >= 0.8
    safe = np.maximum(alpha, 0.8)
    rgb = np.clip(warped[:, :, :3] * (255.0 / safe[:, :, None]), 0.0, 255.0)
    result[:, :, :3][keep] = np.round(rgb[keep]).astype(np.uint8)
    result[:, :, 3][keep] = np.round(alpha[keep]).astype(np.uint8)
    return result


def warp_rigid(source: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    premultiplied = source.astype(np.float32)
    premultiplied[:, :, :3] *= premultiplied[:, :, 3:4] / 255.0
    warped = cv2.warpAffine(
        premultiplied,
        matrix[:2],
        (WIDTH, HEIGHT),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )
    return finish_warp(warped)


def alpha_over(bottom: np.ndarray, top: np.ndarray) -> np.ndarray:
    image = Image.fromarray(bottom, "RGBA")
    image.alpha_composite(Image.fromarray(top, "RGBA"))
    return np.asarray(image, dtype=np.uint8)


def load_canvas(path: Path, bbox: list[int] | None = None) -> np.ndarray:
    canvas = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    image = np.asarray(Image.open(path).convert("RGBA"), dtype=np.uint8)
    if bbox is None:
        canvas[PAD_Y : PAD_Y + SOURCE_H, PAD_X : PAD_X + SOURCE_W] = image
    else:
        x, y, width, height = map(int, bbox)
        canvas[PAD_Y + y : PAD_Y + y + height, PAD_X + x : PAD_X + x + width] = image
    return canvas


def load_assets() -> tuple[list[dict], dict[str, np.ndarray], dict[str, np.ndarray], np.ndarray]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    parts = {}
    for record in manifest["parts"]:
        parts[record["semantic"]] = load_canvas(BASELINE / record["file"], record["source_bbox"])
    source_manifest = json.loads(
        (SOURCE_DIR / "master_mesh_sources.manifest.json").read_text(encoding="utf-8")
    )
    meshes = {}
    for record in source_manifest["continuous_meshes"]:
        semantic = record["semantic"]
        if semantic == "torso":
            continue
        meshes[semantic] = load_canvas(
            SOURCE_DIR / record["file"], record["source_bbox_xywh"]
        )
    master = load_canvas(MASTER)
    return manifest["parts"], parts, meshes, master


def parameters(overrides: dict) -> dict:
    value = DEFAULT.copy()
    value.update(overrides)
    return value


def semantic_matrix(semantic: str, p: dict, root: np.ndarray, chain_mats: dict[str, dict[str, np.ndarray]]) -> np.ndarray:
    if semantic == "near_upper_arm":
        return root @ chain_mats["near_arm"]["upper"]
    if semantic == "near_forearm":
        return root @ chain_mats["near_arm"]["lower"]
    if semantic in {"near_dagger_hand", "dagger"}:
        return root @ chain_mats["near_arm"]["end"]
    if semantic == "near_shoulder_plate":
        return root
    if semantic == "far_forearm":
        return root @ chain_mats["far_arm"]["lower"]
    if semantic == "far_strap_hand":
        return root @ chain_mats["far_arm"]["end"]
    if semantic == "far_shoulder_plate":
        return root
    if semantic == "near_thigh":
        return root @ chain_mats["near_leg"]["upper"]
    if semantic == "near_shin":
        return root @ chain_mats["near_leg"]["lower"]
    if semantic == "near_boot":
        return root @ chain_mats["near_leg"]["end"]
    if semantic == "far_thigh":
        return root @ chain_mats["far_leg"]["upper"]
    if semantic == "far_shin":
        return root @ chain_mats["far_leg"]["lower"]
    if semantic == "far_boot":
        return root @ chain_mats["far_leg"]["end"]

    # Until each soft accessory has its own weighted mesh, it follows the body
    # as a coherent group.  Rotating rigid cape/scarf/sack cutouts around guessed
    # pivots was the source of the detached shards in v01.
    return root


def render(records: list[dict], parts: dict[str, np.ndarray], meshes: dict[str, np.ndarray], p: dict, bind: bool) -> np.ndarray:
    root = root_matrix(p)
    chain_mats = {}
    for name, chain in CHAINS.items():
        chain_mats[name] = chain_matrices(
            chain,
            p[f"{name}_upper"],
            p[f"{name}_lower"],
            p[f"{name}_end"],
        )

    frame = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    inserted = set()
    insert_at = {5: "far_leg", 8: "far_arm", 13: "near_leg", 19: "near_arm"}
    replaced_parts = {
        "far_leg": {"far_thigh", "far_shin", "far_boot"},
        "far_arm": {"far_forearm", "far_strap_hand"},
        "near_leg": {"near_thigh", "near_shin", "near_boot"},
        "near_arm": {"near_upper_arm", "near_forearm", "near_dagger_hand"},
    }
    replaced_semantics = set().union(*replaced_parts.values())
    for record in sorted(records, key=lambda item: (int(item["z"]), int(item["index"]))):
        z = int(record["z"])
        if not bind:
            for threshold, name in insert_at.items():
                if z >= threshold and name not in inserted:
                    posed = warp_mesh(
                        meshes[name],
                        CHAINS[name],
                        p[f"{name}_upper"],
                        p[f"{name}_lower"],
                        root,
                    )
                    frame = alpha_over(frame, posed)
                    inserted.add(name)
        semantic = record["semantic"]
        if not bind and semantic in replaced_semantics:
            continue
        matrix = semantic_matrix(semantic, p, root, chain_mats)
        posed = parts[semantic] if bind else warp_rigid(parts[semantic], matrix)
        frame = alpha_over(frame, posed)
    return frame


def checker(width: int, height: int, cell: int = 12) -> Image.Image:
    yy, xx = np.mgrid[0:height, 0:width]
    pattern = ((xx // cell + yy // cell) % 2).astype(np.uint8)
    rgb = np.where(
        pattern[:, :, None] == 0,
        np.asarray([83, 94, 109]),
        np.asarray([132, 145, 163]),
    ).astype(np.uint8)
    alpha = np.full((height, width, 1), 255, dtype=np.uint8)
    return Image.fromarray(np.concatenate([rgb, alpha], axis=2), "RGBA")


def contact_sheet(frames: list[tuple[str, np.ndarray]], output: Path, checkerboard: bool) -> None:
    cols, cell_w, cell_h = 3, 620, 520
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (27, 31, 39, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (name, array) in enumerate(frames):
        x0, y0 = (index % cols) * cell_w, (index // cols) * cell_h
        draw.text((x0 + 10, y0 + 9), name, fill=(245, 247, 250, 255), font=font)
        image = Image.fromarray(array, "RGBA")
        bbox = image.getchannel("A").getbbox()
        if bbox:
            image = image.crop(bbox)
        scale = min(570 / max(1, image.width), 450 / max(1, image.height), 1.15)
        image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
        if checkerboard:
            shown = checker(image.width, image.height, 10)
            shown.alpha_composite(image)
        else:
            shown = image
        sheet.alpha_composite(shown, (x0 + (cell_w - shown.width) // 2, y0 + 45 + (450 - shown.height) // 2))
    sheet.convert("RGB").save(output, quality=96)


def joint_sheet(name: str, frame: np.ndarray, output: Path) -> None:
    joints = [
        ("near_shoulder", CHAINS["near_arm"]["joints"][0]),
        ("near_elbow", CHAINS["near_arm"]["joints"][1]),
        ("near_wrist", CHAINS["near_arm"]["joints"][2]),
        ("far_shoulder", CHAINS["far_arm"]["joints"][0]),
        ("far_elbow", CHAINS["far_arm"]["joints"][1]),
        ("far_wrist", CHAINS["far_arm"]["joints"][2]),
        ("near_knee", CHAINS["near_leg"]["joints"][1]),
        ("far_knee", CHAINS["far_leg"]["joints"][1]),
        ("waist", ROOT_PIVOT),
    ]
    cols, cell = 3, 300
    sheet = Image.new("RGBA", (cols * cell, 3 * cell), (27, 31, 39, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (label, point) in enumerate(joints):
        x0, y0 = (index % cols) * cell, (index // cols) * cell
        # Static joint centers are sufficient for a high-resolution seam scan;
        # the crop is intentionally wider than the maximum prototype motion.
        half = 78
        left, top = round(float(point[0]) - half), round(float(point[1]) - half)
        crop = Image.fromarray(frame, "RGBA").crop((left, top, left + half * 2, top + half * 2))
        bg = checker(half * 2, half * 2, 8)
        bg.alpha_composite(crop)
        shown = bg.resize((260, 260), Image.Resampling.NEAREST)
        sheet.alpha_composite(shown, (x0 + 20, y0 + 32))
        draw.text((x0 + 10, y0 + 8), f"{name} / {label}", fill=(245, 247, 250, 255), font=font)
    sheet.convert("RGB").save(output, quality=96)


def bounds(frame: np.ndarray) -> list[int]:
    ys, xs = np.where(frame[:, :, 3] > 4)
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records, parts, meshes, master = load_assets()
    frames = []
    audits = []
    for name, overrides in CASES:
        p = parameters(overrides)
        frame = render(records, parts, meshes, p, bind=name == "bind")
        Image.fromarray(frame, "RGBA").save(OUT / f"{name}.png")
        mismatch = int(np.any(frame != master, axis=2).sum()) if name == "bind" else None
        audits.append({"name": name, "params": p, "alpha_bounds": bounds(frame), "bind_mismatch_pixels": mismatch})
        frames.append((name, frame))
        if name in {"attack_windup", "attack_contact", "hurt_recoil", "die_ground_settle"}:
            joint_sheet(name, frame, OUT / f"{name}_joint_checker.jpg")
    if audits[0]["bind_mismatch_pixels"] != 0:
        raise RuntimeError(f"locked bind drifted: {audits[0]}")
    contact_sheet(frames, OUT / "motion_contact_dark.jpg", checkerboard=False)
    contact_sheet(frames, OUT / "motion_contact_checker.jpg", checkerboard=True)
    report = {
        "schema_version": 1,
        "status": "visual_review_required",
        "technique": "one continuous weighted mesh per arm/leg + exact locked-master accessories",
        "padded_canvas": [WIDTH, HEIGHT],
        "bind_exact_rgba": True,
        "rectangular_tile_parts": False,
        "cases": audits,
        "shipping_allowed": False,
        "steam_install_allowed": False,
        "next_gate": "reject_or_tune each checkerboard key pose before Spine export",
    }
    (OUT / "motion_review.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
