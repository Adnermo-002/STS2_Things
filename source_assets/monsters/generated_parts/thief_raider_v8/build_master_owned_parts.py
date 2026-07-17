#!/usr/bin/env python3
"""Build coherent master-pixel ownership for Thief Raider v8.

Unlike the rejected v7 nearest-fill pass, this version uses explicit inner
seeds and bounded semantic regions. Every bind-pose pixel remains sourced from
the single coherent master, while ownership cannot jump arbitrarily across the
character.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
MASTER = ROOT / "01_master_candidates/candidate_01_alpha.png"
OUT = ROOT / "03_clean_parts/master_owned_parts"
MANIFEST = ROOT / "03_clean_parts/master_owned_parts.json"
PREVIEW = ROOT / "03_clean_parts/master_ownership_preview.png"
CONTACT = ROOT / "03_clean_parts/master_owned_parts_contact.png"


@dataclass(frozen=True)
class Spec:
    name: str
    allowed: tuple[tuple[int, int], ...]
    seed: tuple[tuple[int, int], ...]
    material: str = "any"


SPECS = (
    Spec("cape_back", ((600,265),(875,265),(1060,570),(1045,830),(820,830),(690,620),(605,470)), ((700,315),(850,350),(1010,620),(970,770),(835,735),(720,500)), "plum"),
    Spec("loot_sack", ((750,285),(920,300),(970,430),(950,555),(850,585),(760,505)), ((800,350),(880,350),(930,430),(900,520),(820,535),(785,430)), "leather"),
    Spec("sack_knot", ((750,275),(895,275),(910,420),(760,420)), ((785,305),(860,305),(875,385),(790,395)), "leather"),
    Spec("far_boot", ((790,790),(955,790),(1015,900),(990,1035),(815,1040),(785,920)), ((840,860),(945,860),(970,985),(835,1005)), "leather"),
    Spec("far_shin", ((775,780),(930,770),(945,910),(785,930)), ((810,805),(895,800),(910,885),(810,900)), "dark"),
    Spec("far_thigh", ((645,660),(865,650),(925,785),(875,905),(705,885),(640,770)), ((690,690),(810,680),(875,780),(825,850),(720,830),(670,755)), "dark"),
    Spec("near_boot", ((405,795),(625,790),(650,1015),(400,1025)), ((455,860),(590,850),(615,985),(435,990)), "leather"),
    Spec("near_shin", ((435,780),(635,775),(645,915),(430,925)), ((475,810),(595,805),(610,885),(455,895)), "dark"),
    Spec("near_thigh", ((400,650),(665,640),(705,785),(620,890),(425,865),(390,760)), ((450,690),(600,680),(660,770),(580,840),(450,815),(425,750)), "dark"),
    Spec("pelvis_coat", ((470,585),(820,580),(860,700),(830,770),(730,790),(650,730),(515,795),(455,710)), ((510,620),(790,620),(825,690),(790,740),(715,755),(645,700),(525,755),(485,690)), "dark"),
    Spec("torso_core", ((430,330),(845,330),(900,650),(830,740),(465,740),(410,545)), ((505,405),(750,390),(820,550),(770,690),(500,680),(450,540)), "dark"),
    Spec("belt", ((545,585),(810,585),(815,695),(535,695)), ((575,615),(785,615),(790,675),(565,675)), "belt"),
    Spec("hooded_head", ((335,170),(660,170),(675,455),(605,515),(370,510),(330,365)), ((395,220),(585,215),(635,350),(570,475),(390,465),(365,330)), "dark"),
    Spec("scarf_front", ((345,270),(775,270),(800,520),(630,615),(390,570),(335,420)), ((395,330),(690,320),(730,450),(595,565),(420,535),(370,425)), "plum"),
    Spec("free_shoulder_plate", ((645,330),(870,330),(875,505),(640,505)), ((680,355),(825,355),(850,470),(665,480)), "silver"),
    Spec("free_upper_arm", ((735,400),(900,415),(915,550),(855,605),(775,565),(720,465)), ((770,430),(855,440),(885,525),(835,575),(780,545),(740,465)), "dark"),
    Spec("free_forearm", ((690,490),(850,490),(865,600),(820,655),(700,625),(675,545)), ((720,515),(820,510),(840,580),(805,625),(715,605),(695,545)), "silver"),
    Spec("free_hand", ((585,485),(760,480),(775,635),(620,650),(575,570)), ((620,515),(715,500),(750,585),(650,625),(600,570)), "hand"),
    Spec("dagger_shoulder_plate", ((370,440),(515,440),(520,595),(365,595)), ((400,475),(485,480),(490,555),(390,560)), "silver"),
    Spec("dagger_upper_arm", ((370,490),(525,485),(540,675),(335,695),(345,555)), ((400,520),(490,525),(510,645),(365,655),(370,560)), "dark"),
    Spec("dagger_forearm", ((250,590),(470,585),(480,795),(235,815)), ((300,630),(430,625),(450,750),(275,770)), "arm"),
    Spec("dagger_hand", ((220,700),(405,700),(405,875),(220,880)), ((260,740),(365,735),(385,835),(250,850)), "hand"),
    Spec("dagger", ((65,730),(430,730),(440,930),(65,930)), ((95,840),(250,775),(405,770),(400,850),(230,885),(90,905)), "weapon"),
    Spec("eye_glow", ((400,350),(535,350),(535,455),(400,455)), ((425,380),(505,380),(515,435),(415,435)), "yellow"),
)

CLAIM_ORDER = (
    "eye_glow", "dagger_hand", "dagger", "dagger_forearm",
    "dagger_shoulder_plate", "dagger_upper_arm", "free_hand", "free_forearm",
    "free_shoulder_plate", "free_upper_arm", "scarf_front", "hooded_head",
    "belt", "near_boot", "far_boot", "pelvis_coat", "near_thigh", "far_thigh",
    "near_shin", "far_shin", "sack_knot", "loot_sack", "cape_back",
    "torso_core",
)


PALETTE = (
    (240,75,72),(255,170,65),(255,220,70),(86,190,105),(34,190,210),(72,150,245),
    (125,90,205),(235,65,150),(145,110,95),(110,145,160),(0,150,135),(205,220,65),
)


def poly(shape: tuple[int, int], points: tuple[tuple[int, int], ...]) -> np.ndarray:
    result = np.zeros(shape, np.uint8)
    cv2.fillPoly(result, [np.array(points, np.int32)], 255)
    return result > 0


def material_masks(rgba: np.ndarray) -> dict[str, np.ndarray]:
    rgb = rgba[:, :, :3].astype(np.float32)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    chroma = mx - mn
    plum = (r > 48) & (r > g * 1.45) & (b > g * 1.08) & (b > 34)
    leather = (r > 45) & (r > g * 1.18) & (g > b * 1.08) & (chroma > 15)
    silver = (mx > 90) & (chroma < 45)
    skin = (r > 115) & (g > 55) & (r > g * 1.25) & (g > b * 1.08)
    yellow = (r > 150) & (g > 100) & (b < 100) & (r > b * 1.8)
    dark = (mx < 125) & (chroma < 40)
    return {
        "any": np.ones(r.shape, bool),
        "plum": plum,
        "leather": leather,
        "silver": silver,
        "skin": skin,
        "yellow": yellow,
        "dark": dark,
        "belt": leather | silver,
        "arm": dark | leather | silver,
        "hand": skin | leather,
        "weapon": silver | leather,
    }


def clean_seed(seed: np.ndarray, allowed: np.ndarray, material: np.ndarray) -> np.ndarray:
    selected = seed & allowed & material
    # Retain anti-aliased/material-adjacent pixels by a small dilation, but never
    # cross the semantic allowed region.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    selected = cv2.dilate(selected.astype(np.uint8), kernel) > 0
    return selected & allowed


def keep_large_components(mask: np.ndarray, minimum: int = 40) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    result = np.zeros_like(mask)
    for label in range(1, count):
        if int(stats[label, cv2.CC_STAT_AREA]) >= minimum:
            result |= labels == label
    return result


def main() -> None:
    rgba = np.array(Image.open(MASTER).convert("RGBA"))
    h, w = rgba.shape[:2]
    alpha = rgba[:, :, 3] > 8
    materials = material_masks(rgba)

    allowed: list[np.ndarray] = []
    seeds: list[np.ndarray] = []
    for spec in SPECS:
        region = poly((h, w), spec.allowed) & alpha
        seed_region = poly((h, w), spec.seed) & alpha
        seed = clean_seed(seed_region, region, materials[spec.material])
        if int(seed.sum()) < 20:
            raise RuntimeError(f"{spec.name}: seed too small ({int(seed.sum())})")
        allowed.append(region)
        seeds.append(seed)

    allowed_union = np.zeros((h, w), bool)
    for region in allowed:
        allowed_union |= region
    uncovered = alpha & ~allowed_union
    if uncovered.any():
        ys, xs = np.where(uncovered)
        raise RuntimeError(
            f"semantic allowed regions miss {int(uncovered.sum())} alpha pixels; "
            f"bbox={(int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))}"
        )

    by_name = {spec.name: index for index, spec in enumerate(SPECS)}
    if set(CLAIM_ORDER) != set(by_name):
        raise RuntimeError("CLAIM_ORDER must contain every semantic exactly once")

    labels = np.full((h, w), -1, np.int16)
    # First claim material-consistent pixels front-to-back. This is the crucial
    # difference from v7: a dark torso region cannot steal burgundy cape pixels,
    # and a thigh cannot absorb a leather boot merely because its seed is closer.
    for name in CLAIM_ORDER:
        index = by_name[name]
        spec = SPECS[index]
        claim = allowed[index] & materials[spec.material] & alpha & (labels < 0)
        labels[claim] = index

    # Inner semantic seeds are authoritative even when a painterly pixel falls
    # just outside a color classifier.
    for name in CLAIM_ORDER:
        index = by_name[name]
        claim = seeds[index] & alpha & (labels < 0)
        labels[claim] = index

    # Fill only the remaining anti-aliased/ambiguous pixels. Distance is bounded
    # by each semantic region and receives a strong material mismatch penalty.
    unresolved = alpha & (labels < 0)
    best_cost = np.full((h, w), np.float32(1.0e9), np.float32)
    replacement = np.full((h, w), -1, np.int16)
    for index, (spec, region) in enumerate(zip(SPECS, allowed, strict=True)):
        owned = labels == index
        if not owned.any():
            owned = seeds[index]
        distance = cv2.distanceTransform(np.where(owned, 0, 255).astype(np.uint8), cv2.DIST_L2, 5)
        mismatch = ~materials[spec.material]
        cost = distance + mismatch.astype(np.float32) * np.float32(120.0)
        cost = np.where(region, cost, np.float32(1.0e8))
        better = unresolved & (cost < best_cost)
        best_cost[better] = cost[better]
        replacement[better] = index
    labels[unresolved] = replacement[unresolved]

    if np.any(alpha & (labels < 0)):
        raise RuntimeError(f"unassigned alpha pixels: {int(np.sum(alpha & (labels < 0)))}")

    # Remove tiny islands created only by intersecting allowed regions, then
    # reassign them to the nearest surviving semantic region.
    masks = [labels == index for index in range(len(SPECS))]
    removed = np.zeros((h, w), bool)
    for index, mask in enumerate(masks):
        clean = keep_large_components(mask)
        removed |= mask & ~clean
        masks[index] = clean
    if removed.any():
        best_cost.fill(np.float32(1.0e9))
        replacement = np.full((h, w), -1, np.int16)
        for index, mask in enumerate(masks):
            distance = cv2.distanceTransform(np.where(mask, 0, 255).astype(np.uint8), cv2.DIST_L2, 5)
            cost = np.where(allowed[index], distance, np.float32(1.0e8))
            better = removed & (cost < best_cost)
            best_cost[better] = cost[better]
            replacement[better] = index
        if np.any(removed & (replacement < 0)):
            raise RuntimeError("tiny-island reassignment failed")
        for index in range(len(masks)):
            masks[index] |= removed & (replacement == index)

    union = np.zeros((h, w), bool)
    overlap = 0
    for mask in masks:
        overlap += int((union & mask).sum())
        union |= mask
    if not np.array_equal(union, alpha) or overlap:
        raise RuntimeError(
            f"ownership mismatch coverage={int(union.sum())}/{int(alpha.sum())} overlap={overlap}"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.png"):
        stale.unlink()
    preview = np.zeros_like(rgba)
    records: list[dict[str, object]] = []
    for index, (spec, mask) in enumerate(zip(SPECS, masks, strict=True)):
        ys, xs = np.where(mask)
        if not len(xs):
            raise RuntimeError(f"empty final mask: {spec.name}")
        part = rgba.copy()
        part[:, :, 3] = np.where(mask, rgba[:, :, 3], 0)
        filename = f"{index:02d}_{spec.name}.png"
        Image.fromarray(part, "RGBA").save(OUT / filename)
        color = PALETTE[index % len(PALETTE)]
        preview[mask, :3] = color
        preview[mask, 3] = 235
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
        components = sum(1 for label in range(1, count) if int(stats[label, cv2.CC_STAT_AREA]) >= 10)
        records.append(
            {
                "index": index,
                "semantic": spec.name,
                "file": f"master_owned_parts/{filename}",
                "alpha_area": int(mask.sum()),
                "bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
                "connected_components_ge_10px": components,
            }
        )
    Image.fromarray(preview, "RGBA").save(PREVIEW)

    # Render a compact contact sheet of visible master ownership.
    thumb_w, thumb_h, cols = 250, 210, 5
    rows = math.ceil(len(records) / cols)
    contact = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (36, 40, 47))
    draw = ImageDraw.Draw(contact)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 17)
    except OSError:
        font = ImageFont.load_default()
    for record in records:
        full = Image.open(ROOT / "03_clean_parts" / record["file"]).convert("RGBA")
        crop = full.crop(full.getchannel("A").getbbox())
        crop.thumbnail((thumb_w - 24, thumb_h - 48), Image.Resampling.LANCZOS)
        index = int(record["index"])
        col, row = index % cols, index // cols
        x = col * thumb_w + (thumb_w - crop.width) // 2
        y = row * thumb_h + 30 + (thumb_h - 42 - crop.height) // 2
        contact.paste(crop, (x, y), crop)
        draw.text((col * thumb_w + 7, row * thumb_h + 6), str(record["semantic"]), fill=(235,235,235), font=font)
    contact.save(CONTACT)

    manifest = {
        "schema_version": 1,
        "master": MASTER.relative_to(ROOT).as_posix(),
        "part_count": len(records),
        "master_alpha_area": int(alpha.sum()),
        "owned_alpha_area": int(union.sum()),
        "coverage_ratio": float(union.sum() / max(1, alpha.sum())),
        "overlap_pixels": overlap,
        "unmanifested_png_count": 0,
        "visible_pixel_source": "single_v8_master_only",
        "status": "semantic_ownership_draft_requires_visual_review",
        "parts": records,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        f"THIEF_V8_MASTER_OWNERSHIP_PASS parts={len(records)} "
        f"coverage={manifest['coverage_ratio']:.6f} overlap={overlap}"
    )


if __name__ == "__main__":
    main()
