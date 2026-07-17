#!/usr/bin/env python3
"""Render full-character QA poses for the continuous far-arm cloth mesh.

Unlike the rejected v10 strip warp, this prototype interpolates full 2D rigid
transforms (rotation plus translation) across a two-dimensional weight field.
Local cross-section is therefore preserved through the elbow blend.  Exact
master-owned armor, hand and all unrelated character pixels remain separate.
"""

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
ARM_BASE = HERE / "02_semantic_parts" / "context_reveals" / "far_arm_v01" / "far_arm_cloth_base.png"
OUT = HERE / "03_bind_review" / "far_arm_mesh_v01"

WIDTH, HEIGHT = 534, 420
SHOULDER = np.asarray([332.0, 154.0], dtype=np.float32)
ELBOW = np.asarray([367.0, 194.0], dtype=np.float32)
WRIST = np.asarray([302.0, 194.0], dtype=np.float32)
MESH_BOUNDS = (278, 102, 406, 250)
GRID_STEP = 4


CASES = [
    {"name": "bind", "shoulder": 0.0, "elbow": 0.0},
    {"name": "idle_inhale", "shoulder": -1.5, "elbow": 2.0},
    {"name": "idle_exhale", "shoulder": 1.0, "elbow": -1.5},
    {"name": "attack_windup", "shoulder": -6.0, "elbow": 8.0},
    {"name": "attack_contact", "shoulder": 4.0, "elbow": -6.0},
    {"name": "hurt_brace", "shoulder": -10.0, "elbow": 12.0},
]


def alpha_over(bottom: np.ndarray, top: np.ndarray) -> np.ndarray:
    image = Image.fromarray(bottom, "RGBA")
    image.alpha_composite(Image.fromarray(top, "RGBA"))
    return np.asarray(image, dtype=np.uint8)


def rotation(angle_deg: float) -> np.ndarray:
    angle = math.radians(angle_deg)
    return np.asarray([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]], dtype=np.float32)


def transforms(shoulder_deg: float, elbow_deg: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    upper_r = rotation(shoulder_deg)
    upper_t = SHOULDER - upper_r @ SHOULDER
    elbow_after = upper_r @ ELBOW + upper_t
    fore_r = rotation(shoulder_deg + elbow_deg)
    fore_t = elbow_after - fore_r @ ELBOW
    return upper_r, upper_t, fore_r, fore_t


def project_segment(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> tuple[float, float]:
    vector = end - start
    t = float(np.clip(np.dot(point - start, vector) / np.dot(vector, vector), 0.0, 1.0))
    nearest = start + vector * t
    return t, float(np.linalg.norm(point - nearest))


def smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def fore_weight(point: np.ndarray) -> float:
    upper_t, upper_d = project_segment(point, SHOULDER, ELBOW)
    fore_t, fore_d = project_segment(point, ELBOW, WRIST)
    upper_len = float(np.linalg.norm(ELBOW - SHOULDER))
    fore_len = float(np.linalg.norm(WRIST - ELBOW))
    if upper_d <= fore_d:
        chain = upper_t * upper_len
    else:
        chain = upper_len + fore_t * fore_len
    chain_weight = smoothstep((chain - (upper_len - 14.0)) / 28.0)
    distance_weight = upper_d * upper_d / max(1e-5, upper_d * upper_d + fore_d * fore_d)
    return float(np.clip(chain_weight * 0.78 + distance_weight * 0.22, 0.0, 1.0))


def deform_point(point: np.ndarray, shoulder_deg: float, elbow_deg: float) -> np.ndarray:
    upper_r, upper_t, fore_r, fore_t = transforms(shoulder_deg, elbow_deg)
    weight = fore_weight(point)
    # Interpolate the rigid transform itself, not the two transformed points.
    # This avoids the LBS elbow collapse seen in the rejected v10 prototype.
    angle = shoulder_deg + elbow_deg * weight
    blended_r = rotation(angle)
    blended_t = upper_t * (1.0 - weight) + fore_t * weight
    return blended_r @ point + blended_t


def mesh_warp(source: np.ndarray, shoulder_deg: float, elbow_deg: float) -> np.ndarray:
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
            posed = np.asarray([deform_point(p, shoulder_deg, elbow_deg) for p in corners], dtype=np.float32)
            for tri in ((0, 1, 2), (0, 2, 3)):
                src_tri = corners[list(tri)]
                dst_tri = posed[list(tri)]
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
    return cv2.remap(source, map_x, map_y, cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))


def rigid_warp(source: np.ndarray, shoulder_deg: float, elbow_deg: float, bone: str) -> np.ndarray:
    upper_r, upper_t, fore_r, fore_t = transforms(shoulder_deg, elbow_deg)
    if bone == "upper":
        matrix = np.column_stack((upper_r, upper_t)).astype(np.float32)
    elif bone == "fore":
        matrix = np.column_stack((fore_r, fore_t)).astype(np.float32)
    else:
        raise ValueError(bone)
    return cv2.warpAffine(source, matrix, (WIDTH, HEIGHT), cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))


