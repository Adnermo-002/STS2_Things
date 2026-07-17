#!/usr/bin/env python3
"""Create master-faithful linked cutouts with hidden joint underlap.

Visible bind pixels come only from the coherent master.  Underlap colors are a
nearest-pixel continuation of the same attachment and are restricted to pixels
covered by a later draw-order attachment in bind pose.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
MASTER_PATH = ROOT / "master_candidate_01_alpha.png"
OWNED = ROOT / "master_owned_parts"
DONORS = ROOT / "donor_parts"
OUT = ROOT / "linked_parts"
MANIFEST = ROOT / "linked_parts.generated.json"
QA_IMAGE = ROOT / "linked_bind_reconstruction.png"
QA_JSON = ROOT / "linked_bind.qa.json"

DRAW_ORDER = [
    "cape_back",
    "loot_sack",
    "sack_knot",
    "sack_strap",
    "body_underpaint",
    "pelvis_waist_cloth",
    "far_thigh",
    "far_shin",
    "far_boot",
    "near_thigh",
    "near_shin",
    "near_boot",
    "far_upper_arm",
    "near_upper_arm",
    "torso_core",
    "far_shoulder_plate",
    "far_forearm",
    "hooded_head",
    "eye_glow",
    "near_shoulder_plate",
    "near_forearm",
    "dagger",
    "near_dagger_hand",
    "belt_and_pouch",
    "far_hand_strap_grip",
    "scarf_front",
]


def load_owned() -> dict[str, np.ndarray]:
    parts: dict[str, np.ndarray] = {}
    for path in sorted(OWNED.glob("*.png")):
        name = path.stem.split("_", 1)[1]
        parts[name] = np.array(Image.open(path).convert("RGBA"))
    return parts


def split_mask(
    source: np.ndarray,
    selector: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    selected = source.copy()
    selected[:, :, 3] = np.where(selector, source[:, :, 3], 0)
    rest = source.copy()
    rest[:, :, 3] = np.where(selector, 0, source[:, :, 3])
    return rest, selected


def nearest_fill(source: np.ndarray, add_mask: np.ndarray) -> np.ndarray:
    result = source.copy()
    visible = source[:, :, 3] > 0
    if not visible.any() or not add_mask.any():
        return result
    distance_input = np.where(visible, 0, 255).astype(np.uint8)
    _, labels = cv2.distanceTransformWithLabels(
        distance_input,
        cv2.DIST_L2,
        5,
        labelType=cv2.DIST_LABEL_PIXEL,
    )
    max_label = int(labels.max())
    colors = np.zeros((max_label + 1, 4), np.uint8)
    visible_labels = labels[visible]
    colors[visible_labels] = source[visible]
    fill = colors[labels]
    result[add_mask, :3] = fill[add_mask, :3]
    result[add_mask, 3] = 255
    return result


def render_donor(
    filename: str,
    canvas_size: tuple[int, int],
    center_xy: tuple[float, float],
    scale_xy: tuple[float, float],
) -> np.ndarray:
    donor = Image.open(DONORS / filename).convert("RGBA")
    donor = donor.resize(
        (
            max(1, round(donor.width * scale_xy[0])),
            max(1, round(donor.height * scale_xy[1])),
        ),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    x = round(center_xy[0] - donor.width / 2)
    y = round(center_xy[1] - donor.height / 2)
    canvas.alpha_composite(donor, (x, y))
    return np.array(canvas)


def dilated_underlap(
    source: np.ndarray,
    cover_alpha: np.ndarray,
    radius: int,
) -> np.ndarray:
    visible = source[:, :, 3] > 0
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
    expanded = cv2.dilate(visible.astype(np.uint8), kernel) > 0
    return expanded & ~visible & cover_alpha


def main() -> None:
    master = np.array(Image.open(MASTER_PATH).convert("RGBA"))
    parts = load_owned()
    h, w = master.shape[:2]

    # Merge cape bands into one mesh-ready attachment.
    cape = np.zeros_like(master)
    for name in ("cape_upper", "cape_mid", "cape_tail"):
        piece = parts.pop(name)
        mask = piece[:, :, 3] > 0
        cape[mask] = piece[mask]
    parts["cape_back"] = cape

    # Separate eye glow and shoulder cover plates from their parent regions.
    rgb = master[:, :, :3].astype(np.int16)
    eye_selector = (
        (parts["hooded_head"][:, :, 3] > 0)
        & (rgb[:, :, 0] > 175)
        & (rgb[:, :, 1] > 135)
        & (rgb[:, :, 2] < 175)
    )
    parts["hooded_head"], parts["eye_glow"] = split_mask(parts["hooded_head"], eye_selector)

    bright_neutral = (
        (rgb.mean(axis=2) > 98)
        & ((rgb.max(axis=2) - rgb.min(axis=2)) < 62)
    )
    near_plate_region = np.zeros((h, w), np.uint8)
    cv2.fillPoly(near_plate_region, [np.array([(380, 520), (490, 520), (510, 625), (380, 635)], np.int32)], 255)
    near_plate_selector = (
        (parts["near_upper_arm"][:, :, 3] > 0)
        & (near_plate_region > 0)
        & bright_neutral
    )
    parts["near_upper_arm"], parts["near_shoulder_plate"] = split_mask(parts["near_upper_arm"], near_plate_selector)

    far_plate_region = np.zeros((h, w), np.uint8)
    cv2.fillPoly(far_plate_region, [np.array([(690, 370), (870, 370), (875, 520), (700, 525)], np.int32)], 255)
    far_plate_selector = (
        (parts["far_upper_arm"][:, :, 3] > 0)
        & (far_plate_region > 0)
        & bright_neutral
    )
    parts["far_upper_arm"], parts["far_shoulder_plate"] = split_mask(parts["far_upper_arm"], far_plate_selector)

    expected_visible = [name for name in DRAW_ORDER if name != "body_underpaint"]
    missing = [name for name in expected_visible if name not in parts]
    extra = [name for name in parts if name not in DRAW_ORDER]
    if missing or extra:
        raise RuntimeError(f"Draw-order mismatch missing={missing} extra={extra}")

    alpha = {name: parts[name][:, :, 3] > 0 for name in parts}
    donor_underpaint = {
        "torso_core": render_donor(
            "05_torso_core.png", (w, h), (650, 610), (1.42, 1.40)
        ),
        "pelvis_waist_cloth": render_donor(
            "07_pelvis_waist_cloth.png", (w, h), (650, 742), (1.72, 1.28)
        ),
    }
    # A coherent hidden body base remains behind the moving cutouts. It is
    # clipped to the original master silhouette, so it changes zero bind pixels
    # but prevents black wedges when shoulders/hips open during motion.
    torso_donor = donor_underpaint["torso_core"]
    pelvis_donor = donor_underpaint["pelvis_waist_cloth"]
    body_underpaint = np.array(
        Image.alpha_composite(
            Image.fromarray(torso_donor, "RGBA"),
            Image.fromarray(pelvis_donor, "RGBA"),
        )
    )
    central = np.zeros((h, w), np.uint8)
    cv2.fillPoly(
        central,
        [np.array([(390, 390), (900, 380), (965, 720), (900, 930), (390, 930)], np.int32)],
        255,
    )
    keep_underpaint = (
        (body_underpaint[:, :, 3] > 0)
        & (master[:, :, 3] > 0)
        & (central > 0)
    )
    body_underpaint[:, :, 3] = np.where(
        keep_underpaint, body_underpaint[:, :, 3], 0
    )
    parts["body_underpaint"] = body_underpaint
    alpha["body_underpaint"] = body_underpaint[:, :, 3] > 0

    # source -> (later covering attachments, dilation radius)
    underlap_specs = {
        "cape_back": (("torso_core", "pelvis_waist_cloth", "hooded_head", "scarf_front", "near_upper_arm", "far_upper_arm", "near_thigh", "far_thigh"), 120),
        "loot_sack": (("sack_knot", "sack_strap", "far_upper_arm", "far_forearm", "torso_core"), 54),
        "sack_strap": (("far_hand_strap_grip", "torso_core"), 18),
        "pelvis_waist_cloth": (("near_thigh", "far_thigh", "belt_and_pouch", "torso_core"), 64),
        "torso_core": (("near_upper_arm", "near_forearm", "far_upper_arm", "far_forearm", "far_hand_strap_grip", "hooded_head", "scarf_front", "belt_and_pouch", "pelvis_waist_cloth"), 84),
        "far_shin": (("far_boot",), 22),
        "far_thigh": (("far_shin",), 28),
        "far_upper_arm": (("torso_core", "far_shoulder_plate", "far_forearm"), 32),
        "far_forearm": (("far_hand_strap_grip",), 18),
        "near_shin": (("near_boot",), 22),
        "near_thigh": (("near_shin",), 28),
        "hooded_head": (("scarf_front",), 24),
        "near_upper_arm": (("torso_core", "scarf_front", "near_shoulder_plate", "near_forearm"), 42),
        "near_forearm": (("near_dagger_hand",), 18),
        "dagger": (("near_dagger_hand",), 20),
    }

    visible_area = {}
    underlap_area = {}
    for name, (covers, radius) in underlap_specs.items():
        cover = np.zeros((h, w), bool)
        for cover_name in covers:
            cover |= alpha[cover_name]
        if name in donor_underpaint:
            donor = donor_underpaint[name]
            addition = (donor[:, :, 3] > 0) & cover & ~(parts[name][:, :, 3] > 0)
        else:
            addition = dilated_underlap(parts[name], cover, radius)
        visible_area[name] = int(alpha[name].sum())
        underlap_area[name] = int(addition.sum())
        if name in donor_underpaint:
            donor = donor_underpaint[name]
            parts[name][addition] = donor[addition]
        else:
            parts[name] = nearest_fill(parts[name], addition)
    for name in parts:
        visible_area.setdefault(name, int(alpha[name].sum()))
        underlap_area.setdefault(name, 0)

    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for index, name in enumerate(DRAW_ORDER):
        image = parts[name]
        ys, xs = np.where(image[:, :, 3] > 0)
        if len(xs) == 0:
            raise RuntimeError(f"Empty linked part: {name}")
        pad = 4
        x0, y0 = max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad)
        x1, y1 = min(w, int(xs.max()) + 1 + pad), min(h, int(ys.max()) + 1 + pad)
        crop = image[y0:y1, x0:x1]
        filename = f"{index:02d}_{name}.png"
        Image.fromarray(crop, "RGBA").save(OUT / filename)
        records.append(
            {
                "index": index,
                "semantic": name,
                "file": f"linked_parts/{filename}",
                "canvas_origin_xy": [x0, y0],
                "visible_alpha_area": visible_area[name],
                "hidden_underlap_area": underlap_area[name],
                "draw_order": index,
            }
        )

    # Recompose at original coordinates and require exact visible bind pixels.
    composite = np.zeros_like(master)
    for record in records:
        image = np.array(Image.open(ROOT / record["file"]).convert("RGBA"))
        x0, y0 = record["canvas_origin_xy"]
        y1, x1 = y0 + image.shape[0], x0 + image.shape[1]
        src_a = image[:, :, 3:4].astype(np.float32) / 255.0
        dst = composite[y0:y1, x0:x1]
        dst_a = dst[:, :, 3:4].astype(np.float32) / 255.0
        out_a = src_a + dst_a * (1.0 - src_a)
        src_rgb = image[:, :, :3].astype(np.float32)
        dst_rgb = dst[:, :, :3].astype(np.float32)
        numerator = src_rgb * src_a + dst_rgb * dst_a * (1.0 - src_a)
        out_rgb = np.where(out_a > 0, numerator / np.maximum(out_a, 1e-8), 0)
        dst[:, :, :3] = np.clip(np.rint(out_rgb), 0, 255).astype(np.uint8)
        dst[:, :, 3:4] = np.clip(np.rint(out_a * 255), 0, 255).astype(np.uint8)

    Image.fromarray(composite, "RGBA").save(QA_IMAGE)
    ma = master[:, :, 3] > 0
    ca = composite[:, :, 3] > 0
    intersection = int((ma & ca).sum())
    union = int((ma | ca).sum())
    iou = intersection / max(1, union)
    area_ratio = int(ca.sum()) / max(1, int(ma.sum()))
    visible = ma
    mae = float(np.abs(master[:, :, :3].astype(np.int16) - composite[:, :, :3].astype(np.int16))[visible].mean())
    ys_m, xs_m = np.where(ma)
    ys_c, xs_c = np.where(ca)
    centroid_delta = float(np.hypot(xs_m.mean() - xs_c.mean(), ys_m.mean() - ys_c.mean()))
    qa = {
        "alpha_iou": iou,
        "alpha_area_ratio": area_ratio,
        "centroid_delta_px": centroid_delta,
        "visible_rgb_mae_0_255": mae,
        "part_count": len(records),
        "hidden_underlap_area": int(sum(underlap_area.values())),
        "pass": iou >= 0.985 and 0.99 <= area_ratio <= 1.01 and centroid_delta <= 1.0 and mae <= 3.0,
    }
    QA_JSON.write_text(json.dumps(qa, indent=2), encoding="utf-8")
    MANIFEST.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "master": MASTER_PATH.name,
                "part_count": len(records),
                "visible_pixel_source": "master_only",
                "underlap_method": "nearest same-attachment master pixel, restricted to bind-covered regions",
                "draw_order": DRAW_ORDER,
                "parts": records,
                "bind_qa": qa,
                "status": "linked_cutout_draft_requires_extreme_pose_review",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"THIEF_V7_LINKED_PARTS parts={len(records)} underlap={qa['hidden_underlap_area']} bind_pass={qa['pass']}")
    print(json.dumps(qa, indent=2))


if __name__ == "__main__":
    main()
