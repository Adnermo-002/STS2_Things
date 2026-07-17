#!/usr/bin/env python3
"""Render full-character topology poses for the production near dagger arm."""

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
ARM_LAYERS = {
    "back": HERE / "02_semantic_parts" / "context_reveals" / "near_arm_v01" / "near_arm_cloth_base_back.png",
    "front": HERE / "02_semantic_parts" / "context_reveals" / "near_arm_v01" / "near_arm_cloth_base_front.png",
    "elbow": HERE / "02_semantic_parts" / "context_reveals" / "near_arm_v01" / "near_elbow_context_overlay.png",
    "shoulder": HERE / "02_semantic_parts" / "context_reveals" / "near_arm_v01" / "near_shoulder_context_overlay.png",
}
MASTER = HERE / "00_reference" / "locked_master.png"
OUT = HERE / "03_bind_review" / "near_arm_mesh_v01"

SOURCE_WIDTH, SOURCE_HEIGHT = 534, 420
PAD_X, PAD_Y = 100, 50
WIDTH, HEIGHT = SOURCE_WIDTH + PAD_X * 2, SOURCE_HEIGHT + PAD_Y * 2
OFFSET = np.asarray([PAD_X, PAD_Y], dtype=np.float32)
SHOULDER = np.asarray([171.0, 224.0], dtype=np.float32) + OFFSET
ELBOW = np.asarray([139.0, 283.0], dtype=np.float32) + OFFSET
WRIST = np.asarray([110.0, 321.0], dtype=np.float32) + OFFSET
MESH_BOUNDS = (86 + PAD_X, 182 + PAD_Y, 218 + PAD_X, 350 + PAD_Y)
GRID_STEP = 4

CASES = [
    {"name": "bind", "shoulder": 0.0, "elbow": 0.0, "hand": 0.0},
    {"name": "idle_inhale", "shoulder": -0.6, "elbow": 0.8, "hand": 0.0},
    {"name": "idle_exhale", "shoulder": 0.4, "elbow": -0.6, "hand": 0.0},
    {"name": "attack_windup", "shoulder": -18.0, "elbow": 28.0, "hand": 4.0},
    {"name": "attack_contact", "shoulder": 42.0, "elbow": -32.0, "hand": -4.0},
    {"name": "attack_recoil", "shoulder": 15.0, "elbow": -12.0, "hand": 2.0},
    {"name": "hurt_guard", "shoulder": -12.0, "elbow": 20.0, "hand": 5.0},
]


def alpha_over(bottom: np.ndarray, top: np.ndarray) -> np.ndarray:
    image = Image.fromarray(bottom, "RGBA")
    image.alpha_composite(Image.fromarray(top, "RGBA"))
    return np.asarray(image, dtype=np.uint8)


def premultiplied(source: np.ndarray) -> np.ndarray:
    value = source.astype(np.float32)
    value[:, :, :3] *= value[:, :, 3:4] / 255.0
    return value


def finish_warp(value: np.ndarray, largest_only: bool) -> np.ndarray:
    alpha = value[:, :, 3]
    mask = alpha >= 24.0
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if largest_only:
        if count <= 1:
            return np.zeros(value.shape, dtype=np.uint8)
        index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        keep = labels == index
    else:
        keep = np.zeros(mask.shape, dtype=bool)
        for index in range(1, count):
            if int(stats[index, cv2.CC_STAT_AREA]) >= 8:
                keep |= labels == index
    output = np.zeros(value.shape, dtype=np.uint8)
    safe_alpha = np.maximum(alpha, 1.0)
    rgb = np.clip(value[:, :, :3] * (255.0 / safe_alpha[:, :, None]), 0, 255)
    output[:, :, :3][keep] = np.round(rgb[keep]).astype(np.uint8)
    output[:, :, 3][keep] = np.clip(np.round(alpha[keep]), 0, 255).astype(np.uint8)
    return output


def rot(angle_deg: float) -> np.ndarray:
    angle = math.radians(angle_deg)
    return np.asarray([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]], dtype=np.float32)


