#!/usr/bin/env python3
"""Build the 34-slot Thief Raider v5 ownership map from the approved master.

V2 consumes the reviewed V1 semantic partition, corrects its residual cloak /
lower-body ambiguity, then deterministically splits it to match every
``source_part`` and z value in ``skeleton_spec.json``.  Visible RGBA remains
byte-for-byte sourced from ``approved_master.png`` by the linked-cutout tool.
"""

from __future__ import annotations

import colorsys
import hashlib
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from build_ownership_v1 import ID_BY_NAME as V1_ID
from build_ownership_v1 import build_labels as build_v1_labels


HERE = Path(__file__).resolve().parent
MASTER_PATH = HERE.parent / "approved_master.png"
SKELETON_SPEC_PATH = HERE.parent / "skeleton_spec.json"
OWNERSHIP_PATH = HERE / "ownership_v2.png"
CONTRACT_PATH = HERE / "ownership_contract_v2.json"
PREVIEW_PATH = HERE / "ownership_preview_v2.png"
LEGEND_PATH = HERE / "ownership_legend_v2.png"
UNCERTAINTY_PATH = HERE / "ownership_uncertainty_v2.png"
REPORT_PATH = HERE / "ownership_qa_v2.json"


def load_slot_contract() -> tuple[list[dict], list[str]]:
    spec = json.loads(SKELETON_SPEC_PATH.read_text(encoding="utf-8"))
    slots = spec["slot_order_back_to_front"]
    if len(slots) != 34:
        raise RuntimeError(f"skeleton_spec slot count is {len(slots)}, expected 34")
    for expected_z, entry in enumerate(slots):
        if entry["z"] != expected_z:
            raise RuntimeError(
                f"skeleton_spec z discontinuity: expected {expected_z}, got {entry['z']}"
            )
        if entry["source_part"] != entry["slot"]:
            raise RuntimeError(
                f"slot/source_part mismatch at z={expected_z}: "
                f"{entry['slot']} != {entry['source_part']}"
            )
    names = [entry["source_part"] for entry in slots]
    if len(names) != len(set(names)):
        raise RuntimeError("skeleton_spec contains duplicate source_part names")
    return slots, names


SLOTS, PART_NAMES = load_slot_contract()
ID_BY_NAME = {name: z + 1 for z, name in enumerate(PART_NAMES)}
NAME_BY_ID = {idx: name for name, idx in ID_BY_NAME.items()}


def color_for(index: int) -> tuple[int, int, int]:
    """Deterministic high-contrast palette for review views only."""

    hue = (index * 0.618033988749895 + 0.04) % 1.0
    saturation = 0.58 + 0.16 * (index % 3)
    value = 0.92 if index % 2 == 0 else 0.78
    r, g, b = colorsys.hsv_to_rgb(hue, min(saturation, 0.88), value)
    return int(r * 255), int(g * 255), int(b * 255)


COLOR_BY_ID = {idx: color_for(idx) for idx in NAME_BY_ID}


def bbox(mask: np.ndarray) -> list[int] | None:
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def polygon_mask(shape: tuple[int, int], points: list[tuple[int, int]]) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.fillPoly(mask, [np.asarray(points, np.int32).reshape((-1, 1, 2))], 255)
    return mask > 0


def nearest_labels(
    labels: np.ndarray,
    target: np.ndarray,
    candidates: list[str],
) -> None:
    """Assign each target pixel to the spatially nearest candidate attachment."""

    best_distance = np.full(labels.shape, np.inf, dtype=np.float32)
    best_id = np.zeros(labels.shape, dtype=np.uint8)
    for name in candidates:
        idx = ID_BY_NAME[name]
        if not np.any(labels == idx):
            continue
        distance = cv2.distanceTransform(
            (labels != idx).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE
        )
        better = target & (distance < best_distance)
        best_distance[better] = distance[better]
        best_id[better] = idx
    if np.any(target & (best_id == 0)):
        raise RuntimeError("nearest-label repair had no seeded candidate")
    labels[target] = best_id[target]


