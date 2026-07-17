#!/usr/bin/env python3
"""Build the first semantic visible-pixel ownership map for Thief Raider v5.

The approved master is the sole RGBA payload.  This script only labels its
already-visible pixels; it never paints or reconstructs character artwork.
Polygons are intentionally stored as data in this file so boundary edits are
reviewable and reproducible.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
MASTER_PATH = HERE.parent / "approved_master.png"
OWNERSHIP_PATH = HERE / "ownership_v1.png"
CONTRACT_PATH = HERE / "ownership_contract_v1.json"
PREVIEW_PATH = HERE / "ownership_preview_v1.png"
LEGEND_PATH = HERE / "ownership_legend_v1.png"
UNCERTAINTY_PATH = HERE / "ownership_uncertainty_v1.png"
REPORT_PATH = HERE / "ownership_qa_v1.json"


# Stable IDs.  Names required by the downstream rig contract remain present;
# articulated limbs are split where the master exposes a usable joint break.
PARTS = [
    (1, "rear_cloak", (196, 49, 143)),
    (2, "loot_sack", (151, 94, 43)),
    (3, "bag_knot", (207, 135, 64)),
    (4, "strap_back", (230, 171, 88)),
    (5, "far_leg_thigh", (53, 78, 137)),
    (6, "far_leg_shin", (55, 120, 185)),
    (7, "far_foot", (57, 168, 211)),
    (8, "near_leg_thigh", (67, 104, 67)),
    (9, "near_leg_shin", (76, 156, 89)),
    (10, "near_foot", (126, 201, 105)),
    (11, "torso", (78, 80, 91)),
    (12, "pelvis_skirt", (124, 126, 139)),
    (13, "belt_pouch", (235, 139, 39)),
    (14, "near_upper_arm", (172, 69, 221)),
    (15, "near_shoulder_plate", (218, 124, 245)),
    (16, "near_forearm", (236, 85, 94)),
    (17, "near_hand", (255, 152, 104)),
    (18, "far_upper_arm", (109, 48, 177)),
    (19, "far_shoulder_plate", (159, 110, 230)),
    (20, "far_forearm", (244, 100, 204)),
    (21, "far_hand", (255, 187, 117)),
    (22, "hood_head", (69, 198, 204)),
    (23, "scarf_back", (231, 57, 136)),
    (24, "scarf_front", (255, 93, 162)),
    (25, "strap_front_grip", (255, 215, 90)),
    (26, "dagger", (205, 216, 228)),
]

ID_BY_NAME = {name: idx for idx, name, _ in PARTS}
COLOR_BY_ID = {idx: color for idx, _, color in PARTS}


# Back-to-front intent for later hidden-underlap checks.  It does not alter the
# visible ownership map.
DRAW_ORDER = [
    "rear_cloak",
    "far_leg_thigh",
    "far_leg_shin",
    "far_foot",
    "near_leg_thigh",
    "near_leg_shin",
    "near_foot",
    "loot_sack",
    "scarf_back",
    "strap_back",
    "torso",
    "pelvis_skirt",
    "far_upper_arm",
    "far_shoulder_plate",
    "far_forearm",
    "far_hand",
    "near_upper_arm",
    "near_shoulder_plate",
    "near_forearm",
    "dagger",
    "near_hand",
    "belt_pouch",
    "hood_head",
    "scarf_front",
    "strap_front_grip",
    "bag_knot",
]


def poly(points: list[tuple[int, int]]) -> np.ndarray:
    return np.asarray(points, dtype=np.int32).reshape((-1, 1, 2))


def paint(labels: np.ndarray, visible: np.ndarray, name: str, *polygons: list[tuple[int, int]]) -> None:
    mask = np.zeros(labels.shape, dtype=np.uint8)
    cv2.fillPoly(mask, [poly(points) for points in polygons], 255, lineType=cv2.LINE_8)
    labels[(mask > 0) & visible] = ID_BY_NAME[name]


def reassign_stray_default_pixels(labels: np.ndarray) -> None:
    """Move polygon-edge leftovers to the nearest intentional attachment.

    The default rear-cloak carrier is useful for the cape's irregular torn
    silhouette, but any untraced anti-aliased fringe would otherwise become a
    tiny cloak island on a hood, boot or dagger edge.  Preserve the three real
    cloak bodies and small torn-tail islands, then classify every remaining
    default pixel by Euclidean distance to the nearest non-cloak attachment.
    """

    cloak_id = ID_BY_NAME["rear_cloak"]
    mask = (labels == cloak_id).astype(np.uint8)
    count, components, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    stray = np.zeros(labels.shape, dtype=bool)
    for component in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[component])
        x2, y2 = x + w, y + h
        keep = (
            area >= 1000
            or (x >= 300 and y >= 300 and y2 <= 660)
            or (x >= 240 and x2 <= 280 and y >= 500 and y2 <= 590 and area >= 100)
            or (x >= 580 and y >= 450 and y2 <= 660)
        )
        if not keep:
            stray |= components == component

    if not np.any(stray):
        return
    candidates = [idx for idx, _, _ in PARTS if idx != cloak_id]
    best_distance = np.full(labels.shape, np.inf, dtype=np.float32)
    best_label = np.zeros(labels.shape, dtype=np.uint8)
    for idx in candidates:
        # distanceTransform measures every non-zero pixel to the nearest zero;
        # making the candidate label zero yields distance to that attachment.
        distance = cv2.distanceTransform(
            (labels != idx).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE
        )
        better = stray & (distance < best_distance)
        best_distance[better] = distance[better]
        best_label[better] = idx
    labels[stray] = best_label[stray]


def build_labels(master: np.ndarray) -> np.ndarray:
    visible = master[:, :, 3] > 0
    labels = np.zeros(visible.shape, dtype=np.uint8)

    # The cloak is the continuous rear-most carrier silhouette.  More specific
    # visible pieces overwrite it below.
    labels[visible] = ID_BY_NAME["rear_cloak"]

    # Legs first, then the waist/skirt occludes their upper roots.
    paint(labels, visible, "far_leg_thigh", [
        (405, 399), (473, 390), (507, 416), (529, 474), (541, 535),
        (525, 568), (492, 576), (455, 544), (432, 505), (417, 455),
    ])
    paint(labels, visible, "far_leg_shin", [
        (494, 543), (531, 551), (553, 587), (569, 651), (558, 694),
        (528, 710), (497, 686), (482, 635), (473, 589),
    ])
    paint(labels, visible, "far_foot", [
        (511, 676), (550, 672), (573, 692), (581, 728), (568, 752),
        (532, 760), (503, 755), (479, 740), (487, 708),
    ])
    paint(labels, visible, "near_leg_thigh", [
        (281, 397), (345, 396), (369, 432), (365, 491), (346, 555),
        (326, 581), (285, 579), (257, 543), (248, 500), (253, 450),
    ])
    paint(labels, visible, "near_leg_shin", [
        (272, 550), (323, 548), (341, 589), (347, 665), (330, 704),
        (299, 710), (268, 688), (256, 624), (254, 580),
    ])
    paint(labels, visible, "near_foot", [
        (273, 675), (324, 674), (346, 692), (353, 720), (340, 741),
        (302, 747), (257, 748), (230, 740), (225, 721), (241, 701),
    ])

    # Dagger is behind the grip.  Its three visible islands (blade, guard and
    # pommel/hilt) share one semantic attachment.
    paint(labels, visible, "dagger", [
        (78, 571), (96, 541), (145, 497), (163, 484), (154, 466),
        (178, 473), (203, 459), (238, 451), (251, 463), (244, 476),
        (213, 482), (193, 493), (197, 510), (170, 515), (143, 535),
        (110, 558),
    ])

    # Bag body and knot, both in front of the rear cloak.
    paint(labels, visible, "loot_sack", [
        (446, 164), (482, 176), (535, 186), (581, 211), (612, 248),
        (629, 293), (626, 344), (608, 374), (579, 390), (550, 370),
        (529, 340), (518, 303), (494, 266), (466, 232), (441, 202),
    ])
    paint(labels, visible, "bag_knot", [
        (449, 112), (467, 128), (484, 112), (507, 116), (510, 140),
        (535, 140), (548, 159), (541, 180), (518, 194), (487, 190),
        (466, 197), (449, 184), (432, 171), (432, 143),
    ])

    # Magenta scarf behind the hood and tan back strap arch.
    paint(labels, visible, "scarf_back", [
        (353, 151), (388, 158), (416, 176), (435, 204), (428, 234),
        (404, 265), (374, 273), (353, 243),
    ])
    paint(labels, visible, "strap_back", [
        (392, 291), (386, 260), (389, 224), (399, 195), (416, 173),
        (439, 158), (459, 159), (468, 173), (448, 187), (432, 205),
        (420, 231), (416, 259), (418, 292),
    ])

    # Core body and articulated skirt carrier.  Pointed skirt hems are traced
    # separately to avoid swallowing leg pixels at the negative spaces.
    paint(labels, visible, "torso", [
        (278, 281), (331, 266), (404, 263), (443, 291), (466, 336),
        (454, 381), (420, 405), (350, 410), (299, 393), (268, 349),
    ])
    paint(labels, visible, "pelvis_skirt", [
        (284, 377), (430, 374), (464, 393), (483, 431), (515, 470),
        (530, 523), (505, 514), (481, 496), (484, 547), (448, 513),
        (417, 483), (415, 540), (384, 500), (357, 457), (355, 563),
        (326, 511), (296, 482), (262, 512), (255, 469), (267, 423),
    ])

    # Near weapon arm (screen left).  Shoulder and bracer boundaries follow
    # the silver joint covers in the approved art.
    paint(labels, visible, "near_upper_arm", [
        (239, 286), (275, 282), (303, 307), (307, 346), (291, 384),
        (261, 404), (224, 385), (224, 337),
    ])
    paint(labels, visible, "near_shoulder_plate", [
        (249, 269), (276, 272), (292, 289), (281, 315), (255, 322),
        (237, 307), (242, 286),
    ])
    paint(labels, visible, "near_forearm", [
        (225, 366), (261, 375), (279, 408), (269, 448), (238, 475),
        (202, 469), (185, 438), (194, 403),
    ])

    # Far strap arm (screen right), then the gripping hand in front.
    paint(labels, visible, "far_upper_arm", [
        (409, 213), (451, 211), (488, 230), (512, 260), (507, 288),
        (477, 306), (438, 296), (409, 268),
    ])
    paint(labels, visible, "far_shoulder_plate", [
        (414, 181), (448, 174), (476, 188), (491, 211), (479, 241),
        (447, 250), (416, 235), (405, 211),
    ])
    paint(labels, visible, "far_forearm", [
        (471, 273), (511, 274), (530, 290), (535, 319), (519, 340),
        (483, 343), (450, 326), (442, 300),
    ])
    paint(labels, visible, "far_hand", [
        (386, 239), (417, 239), (440, 256), (449, 280), (435, 306),
        (407, 313), (382, 298), (373, 269),
    ])

    # Hood carrier and front scarf are intentionally late: both occlude the
    # neck, rear scarf and torso in the approved bind pose.
    paint(labels, visible, "hood_head", [
        (226, 181), (244, 145), (278, 116), (319, 99), (348, 95),
        (366, 105), (358, 124), (379, 151), (389, 188), (387, 226),
        (371, 257), (341, 278), (297, 277), (258, 258), (239, 231),
    ])
    paint(labels, visible, "scarf_front", [
        (250, 246), (273, 252), (301, 266), (338, 275), (369, 267),
        (393, 245), (414, 254), (409, 279), (390, 303), (357, 317),
        (319, 312), (283, 300), (256, 282),
    ])

    # Brown waist assembly is one rigid carrier at this stage.  It overwrites
    # torso/skirt but stays behind the far forearm and front grip.
    paint(labels, visible, "belt_pouch", [
        (315, 338), (351, 342), (388, 352), (422, 346), (463, 337),
        (497, 344), (508, 376), (502, 415), (484, 441), (452, 443),
        (428, 421), (407, 392), (367, 389), (330, 384),
    ])

    # Reassert foreground objects that overlap the broad waist polygon.
    paint(labels, visible, "far_forearm", [
        (471, 273), (511, 274), (530, 290), (535, 319), (519, 340),
        (483, 343), (450, 326), (442, 300),
    ])
    paint(labels, visible, "near_forearm", [
        (225, 366), (261, 375), (279, 408), (269, 448), (238, 475),
        (202, 469), (185, 438), (194, 403),
    ])
    paint(labels, visible, "near_hand", [
        (164, 449), (196, 446), (222, 461), (230, 485), (216, 509),
        (186, 516), (160, 499), (151, 474),
    ])

    # Visible hanging strap below the fist.  The tight polygon excludes skin;
    # a later pass may split finger-over/under islands after pixel review.
    paint(labels, visible, "strap_front_grip", [
        (386, 292), (397, 298), (407, 295), (421, 300), (427, 321),
        (417, 341), (390, 340), (383, 321),
    ])

    reassign_stray_default_pixels(labels)
    labels[~visible] = 0
    return labels


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def bbox(mask: np.ndarray) -> list[int] | None:
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def save_preview(master: np.ndarray, labels: np.ndarray) -> None:
    colors = np.zeros((*labels.shape, 3), dtype=np.uint8)
    for idx, color in COLOR_BY_ID.items():
        colors[labels == idx] = color
    visible = master[:, :, 3] > 0
    base = master[:, :, :3].astype(np.float32)
    blend = np.zeros_like(base)
    blend[visible] = base[visible] * 0.47 + colors[visible].astype(np.float32) * 0.53
    blend = np.clip(blend, 0, 255).astype(np.uint8)
    # Thin label boundaries make internal cuts inspectable at 1:1.
    boundary = np.zeros(labels.shape, dtype=bool)
    boundary[:, 1:] |= labels[:, 1:] != labels[:, :-1]
    boundary[1:, :] |= labels[1:, :] != labels[:-1, :]
    boundary &= visible
    blend[boundary] = (255, 255, 255)
    out = np.dstack([blend, master[:, :, 3]])
    Image.fromarray(out, "RGBA").save(PREVIEW_PATH)

    # Opaque color map plus a compact legend panel.
    rgb = np.zeros((*labels.shape, 3), dtype=np.uint8)
    for idx, color in COLOR_BY_ID.items():
        rgb[labels == idx] = color
    legend = Image.new("RGB", (1100, 896), (22, 22, 25))
    legend.paste(Image.fromarray(rgb, "RGB"), (0, 0))
    draw = ImageDraw.Draw(legend)
    font = ImageFont.load_default(size=18)
    x0 = 782
    for row, (idx, name, color) in enumerate(PARTS):
        y = 18 + row * 32
        draw.rectangle((x0, y, x0 + 22, y + 22), fill=color)
        draw.text((x0 + 32, y + 2), f"{idx:02d}  {name}", fill=(238, 238, 238), font=font)
    legend.save(LEGEND_PATH)


def boundary_between(labels: np.ndarray, first: int, second: int) -> np.ndarray:
    """Return a one-pixel 8-neighbour boundary shared by two label IDs."""

    kernel = np.ones((3, 3), dtype=np.uint8)
    a = labels == first
    b = labels == second
    touch_a = a & (cv2.dilate(b.astype(np.uint8), kernel) > 0)
    touch_b = b & (cv2.dilate(a.astype(np.uint8), kernel) > 0)
    return touch_a | touch_b


def save_uncertainty(master: np.ndarray, labels: np.ndarray) -> tuple[list[dict], int]:
    pairs = [
        ("hood_head", "scarf_back", "back-scarf emergence from behind hood"),
        ("scarf_back", "strap_back", "back-scarf/strap transition behind far shoulder"),
        ("strap_back", "far_shoulder_plate", "strap arch against shoulder plate"),
        ("strap_back", "bag_knot", "strap insertion at knot"),
        ("far_hand", "strap_front_grip", "finger-over/under strap islands"),
        ("belt_pouch", "torso", "left belt return against tunic"),
        ("pelvis_skirt", "near_leg_thigh", "near hip cloth/thigh root"),
        ("pelvis_skirt", "far_leg_thigh", "far hip cloth/thigh root"),
        ("near_leg_shin", "near_foot", "chosen boot articulation seam"),
        ("far_leg_shin", "far_foot", "chosen boot articulation seam"),
    ]
    union = np.zeros(labels.shape, dtype=bool)
    records: list[dict] = []
    for first, second, reason in pairs:
        boundary = boundary_between(labels, ID_BY_NAME[first], ID_BY_NAME[second])
        review_band = cv2.dilate(boundary.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        review_band &= master[:, :, 3] > 0
        union |= review_band
        records.append(
            {
                "parts": [first, second],
                "reason": reason,
                "shared_boundary_pixels": int(np.count_nonzero(boundary)),
                "review_band_pixels": int(np.count_nonzero(review_band)),
                "review_bbox_xyxy": bbox(review_band),
            }
        )

    rgb = master[:, :, :3].copy()
    rgb = (rgb.astype(np.float32) * 0.42).astype(np.uint8)
    rgb[union] = (255, 40, 32)
    # Preserve the exact one-pixel seams in yellow inside the wider red band.
    exact = np.zeros(labels.shape, dtype=bool)
    for first, second, _ in pairs:
        exact |= boundary_between(labels, ID_BY_NAME[first], ID_BY_NAME[second])
    rgb[exact] = (255, 235, 32)
    rgba = np.dstack([rgb, master[:, :, 3]])
    Image.fromarray(rgba, "RGBA").save(UNCERTAINTY_PATH)
    return records, int(np.count_nonzero(union))


def main() -> None:
    master = np.asarray(Image.open(MASTER_PATH).convert("RGBA"), dtype=np.uint8)
    labels = build_labels(master)
    visible = master[:, :, 3] > 0

    # L mode preserves exact index values and avoids palette/RGB ambiguity.
    Image.fromarray(labels, "L").save(OWNERSHIP_PATH)
    save_preview(master, labels)
    uncertainty_records, uncertainty_pixels = save_uncertainty(master, labels)

    contract = {
        "version": 1,
        "schema": "sts2-visible-pixel-ownership/v1",
        "character": "thief_raider_v5",
        "approved_master": "../approved_master.png",
        "label_mode": "index",
        "background": 0,
        "map_alpha_zero_is_background": True,
        "draw_order": DRAW_ORDER,
        "parts": [
            {
                "name": name,
                "label": idx,
                "z": DRAW_ORDER.index(name),
                "filename": f"{name}.png",
            }
            for idx, name, _ in PARTS
        ],
        "visible_payload_rule": (
            "Every label selects byte-exact pixels from approved_master.png; "
            "the ownership map never supplies RGBA artwork."
        ),
    }
    CONTRACT_PATH.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    counts = Counter(int(value) for value in labels[visible])
    missing = int(np.count_nonzero(visible & (labels == 0)))
    transparent_labeled = int(np.count_nonzero((~visible) & (labels != 0)))
    unknown = int(np.count_nonzero(visible & (labels > max(ID_BY_NAME.values()))))
    empty = [name for idx, name, _ in PARTS if counts.get(idx, 0) == 0]
    report = {
        "schema": "sts2-visible-pixel-ownership-manual-qa/v1",
        "status": "pass" if not (missing or transparent_labeled or unknown or empty) else "fail",
        "master": str(MASTER_PATH),
        "master_size": [int(master.shape[1]), int(master.shape[0])],
        "master_visible_pixels": int(np.count_nonzero(visible)),
        "ownership_visible_pixels": int(np.count_nonzero(labels)),
        "invariants": {
            "every_master_alpha_pixel_has_exactly_one_index": missing == 0 and unknown == 0,
            "transparent_pixels_are_background": transparent_labeled == 0,
            "all_contract_parts_have_visible_pixels": not empty,
        },
        "issues": {
            "missing_visible_pixels": missing,
            "transparent_labeled_pixels": transparent_labeled,
            "unknown_label_pixels": unknown,
            "empty_parts": empty,
        },
        "parts": [
            {
                "id": idx,
                "name": name,
                "visible_pixels": counts.get(idx, 0),
                "bbox_xyxy": bbox(labels == idx),
            }
            for idx, name, _ in PARTS
        ],
        "manual_boundary_review": {
            "state": "v1_requires_visual_review",
            "uncertainty_overlay": UNCERTAINTY_PATH.name,
            "unique_visible_pixels_in_review_bands": uncertainty_pixels,
            "boundaries": uncertainty_records,
            "known_uncertainty": [
                "scarf_back emergence between the hood and rear shoulder stack",
                "strap_back arch against the scarf, shoulder plate, and bag knot",
                "far_hand finger islands versus strap_front_grip",
                "belt_pouch belt pixels versus torso at the left belt return",
                "cloth-only thigh/skirt seam at both hip roots",
                "boot shin/foot cuts are articulation seams inside a continuous painted boot",
            ],
            "visible_rgba_repainted": False,
        },
        "files": {
            "ownership": OWNERSHIP_PATH.name,
            "contract": CONTRACT_PATH.name,
            "preview": PREVIEW_PATH.name,
            "legend": LEGEND_PATH.name,
            "uncertainty": UNCERTAINTY_PATH.name,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["hashes"] = {
        "approved_master_sha256": sha256(MASTER_PATH),
        "ownership_sha256": sha256(OWNERSHIP_PATH),
        "contract_sha256": sha256(CONTRACT_PATH),
        "preview_sha256": sha256(PREVIEW_PATH),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "issues": report["issues"], "files": report["files"]}, indent=2))


if __name__ == "__main__":
    main()