def load_parts() -> tuple[list[dict], dict[str, np.ndarray]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    parts: dict[str, np.ndarray] = {}
    for record in manifest["parts"]:
        canvas = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
        image = np.asarray(Image.open(BASELINE / record["file"]).convert("RGBA"), dtype=np.uint8)
        x, y, w, h = map(int, record["source_bbox"])
        canvas[y : y + h, x : x + w] = image
        parts[record["semantic"]] = canvas
    return manifest["parts"], parts


def render_case(records: list[dict], parts: dict[str, np.ndarray], arm_base: np.ndarray, shoulder_deg: float, elbow_deg: float) -> np.ndarray:
    result = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    # The generated base is behind every exact master-owned layer.  This keeps
    # setup identical while still filling joint gaps as armor moves.
    result = alpha_over(result, mesh_warp(arm_base, shoulder_deg, elbow_deg))
    for record in sorted(records, key=lambda item: (int(item["z"]), int(item["index"]))):
        semantic = record["semantic"]
        source = parts[semantic]
        if semantic == "far_forearm":
            source = rigid_warp(source, shoulder_deg, elbow_deg, "fore")
        elif semantic == "far_shoulder_plate":
            source = rigid_warp(source, shoulder_deg, elbow_deg, "upper")
        elif semantic == "far_strap_hand":
            source = rigid_warp(source, shoulder_deg, elbow_deg, "fore")
        result = alpha_over(result, source)
    return result


def alpha_bounds(image: np.ndarray) -> list[int]:
    ys, xs = np.where(image[:, :, 3] > 16)
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def make_contact(frames: list[tuple[dict, np.ndarray]], output: Path) -> None:
    cols, rows = 3, 2
    cell_w, cell_h = 620, 520
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (27, 31, 39, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for i, (case, frame) in enumerate(frames):
        x = (i % cols) * cell_w
        y = (i // cols) * cell_h
        draw.text((x + 12, y + 10), case["name"], fill=(242, 244, 248, 255), font=font)
        draw.text(
            (x + 12, y + 27),
            f"shoulder {case['shoulder']:+.1f} / elbow {case['elbow']:+.1f}",
            fill=(155, 216, 240, 255),
            font=font,
        )
        shown = Image.fromarray(frame, "RGBA")
        sheet.alpha_composite(shown, (x + 40, y + 58))
    sheet.convert("RGB").save(output, quality=95)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records, parts = load_parts()
    arm_base = np.asarray(Image.open(ARM_BASE).convert("RGBA"), dtype=np.uint8)
    master = np.asarray(Image.open(HERE / "00_reference" / "locked_master.png").convert("RGBA"), dtype=np.uint8)
    frames: list[tuple[dict, np.ndarray]] = []
    audits = []
    for case in CASES:
        frame = render_case(records, parts, arm_base, case["shoulder"], case["elbow"])
        frame_path = OUT / f"{case['name']}.png"
        Image.fromarray(frame, "RGBA").save(frame_path)
        bind_mismatch = int(np.any(frame != master, axis=2).sum()) if case["name"] == "bind" else None
        audits.append({**case, "alpha_bounds": alpha_bounds(frame), "bind_mismatch_pixels": bind_mismatch})
        frames.append((case, frame))
    make_contact(frames, OUT / "full_character_contact.jpg")
    report = {
        "schema_version": 1,
        "status": "full_character_visual_review_required",
        "technique": "two-dimensional rigid-transform blend mesh plus exact rigid overlays",
        "mesh": {
            "bounds_xyxy": list(MESH_BOUNDS),
            "grid_step": GRID_STEP,
            "shoulder_xy": SHOULDER.tolist(),
            "elbow_xy": ELBOW.tolist(),
            "wrist_xy": WRIST.tolist(),
            "weight": "78% arc-length smoothstep + 22% nearest-segment distance",
        },
        "cases": audits,
        "bind_exact_rgba": audits[0]["bind_mismatch_pixels"] == 0,
        "shipping_allowed": False,
        "steam_install_allowed": False,
        "next_gate": "visual review at full character scale before Spine mesh export",
    }
    if not report["bind_exact_rgba"]:
        raise RuntimeError(f"bind reconstruction drifted: {audits[0]}")
    (OUT / "audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