def split_cloak(
    master: np.ndarray,
    v1: np.ndarray,
    labels: np.ndarray,
) -> dict[str, int]:
    """Clean V1's default carrier, then create upper / near / far cloak slots."""

    rear = v1 == V1_ID["rear_cloak"]
    hsv = cv2.cvtColor(master[:, :, :3], cv2.COLOR_RGB2HSV)
    h, s, value = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

    # A real cloak pixel is plum/magenta.  Three-pixel expansion keeps painted
    # outlines and dark fold cores; position guards retain the small near-tail
    # island and outer torn-edge outline while excluding V1's gray leg wedge.
    plum_seed = rear & (h >= 150) & (s >= 70) & (value >= 15)
    plum_neighbourhood = cv2.dilate(
        plum_seed.astype(np.uint8), np.ones((7, 7), np.uint8)
    ) > 0
    yy, xx = np.indices(rear.shape)
    cloak = rear & (
        plum_neighbourhood
        | (xx < 418)
        | (yy < 480)
        | (xx > 485)
    )
    residual = rear & ~cloak

    # Seed the previously missing gray wedge from its actual neighbouring body
    # carriers instead of silently leaving it on a cloth slot.
    nearest_labels(
        labels,
        residual,
        ["pelvis_skirt", "far_thigh", "far_shin", "near_thigh"],
    )

    upper_boundary = np.clip(360.0 + 0.35 * (xx - 480), 348.0, 424.0)
    upper = cloak & (yy < upper_boundary)
    tail_pixels = cloak & ~upper
    tail_split_x = 495.0 + 0.18 * (yy - 380)
    far = tail_pixels & (xx >= tail_split_x)
    near = tail_pixels & ~far

    labels[upper] = ID_BY_NAME["upper_back_cloak"]
    labels[far] = ID_BY_NAME["cloak_tail_far"]
    labels[near] = ID_BY_NAME["cloak_tail_near"]
    return {
        "v1_rear_cloak_pixels": int(np.count_nonzero(rear)),
        "plum_cloak_pixels": int(np.count_nonzero(cloak)),
        "repaired_gray_body_pixels": int(np.count_nonzero(residual)),
    }


def carve_cover(
    labels: np.ndarray,
    target_name: str,
    eligible_names: list[str],
    points: list[tuple[int, int]],
) -> int:
    eligible = np.isin(labels, [ID_BY_NAME[name] for name in eligible_names])
    selected = eligible & polygon_mask(labels.shape, points)
    labels[selected] = ID_BY_NAME[target_name]
    return int(np.count_nonzero(selected))


