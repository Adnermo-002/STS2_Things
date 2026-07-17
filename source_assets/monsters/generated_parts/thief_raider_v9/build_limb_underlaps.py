#!/usr/bin/env python3
"""Build local, generated-texture limb underlaps for Thief Raider v9.

Sheet B2 is never used as a visible replacement.  Its painted material is
registered to the current master, clipped to small real joint zones, and drawn
behind the exact master-owned visible layers.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
MASTER_PATH = ROOT / "00_reference/current_master.png"
PRODUCTION_ROOT = ROOT / "04_production_attachments"
VISIBLE_MANIFEST = PRODUCTION_ROOT / "production_visible.manifest.json"
DONOR_MANIFEST = ROOT / "02_extracted_donors/sheet_b2.manifest.json"
UNDERLAP_DIR = PRODUCTION_ROOT / "underlap_limbs"
COMBINED_DIR = PRODUCTION_ROOT / "combined_limb_preview"
MANIFEST_PATH = PRODUCTION_ROOT / "limb_underlap.manifest.json"
CONTACT_PATH = PRODUCTION_ROOT / "limb_underlap.contact.png"
COMBINED_CONTACT_PATH = PRODUCTION_ROOT / "combined_limb_preview.contact.png"


# Local hidden zones.  They are deliberately small and remain inside the
# current master silhouette at bind pose.
JOINT_ZONES = {
    "near_upper_arm": [(169, 232, 15), (138, 282, 12)],
    "near_forearm": [(138, 282, 12), (116, 331, 10)],
    "near_thigh": [(221, 279, 17), (215, 344, 14)],
    "near_shin": [(215, 344, 14), (225, 377, 12)],
    "near_boot": [(225, 377, 13)],
    "far_upper_arm": [(334, 170, 16), (350, 204, 13)],
    "far_forearm": [(350, 204, 13), (290, 187, 10)],
    "far_thigh": [(354, 282, 17), (382, 345, 14)],
    "far_shin": [(382, 345, 14), (401, 376, 12)],
    "far_boot": [(401, 376, 13)],
}


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _load_visible(canvas: tuple[int, int]) -> tuple[dict[str, np.ndarray], dict[str, dict]]:
    data = json.loads(VISIBLE_MANIFEST.read_text(encoding="utf-8"))
    masks: dict[str, np.ndarray] = {}
    records: dict[str, dict] = {}
    for record in data["parts"]:
        full = np.zeros((canvas[1], canvas[0]), dtype=bool)
        x, y, width, height = map(int, record["source_bbox"])
        rgba = np.asarray(
            Image.open(PRODUCTION_ROOT / record["file"]).convert("RGBA"),
            dtype=np.uint8,
        )
        local = rgba[:, :, 3] > 0
        full[y:y + height, x:x + width] = local
        semantic = str(record["semantic"])
        masks[semantic] = full
        records[semantic] = record
    return masks, records


def _load_donors() -> dict[str, tuple[np.ndarray, Path, dict]]:
    data = json.loads(DONOR_MANIFEST.read_text(encoding="utf-8"))
    result = {}
    for record in data["parts"]:
        semantic = str(record["semantic"])
        if semantic not in JOINT_ZONES:
            continue
        path = ROOT / "02_extracted_donors" / record["file"]
        result[semantic] = (
            np.asarray(Image.open(path).convert("RGBA"), dtype=np.uint8),
            path,
            record,
        )
    return result


def _pca(mask: np.ndarray) -> tuple[np.ndarray, float]:
    ys, xs = np.where(mask)
    if len(xs) < 2:
        raise RuntimeError("PCA mask has fewer than two pixels")
    points = np.column_stack((xs, ys)).astype(np.float64)
    center = points.mean(axis=0)
    covariance = np.cov(points - center, rowvar=False)
    values, vectors = np.linalg.eigh(covariance)
    axis = vectors[:, int(np.argmax(values))]
    angle = math.atan2(float(axis[1]), float(axis[0]))
    return center, angle


def _capsule_mask(shape: tuple[int, int], zones: list[tuple[int, int, int]]) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    for x, y, radius in zones:
        cv2.circle(mask, (x, y), radius, 255, -1, lineType=cv2.LINE_AA)
    if len(zones) >= 2:
        for first, second in zip(zones, zones[1:]):
            width = max(4, int(round(min(first[2], second[2]) * 1.45)))
            cv2.line(mask, (first[0], first[1]), (second[0], second[1]), 255, width, cv2.LINE_AA)
    return mask > 0


def _alignment_target(
    semantic: str,
    visible: np.ndarray,
) -> np.ndarray:
    capsule = _capsule_mask(visible.shape, JOINT_ZONES[semantic])
    if np.any(visible):
        kernel = np.ones((7, 7), np.uint8)
        closed = cv2.morphologyEx(visible.astype(np.uint8), cv2.MORPH_CLOSE, kernel, iterations=2)
        return (closed > 0) | capsule
    return capsule


def _warp_matrix(
    source_mask: np.ndarray,
    target_mask: np.ndarray,
) -> tuple[np.ndarray, dict[str, float]]:
    source_center, source_angle = _pca(source_mask)
    target_center, target_angle = _pca(target_mask)
    source_area = max(1, int(source_mask.sum()))
    target_area = max(1, int(target_mask.sum()))
    base_scale = math.sqrt(target_area / source_area)
    allowed = cv2.dilate(target_mask.astype(np.uint8), np.ones((13, 13), np.uint8), 1) > 0

    best: tuple[float, np.ndarray, dict[str, float]] | None = None
    base_angle = math.degrees(target_angle - source_angle)
    for flip in (0.0, 180.0):
        for delta in (-30.0, -20.0, -10.0, 0.0, 10.0, 20.0, 30.0):
            angle = base_angle + flip + delta
            for factor in (0.72, 0.84, 0.94, 1.0, 1.08, 1.18, 1.32):
                scale = base_scale * factor
                matrix = cv2.getRotationMatrix2D(
                    (float(source_center[0]), float(source_center[1])),
                    angle,
                    scale,
                )
                transformed_center = matrix[:, :2] @ source_center + matrix[:, 2]
                matrix[0, 2] += float(target_center[0] - transformed_center[0])
                matrix[1, 2] += float(target_center[1] - transformed_center[1])
                warped = cv2.warpAffine(
                    source_mask.astype(np.uint8),
                    matrix,
                    (target_mask.shape[1], target_mask.shape[0]),
                    flags=cv2.INTER_NEAREST,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=0,
                ) > 0
                warped_area = max(1, int(warped.sum()))
                intersection = int((warped & target_mask).sum())
                union = max(1, int((warped | target_mask).sum()))
                coverage = intersection / max(1, int(target_mask.sum()))
                iou = intersection / union
                outside_ratio = int((warped & ~allowed).sum()) / warped_area
                score = coverage * 3.5 + iou * 1.5 - outside_ratio * 2.0
                metrics = {
                    "angle_deg": round(angle, 4),
                    "scale": round(scale, 6),
                    "coverage": round(coverage, 6),
                    "iou": round(iou, 6),
                    "outside_ratio": round(outside_ratio, 6),
                    "score": round(score, 6),
                }
                if best is None or score > best[0]:
                    best = (score, matrix.copy(), metrics)
    if best is None:
        raise RuntimeError("donor alignment search produced no candidate")
    return best[1], best[2]


def _nearest_rgba_fill(warped: np.ndarray, wanted: np.ndarray) -> np.ndarray:
    valid = warped[:, :, 3] > 24
    if not np.any(valid):
        raise RuntimeError("warped donor has no valid pixels")
    inverse = (~valid).astype(np.uint8)
    _, labels = cv2.distanceTransformWithLabels(
        inverse,
        cv2.DIST_L2,
        5,
        labelType=cv2.DIST_LABEL_PIXEL,
    )
    valid_labels = labels[valid]
    valid_coords = np.argwhere(valid)
    max_label = int(labels.max())
    map_y = np.zeros(max_label + 1, dtype=np.int32)
    map_x = np.zeros(max_label + 1, dtype=np.int32)
    # One coordinate per unique zero-pixel label.
    for label, (y, x) in zip(valid_labels, valid_coords):
        map_y[int(label)] = int(y)
        map_x[int(label)] = int(x)
    nearest_y = map_y[labels]
    nearest_x = map_x[labels]
    filled = warped.copy()
    missing = wanted & ~valid
    filled[missing, :3] = warped[nearest_y[missing], nearest_x[missing], :3]
    return filled


def _crop_save(rgba: np.ndarray, path: Path) -> tuple[list[int], int]:
    mask = rgba[:, :, 3] > 0
    if not np.any(mask):
        Image.fromarray(np.zeros((1, 1, 4), dtype=np.uint8), "RGBA").save(path)
        return [0, 0, 1, 1], 0
    ys, xs = np.where(mask)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    Image.fromarray(rgba[y0:y1, x0:x1], "RGBA").save(path)
    return [x0, y0, x1 - x0, y1 - y0], int(mask.sum())


def main() -> None:
    master = np.asarray(Image.open(MASTER_PATH).convert("RGBA"), dtype=np.uint8)
    height, width = master.shape[:2]
    master_foreground = master[:, :, 3] > 0
    visible_masks, visible_records = _load_visible((width, height))
    donors = _load_donors()
    if set(donors) != set(JOINT_ZONES):
        raise RuntimeError(f"donor mismatch: {sorted(set(JOINT_ZONES) ^ set(donors))}")

    UNDERLAP_DIR.mkdir(parents=True, exist_ok=True)
    COMBINED_DIR.mkdir(parents=True, exist_ok=True)
    for folder in (UNDERLAP_DIR, COMBINED_DIR):
        for stale in folder.glob("*.png"):
            stale.unlink()

    records = []
    total_hidden = 0
    for index, semantic in enumerate(JOINT_ZONES):
        donor, donor_path, donor_record = donors[semantic]
        donor_mask = donor[:, :, 3] > 24
        visible = visible_masks[semantic]
        target = _alignment_target(semantic, visible)
        matrix, metrics = _warp_matrix(donor_mask, target)
        warped = cv2.warpAffine(
            donor,
            matrix,
            (width, height),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )

        joint_zone = _capsule_mask((height, width), JOINT_ZONES[semantic])
        hidden_mask = joint_zone & master_foreground & ~visible
        warped = _nearest_rgba_fill(warped, hidden_mask)
        # Two-pixel soft alpha at the outer joint-zone edge.
        inside_distance = cv2.distanceTransform(hidden_mask.astype(np.uint8), cv2.DIST_L2, 5)
        alpha = np.clip(inside_distance * 150.0, 0, 255).astype(np.uint8)
        underlap = np.zeros_like(master)
        underlap[hidden_mask, :3] = warped[hidden_mask, :3]
        underlap[:, :, 3] = np.where(hidden_mask, alpha, 0)

        underlap_path = UNDERLAP_DIR / f"{index:02d}_{semantic}_underlap.png"
        underlap_bbox, hidden_pixels = _crop_save(underlap, underlap_path)
        total_hidden += hidden_pixels

        combined = underlap.copy()
        combined[visible] = master[visible]
        combined_path = COMBINED_DIR / f"{index:02d}_{semantic}.png"
        combined_bbox, combined_pixels = _crop_save(combined, combined_path)
        records.append(
            {
                "index": index,
                "semantic": semantic,
                "bone": visible_records[semantic]["bone"],
                "pivot_source_xy": visible_records[semantic]["pivot_source_xy"],
                "donor": donor_path.relative_to(ROOT).as_posix(),
                "donor_status": donor_record["status"],
                "alignment": metrics,
                "underlap_file": f"underlap_limbs/{underlap_path.name}",
                "underlap_bbox": underlap_bbox,
                "hidden_pixel_count": hidden_pixels,
                "combined_preview_file": f"combined_limb_preview/{combined_path.name}",
                "combined_bbox": combined_bbox,
                "combined_pixel_count": combined_pixels,
                "underlap_sha256": hashlib.sha256(underlap_path.read_bytes()).hexdigest(),
                "status": "local_generated_texture_underlap_extreme_pose_pending",
            }
        )

    hidden_ratio = total_hidden / max(1, int(master_foreground.sum()))
    manifest = {
        "schema_version": 1,
        "identity_source": MASTER_PATH.relative_to(ROOT).as_posix(),
        "donor_manifest": DONOR_MANIFEST.relative_to(ROOT).as_posix(),
        "policy": "B2 contributes hidden local joint texture only; visible pixels remain current-master-owned",
        "part_count": len(records),
        "total_hidden_pixels": total_hidden,
        "hidden_to_master_area_ratio": round(hidden_ratio, 6),
        "hidden_area_gate": {"minimum": 0.04, "maximum": 0.18},
        "status": (
            "limb_underlap_area_pass_extreme_pose_pending"
            if 0.04 <= hidden_ratio <= 0.18
            else "limb_underlap_area_fail"
        ),
        "parts": records,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def contact(source_key: str, output_path: Path, title_suffix: str) -> None:
        tile_w, tile_h, columns = 270, 230, 4
        rows = math.ceil(len(records) / columns)
        canvas = Image.new("RGB", (columns * tile_w, rows * tile_h), (29, 32, 38))
        draw = ImageDraw.Draw(canvas)
        font, small = _font(15), _font(12)
        for record in records:
            image = Image.open(PRODUCTION_ROOT / record[source_key]).convert("RGBA")
            image.thumbnail((tile_w - 20, tile_h - 62), Image.Resampling.LANCZOS)
            idx = int(record["index"])
            col, row = idx % columns, idx // columns
            x = col * tile_w + (tile_w - image.width) // 2
            y = row * tile_h + 48 + (tile_h - 52 - image.height) // 2
            canvas.paste(image, (x, y), image)
            left, top = col * tile_w + 7, row * tile_h + 6
            draw.text((left, top), f"{record['semantic']} {title_suffix}", fill=(240, 240, 240), font=font)
            draw.text(
                (left, top + 21),
                f"hidden={record['hidden_pixel_count']} cov={record['alignment']['coverage']:.2f}",
                fill=(245, 184, 78),
                font=small,
            )
        canvas.save(output_path)

    contact("underlap_file", CONTACT_PATH, "underlap")
    contact("combined_preview_file", COMBINED_CONTACT_PATH, "combined")
    print(
        "THIEF_V9_LIMB_UNDERLAP_BUILD "
        f"status={manifest['status']} parts={len(records)} hidden_ratio={hidden_ratio:.4f}"
    )


if __name__ == "__main__":
    main()
