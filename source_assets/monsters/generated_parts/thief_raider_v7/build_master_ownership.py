#!/usr/bin/env python3
"""Author semantic ownership masks from the coherent v7 master.

Every visible bind pixel comes from the master.  The generated parts sheet is
never used for visible bind-pose pixels; it is only a hidden-underlap donor.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
MASTER = ROOT / "master_candidate_01_alpha.png"
OUT = ROOT / "master_owned_parts"
PREVIEW = ROOT / "master_ownership_preview.png"
MANIFEST = ROOT / "master_ownership.generated.json"


def polygon(shape: tuple[int, int], points: list[tuple[int, int]]) -> np.ndarray:
    mask = np.zeros(shape, np.uint8)
    cv2.fillPoly(mask, [np.array(points, np.int32)], 255)
    return mask > 0


def main() -> None:
    rgba = np.array(Image.open(MASTER).convert("RGBA"))
    h, w = rgba.shape[:2]
    alpha = rgba[:, :, 3] > 0
    r = rgba[:, :, 0].astype(np.float32)
    g = rgba[:, :, 1].astype(np.float32)
    b = rgba[:, :, 2].astype(np.float32)
    plum = (r > 28) & (r > g * 1.22) & (b > g * 1.08) & (r < b * 2.15)
    leather = (r > 25) & (r > g * 1.18) & (b < g * 0.98)
    silver = (r > 85) & (np.maximum.reduce([r, g, b]) - np.minimum.reduce([r, g, b]) < 48)

    specs: list[tuple[str, np.ndarray]] = []

    def add(name: str, pts: list[tuple[int, int]], material: np.ndarray | None = None) -> None:
        region = polygon((h, w), pts)
        if material is not None:
            region &= material
        specs.append((name, region))

    # Foreground cloth and accessories first.
    add("scarf_front", [(390, 455), (420, 520), (480, 580), (570, 610), (650, 575), (704, 465), (690, 355), (625, 325), (600, 420), (535, 505), (455, 505)], plum)
    add("belt_and_pouch", [(535, 625), (875, 630), (890, 805), (560, 800)], leather | silver)

    # Near/weapon arm and dagger, screen-left.
    add("near_dagger_hand", [(228, 775), (330, 775), (390, 820), (382, 905), (285, 918), (230, 875)])
    add("dagger", [(72, 985), (70, 940), (250, 820), (420, 780), (430, 840), (285, 890)])
    add("near_forearm", [(270, 670), (380, 650), (445, 695), (415, 790), (350, 835), (275, 790)])
    add("near_upper_arm", [(345, 535), (465, 525), (520, 605), (475, 705), (390, 705), (342, 625)])

    # Strap hand is visually above torso and strap.
    add("far_hand_strap_grip", [(620, 430), (735, 420), (785, 525), (742, 615), (655, 600), (620, 525)])

    # Head/face; scarf pixels were removed above.
    add("hooded_head", [(345, 360), (385, 280), (500, 225), (610, 235), (655, 330), (645, 435), (575, 535), (430, 530), (365, 470)])

    # Near leg, screen-left, separated at cloth/leather seam bands.
    add("near_boot", [(430, 900), (630, 890), (660, 1045), (420, 1045)])
    add("near_shin", [(455, 820), (625, 815), (640, 955), (450, 965)])
    add("near_thigh", [(410, 645), (625, 645), (665, 815), (595, 900), (450, 890), (405, 805)])

    # Far arm on screen-right.  Shoulder plate stays with upper arm for the
    # first semantic pass; it can become a cover slot after bind approval.
    add("far_forearm", [(695, 495), (835, 500), (890, 565), (860, 665), (735, 655), (680, 565)])
    add("far_upper_arm", [(700, 390), (840, 400), (905, 500), (880, 585), (775, 565), (700, 485)])

    # Torso and pelvis.
    add("torso_core", [(465, 455), (825, 445), (910, 585), (850, 720), (790, 770), (530, 760), (455, 635)])
    add("pelvis_waist_cloth", [(455, 625), (860, 620), (880, 820), (420, 825)])

    # Far leg, screen-right.
    add("far_boot", [(835, 910), (1035, 905), (1040, 1045), (830, 1045)])
    add("far_shin", [(790, 815), (970, 810), (995, 960), (815, 970)])
    add("far_thigh", [(670, 635), (900, 645), (945, 820), (885, 910), (735, 900), (675, 810)])

    # Sack assembly behind body.
    add("sack_knot", [(775, 285), (915, 285), (920, 410), (775, 410)], leather)
    add("sack_strap", [(620, 320), (790, 325), (845, 520), (760, 595), (625, 520)], leather)
    add("loot_sack", [(765, 350), (930, 345), (1025, 430), (1025, 620), (940, 680), (800, 635), (760, 510)], leather)

    # Plum pixels not already owned are the three cape bands.  The split is
    # intentionally broad; later mesh/underlap work hides these internal seams.
    add("cape_upper", [(525, 315), (820, 310), (910, 650), (700, 760), (520, 650)], plum)
    add("cape_mid", [(610, 410), (1010, 405), (1080, 840), (785, 925), (610, 760)], plum)
    add("cape_tail", [(780, 500), (1198, 520), (1210, 990), (790, 995)], plum)

    remaining = alpha.copy()
    masks: dict[str, np.ndarray] = {}
    for name, proposed in specs:
        owned = proposed & remaining
        if name in masks:
            masks[name] |= owned
        else:
            masks[name] = owned
        remaining &= ~owned

    # Grow the nearest semantic seed into every unassigned master pixel. This
    # keeps each part spatially coherent instead of dumping uncertainty into a
    # giant, disconnected torso attachment.
    seed_union = np.zeros((h, w), bool)
    for mask in masks.values():
        seed_union |= mask
    distance_input = np.where(seed_union, 0, 255).astype(np.uint8)
    _, nearest_labels = cv2.distanceTransformWithLabels(
        distance_input,
        cv2.DIST_L2,
        5,
        labelType=cv2.DIST_LABEL_PIXEL,
    )
    label_to_part = np.full(int(nearest_labels.max()) + 1, -1, np.int16)
    names = list(masks)
    for part_index, name in enumerate(names):
        labels_for_part = np.unique(nearest_labels[masks[name]])
        label_to_part[labels_for_part] = part_index
    nearest_part = label_to_part[nearest_labels]
    for part_index, name in enumerate(names):
        masks[name] |= remaining & (nearest_part == part_index)
    still_unassigned = alpha.copy()
    for mask in masks.values():
        still_unassigned &= ~mask
    if still_unassigned.any():
        raise RuntimeError(f"Nearest-seed fill left {int(still_unassigned.sum())} pixels")
    remaining[:] = False

    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.png"):
        stale.unlink()
    palette = [
        (239, 83, 80), (255, 183, 77), (255, 238, 88), (102, 187, 106),
        (38, 198, 218), (66, 165, 245), (126, 87, 194), (236, 64, 122),
        (141, 110, 99), (120, 144, 156), (0, 137, 123), (205, 220, 57),
    ]
    preview = np.zeros_like(rgba)
    records = []
    union = np.zeros((h, w), bool)
    for index, (name, mask) in enumerate(masks.items()):
        union |= mask
        part = rgba.copy()
        part[:, :, 3] = np.where(mask, rgba[:, :, 3], 0)
        ys, xs = np.where(mask)
        if len(xs) == 0:
            bbox = None
            area = 0
        else:
            bbox = [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]
            area = int(mask.sum())
        Image.fromarray(part, "RGBA").save(OUT / f"{index:02d}_{name}.png")
        color = palette[index % len(palette)]
        preview[mask, :3] = color
        preview[mask, 3] = 235
        records.append({"index": index, "semantic": name, "area": area, "bbox_xyxy": bbox})

    Image.fromarray(preview, "RGBA").save(PREVIEW)
    manifest = {
        "schema_version": 1,
        "master": MASTER.name,
        "part_count": len(records),
        "master_alpha_area": int(alpha.sum()),
        "owned_alpha_area": int(union.sum()),
        "coverage_ratio": float(union.sum() / max(1, alpha.sum())),
        "overlap_pixels": int(sum(mask.sum() for mask in masks.values()) - union.sum()),
        "visible_pixel_source": "master_only",
        "status": "semantic_mask_draft_requires_visual_review",
        "parts": records,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        "THIEF_V7_OWNERSHIP_DRAFT "
        f"parts={len(records)} coverage={manifest['coverage_ratio']:.6f} "
        f"overlap={manifest['overlap_pixels']}"
    )


if __name__ == "__main__":
    main()