def semantic_color_cleanup(
    master: np.ndarray,
    labels: np.ndarray,
    v1: np.ndarray,
) -> dict[str, int]:
    """Snap conspicuous V1 polygon spill to the painted semantic material.

    Plum cloth is unique in this character palette, so a conservative HSV seed
    can recover cape/scarf pixels swallowed by sack, limb, belt, head or torso
    polygons without inventing any artwork.  A precise hand silhouette then
    restores the fist that V1's front-scarf polygon covered.
    """

    visible = master[:, :, 3] > 0
    yy, xx = np.indices(labels.shape)
    hsv = cv2.cvtColor(master[:, :, :3], cv2.COLOR_RGB2HSV)
    h, s, value = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    red = master[:, :, 0].astype(np.int16)
    green = master[:, :, 1].astype(np.int16)
    blue = master[:, :, 2].astype(np.int16)

    # Low-value charcoal receives unstable HSV hues, so hue alone creates
    # isolated false plum speckles.  Require material-channel separation and
    # retain only connected painted regions before closing tiny fold holes.
    raw_plum_seed = (
        visible
        & (h >= 145)
        & (s >= 70)
        & (value >= 14)
        & (red >= green + 12)
        & (blue >= green + 5)
    )
    count, components, stats, _ = cv2.connectedComponentsWithStats(
        raw_plum_seed.astype(np.uint8), connectivity=8
    )
    plum_core = np.zeros(labels.shape, dtype=bool)
    for component in range(1, count):
        if int(stats[component, cv2.CC_STAT_AREA]) >= 18:
            plum_core |= components == component
    plum_closed = cv2.morphologyEx(
        plum_core.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)
    ) > 0
    plum_near = cv2.dilate(plum_core.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    plum = plum_closed | (
        plum_near
        & (red >= green + 6)
        & (blue >= green + 2)
        & (value >= 8)
    )

    scarf_back = plum & (xx >= 345) & (xx <= 428) & (yy >= 148) & (yy <= 252)
    scarf_front = plum & (xx >= 240) & (xx <= 422) & (yy >= 238) & (yy <= 324)
    labels[scarf_back] = ID_BY_NAME["scarf_back"]
    labels[scarf_front & ~scarf_back] = ID_BY_NAME["scarf_front"]

    # Only recover cape material at the reviewed V1 cape boundary.  This blocks
    # charcoal boot/tunic brush texture from becoming isolated cloak speckles.
    near_v1_cloak = cv2.dilate(
        (v1 == V1_ID["rear_cloak"]).astype(np.uint8), np.ones((13, 13), np.uint8)
    ) > 0
    cape = (
        plum
        & near_v1_cloak
        & (xx >= 240)
        & (xx <= 700)
        & (yy >= 300)
        & (yy <= 665)
    )
    upper_boundary = np.clip(360.0 + 0.35 * (xx - 480), 348.0, 424.0)
    upper = cape & (yy < upper_boundary)
    tails = cape & ~upper
    tail_split_x = 495.0 + 0.18 * (yy - 380)
    far = tails & (xx >= tail_split_x)
    near = tails & ~far
    labels[upper] = ID_BY_NAME["upper_back_cloak"]
    labels[far] = ID_BY_NAME["cloak_tail_far"]
    labels[near] = ID_BY_NAME["cloak_tail_near"]

    # Remove the small brown boot/belt fringe that V1's default carrier kept as
    # a disconnected cloak island.  Dark plum folds are unaffected by hue.
    cloak_ids = [
        ID_BY_NAME["cloak_tail_far"],
        ID_BY_NAME["cloak_tail_near"],
        ID_BY_NAME["upper_back_cloak"],
    ]
    obvious_brown_cloak = (
        np.isin(labels, cloak_ids)
        & (h <= 35)
        & (s >= 65)
        & (value >= 12)
        & ~plum
    )
    brown_count, brown_components, brown_stats, _ = cv2.connectedComponentsWithStats(
        obvious_brown_cloak.astype(np.uint8), connectivity=8
    )
    coherent_brown_cloak = np.zeros(labels.shape, dtype=bool)
    for component in range(1, brown_count):
        if int(brown_stats[component, cv2.CC_STAT_AREA]) >= 8:
            coherent_brown_cloak |= brown_components == component
    nearest_labels(
        labels,
        coherent_brown_cloak,
        [
            "loot_sack",
            "bag_knot",
            "sack_strap_back",
            "far_thigh",
            "far_shin",
            "far_foot",
            "near_thigh",
            "near_shin",
            "near_foot",
            "belt_and_pouch",
            "waist_cloth_front",
        ],
    )

    # The long brown belt tongue is rigid belt hardware, not gray skirt cloth.
    belt_tail_zone = polygon_mask(labels.shape, [
        (386, 369), (421, 367), (430, 397), (421, 448),
        (404, 457), (390, 430),
    ])
    belt_tail = (
        belt_tail_zone
        & np.isin(
            labels,
            [
                ID_BY_NAME["pelvis_skirt"],
                ID_BY_NAME["waist_cloth_front"],
                ID_BY_NAME["torso_core"],
            ],
        )
        & (h <= 35)
        & (s >= 55)
        & (value >= 18)
        & ~plum
    )
    labels[belt_tail] = ID_BY_NAME["belt_and_pouch"]

    # Rebuild the exact fist silhouette after scarf material recovery.  Existing
    # front/grip strap pixels stay underneath the hand by z-contract.
    hand_zone = polygon_mask(labels.shape, [
        (383, 238), (417, 238), (441, 253), (451, 280),
        (438, 307), (409, 314), (382, 300), (372, 269),
    ])
    strap_ids = [ID_BY_NAME["sack_strap_front"], ID_BY_NAME["strap_grip"]]
    hand = visible & hand_zone & ~plum & ~np.isin(labels, strap_ids)
    labels[hand] = ID_BY_NAME["far_strap_hand"]

    return {
        "plum_pixels_recovered_to_scarf_back": int(np.count_nonzero(scarf_back)),
        "plum_pixels_recovered_to_scarf_front": int(
            np.count_nonzero(scarf_front & ~scarf_back)
        ),
        "plum_pixels_recovered_to_cloak": int(np.count_nonzero(cape)),
        "brown_pixels_removed_from_cloak": int(np.count_nonzero(coherent_brown_cloak)),
        "belt_tail_pixels_recovered": int(np.count_nonzero(belt_tail)),
        "tan_pixels_recovered_to_front_strap": 0,
        "fist_pixels_rebuilt": int(np.count_nonzero(hand)),
        "pinch_pixels": int(np.count_nonzero(labels == ID_BY_NAME["strap_grip"])),
    }


def build_labels(master: np.ndarray) -> tuple[np.ndarray, dict]:
    visible = master[:, :, 3] > 0
    v1 = build_v1_labels(master)
    labels = np.zeros(v1.shape, dtype=np.uint8)

    direct = {
        "loot_sack": "loot_sack",
        "bag_knot": "bag_knot",
        "far_leg_thigh": "far_thigh",
        "far_leg_shin": "far_shin",
        "far_foot": "far_foot",
        "scarf_back": "scarf_back",
        "far_upper_arm": "far_upper_arm",
        "far_shoulder_plate": "far_shoulder_plate",
        "torso": "torso_core",
        "near_leg_thigh": "near_thigh",
        "near_leg_shin": "near_shin",
        "near_foot": "near_foot",
        "pelvis_skirt": "pelvis_skirt",
        "far_forearm": "far_forearm",
        "far_hand": "far_strap_hand",
        "belt_pouch": "belt_and_pouch",
        "hood_head": "hooded_head",
        "scarf_front": "scarf_front",
        "near_upper_arm": "near_upper_arm",
        "near_shoulder_plate": "near_shoulder_plate",
        "near_forearm": "near_forearm",
        "near_hand": "near_dagger_hand",
        "dagger": "dagger",
    }
    for old_name, new_name in direct.items():
        labels[v1 == V1_ID[old_name]] = ID_BY_NAME[new_name]

    # Two-anchor strap: the upper arch remains bag-side back strap; the lower
    # left descent and hanging segment are front strap; the hand-contact band is
    # its own cover drawn immediately below far_strap_hand.
    yy, xx = np.indices(labels.shape)
    old_back = v1 == V1_ID["strap_back"]
    back_front_descent = old_back & (xx < 419) & (yy > 194)
    labels[old_back & ~back_front_descent] = ID_BY_NAME["sack_strap_back"]
    labels[back_front_descent] = ID_BY_NAME["sack_strap_front"]

    old_front = v1 == V1_ID["strap_front_grip"]
    grip = old_front & (yy <= 314)
    labels[old_front & ~grip] = ID_BY_NAME["sack_strap_front"]
    labels[grip] = ID_BY_NAME["strap_grip"]

    # Recover a narrow dark-tan pinch segment that V1 conservatively grouped
    # with the fist.  Bright orange skin is excluded by the value threshold.
    hsv = cv2.cvtColor(master[:, :, :3], cv2.COLOR_RGB2HSV)
    h, s, value = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    grip_zone = polygon_mask(labels.shape, [
        (381, 242), (394, 240), (402, 272), (401, 300),
        (393, 311), (383, 300),
    ])
    grip_tan = (
        (labels == ID_BY_NAME["far_strap_hand"])
        & grip_zone
        & (h <= 28)
        & (s >= 55)
        & (value <= 155)
    )
    labels[grip_tan] = ID_BY_NAME["strap_grip"]

    cloak_stats = split_cloak(master, v1, labels)

    # Repair the V1 scarf-back boundary with a source-color seed.  Only the
    # hood/scarf/back-strap stack participates, so the front scarf remains
    # untouched even though it shares the plum palette.
    back_region = np.isin(
        v1,
        [V1_ID["hood_head"], V1_ID["scarf_back"], V1_ID["strap_back"]],
    )
    scarf_seed = (
        back_region
        & (xx >= 350)
        & (xx <= 425)
        & (yy >= 150)
        & (yy <= 252)
        & (h >= 150)
        & (s >= 75)
        & (value >= 18)
    )
    scarf_refined = back_region & (
        cv2.dilate(scarf_seed.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    )
    labels[scarf_refined] = ID_BY_NAME["scarf_back"]

    # Split the hanging front cloth below a V-shaped seam hidden under the belt.
    skirt = labels == ID_BY_NAME["pelvis_skirt"]
    waist_seam_y = 430.0 + 0.12 * np.abs(xx - 385)
    waist = skirt & (yy >= waist_seam_y)
    labels[waist] = ID_BY_NAME["waist_cloth_front"]

    # Rebuild both ankle ownership cuts along painted boot/foot direction rather
    # than preserving the V1 polygon's small translation-oriented corners.
    near_lower = np.isin(labels, [ID_BY_NAME["near_shin"], ID_BY_NAME["near_foot"]])
    near_foot = near_lower & (yy >= 672.0 + 0.225 * (xx - 260))
    labels[near_lower] = ID_BY_NAME["near_shin"]
    labels[near_foot] = ID_BY_NAME["near_foot"]

    far_lower = np.isin(labels, [ID_BY_NAME["far_shin"], ID_BY_NAME["far_foot"]])
    far_foot = far_lower & (yy >= 676.0 + 0.18 * (xx - 500))
    labels[far_lower] = ID_BY_NAME["far_shin"]
    labels[far_foot] = ID_BY_NAME["far_foot"]

    cover_counts = {
        "far_knee_cover": carve_cover(
            labels,
            "far_knee_cover",
            ["far_thigh", "far_shin"],
            [(469, 559), (502, 550), (535, 561), (553, 582),
             (552, 607), (531, 625), (500, 619), (476, 602), (463, 579)],
        ),
        "near_knee_cover": carve_cover(
            labels,
            "near_knee_cover",
            ["near_thigh", "near_shin"],
            [(254, 557), (286, 549), (320, 557), (338, 578),
             (339, 599), (321, 616), (286, 613), (260, 600), (248, 578)],
        ),
        "far_elbow_cover": carve_cover(
            labels,
            "far_elbow_cover",
            ["far_upper_arm", "far_forearm"],
            [(449, 276), (478, 271), (510, 277), (526, 290),
             (526, 305), (511, 316), (481, 309), (457, 300)],
        ),
        "near_elbow_cover": carve_cover(
            labels,
            "near_elbow_cover",
            ["near_upper_arm", "near_forearm"],
            [(191, 376), (216, 372), (238, 382), (254, 397),
             (253, 422), (239, 446), (215, 450), (193, 440),
             (184, 418), (188, 395)],
        ),
    }

    cleanup_stats = semantic_color_cleanup(master, labels, v1)

    labels[~visible] = 0
    missing = visible & (labels == 0)
    if np.any(missing):
        raise RuntimeError(f"V2 construction left {int(np.count_nonzero(missing))} visible pixels unlabeled")
    return labels, {
        "cloak_cleanup": cloak_stats,
        "cover_pixels": cover_counts,
        "grip_pixels_recovered_from_v1_hand": int(np.count_nonzero(grip_tan)),
        "scarf_back_pixels_after_refine": int(
            np.count_nonzero(labels == ID_BY_NAME["scarf_back"])
        ),
        "waist_cloth_pixels": int(np.count_nonzero(waist)),
        "semantic_color_cleanup": cleanup_stats,
    }


def boundary_between(labels: np.ndarray, first: str, second: str) -> np.ndarray:
    a = labels == ID_BY_NAME[first]
    b = labels == ID_BY_NAME[second]
    kernel = np.ones((3, 3), dtype=np.uint8)
    return (a & (cv2.dilate(b.astype(np.uint8), kernel) > 0)) | (
        b & (cv2.dilate(a.astype(np.uint8), kernel) > 0)
    )


def save_views(master: np.ndarray, labels: np.ndarray) -> tuple[list[dict], int]:
    visible = master[:, :, 3] > 0
    colors = np.zeros((*labels.shape, 3), dtype=np.uint8)
    for idx, color in COLOR_BY_ID.items():
        colors[labels == idx] = color
    blend = np.zeros_like(master[:, :, :3])
    blend[visible] = np.clip(
        master[:, :, :3][visible].astype(np.float32) * 0.43
        + colors[visible].astype(np.float32) * 0.57,
        0,
        255,
    ).astype(np.uint8)
    seam = np.zeros(labels.shape, dtype=bool)
    seam[:, 1:] |= labels[:, 1:] != labels[:, :-1]
    seam[1:, :] |= labels[1:, :] != labels[:-1, :]
    seam &= visible
    blend[seam] = (255, 255, 255)
    Image.fromarray(np.dstack([blend, master[:, :, 3]]), "RGBA").save(PREVIEW_PATH)

    legend_h = max(master.shape[0], 34 * 27 + 32)
    legend = Image.new("RGB", (1160, legend_h), (20, 20, 23))
    legend.paste(Image.fromarray(colors, "RGB"), (0, 0))
    draw = ImageDraw.Draw(legend)
    font = ImageFont.load_default(size=17)
    for row, entry in enumerate(SLOTS):
        idx = entry["z"] + 1
        y = 12 + row * 27
        draw.rectangle((780, y, 800, y + 20), fill=COLOR_BY_ID[idx])
        draw.text(
            (810, y + 1),
            f"z={entry['z']:02d}  {entry['source_part']}",
            fill=(240, 240, 240),
            font=font,
        )
    legend.save(LEGEND_PATH)

    review_pairs = [
        ("hooded_head", "scarf_back", "refined rear-scarf emergence"),
        ("scarf_back", "sack_strap_back", "refined scarf/back-strap contact"),
        ("sack_strap_front", "strap_grip", "two-anchor front/grip split"),
        ("strap_grip", "far_strap_hand", "finger-over/under grip seam"),
        ("torso_core", "belt_and_pouch", "tightened belt/tunic boundary"),
        ("pelvis_skirt", "waist_cloth_front", "hidden V-shaped waist seam"),
        ("waist_cloth_front", "near_thigh", "near hip cloth/thigh root"),
        ("waist_cloth_front", "far_thigh", "far hip cloth/thigh root"),
        ("near_shin", "near_foot", "paint-direction ankle seam"),
        ("far_shin", "far_foot", "paint-direction ankle seam"),
        ("near_forearm", "near_elbow_cover", "near elbow cover edge"),
        ("far_forearm", "far_elbow_cover", "far elbow cover edge"),
        ("near_shin", "near_knee_cover", "near knee cover edge"),
        ("far_shin", "far_knee_cover", "far knee cover edge"),
        ("upper_back_cloak", "cloak_tail_far", "upper/far cloak carrier seam"),
    ]
    exact = np.zeros(labels.shape, dtype=bool)
    union = np.zeros(labels.shape, dtype=bool)
    records: list[dict] = []
    for first, second, reason in review_pairs:
        boundary = boundary_between(labels, first, second)
        band = cv2.dilate(boundary.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        band &= visible
        exact |= boundary
        union |= band
        records.append(
            {
                "parts": [first, second],
                "reason": reason,
                "shared_boundary_pixels": int(np.count_nonzero(boundary)),
                "review_band_pixels": int(np.count_nonzero(band)),
                "review_bbox_xyxy": bbox(band),
            }
        )
    uncertainty = (master[:, :, :3].astype(np.float32) * 0.42).astype(np.uint8)
    uncertainty[union] = (255, 42, 32)
    uncertainty[exact] = (255, 235, 32)
    Image.fromarray(
        np.dstack([uncertainty, master[:, :, 3]]), "RGBA"
    ).save(UNCERTAINTY_PATH)
    return records, int(np.count_nonzero(union))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> None:
    master = np.asarray(Image.open(MASTER_PATH).convert("RGBA"), dtype=np.uint8)
    labels, construction = build_labels(master)
    visible = master[:, :, 3] > 0
    Image.fromarray(labels, "L").save(OWNERSHIP_PATH)
    boundary_records, review_pixels = save_views(master, labels)

    contract = {
        "version": 2,
        "schema": "sts2-visible-pixel-ownership/v2",
        "character": "thief_raider_v5",
        "approved_master": "../approved_master.png",
        "skeleton_spec": "../skeleton_spec.json",
        "label_mode": "index",
        "background": 0,
        "map_alpha_zero_is_background": True,
        "draw_order": PART_NAMES,
        "parts": [
            {
                "name": entry["source_part"],
                "label": entry["z"] + 1,
                "z": entry["z"],
                "filename": f"{entry['source_part']}.png",
                "bone": entry["bone"],
                "slot": entry["slot"],
                "joint_cover": entry["joint_cover"],
            }
            for entry in SLOTS
        ],
        "visible_payload_rule": (
            "Every label extracts byte-exact approved_master.png pixels; "
            "the ownership map contains indices only."
        ),
    }
    CONTRACT_PATH.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    counts = Counter(int(value) for value in labels[visible])
    missing = int(np.count_nonzero(visible & (labels == 0)))
    transparent_labeled = int(np.count_nonzero((~visible) & (labels != 0)))
    invalid = int(np.count_nonzero(visible & (labels > 34)))
    empty = [name for name in PART_NAMES if counts.get(ID_BY_NAME[name], 0) == 0]
    contract_names = [part["name"] for part in contract["parts"]]
    contract_z = [part["z"] for part in contract["parts"]]
    report = {
        "schema": "sts2-visible-pixel-ownership-manual-qa/v2",
        "status": "pass"
        if not (missing or transparent_labeled or invalid or empty)
        and contract_names == PART_NAMES
        and contract_z == list(range(34))
        else "fail",
        "master": str(MASTER_PATH),
        "skeleton_spec": str(SKELETON_SPEC_PATH),
        "master_size": [int(master.shape[1]), int(master.shape[0])],
        "master_visible_pixels": int(np.count_nonzero(visible)),
        "ownership_visible_pixels": int(np.count_nonzero(labels)),
        "invariants": {
            "every_master_alpha_pixel_has_exactly_one_index": missing == 0 and invalid == 0,
            "transparent_pixels_are_background": transparent_labeled == 0,
            "all_34_source_parts_have_visible_pixels": not empty,
            "source_part_names_equal_skeleton_spec": contract_names == PART_NAMES,
            "z_is_exactly_0_through_33": contract_z == list(range(34)),
            "visible_rgba_repainted": False,
        },
        "issues": {
            "missing_visible_pixels": missing,
            "transparent_labeled_pixels": transparent_labeled,
            "invalid_label_pixels": invalid,
            "empty_parts": empty,
        },
        "construction": construction,
        "parts": [
            {
                "z": entry["z"],
                "id": entry["z"] + 1,
                "name": entry["source_part"],
                "visible_pixels": counts.get(entry["z"] + 1, 0),
                "bbox_xyxy": bbox(labels == entry["z"] + 1),
            }
            for entry in SLOTS
        ],
        "boundary_review": {
            "state": "v2_refined_requires_bind_motion_review",
            "uncertainty_overlay": UNCERTAINTY_PATH.name,
            "unique_visible_pixels_in_review_bands": review_pixels,
            "boundaries": boundary_records,
            "note": (
                "Review bands quantify the inspection envelope around intentional "
                "rig seams; they are not a count of known wrong pixels."
            ),
        },
        "files": {
            "ownership": OWNERSHIP_PATH.name,
            "contract": CONTRACT_PATH.name,
            "preview": PREVIEW_PATH.name,
            "legend": LEGEND_PATH.name,
            "uncertainty": UNCERTAINTY_PATH.name,
            "builder": Path(__file__).name,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["hashes"] = {
        "approved_master_sha256": sha256(MASTER_PATH),
        "skeleton_spec_sha256": sha256(SKELETON_SPEC_PATH),
        "ownership_sha256": sha256(OWNERSHIP_PATH),
        "contract_sha256": sha256(CONTRACT_PATH),
        "preview_sha256": sha256(PREVIEW_PATH),
        "legend_sha256": sha256(LEGEND_PATH),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "parts": len(PART_NAMES),
                "issues": report["issues"],
                "construction": construction,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
