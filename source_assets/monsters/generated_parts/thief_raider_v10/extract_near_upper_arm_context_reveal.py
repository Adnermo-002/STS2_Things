#!/usr/bin/env python3
"""Align a full-character occlusion-reveal edit and extract one upper arm.

The generated edit is never used as a replacement character.  It contributes
only short, context-correct cloth pixels hidden beneath the pauldron and elbow
overlap.  Every bind-visible pixel remains byte-for-byte owned by the locked
master image.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[3]
MASTER_PATH = ROOT / "00_reference/current_master.png"
TARGET_PATH = ROOT / "00_reference/near_upper_arm_context_edit_target_alpha.png"
EDIT_MASK_PATH = ROOT / "00_reference/near_upper_arm_context_edit_mask.png"
CANDIDATE_PATH = ROOT / "01_image_to_image_families/near_upper_arm_context_reveal_candidate_01_alpha.png"
CORRECTED_ROOT = ROOT / "00_reference/near_arm_ownership_v2"
CORRECTED_MANIFEST = CORRECTED_ROOT / "near_arm_ownership_v2.manifest.json"
OUT = ROOT / "02_semantic_parts/near_upper_arm_context_01"

CANVAS_SIZE = (1536, 1024)
MASTER_POS = (234, 92)
MASTER_SCALE = 2


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _font(size: int) -> ImageFont.ImageFont:
    for path in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _load_visible_upper_arm(canvas_shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    manifest = json.loads(CORRECTED_MANIFEST.read_text(encoding="utf-8-sig"))
    source = manifest["corrected_parts"]["near_upper_arm"]
    crop = np.asarray(Image.open(CORRECTED_ROOT / source["file"]).convert("RGBA"), dtype=np.uint8)
    left, top, right, bottom = map(int, source["source_bbox_xyxy"])
    x, y, width, height = left, top, right - left, bottom - top
    if crop.shape[:2] != (height, width):
        raise RuntimeError(f"visible crop shape {crop.shape[:2]} does not match manifest {(height, width)}")
    canvas_h, canvas_w = canvas_shape
    rgba = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
    rgba[y : y + height, x : x + width] = crop
    mask = rgba[:, :, 3] > 0
    record = {
        "semantic": "near_upper_arm",
        "file": (CORRECTED_ROOT / source["file"]).relative_to(ROOT).as_posix(),
        "source_bbox_xyxy": source["source_bbox_xyxy"],
        "visible_pixel_count": source["visible_pixel_count"],
        "sha256": source["sha256"],
        "ownership_manifest": CORRECTED_MANIFEST.relative_to(ROOT).as_posix(),
    }
    return rgba, mask, record


def _sift_align(target: np.ndarray, candidate: np.ndarray, edit_mask: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
    exclusion = cv2.dilate((edit_mask > 127).astype(np.uint8), np.ones((81, 81), np.uint8), 1).astype(bool)

    def prep(rgba: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        gray = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2GRAY)
        valid = (rgba[:, :, 3] > 128) & ~exclusion
        prepared = np.full_like(gray, 24)
        prepared[valid] = gray[valid]
        return prepared, (valid.astype(np.uint8) * 255)

    target_gray, target_mask = prep(target)
    candidate_gray, candidate_mask = prep(candidate)
    sift = cv2.SIFT_create(nfeatures=8000, contrastThreshold=0.015, edgeThreshold=25)
    target_points, target_desc = sift.detectAndCompute(target_gray, target_mask)
    candidate_points, candidate_desc = sift.detectAndCompute(candidate_gray, candidate_mask)
    if target_desc is None or candidate_desc is None:
        raise RuntimeError("SIFT descriptors missing")
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(candidate_desc, target_desc, k=2)
    good = [first for first, second in pairs if first.distance < 0.72 * second.distance]
    if len(good) < 20:
        raise RuntimeError(f"not enough identity matches: {len(good)}")
    source = np.float32([candidate_points[match.queryIdx].pt for match in good])
    destination = np.float32([target_points[match.trainIdx].pt for match in good])
    matrix, inliers = cv2.estimateAffinePartial2D(
        source,
        destination,
        method=cv2.RANSAC,
        ransacReprojThreshold=4.0,
        maxIters=5000,
        confidence=0.999,
        refineIters=50,
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
    scale = float(np.hypot(matrix[0, 0], matrix[0, 1]))
    angle = float(np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0])))
    valid = ~exclusion
    target_alpha = (target[:, :, 3] > 64) & valid
    aligned_alpha = (aligned[:, :, 3] > 64) & valid
    intersection = int((target_alpha & aligned_alpha).sum())
    union = int((target_alpha | aligned_alpha).sum())
    both = target_alpha & aligned_alpha
    color_delta = np.abs(target[:, :, :3].astype(np.int16) - aligned[:, :, :3].astype(np.int16)).mean(axis=2)[both]
    metrics = {
        "matrix": [[round(float(value), 9) for value in row] for row in matrix],
        "scale": round(scale, 9),
        "angle_deg": round(angle, 9),
        "translation_xy": [round(float(matrix[0, 2]), 6), round(float(matrix[1, 2]), 6)],
        "target_keypoints": len(target_points),
        "candidate_keypoints": len(candidate_points),
        "ratio_matches": len(good),
        "inliers": int(inliers.sum()),
        "inlier_ratio": round(float(inliers.mean()), 6),
        "alpha_iou_outside_edit": round(intersection / max(1, union), 9),
        "rgb_abs_delta_outside_edit": {
            "mean": round(float(color_delta.mean()), 6),
            "median": round(float(np.median(color_delta)), 6),
            "p90": round(float(np.percentile(color_delta, 90)), 6),
        },
    }
    return aligned, metrics


def _canvas_to_master(aligned: np.ndarray) -> np.ndarray:
    x, y = MASTER_POS
    width, height = Image.open(MASTER_PATH).size
    crop = aligned[y : y + height * MASTER_SCALE, x : x + width * MASTER_SCALE]
    return cv2.resize(crop, (width, height), interpolation=cv2.INTER_AREA)


def _ellipse_mask(shape: tuple[int, int], center: tuple[int, int], axes: tuple[int, int], angle: float) -> np.ndarray:
    result = np.zeros(shape, dtype=np.uint8)
    cv2.ellipse(result, center, axes, angle, 0, 360, 255, -1, cv2.LINE_AA)
    return result > 0


def _fit_color(master: np.ndarray, donor: np.ndarray, overlap: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
    valid = overlap & (master[:, :, 3] >= 192) & (donor[:, :, 3] >= 192)
    if int(valid.sum()) < 100:
        raise RuntimeError(f"not enough sleeve pixels for color fit: {int(valid.sum())}")
    corrected = donor.copy()
    fit: dict[str, object] = {}
    for channel, name in enumerate(("r", "g", "b")):
        source = donor[:, :, channel][valid].astype(np.float32)
        destination = master[:, :, channel][valid].astype(np.float32)
        design = np.column_stack((source, np.ones_like(source)))
        slope, intercept = np.linalg.lstsq(design, destination, rcond=None)[0]
        slope = float(np.clip(slope, 0.80, 1.20))
        intercept = float(np.clip(intercept, -24.0, 24.0))
        corrected[:, :, channel] = np.clip(donor[:, :, channel].astype(np.float32) * slope + intercept, 0, 255).astype(np.uint8)
        before = np.abs(source - destination)
        after = np.abs(np.clip(source * slope + intercept, 0, 255) - destination)
        fit[name] = {
            "slope": round(slope, 7),
            "intercept": round(intercept, 7),
            "mae_before": round(float(before.mean()), 6),
            "mae_after": round(float(after.mean()), 6),
        }
    return corrected, fit


def _extract(master: np.ndarray, donor: np.ndarray, visible_rgba: np.ndarray, visible: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    hsv = cv2.cvtColor(donor[:, :, :3], cv2.COLOR_RGB2HSV)
    candidate_alpha = donor[:, :, 3] >= 80
    # Charcoal cloth is low-to-moderate saturation and deliberately dark.  The
    # two ellipses constrain the reveal to short joint overlaps rather than a
    # generated replacement limb.
    cloth = candidate_alpha & (hsv[:, :, 1] <= 90) & (hsv[:, :, 2] >= 22) & (hsv[:, :, 2] <= 145)
    shoulder = _ellipse_mask(visible.shape, (171, 230), (24, 18), -12.0)
    elbow = _ellipse_mask(visible.shape, (139, 284), (25, 18), -36.0)
    distance_to_visible = cv2.distanceTransform((~visible).astype(np.uint8), cv2.DIST_L2, 5)
    # A production underlap is a short cuff hidden behind its neighbour, not a
    # second generated limb.  Distance limits keep only the contextual reveal
    # immediately beyond each exact master boundary.
    allowed = (shoulder & (distance_to_visible <= 10.5)) | (elbow & (distance_to_visible <= 11.5))
    # Hidden overlap must be covered by some other master attachment in bind
    # pose.  Context reveal supplies its *material and semantic silhouette*;
    # the locked-master foreground intersection merely enforces zero bind leak.
    # This differs from the rejected v9 route, which used neighbouring master
    # silhouettes to invent the donor shape before any semantic reveal existed.
    hidden = cloth & allowed & ~visible & (master[:, :, 3] == 255)

    # Retain only hidden regions that touch the exact visible sleeve after a
    # very small antialias bridge.  This rejects torso/scarf/leg islands.
    union = visible | hidden
    count, labels, stats, _ = cv2.connectedComponentsWithStats(union.astype(np.uint8), 8)
    visible_labels = labels[visible]
    dominant = int(np.bincount(visible_labels[visible_labels > 0]).argmax())
    semantic_union = labels == dominant
    hidden &= semantic_union

    corrected, color_fit = _fit_color(master, donor, visible)
    attachment = np.zeros_like(master)
    attachment[hidden] = corrected[hidden]
    attachment[visible] = visible_rgba[visible]
    attachment[:, :, 3][hidden] = np.maximum(attachment[:, :, 3][hidden], donor[:, :, 3][hidden])

    component_count, _, component_stats, _ = cv2.connectedComponentsWithStats((attachment[:, :, 3] >= 24).astype(np.uint8), 8)
    components = sorted((int(component_stats[index, cv2.CC_STAT_AREA]) for index in range(1, component_count)), reverse=True)
    if len([area for area in components if area >= 8]) != 1:
        raise RuntimeError(f"attachment is not one semantic component: {components}")

    seam = cv2.dilate(visible.astype(np.uint8), np.ones((3, 3), np.uint8), 1).astype(bool) & hidden
    seam_delta = np.abs(attachment[:, :, :3].astype(np.int16) - master[:, :, :3].astype(np.int16)).mean(axis=2)[seam]
    metrics = {
        "visible_pixels": int(visible.sum()),
        "hidden_pixels": int(hidden.sum()),
        "hidden_to_visible_ratio": round(float(hidden.sum() / max(1, visible.sum())), 6),
        "components_over_8px": [area for area in components if area >= 8],
        "color_fit": color_fit,
        "seam_pixels": int(seam.sum()),
        "seam_rgb_delta_mean": round(float(seam_delta.mean()), 6) if len(seam_delta) else None,
        "seam_rgb_delta_p90": round(float(np.percentile(seam_delta, 90)), 6) if len(seam_delta) else None,
    }
    return attachment, hidden, metrics


def _make_contact(master: np.ndarray, aligned: np.ndarray, donor_master: np.ndarray, attachment: np.ndarray, hidden: np.ndarray) -> Image.Image:
    contact = Image.new("RGBA", (1600, 1080), (28, 31, 37, 255))
    draw = ImageDraw.Draw(contact)
    panels = [
        ("LOCKED MASTER", Image.fromarray(master, "RGBA")),
        ("ALIGNED CONTEXT REVEAL", Image.fromarray(aligned, "RGBA")),
        ("REVEAL IN MASTER SPACE", Image.fromarray(donor_master, "RGBA")),
        ("EXACT VISIBLE + HIDDEN ONLY", Image.fromarray(attachment, "RGBA")),
    ]
    positions = [(30, 70), (810, 70), (30, 590), (810, 590)]
    sizes = [(720, 460), (720, 460), (720, 430), (720, 430)]
    for (title, image), (x, y), (width, height) in zip(panels, positions, sizes):
        draw.text((x, y - 40), title, font=_font(25), fill=(238, 241, 246, 255))
        checker = Image.new("RGBA", (width, height), (38, 42, 50, 255))
        src = image.copy()
        bbox = src.getchannel("A").getbbox()
        if bbox:
            src = src.crop(bbox)
        scale = min(width / max(1, src.width), height / max(1, src.height))
        shown = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))), Image.Resampling.LANCZOS)
        checker.alpha_composite(shown, ((width - shown.width) // 2, (height - shown.height) // 2))
        contact.alpha_composite(checker, (x, y))
    # Put the hidden mask over the lower-right panel in cyan for quick review.
    hidden_img = np.zeros((*hidden.shape, 4), dtype=np.uint8)
    hidden_img[hidden] = (35, 235, 235, 190)
    overlay = Image.fromarray(hidden_img, "RGBA")
    bbox = overlay.getchannel("A").getbbox()
    if bbox:
        overlay = overlay.crop(bbox).resize((260, 210), Image.Resampling.NEAREST)
        contact.alpha_composite(overlay, (1320, 845))
        draw.text((1320, 815), "CYAN = GENERATED HIDDEN PIXELS", font=_font(14), fill=(70, 245, 245, 255))
    return contact


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master = np.asarray(Image.open(MASTER_PATH).convert("RGBA"), dtype=np.uint8)
    target = np.asarray(Image.open(TARGET_PATH).convert("RGBA"), dtype=np.uint8)
    candidate = np.asarray(Image.open(CANDIDATE_PATH).convert("RGBA"), dtype=np.uint8)
    edit_mask = np.asarray(Image.open(EDIT_MASK_PATH).convert("L"), dtype=np.uint8)
    visible_rgba, visible, visible_record = _load_visible_upper_arm(master.shape[:2])

    aligned, alignment = _sift_align(target, candidate, edit_mask)
    donor_master = _canvas_to_master(aligned)
    attachment, hidden, extraction = _extract(master, donor_master, visible_rgba, visible)

    Image.fromarray(aligned, "RGBA").save(OUT / "context_reveal_aligned.png")
    Image.fromarray(donor_master, "RGBA").save(OUT / "context_reveal_master_space.png")
    hidden_rgba = np.zeros_like(master)
    hidden_rgba[hidden] = attachment[hidden]
    Image.fromarray(hidden_rgba, "RGBA").save(OUT / "near_upper_arm_hidden_only.png")
    Image.fromarray(attachment, "RGBA").save(OUT / "near_upper_arm_attachment.png")

    bind = Image.fromarray(hidden_rgba, "RGBA")
    bind.alpha_composite(Image.fromarray(master, "RGBA"))
    bind.save(OUT / "full_bind_preview.png")
    contact = _make_contact(master, aligned, donor_master, attachment, hidden)
    contact.convert("RGB").save(OUT / "contact.jpg", quality=95)

    bind_array = np.asarray(bind.convert("RGBA"), dtype=np.uint8)
    bind_exact = bool(np.array_equal(bind_array, master))
    report = {
        "schema_version": 1,
        "status": "static_extraction_pass_extreme_pose_pending",
        "identity_master": MASTER_PATH.relative_to(ROOT).as_posix(),
        "identity_sha256": _sha256(MASTER_PATH),
        "candidate": CANDIDATE_PATH.relative_to(ROOT).as_posix(),
        "candidate_sha256": _sha256(CANDIDATE_PATH),
        "visible_source": visible_record,
        "policy": "candidate supplies hidden local cloth only; all bind-visible pixels are exact current-master pixels",
        "alignment": alignment,
        "extraction": extraction,
        "full_bind_rgba_exact": bind_exact,
        "outputs": {
            "aligned": "context_reveal_aligned.png",
            "master_space": "context_reveal_master_space.png",
            "hidden_only": "near_upper_arm_hidden_only.png",
            "attachment": "near_upper_arm_attachment.png",
            "bind": "full_bind_preview.png",
            "contact": "contact.jpg",
        },
        "shipping_allowed": False,
        "steam_install_allowed": False,
        "next_gate": "full_chain_shoulder_elbow_extreme_pose_visual_review",
    }
    (OUT / "audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        "THIEF_V10_NEAR_UPPER_ARM_CONTEXT_EXTRACT "
        f"status={report['status']} hidden={extraction['hidden_pixels']} "
        f"alpha_iou={alignment['alpha_iou_outside_edit']} bind_exact={str(bind_exact).lower()}"
    )


if __name__ == "__main__":
    main()
