#!/usr/bin/env python3
"""Create the clean v8 linked cutouts with tightly bounded joint underlap.

The rejected v7 pipeline added hidden material equal to 58.73% of the master.
This builder has no full-body underpaint, caps every dilation radius at 24 px,
and fails when total hidden underlap exceeds 18% of master alpha.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
MASTER = ROOT / "01_master_candidates/candidate_01_alpha.png"
OWNED = ROOT / "03_clean_parts/master_owned_parts"
OUT = ROOT / "03_clean_parts/linked_parts"
MANIFEST = ROOT / "03_clean_parts/linked_parts.json"
RECONSTRUCTION = ROOT / "03_clean_parts/linked_bind_reconstruction.png"
CONTACT = ROOT / "03_clean_parts/linked_parts_contact.png"

DRAW_ORDER = (
    "cape_back",
    "loot_sack",
    "sack_knot",
    "far_lower_leg_boot",
    "far_thigh",
    "near_lower_leg_boot",
    "near_thigh",
    "pelvis_coat",
    "torso_core",
    "dagger_upper_arm",
    "free_upper_arm",
    "hooded_head",
    "scarf_front",
    "dagger_shoulder_plate",
    "free_shoulder_plate",
    "dagger_forearm",
    "free_forearm",
    "dagger",
    "dagger_hand",
    "free_hand",
    "belt",
    "eye_glow",
)

# source -> (later covering attachments, dilation radius)
UNDERLAP = {
    "cape_back": (("loot_sack", "sack_knot", "far_thigh", "far_lower_leg_boot", "near_thigh", "near_lower_leg_boot", "pelvis_coat", "torso_core", "dagger_upper_arm", "free_upper_arm", "hooded_head", "scarf_front", "dagger_shoulder_plate", "free_shoulder_plate", "dagger_forearm", "free_forearm"), 14),
    "loot_sack": (("sack_knot", "free_upper_arm", "free_shoulder_plate", "torso_core"), 10),
    "far_thigh": (("pelvis_coat",), 10),
    "far_lower_leg_boot": (("far_thigh", "pelvis_coat"), 12),
    "near_thigh": (("pelvis_coat",), 10),
    "near_lower_leg_boot": (("near_thigh", "pelvis_coat"), 12),
    "pelvis_coat": (("torso_core", "belt"), 10),
    "torso_core": (("hooded_head", "scarf_front", "dagger_upper_arm", "free_upper_arm", "dagger_forearm", "free_forearm", "dagger_hand", "free_hand", "belt", "dagger_shoulder_plate", "free_shoulder_plate"), 8),
    "dagger_upper_arm": (("dagger_shoulder_plate", "dagger_forearm", "scarf_front"), 10),
    "free_upper_arm": (("free_shoulder_plate", "free_forearm", "scarf_front"), 10),
    "hooded_head": (("scarf_front", "eye_glow"), 10),
    "scarf_front": (("free_shoulder_plate", "dagger_shoulder_plate", "free_hand"), 8),
    "dagger_forearm": (("dagger_hand",), 8),
    "free_forearm": (("free_hand",), 8),
    "dagger": (("dagger_hand",), 8),
}


def load_owned() -> dict[str, np.ndarray]:
    parts: dict[str, np.ndarray] = {}
    for path in sorted(OWNED.glob("*.png")):
        semantic = path.stem.split("_", 1)[1]
        parts[semantic] = np.array(Image.open(path).convert("RGBA"))
    required = set(DRAW_ORDER) - {"near_lower_leg_boot", "far_lower_leg_boot"}
    required |= {"near_boot", "near_shin", "far_boot", "far_shin"}
    missing = sorted(required - set(parts))
    if missing:
        raise RuntimeError(f"missing master-owned inputs: {missing}")
    return parts


def merge(parts: dict[str, np.ndarray], output: str, inputs: tuple[str, ...]) -> None:
    canvas = np.zeros_like(next(iter(parts.values())))
    for name in inputs:
        image = parts.pop(name)
        mask = image[:, :, 3] > 0
        canvas[mask] = image[mask]
    parts[output] = canvas


def nearest_fill(source: np.ndarray, addition: np.ndarray) -> np.ndarray:
    result = source.copy()
    visible = source[:, :, 3] > 0
    if not visible.any() or not addition.any():
        return result
    distance_input = np.where(visible, 0, 255).astype(np.uint8)
    _, labels = cv2.distanceTransformWithLabels(
        distance_input, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL
    )
    colors = np.zeros((int(labels.max()) + 1, 4), np.uint8)
    colors[labels[visible]] = source[visible]
    fill = colors[labels]
    result[addition, :3] = fill[addition, :3]
    result[addition, 3] = 255
    return result


def alpha_composite(dst: np.ndarray, src: np.ndarray, x: int, y: int) -> None:
    height, width = src.shape[:2]
    region = dst[y:y + height, x:x + width]
    src_a = src[:, :, 3:4].astype(np.float32) / 255.0
    dst_a = region[:, :, 3:4].astype(np.float32) / 255.0
    out_a = src_a + dst_a * (1.0 - src_a)
    numerator = (
        src[:, :, :3].astype(np.float32) * src_a
        + region[:, :, :3].astype(np.float32) * dst_a * (1.0 - src_a)
    )
    region[:, :, :3] = np.where(
        out_a > 0, numerator / np.maximum(out_a, 1.0e-8), 0
    ).round().clip(0, 255).astype(np.uint8)
    region[:, :, 3:4] = (out_a * 255.0).round().clip(0, 255).astype(np.uint8)


def main() -> None:
    master = np.array(Image.open(MASTER).convert("RGBA"))
    parts = load_owned()
    merge(parts, "near_lower_leg_boot", ("near_shin", "near_boot"))
    merge(parts, "far_lower_leg_boot", ("far_shin", "far_boot"))
    extra = sorted(set(parts) - set(DRAW_ORDER))
    missing = sorted(set(DRAW_ORDER) - set(parts))
    if extra or missing:
        raise RuntimeError(f"clean draw-order mismatch extra={extra} missing={missing}")

    visible_alpha = {name: parts[name][:, :, 3] > 0 for name in DRAW_ORDER}
    underlap_area: dict[str, int] = {name: 0 for name in DRAW_ORDER}
    order_index = {name: index for index, name in enumerate(DRAW_ORDER)}
    for name, (covers, radius) in UNDERLAP.items():
        if radius > 24:
            raise RuntimeError(f"{name}: underlap radius exceeds 24px")
        invalid = [cover for cover in covers if order_index[cover] <= order_index[name]]
        if invalid:
            raise RuntimeError(f"{name}: underlap covers must be later slots, got {invalid}")
        cover = np.zeros(master.shape[:2], bool)
        for cover_name in covers:
            cover |= visible_alpha[cover_name]
        visible = visible_alpha[name]
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
        expanded = cv2.dilate(visible.astype(np.uint8), kernel) > 0
        addition = expanded & ~visible & cover
        parts[name] = nearest_fill(parts[name], addition)
        underlap_area[name] = int(addition.sum())

    master_area = int((master[:, :, 3] > 0).sum())
    total_underlap = int(sum(underlap_area.values()))
    ratio = total_underlap / max(1, master_area)
    if ratio > 0.18:
        largest = sorted(underlap_area.items(), key=lambda item: item[1], reverse=True)[:8]
        raise RuntimeError(
            f"hidden underlap ratio {ratio:.4f} exceeds 0.18 "
            f"({total_underlap}/{master_area}); largest={largest}"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.png"):
        stale.unlink()
    records: list[dict[str, object]] = []
    for index, name in enumerate(DRAW_ORDER):
        image = parts[name]
        ys, xs = np.where(image[:, :, 3] > 0)
        if not len(xs):
            raise RuntimeError(f"empty linked part: {name}")
        pad = 5
        x0 = max(0, int(xs.min()) - pad)
        y0 = max(0, int(ys.min()) - pad)
        x1 = min(image.shape[1], int(xs.max()) + 1 + pad)
        y1 = min(image.shape[0], int(ys.max()) + 1 + pad)
        crop = image[y0:y1, x0:x1]
        filename = f"{index:02d}_{name}.png"
        Image.fromarray(crop, "RGBA").save(OUT / filename)
        records.append(
            {
                "index": index,
                "semantic": name,
                "file": f"linked_parts/{filename}",
                "canvas_origin_xy": [x0, y0],
                "visible_alpha_area": int(visible_alpha[name].sum()),
                "hidden_underlap_area": underlap_area[name],
                "draw_order": index,
            }
        )

    reconstruction = np.zeros_like(master)
    for record in records:
        image = np.array(Image.open(ROOT / "03_clean_parts" / record["file"]).convert("RGBA"))
        x, y = map(int, record["canvas_origin_xy"])
        alpha_composite(reconstruction, image, x, y)
    Image.fromarray(reconstruction, "RGBA").save(RECONSTRUCTION)

    ma = master[:, :, 3] > 0
    ra = reconstruction[:, :, 3] > 0
    intersection = int((ma & ra).sum())
    union = int((ma | ra).sum())
    rgb_mae = float(
        np.abs(master[:, :, :3].astype(np.int16) - reconstruction[:, :, :3].astype(np.int16))[ma].mean()
    )
    qa = {
        "alpha_iou": intersection / max(1, union),
        "alpha_area_ratio": int(ra.sum()) / max(1, int(ma.sum())),
        "visible_rgb_mae_0_255": rgb_mae,
        "master_alpha_area": master_area,
        "hidden_underlap_area": total_underlap,
        "hidden_underlap_ratio": ratio,
        "part_count": len(records),
        "unmanifested_png_count": len(list(OUT.glob("*.png"))) - len(records),
    }
    qa["pass"] = (
        qa["alpha_iou"] >= 0.995
        and 0.995 <= qa["alpha_area_ratio"] <= 1.005
        and qa["visible_rgb_mae_0_255"] <= 2.0
        and qa["hidden_underlap_ratio"] <= 0.18
        and qa["unmanifested_png_count"] == 0
    )
    if not qa["pass"]:
        raise RuntimeError(f"linked bind QA failed: {qa}")

    # Contact sheet contains cropped attachments, making excessive fake bodies
    # or hollow joint geometry immediately visible.
    thumb_w, thumb_h, cols = 250, 220, 5
    rows = math.ceil(len(records) / cols)
    contact = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (36, 40, 47))
    draw = ImageDraw.Draw(contact)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 17)
    except OSError:
        font = ImageFont.load_default()
    for record in records:
        image = Image.open(ROOT / "03_clean_parts" / record["file"]).convert("RGBA")
        image.thumbnail((thumb_w - 20, thumb_h - 52), Image.Resampling.LANCZOS)
        index = int(record["index"])
        col, row = index % cols, index // cols
        x = col * thumb_w + (thumb_w - image.width) // 2
        y = row * thumb_h + 34 + (thumb_h - 48 - image.height) // 2
        contact.paste(image, (x, y), image)
        label = f"{record['semantic']}  +{record['hidden_underlap_area']}"
        draw.text((col * thumb_w + 6, row * thumb_h + 7), label, fill=(235,235,235), font=font)
    contact.save(CONTACT)

    MANIFEST.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "master": MASTER.relative_to(ROOT).as_posix(),
                "visible_pixel_source": "single_v8_master_only",
                "hidden_underlap_method": "bounded_same_attachment_nearest_fill_under_later_slots",
                "status": "linked_cutout_draft_requires_extreme_pose_review",
                "draw_order": list(DRAW_ORDER),
                "parts": records,
                "bind_qa": qa,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"THIEF_V8_LINKED_PARTS_PASS parts={len(records)} "
        f"underlap={total_underlap} ratio={ratio:.4f} iou={qa['alpha_iou']:.6f}"
    )


if __name__ == "__main__":
    main()
