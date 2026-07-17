#!/usr/bin/env python3
"""Promote the accepted context reveal into a draw-order-safe near-arm base."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


HERE = Path(__file__).resolve().parent
BASELINE = HERE / "00_reference" / "visible_baseline"
MANIFEST = BASELINE / "visible_baseline.manifest.json"
SOURCE = HERE / "02_semantic_parts" / "context_reveals" / "near_arm_v01" / "context_reveal_master_space.png"
MASTER = HERE / "00_reference" / "locked_master.png"
OUT = HERE / "02_semantic_parts" / "context_reveals" / "near_arm_v01"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    owner_z = np.full((420, 534), -999, dtype=np.int16)
    owner_alpha = np.zeros((420, 534), dtype=np.uint8)
    for record in manifest["parts"]:
        image = np.asarray(Image.open(BASELINE / record["file"]).convert("RGBA"), dtype=np.uint8)
        x, y, width, height = map(int, record["source_bbox"])
        alpha = image[:, :, 3] > 0
        owner_z[y : y + height, x : x + width][alpha] = int(record["z"])
        owner_alpha[y : y + height, x : x + width][alpha] = image[:, :, 3][alpha]

    donor = np.asarray(Image.open(SOURCE).convert("RGBA"), dtype=np.uint8)
    hsv = cv2.cvtColor(donor[:, :, :3], cv2.COLOR_RGB2HSV)
    yy, xx = np.indices((420, 534), dtype=np.float32)
    points = np.stack((xx, yy), axis=-1)
    shoulder = np.asarray([171.0, 224.0], dtype=np.float32)
    elbow = np.asarray([139.0, 283.0], dtype=np.float32)
    wrist = np.asarray([110.0, 321.0], dtype=np.float32)

    def segment(start: np.ndarray, end: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        vector = end - start
        parameter = ((points - start) * vector).sum(axis=2) / float(vector @ vector)
        nearest = start + np.clip(parameter, 0.0, 1.0)[:, :, None] * vector
        distance = np.linalg.norm(points - nearest, axis=2)
        return parameter, distance

    upper_t, upper_distance = segment(shoulder, elbow)
    fore_t, fore_distance = segment(elbow, wrist)
    upper_radius = 22.5 - 2.5 * np.clip(upper_t, 0.0, 1.0)
    fore_radius = 19.5 - 2.0 * np.clip(fore_t, 0.0, 1.0)
    semantic_tube = (
        ((upper_t >= -0.10) & (upper_t <= 1.12) & (upper_distance <= upper_radius))
        | ((fore_t >= -0.16) & (fore_t <= 1.12) & (fore_distance <= fore_radius))
    )
    source_mask = (
        (donor[:, :, 3] >= 80)
        & (hsv[:, :, 1] <= 95)
        & (hsv[:, :, 2] >= 18)
        & (hsv[:, :, 2] <= 150)
        & semantic_tube
    )
    component_count, component_labels, component_stats, _ = cv2.connectedComponentsWithStats(source_mask.astype(np.uint8), 8)
    component_index = 1 + int(np.argmax(component_stats[1:, cv2.CC_STAT_AREA]))
    source_mask = component_labels == component_index
    source_mask = cv2.morphologyEx(source_mask.astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)) > 0
    source_mask &= (donor[:, :, 3] >= 40) & semantic_tube
    component_count, component_labels, component_stats, _ = cv2.connectedComponentsWithStats(source_mask.astype(np.uint8), 8)
    component_index = 1 + int(np.argmax(component_stats[1:, cv2.CC_STAT_AREA]))
    source_mask = component_labels == component_index
    source = np.zeros_like(donor)
    source[source_mask] = donor[source_mask]
    Image.fromarray(source, "RGBA").save(OUT / "near_arm_cloth_base_semantic_source.png")
    # The base is inserted immediately before z=19 near_upper_arm.  Retaining
    # only pixels owned by z>=19 guarantees that exact earlier layers never get
    # painted over in setup.
    opaque_cover = owner_alpha == 255
    back_keep = source_mask & (owner_z < 19) & (owner_z >= 0) & opaque_cover
    front_keep = source_mask & (owner_z >= 19) & opaque_cover
    keep = back_keep | front_keep
    count, labels, stats, _ = cv2.connectedComponentsWithStats(keep.astype(np.uint8), 8)
    index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    keep = labels == index
    back_keep &= keep
    front_keep &= keep

    elbow_region = np.zeros((420, 534), dtype=np.uint8)
    cv2.ellipse(elbow_region, (139, 283), (27, 23), -36.0, 0, 360, 255, -1, cv2.LINE_AA)
    elbow_keep = keep & (elbow_region > 0) & (owner_z >= 20) & opaque_cover
    shoulder_region = np.zeros((420, 534), dtype=np.uint8)
    cv2.ellipse(shoulder_region, (171, 224), (29, 24), -12.0, 0, 360, 255, -1, cv2.LINE_AA)
    shoulder_keep = keep & (shoulder_region > 0) & (owner_z >= 21) & opaque_cover

    def write_layer(name: str, mask: np.ndarray) -> np.ndarray:
        layer = np.zeros_like(source)
        layer[mask] = source[mask]
        Image.fromarray(layer, "RGBA").save(OUT / name)
        return layer

    base = write_layer("near_arm_cloth_base.png", keep)
    base_back = write_layer("near_arm_cloth_base_back.png", back_keep)
    base_front = write_layer("near_arm_cloth_base_front.png", front_keep)
    elbow_overlay = write_layer("near_elbow_context_overlay.png", elbow_keep)
    shoulder_overlay = write_layer("near_shoulder_context_overlay.png", shoulder_keep)
    base_path = OUT / "near_arm_cloth_base.png"

    master = np.asarray(Image.open(MASTER).convert("RGBA"), dtype=np.uint8)
    # Rebuild through the actual z insertion point rather than merely placing
    # the master on top, proving the draw-order contract itself.
    result = np.zeros_like(master)
    # Back fragment sits beneath the character.
    result = np.asarray(Image.fromarray(result, "RGBA"), dtype=np.uint8)
    composed = Image.fromarray(result, "RGBA")
    composed.alpha_composite(Image.fromarray(base_back, "RGBA"))
    result = np.asarray(composed, dtype=np.uint8)
    inserted_front = False
    inserted_elbow = False
    inserted_shoulder = False
    for record in sorted(manifest["parts"], key=lambda item: (int(item["z"]), int(item["index"]))):
        z = int(record["z"])
        if not inserted_front and z >= 19:
            layer = Image.fromarray(result, "RGBA")
            layer.alpha_composite(Image.fromarray(base_front, "RGBA"))
            result = np.asarray(layer, dtype=np.uint8)
            inserted_front = True
        if not inserted_elbow and z >= 20:
            layer = Image.fromarray(result, "RGBA")
            layer.alpha_composite(Image.fromarray(elbow_overlay, "RGBA"))
            result = np.asarray(layer, dtype=np.uint8)
            inserted_elbow = True
        if not inserted_shoulder and z >= 21:
            layer = Image.fromarray(result, "RGBA")
            layer.alpha_composite(Image.fromarray(shoulder_overlay, "RGBA"))
            result = np.asarray(layer, dtype=np.uint8)
            inserted_shoulder = True
        crop = np.asarray(Image.open(BASELINE / record["file"]).convert("RGBA"), dtype=np.uint8)
        x, y, width, height = map(int, record["source_bbox"])
        canvas = np.zeros_like(master)
        canvas[y : y + height, x : x + width] = crop
        layer = Image.fromarray(result, "RGBA")
        layer.alpha_composite(Image.fromarray(canvas, "RGBA"))
        result = np.asarray(layer, dtype=np.uint8)
    mismatch = int(np.any(result != master, axis=2).sum())
    Image.fromarray(result, "RGBA").save(OUT / "near_arm_draw_order_bind_preview.png")

    report = {
        "schema_version": 1,
        "status": "draw_order_safe_continuous_base_pass",
        "source_pixels": int(source_mask.sum()),
        "kept_pixels": int(keep.sum()),
        "removed_before_z19_or_outside": int(source_mask.sum() - keep.sum()),
        "back_pixels": int(back_keep.sum()),
        "front_pixels": int(front_keep.sum()),
        "elbow_overlay_pixels": int(elbow_keep.sum()),
        "shoulder_overlay_pixels": int(shoulder_keep.sum()),
        "components": [int(stats[index, cv2.CC_STAT_AREA])],
        "insert_before_z": 19,
        "bind_mismatch_pixels": mismatch,
        "bind_exact_rgba": mismatch == 0,
        "output": "near_arm_cloth_base.png",
        "next_gate": "full_character_two_dimensional_mesh_pose_review",
    }
    if mismatch:
        raise RuntimeError(report)
    (OUT / "near_arm_cloth_base.audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