def bone_transforms(shoulder_deg: float, elbow_deg: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    upper_r = rot(shoulder_deg)
    upper_t = SHOULDER - upper_r @ SHOULDER
    elbow_after = upper_r @ ELBOW + upper_t
    fore_r = rot(shoulder_deg + elbow_deg)
    fore_t = elbow_after - fore_r @ ELBOW
    return upper_r, upper_t, fore_r, fore_t


def project(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> tuple[float, float]:
    vector = end - start
    t = float(np.clip(np.dot(point - start, vector) / np.dot(vector, vector), 0.0, 1.0))
    nearest = start + vector * t
    return t, float(np.linalg.norm(point - nearest))


def smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def weight(point: np.ndarray) -> float:
    upper_t, upper_d = project(point, SHOULDER, ELBOW)
    fore_t, fore_d = project(point, ELBOW, WRIST)
    upper_len = float(np.linalg.norm(ELBOW - SHOULDER))
    fore_len = float(np.linalg.norm(WRIST - ELBOW))
    chain = upper_t * upper_len if upper_d <= fore_d else upper_len + fore_t * fore_len
    chain_weight = smoothstep((chain - (upper_len - 14.0)) / 28.0)
    distance_weight = upper_d * upper_d / max(1e-5, upper_d * upper_d + fore_d * fore_d)
    return float(np.clip(chain_weight * 0.78 + distance_weight * 0.22, 0.0, 1.0))


def deform(point: np.ndarray, shoulder_deg: float, elbow_deg: float) -> np.ndarray:
    upper_r, upper_t, _, fore_t = bone_transforms(shoulder_deg, elbow_deg)
    w = weight(point)
    blended_r = rot(shoulder_deg + elbow_deg * w)
    blended_t = upper_t * (1.0 - w) + fore_t * w
    return blended_r @ point + blended_t


def mesh_warp(source: np.ndarray, shoulder_deg: float, elbow_deg: float) -> np.ndarray:
    if abs(shoulder_deg) < 1e-9 and abs(elbow_deg) < 1e-9:
        return source.copy()
    left, top, right, bottom = MESH_BOUNDS
    xs = list(range(left, right, GRID_STEP)) + [right]
    ys = list(range(top, bottom, GRID_STEP)) + [bottom]
    map_x = np.full((HEIGHT, WIDTH), -1.0, dtype=np.float32)
    map_y = np.full((HEIGHT, WIDTH), -1.0, dtype=np.float32)
    for yi in range(len(ys) - 1):
        for xi in range(len(xs) - 1):
            corners = np.asarray(
                [[xs[xi], ys[yi]], [xs[xi + 1], ys[yi]], [xs[xi + 1], ys[yi + 1]], [xs[xi], ys[yi + 1]]],
                dtype=np.float32,
            )
            posed = np.asarray([deform(p, shoulder_deg, elbow_deg) for p in corners], dtype=np.float32)
            for tri in ((0, 1, 2), (0, 2, 3)):
                src_tri, dst_tri = corners[list(tri)], posed[list(tri)]
                dx, dy, dw, dh = cv2.boundingRect(dst_tri)
                l, t = max(0, dx), max(0, dy)
                r, b = min(WIDTH, dx + dw), min(HEIGHT, dy + dh)
                if l >= r or t >= b:
                    continue
                local = dst_tri - np.asarray([dx, dy], dtype=np.float32)
                tri_mask = np.zeros((dh, dw), dtype=np.uint8)
                cv2.fillConvexPoly(tri_mask, np.round(local).astype(np.int32), 255, cv2.LINE_8)
                inverse = cv2.getAffineTransform(dst_tri.astype(np.float32), src_tri.astype(np.float32))
                yy, xx = np.indices((b - t, r - l), dtype=np.float32)
                wx, wy = xx + l, yy + t
                sx = inverse[0, 0] * wx + inverse[0, 1] * wy + inverse[0, 2]
                sy = inverse[1, 0] * wx + inverse[1, 1] * wy + inverse[1, 2]
                take = tri_mask[t - dy : b - dy, l - dx : r - dx] > 0
                map_x[t:b, l:r][take] = sx[take]
                map_y[t:b, l:r][take] = sy[take]
    warped = cv2.remap(
        premultiplied(source),
        map_x,
        map_y,
        cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )
    return finish_warp(warped, largest_only=True)


def rigid_matrix(shoulder_deg: float, elbow_deg: float, hand_deg: float, bone: str) -> np.ndarray:
    upper_r, upper_t, fore_r, fore_t = bone_transforms(shoulder_deg, elbow_deg)
    if bone == "upper":
        return np.column_stack((upper_r, upper_t)).astype(np.float32)
    if bone == "plate":
        # A pauldron is clavicle armour, not painted onto the upper arm.  It
        # follows only a restrained fraction of the arm swing and continues to
        # cover the shoulder seam during the dagger extension.
        plate_r = rot(shoulder_deg * 0.28)
        plate_t = SHOULDER - plate_r @ SHOULDER
        return np.column_stack((plate_r, plate_t)).astype(np.float32)
    if bone == "fore":
        return np.column_stack((fore_r, fore_t)).astype(np.float32)
    if bone == "hand":
        wrist_after = fore_r @ WRIST + fore_t
        hand_r = rot(hand_deg)
        final_r = hand_r @ fore_r
        final_t = hand_r @ fore_t + wrist_after - hand_r @ wrist_after
        return np.column_stack((final_r, final_t)).astype(np.float32)
    raise ValueError(bone)


def rigid_warp(source: np.ndarray, shoulder_deg: float, elbow_deg: float, hand_deg: float, bone: str) -> np.ndarray:
    if abs(shoulder_deg) < 1e-9 and abs(elbow_deg) < 1e-9 and abs(hand_deg) < 1e-9:
        return source.copy()
    warped = cv2.warpAffine(
        premultiplied(source),
        rigid_matrix(shoulder_deg, elbow_deg, hand_deg, bone),
        (WIDTH, HEIGHT),
        cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )
    return finish_warp(warped, largest_only=False)


def load_parts() -> tuple[list[dict], dict[str, np.ndarray]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    parts: dict[str, np.ndarray] = {}
    for record in manifest["parts"]:
        image = np.asarray(Image.open(BASELINE / record["file"]).convert("RGBA"), dtype=np.uint8)
        canvas = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
        x, y, width, height = map(int, record["source_bbox"])
        canvas[y + PAD_Y : y + PAD_Y + height, x + PAD_X : x + PAD_X + width] = image
        parts[record["semantic"]] = canvas
    return manifest["parts"], parts


def render(records: list[dict], parts: dict[str, np.ndarray], arm_layers: dict[str, np.ndarray], case: dict) -> np.ndarray:
    result = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    result = alpha_over(result, mesh_warp(arm_layers["back"], case["shoulder"], case["elbow"]))
    inserted_front = False
    inserted_elbow = False
    inserted_shoulder = False
    for record in sorted(records, key=lambda item: (int(item["z"]), int(item["index"]))):
        z = int(record["z"])
        if not inserted_front and z >= 19:
            result = alpha_over(result, mesh_warp(arm_layers["front"], case["shoulder"], case["elbow"]))
            inserted_front = True
        if not inserted_elbow and z >= 20:
            result = alpha_over(result, mesh_warp(arm_layers["elbow"], case["shoulder"], case["elbow"]))
            inserted_elbow = True
        if not inserted_shoulder and z >= 21:
            result = alpha_over(result, mesh_warp(arm_layers["shoulder"], case["shoulder"], case["elbow"]))
            inserted_shoulder = True
        semantic = record["semantic"]
        source = parts[semantic]
        if semantic == "near_upper_arm":
            source = rigid_warp(source, case["shoulder"], case["elbow"], case["hand"], "upper")
        elif semantic == "near_shoulder_plate":
            source = rigid_warp(source, case["shoulder"], case["elbow"], case["hand"], "plate")
        elif semantic == "near_forearm":
            source = rigid_warp(source, case["shoulder"], case["elbow"], case["hand"], "fore")
        elif semantic in {"near_dagger_hand", "dagger"}:
            source = rigid_warp(source, case["shoulder"], case["elbow"], case["hand"], "hand")
        result = alpha_over(result, source)
    return result


def bounds(image: np.ndarray) -> list[int]:
    ys, xs = np.where(image[:, :, 3] > 16)
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def make_contact(frames: list[tuple[dict, np.ndarray]], output: Path) -> None:
    cols, rows = 4, 2
    cell_w, cell_h = 560, 500
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (27, 31, 39, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for i, (case, frame) in enumerate(frames):
        x, y = (i % cols) * cell_w, (i // cols) * cell_h
        draw.text((x + 10, y + 9), case["name"], fill=(242, 244, 248, 255), font=font)
        draw.text(
            (x + 10, y + 25),
            f"S {case['shoulder']:+.1f} / E {case['elbow']:+.1f} / H {case['hand']:+.1f}",
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
    records, parts = load_parts()
    arm_layers: dict[str, np.ndarray] = {}
    for name, path in ARM_LAYERS.items():
        source = np.asarray(Image.open(path).convert("RGBA"), dtype=np.uint8)
        padded = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
        padded[PAD_Y : PAD_Y + SOURCE_HEIGHT, PAD_X : PAD_X + SOURCE_WIDTH] = source
        arm_layers[name] = padded
    master_source = np.asarray(Image.open(MASTER).convert("RGBA"), dtype=np.uint8)
    master = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    master[PAD_Y : PAD_Y + SOURCE_HEIGHT, PAD_X : PAD_X + SOURCE_WIDTH] = master_source
    frames = []
    audits = []
    for case in CASES:
        frame = render(records, parts, arm_layers, case)
        Image.fromarray(frame, "RGBA").save(OUT / f"{case['name']}.png")
        mismatch = int(np.any(frame != master, axis=2).sum()) if case["name"] == "bind" else None
        audits.append({**case, "alpha_bounds": bounds(frame), "bind_mismatch_pixels": mismatch})
        frames.append((case, frame))
    make_contact(frames, OUT / "full_character_contact.jpg")
    report = {
        "schema_version": 1,
        "status": "full_character_topology_visual_review_required",
        "technique": "continuous context-reveal base + 2D rigid-transform blend + rigid semantic overlays",
        "draw_order": "near upper -> forearm -> shoulder plate -> dagger -> gripping hand",
        "mesh": {
            "bounds_xyxy": list(MESH_BOUNDS),
            "grid_step": GRID_STEP,
            "shoulder_xy": SHOULDER.tolist(),
            "elbow_xy": ELBOW.tolist(),
            "wrist_xy": WRIST.tolist(),
        },
        "cases": audits,
        "bind_exact_rgba": audits[0]["bind_mismatch_pixels"] == 0,
        "shipping_allowed": False,
        "steam_install_allowed": False,
        "next_gate": "reject_or_tune_attack_contact_before_full_body_motion",
    }
    if not report["bind_exact_rgba"]:
        raise RuntimeError(report)
    (OUT / "audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
