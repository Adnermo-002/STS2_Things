#!/usr/bin/env python3
"""Align the generated far-arm context plate to the immutable master."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
MASTER = HERE / "00_reference" / "locked_master.png"
TARGET = HERE / "00_reference" / "far_arm_context" / "far_arm_context_edit_target_alpha.png"
EDIT_MASK = HERE / "00_reference" / "far_arm_context" / "far_arm_context_edit_mask.png"
CANDIDATE = HERE / "01_imagegen_boards" / "far_arm_context_reveal_candidate_v01_alpha.png"
OUT = HERE / "02_semantic_parts" / "context_reveals" / "far_arm_v01"
CANVAS_SIZE = (1536, 1024)
MASTER_POS = (234, 92)
MASTER_SCALE = 2


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sift_align(target: np.ndarray, candidate: np.ndarray, edit_mask: np.ndarray) -> tuple[np.ndarray, dict]:
    exclusion = cv2.dilate((edit_mask > 127).astype(np.uint8), np.ones((101, 101), np.uint8), 1).astype(bool)

    def prep(rgba: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        gray = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2GRAY)
        valid = (rgba[:, :, 3] > 128) & ~exclusion
        prepared = np.full_like(gray, 24)
        prepared[valid] = gray[valid]
        return prepared, valid.astype(np.uint8) * 255

    target_gray, target_valid = prep(target)
    candidate_gray, candidate_valid = prep(candidate)
    sift = cv2.SIFT_create(nfeatures=12000, contrastThreshold=0.012, edgeThreshold=28)
    target_points, target_desc = sift.detectAndCompute(target_gray, target_valid)
    candidate_points, candidate_desc = sift.detectAndCompute(candidate_gray, candidate_valid)
    if target_desc is None or candidate_desc is None:
        raise RuntimeError("SIFT descriptors missing")
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(candidate_desc, target_desc, k=2)
    good = [a for a, b in pairs if a.distance < 0.74 * b.distance]
    if len(good) < 24:
        raise RuntimeError(f"insufficient identity matches: {len(good)}")
    src = np.float32([candidate_points[m.queryIdx].pt for m in good])
    dst = np.float32([target_points[m.trainIdx].pt for m in good])
    matrix, inliers = cv2.estimateAffinePartial2D(
        src,
        dst,
        method=cv2.RANSAC,
        ransacReprojThreshold=4.0,
        maxIters=8000,
        confidence=0.999,
        refineIters=80,
    )
    if matrix is None or inliers is None:
        raise RuntimeError("similarity alignment failed")
    aligned = cv2.warpAffine(
        candidate,
        matrix,
        CANVAS_SIZE,
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    valid = ~exclusion
    ta = (target[:, :, 3] > 64) & valid
    aa = (aligned[:, :, 3] > 64) & valid
    intersection = int((ta & aa).sum())
    union = int((ta | aa).sum())
    both = ta & aa
    delta = np.abs(target[:, :, :3].astype(np.int16) - aligned[:, :, :3].astype(np.int16)).mean(axis=2)[both]
    metrics = {
        "matrix": [[round(float(v), 9) for v in row] for row in matrix],
        "scale": round(float(np.hypot(matrix[0, 0], matrix[0, 1])), 9),
        "angle_deg": round(float(np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0]))), 9),
        "translation_xy": [round(float(matrix[0, 2]), 6), round(float(matrix[1, 2]), 6)],
        "target_keypoints": len(target_points),
        "candidate_keypoints": len(candidate_points),
        "ratio_matches": len(good),
        "inliers": int(inliers.sum()),
        "inlier_ratio": round(float(inliers.mean()), 6),
        "alpha_iou_outside_edit": round(intersection / max(1, union), 9),
        "rgb_abs_delta_outside_edit": {
            "mean": round(float(delta.mean()), 6),
            "median": round(float(np.median(delta)), 6),
            "p90": round(float(np.percentile(delta, 90)), 6),
        },
    }
    return aligned, metrics


def canvas_to_master(aligned: np.ndarray) -> np.ndarray:
    x, y = MASTER_POS
    width, height = Image.open(MASTER).size
    crop = aligned[y : y + height * MASTER_SCALE, x : x + width * MASTER_SCALE]
    return cv2.resize(crop, (width, height), interpolation=cv2.INTER_AREA)


def make_contact(master: np.ndarray, donor: np.ndarray, output: Path) -> None:
    width, height = 1200, 620
    contact = Image.new("RGBA", (width, height), (27, 31, 39, 255))
    draw = ImageDraw.Draw(contact)
    font = ImageFont.load_default()
    panels = [("LOCKED MASTER", master), ("ALIGNED DONOR / MASTER SPACE", donor)]
    for i, (label, rgba) in enumerate(panels):
        x = 24 + i * 590
        draw.text((x, 18), label, fill=(240, 242, 246, 255), font=font)
        image = Image.fromarray(rgba, "RGBA").resize((534, 420), Image.Resampling.NEAREST)
        contact.alpha_composite(image, (x, 48))
    delta = np.abs(master[:, :, :3].astype(np.int16) - donor[:, :, :3].astype(np.int16)).mean(axis=2)
    alpha = (master[:, :, 3] > 32) | (donor[:, :, 3] > 32)
    heat = np.zeros_like(master)
    heat[:, :, 0] = np.clip(delta * 4, 0, 255).astype(np.uint8)
    heat[:, :, 1] = np.clip(255 - delta * 3, 0, 255).astype(np.uint8)
    heat[:, :, 3] = np.where(alpha, 220, 0).astype(np.uint8)
    heat_img = Image.fromarray(heat, "RGBA").resize((534, 420), Image.Resampling.NEAREST)
    contact.alpha_composite(heat_img, (333, 492))
    draw.text((333, 476), "RGB DELTA HEAT (crop)", fill=(240, 242, 246, 255), font=font)
    contact.crop((0, 0, width, 620)).convert("RGB").save(output, quality=95)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master = np.asarray(Image.open(MASTER).convert("RGBA"), dtype=np.uint8)
    target = np.asarray(Image.open(TARGET).convert("RGBA"), dtype=np.uint8)
    candidate = np.asarray(Image.open(CANDIDATE).convert("RGBA"), dtype=np.uint8)
    edit_mask = np.asarray(Image.open(EDIT_MASK).convert("L"), dtype=np.uint8)
    aligned, metrics = sift_align(target, candidate, edit_mask)
    donor = canvas_to_master(aligned)
    Image.fromarray(aligned, "RGBA").save(OUT / "context_reveal_aligned.png")
    Image.fromarray(donor, "RGBA").save(OUT / "context_reveal_master_space.png")
    make_contact(master, donor, OUT / "alignment_contact.jpg")
    report = {
        "schema_version": 1,
        "status": "alignment_pass_semantic_extraction_pending",
        "identity_sha256": sha256(MASTER),
        "candidate_sha256": sha256(CANDIDATE),
        "alignment": metrics,
        "outputs": {
            "aligned": "context_reveal_aligned.png",
            "master_space": "context_reveal_master_space.png",
            "contact": "alignment_contact.jpg",
        },
        "shipping_allowed": False,
        "steam_install_allowed": False,
    }
    (OUT / "alignment.audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
