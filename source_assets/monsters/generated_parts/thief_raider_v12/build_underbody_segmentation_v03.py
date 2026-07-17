#!/usr/bin/env python3
"""Split the intact generated underbody into semantic one-bone attachments.

The source remains an intact painted character while ownership masks partition
its visible pixels.  Each exported attachment also receives opaque neighboring
pixels as hidden underlap.  This avoids both rectangular crops and hollow
garment ends while preserving an exact static reconstruction.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from extract_semantic_parts_v01 import sha256


HERE = Path(__file__).resolve().parent
ROOT = HERE / "02_semantic_parts" / "underbody_context_v03"
SOURCE = ROOT / "underbody_context_candidate_v03_alpha.png"
OUT = ROOT / "segmentation_v01"

WIDTH, HEIGHT = 1536, 1024

# Bind-pose bone segments in source-canvas coordinates.  The segment endpoints
# are later reused as pivots for the rig prototype.
BONES = [
    {"name": "hooded_head", "a": (630, 250), "b": (650, 390), "underlap": 26},
    {"name": "torso", "a": (760, 330), "b": (795, 595), "underlap": 60},
    {"name": "pelvis", "a": (760, 575), "b": (825, 650), "underlap": 55},
    {"name": "near_upper_arm", "a": (655, 395), "b": (570, 545), "underlap": 48},
    {"name": "near_forearm", "a": (570, 545), "b": (465, 690), "underlap": 42},
    {"name": "near_hand", "a": (465, 690), "b": (430, 735), "underlap": 18},
    {"name": "far_upper_arm", "a": (820, 300), "b": (950, 405), "underlap": 42},
    {"name": "far_forearm", "a": (950, 405), "b": (855, 465), "underlap": 40},
    {"name": "far_hand", "a": (855, 465), "b": (800, 445), "underlap": 18},
    {"name": "near_thigh", "a": (730, 620), "b": (655, 715), "underlap": 42},
    {"name": "near_boot", "a": (655, 715), "b": (690, 830), "underlap": 34},
    {"name": "far_thigh", "a": (865, 620), "b": (980, 715), "underlap": 42},
    {"name": "far_boot", "a": (980, 715), "b": (1070, 820), "underlap": 34},
]

# Region penalties keep nearby bent limbs from stealing torso/leg pixels.
BOUNDS = {
    "hooded_head": (475, 120, 785, 465),
    "torso": (560, 230, 1025, 700),
    "pelvis": (570, 510, 1030, 720),
    "near_upper_arm": (500, 330, 730, 625),
    "near_forearm": (390, 470, 635, 735),
    "near_hand": (382, 660, 502, 790),
    "far_upper_arm": (735, 230, 1025, 495),
    "far_forearm": (780, 340, 1030, 550),
    "far_hand": (748, 388, 865, 515),
    "near_thigh": (555, 540, 830, 780),
    "near_boot": (550, 680, 805, 900),
    "far_thigh": (770, 530, 1050, 800),
    "far_boot": (900, 650, 1165, 900),
}

DRAW_ORDER = [
    "far_boot",
    "far_thigh",
    "near_boot",
    "near_thigh",
    "far_upper_arm",
    "near_upper_arm",
    "pelvis",
    "torso",
    "far_forearm",
    "far_hand",
    "near_forearm",
    "near_hand",
    "hooded_head",
]

NEIGHBORS = {
    "hooded_head": {"torso", "near_upper_arm", "far_upper_arm"},
    "torso": {"hooded_head", "pelvis", "near_upper_arm", "far_upper_arm", "far_forearm"},
    "pelvis": {"torso", "near_thigh", "far_thigh"},
    "near_upper_arm": {"torso", "near_forearm"},
    "near_forearm": {"near_upper_arm", "near_hand"},
    "near_hand": {"near_forearm"},
    "far_upper_arm": {"torso", "far_forearm"},
    "far_forearm": {"far_upper_arm", "torso", "far_hand"},
    "far_hand": {"far_forearm", "torso"},
    "near_thigh": {"pelvis", "near_boot"},
    "near_boot": {"near_thigh"},
    "far_thigh": {"pelvis", "far_boot"},
    "far_boot": {"far_thigh"},
}

FORCED_POLYGONS = {
    "hooded_head": [(500, 275), (526, 225), (620, 145), (735, 145), (758, 240), (760, 320), (720, 430), (650, 447), (530, 405), (500, 350)],
}

PALETTE = [
    (236, 86, 94), (77, 181, 255), (245, 189, 72), (119, 214, 123),
    (179, 118, 255), (255, 143, 71), (72, 221, 210), (238, 105, 186),
    (165, 205, 76), (92, 132, 238), (224, 154, 112), (87, 196, 156),
    (210, 103, 240),
]


def distance_to_segment(xx: np.ndarray, yy: np.ndarray, a: tuple[int, int], b: tuple[int, int]) -> np.ndarray:
    ax, ay = map(float, a)
    bx, by = map(float, b)
    vx, vy = bx - ax, by - ay
    denom = max(1.0, vx * vx + vy * vy)
    t = np.clip(((xx - ax) * vx + (yy - ay) * vy) / denom, 0.0, 1.0)
    px, py = ax + t * vx, ay + t * vy
    return np.hypot(xx - px, yy - py)


def make_ownership(source: np.ndarray, foreground: np.ndarray) -> np.ndarray:
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
    scores = []
    for index, bone in enumerate(BONES):
        score = distance_to_segment(xx, yy, bone["a"], bone["b"])
        x0, y0, x1, y1 = BOUNDS[bone["name"]]
        outside = (xx < x0) | (xx >= x1) | (yy < y0) | (yy >= y1)
        score = score + outside.astype(np.float32) * 5000.0
        # Small deterministic tie bias keeps ownership stable across platforms.
        score += index * 0.0001
        scores.append(score)
    stacked = np.stack(scores, axis=0)
    owner = np.argmin(stacked, axis=0).astype(np.int16)
    owner[~foreground] = -1
    by_name = {bone["name"]: index for index, bone in enumerate(BONES)}
    for name, points in FORCED_POLYGONS.items():
        forced = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
        cv2.fillPoly(forced, [np.asarray(points, dtype=np.int32)], 1)
        owner[(forced > 0) & foreground] = by_name[name]
    # Hands are selected from their actual warm skin pixels plus a narrow cuff
    # halo.  Pure nearest-bone ownership otherwise steals a large patch of the
    # adjacent torso because the far fist rests directly on the chest.
    rgb = source[:, :, :3].astype(np.int16)
    skin = (
        (rgb[:, :, 0] > 80)
        & ((rgb[:, :, 0] - rgb[:, :, 1]) > 12)
        & ((rgb[:, :, 1] - rgb[:, :, 2]) > 4)
        & foreground
    )
    hand_specs = [
        ("near_hand", "near_forearm", (382, 660, 502, 790)),
        ("far_hand", "far_forearm", (748, 388, 865, 515)),
    ]
    for hand_name, parent_name, (x0, y0, x1, y1) in hand_specs:
        bounded_skin = np.zeros_like(foreground)
        bounded_skin[y0:y1, x0:x1] = skin[y0:y1, x0:x1]
        halo = cv2.dilate(
            bounded_skin.astype(np.uint8),
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17)),
            iterations=1,
        ).astype(bool)
        halo &= foreground
        hand_id, parent_id = by_name[hand_name], by_name[parent_name]
        owner[(owner == hand_id) & ~halo] = parent_id
        owner[halo] = hand_id
    # Replace the near shoulder's irregular Voronoi wedge with a clean capsule
    # following the actual upper-arm bone.  Its elbow cut is perpendicular to
    # the upper-arm axis, which prevents a triangular cloth spike after rotation.
    near_upper_id = by_name["near_upper_arm"]
    torso_id = by_name["torso"]
    near_forearm_id = by_name["near_forearm"]
    upper_a = np.asarray([655.0, 395.0], dtype=np.float32)
    upper_b = np.asarray([570.0, 545.0], dtype=np.float32)
    upper_vector = upper_b - upper_a
    upper_distance = distance_to_segment(xx, yy, tuple(upper_a), tuple(upper_b))
    shoulder_side = (xx - upper_a[0]) * upper_vector[0] + (yy - upper_a[1]) * upper_vector[1]
    elbow_side = (xx - upper_b[0]) * upper_vector[0] + (yy - upper_b[1]) * upper_vector[1]
    clean_upper = (
        (upper_distance <= 82.0)
        & (shoulder_side >= 0.0)
        & (elbow_side <= 0.0)
        & (yy >= 385.0)
        & foreground
    )
    old_upper_outside = (owner == near_upper_id) & ~clean_upper
    owner[old_upper_outside & (yy < 520.0)] = torso_id
    owner[old_upper_outside & (yy >= 520.0)] = near_forearm_id
    claimable = np.isin(owner, [torso_id, near_upper_id, near_forearm_id])
    owner[clean_upper & claimable] = near_upper_id
    # Voronoi ownership can leave tiny detached islands on a nearby fold.  A
    # rigid bone attachment must remain one semantic body piece, so reassign all
    # but the largest connected component to the next-best bone score.
    for _ in range(2):
        for part_id in range(len(BONES)):
            part_mask = owner == part_id
            count, labels, stats, _ = cv2.connectedComponentsWithStats(part_mask.astype(np.uint8), connectivity=8)
            if count <= 2:
                continue
            largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            detached = part_mask & (labels != largest)
            if not np.any(detached):
                continue
            candidate_scores = stacked[:, detached].copy()
            candidate_scores[part_id, :] = np.inf
            owner[detached] = np.argmin(candidate_scores, axis=0).astype(np.int16)
    # The near shoulder has one tiny Voronoi island near the tunic hem that can
    # oscillate between arm and torso during the generic cleanup above.  Resolve
    # that last ambiguity explicitly so the arm texture is a single component.
    near_upper_id = by_name["near_upper_arm"]
    near_upper_mask = owner == near_upper_id
    count, labels, stats, _ = cv2.connectedComponentsWithStats(near_upper_mask.astype(np.uint8), connectivity=8)
    if count > 2:
        largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        owner[near_upper_mask & (labels != largest)] = by_name["torso"]
    return owner


def crop_attachment(source: np.ndarray, mask: np.ndarray, padding: int = 12) -> tuple[np.ndarray, list[int]]:
    ys, xs = np.where(mask)
    if not len(xs):
        raise RuntimeError("empty attachment")
    x0, y0 = max(0, int(xs.min()) - padding), max(0, int(ys.min()) - padding)
    x1, y1 = min(WIDTH, int(xs.max()) + 1 + padding), min(HEIGHT, int(ys.max()) + 1 + padding)
    crop = source[y0:y1, x0:x1].copy()
    crop_mask = mask[y0:y1, x0:x1]
    crop[~crop_mask] = 0
    return crop, [x0, y0, x1, y1]


def keep_components_touching_visible(attachment: np.ndarray, visible: np.ndarray) -> np.ndarray:
    """Discard detached dilation islands that would float with the wrong bone."""
    count, labels = cv2.connectedComponents(attachment.astype(np.uint8), connectivity=8)
    keep = np.zeros_like(attachment)
    for component_id in range(1, count):
        component = labels == component_id
        if np.any(component & visible):
            keep |= component
    return keep


def compose(source: np.ndarray, records: list[dict]) -> np.ndarray:
    result = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    by_name = {record["name"]: record for record in records}
    for name in DRAW_ORDER:
        record = by_name[name]
        part = Image.open(OUT / record["attachment_file"]).convert("RGBA")
        x0, y0, _, _ = record["source_bbox"]
        result.alpha_composite(part, (x0, y0))
    return np.asarray(result, dtype=np.uint8)


def make_review(source: np.ndarray, owner: np.ndarray, records: list[dict]) -> None:
    overlay = source.copy()
    for index, color in enumerate(PALETTE):
        region = owner == index
        overlay[:, :, :3][region] = np.round(source[:, :, :3][region] * 0.38 + np.asarray(color) * 0.62).astype(np.uint8)
    Image.fromarray(overlay, "RGBA").save(OUT / "ownership_overlay.png")

    skeleton = Image.fromarray(source, "RGBA")
    draw = ImageDraw.Draw(skeleton)
    font = ImageFont.load_default()
    for index, bone in enumerate(BONES):
        color = PALETTE[index]
        draw.line((*bone["a"], *bone["b"]), fill=(*color, 255), width=6)
        for point in (bone["a"], bone["b"]):
            x, y = point
            draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(*color, 255), outline=(255, 255, 255, 255), width=2)
        draw.text((bone["a"][0] + 8, bone["a"][1] - 13), bone["name"], fill=(255, 255, 255, 255), font=font)
    skeleton.save(OUT / "skeleton_overlay.png")

    cols, cell_w, cell_h = 4, 360, 330
    rows = (len(records) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (26, 30, 38, 255))
    d = ImageDraw.Draw(sheet)
    for index, record in enumerate(records):
        x, y = (index % cols) * cell_w, (index // cols) * cell_h
        d.text((x + 10, y + 8), record["name"], fill=(244, 246, 250, 255), font=font)
        d.text((x + 10, y + 24), f'underlap={record["underlap_px"]} px', fill=(*PALETTE[index], 255), font=font)
        part = Image.open(OUT / record["attachment_file"]).convert("RGBA")
        scale = min(320 / max(1, part.width), 260 / max(1, part.height), 1.2)
        shown = part.resize((max(1, round(part.width * scale)), max(1, round(part.height * scale))), Image.Resampling.LANCZOS)
        sheet.alpha_composite(shown, (x + (cell_w - shown.width) // 2, y + 52 + (260 - shown.height) // 2))
    sheet.convert("RGB").save(OUT / "semantic_attachments_contact.jpg", quality=96)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source = np.asarray(Image.open(SOURCE).convert("RGBA"), dtype=np.uint8)
    # Preserve every antialias sample in exactly one visible owner.  A higher
    # threshold is useful for visual bounds, but would discard faint edge pixels
    # and make an exact RGBA bind reconstruction impossible.
    foreground = source[:, :, 3] > 0
    owner = make_ownership(source, foreground)
    if int((owner < 0).sum()) != int((~foreground).sum()):
        raise RuntimeError("foreground ownership incomplete")

    # Duplicate only mathematically opaque pixels.  Re-compositing a 250-alpha
    # antialiased edge would increase its alpha and break exact reconstruction.
    opaque = source[:, :, 3] == 255
    # The far fist rests on the chest.  Generate a hidden cloth plate beneath it
    # from neighboring torso pixels; copying the fist into the torso attachment
    # would create a second hand when the wrist moves.
    by_name = {bone["name"]: index for index, bone in enumerate(BONES)}
    far_hand_region = owner == by_name["far_hand"]
    fill_mask = cv2.dilate(far_hand_region.astype(np.uint8), np.ones((5, 5), np.uint8), iterations=1) * 255
    torso_source = source.copy()
    inpainted = cv2.inpaint(source[:, :, :3], fill_mask, 15.0, cv2.INPAINT_TELEA)
    torso_source[:, :, :3][fill_mask > 0] = inpainted[fill_mask > 0]
    records = []
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
    underlap_radius = {
        "near_upper_arm": 105.0,
        "near_forearm": 92.0,
        "near_hand": 82.0,
        "far_upper_arm": 135.0,
        "far_forearm": 118.0,
        "far_hand": 92.0,
        "near_thigh": 145.0,
        "near_boot": 125.0,
        "far_thigh": 155.0,
        "far_boot": 135.0,
    }
    for index, bone in enumerate(BONES):
        visible = owner == index
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (bone["underlap"] * 2 + 1, bone["underlap"] * 2 + 1))
        expanded = cv2.dilate(visible.astype(np.uint8), kernel, iterations=1).astype(bool)
        allowed_names = {bone["name"], *NEIGHBORS[bone["name"]]}
        allowed_ids = [i for i, candidate in enumerate(BONES) if candidate["name"] in allowed_names]
        adjacent_owner = np.isin(owner, allowed_ids)
        attachment = visible | (expanded & opaque & adjacent_owner)
        if bone["name"] in underlap_radius:
            tube = distance_to_segment(xx, yy, bone["a"], bone["b"]) <= underlap_radius[bone["name"]]
            attachment = visible | (attachment & tube)
        hidden_fill = np.zeros_like(visible)
        part_source = source
        if bone["name"] == "torso":
            hidden_fill = far_hand_region & opaque
            attachment |= hidden_fill
            part_source = torso_source
        attachment = keep_components_touching_visible(attachment, visible)
        visible_crop, bbox = crop_attachment(source, visible)
        attachment_crop, attachment_bbox = crop_attachment(source, attachment)
        # Use a shared bbox so placement and later Spine offsets remain simple.
        x0 = min(bbox[0], attachment_bbox[0]); y0 = min(bbox[1], attachment_bbox[1])
        x1 = max(bbox[2], attachment_bbox[2]); y1 = max(bbox[3], attachment_bbox[3])
        full_visible = source[y0:y1, x0:x1].copy(); full_visible[~visible[y0:y1, x0:x1]] = 0
        full_attachment = part_source[y0:y1, x0:x1].copy(); full_attachment[~attachment[y0:y1, x0:x1]] = 0
        visible_file = f"{index:02d}_{bone['name']}_visible.png"
        attachment_file = f"{index:02d}_{bone['name']}_attachment.png"
        Image.fromarray(full_visible, "RGBA").save(OUT / visible_file)
        Image.fromarray(full_attachment, "RGBA").save(OUT / attachment_file)
        records.append({
            **bone,
            "index": index,
            "visible_file": visible_file,
            "attachment_file": attachment_file,
            "source_bbox": [x0, y0, x1, y1],
            "visible_pixels": int(visible.sum()),
            "attachment_pixels": int(attachment.sum()),
            "underlap_pixels": int((attachment & ~visible).sum()),
            "hidden_fill_pixels": int(hidden_fill.sum()),
            "underlap_px": bone["underlap"],
        })

    reconstruction = compose(source, records)
    Image.fromarray(reconstruction, "RGBA").save(OUT / "bind_reconstruction.png")
    mismatch = int(np.any(reconstruction != source, axis=2).sum())
    uncovered = int((foreground & (reconstruction[:, :, 3] == 0)).sum())
    make_review(source, owner, records)
    report = {
        "schema_version": 1,
        "source_sha256": sha256(SOURCE),
        "status": "semantic_segmentation_visual_review_required",
        "parts": records,
        "draw_order": DRAW_ORDER,
        "foreground_pixels": int(foreground.sum()),
        "uncovered_pixels": uncovered,
        "bind_mismatch_pixels": mismatch,
        "bind_exact_rgba": mismatch == 0,
        "production_rig_allowed": False,
        "shipping_allowed": False,
        "steam_install_allowed": False,
        "next_gate": "ownership_and_joint_underlap_visual_review",
    }
    if uncovered or mismatch:
        raise RuntimeError(report)
    (OUT / "segmentation_review.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
