#!/usr/bin/env python3
"""Partition the current Thief Raider master into semantic visible ownership.

The v4 generated rig is used only as a geometric proxy for automatic labels.
Every output color/alpha pixel comes from the immutable current master.  The
resulting bind reconstruction is therefore exact; hidden joint extensions are
added by a later, separately audited stage.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[3]
MASTER_PATH = ROOT / "00_reference/current_master.png"
PROXY_MANIFEST = PROJECT / "build/thief_v4_ai_manifest.json"
OUT_ROOT = ROOT / "03_master_ownership"
PARTS_DIR = OUT_ROOT / "parts"
MANIFEST_PATH = OUT_ROOT / "master_ownership.manifest.json"
RECOMPOSED_PATH = OUT_ROOT / "bind_reconstruction.png"
LABEL_PATH = OUT_ROOT / "ownership_labels.png"
OVERLAY_PATH = OUT_ROOT / "ownership_overlay.png"
CONTACT_PATH = OUT_ROOT / "parts_contact.png"


def _short_semantic(value: str) -> str:
    prefix = "smooth_left_facing_"
    return value[len(prefix):] if value.startswith(prefix) else value


def _load_proxy_parts(canvas: tuple[int, int]) -> list[dict[str, object]]:
    data = json.loads(PROXY_MANIFEST.read_text(encoding="utf-8-sig"))["thief_raider"]
    if tuple(data["canvas"]) != canvas:
        raise RuntimeError(f"proxy canvas {data['canvas']} does not match master {canvas}")
    records: list[dict[str, object]] = []
    for order, entry in enumerate(sorted(data["parts"], key=lambda item: (item["z"], item["name"]))):
        texture_resource = str(entry["texture"])
        if not texture_resource.startswith("res://"):
            raise RuntimeError(f"unexpected proxy resource: {texture_resource}")
        texture_path = PROJECT / texture_resource.removeprefix("res://")
        if not texture_path.is_file():
            raise FileNotFoundError(texture_path)
        texture = np.asarray(Image.open(texture_path).convert("RGBA"), dtype=np.uint8)
        center_x, center_y = map(float, entry["source_center_xy"])
        left = int(round(center_x - texture.shape[1] / 2.0))
        top = int(round(center_y - texture.shape[0] / 2.0))
        canvas_rgba = np.zeros((canvas[1], canvas[0], 4), dtype=np.uint8)
        src_x0 = max(0, -left)
        src_y0 = max(0, -top)
        dst_x0 = max(0, left)
        dst_y0 = max(0, top)
        width = min(texture.shape[1] - src_x0, canvas[0] - dst_x0)
        height = min(texture.shape[0] - src_y0, canvas[1] - dst_y0)
        if width <= 0 or height <= 0:
            raise RuntimeError(f"proxy part is outside canvas: {entry['name']}")
        canvas_rgba[dst_y0:dst_y0 + height, dst_x0:dst_x0 + width] = texture[
            src_y0:src_y0 + height, src_x0:src_x0 + width
        ]
        semantic = _short_semantic(str(entry["semantic"]))
        records.append(
            {
                "index": order,
                "semantic": semantic,
                "z": int(entry["z"]),
                "proxy_path": texture_path,
                "proxy_canvas": canvas_rgba,
                "proxy_center": [center_x, center_y],
                "bone": str(entry["bone"]),
            }
        )
    return records


def _yellow_eye_mask(master: np.ndarray, head_hint: np.ndarray) -> np.ndarray:
    rgb = master[:, :, :3]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    # Tight yellow range plus the head proxy keeps metal and skin highlights out.
    mask = (
        (hsv[:, :, 0] >= 18)
        & (hsv[:, :, 0] <= 42)
        & (hsv[:, :, 1] >= 130)
        & (hsv[:, :, 2] >= 150)
        & head_hint
    )
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    keep = np.zeros_like(mask)
    candidates: list[tuple[int, int]] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        if 3 <= area <= 120 and 120 <= x <= 260 and 70 <= y <= 220:
            candidates.append((area, label))
    for _, label in sorted(candidates, reverse=True)[:2]:
        keep |= labels == label
    if int(keep.sum()) < 6:
        raise RuntimeError("eye-glow extraction did not find both yellow islands")
    return keep


def _initial_labels(master: np.ndarray, proxies: list[dict[str, object]]) -> np.ndarray:
    foreground = master[:, :, 3] > 0
    labels = np.full(foreground.shape, -1, dtype=np.int16)

    # First reproduce the intended proxy draw order.  Alpha ownership is much
    # more coherent than per-pixel RGB matching: front slots overwrite back
    # slots exactly as they would in Spine/Godot.
    solid_masks: list[np.ndarray] = []
    for index, proxy in enumerate(proxies):
        rgba = np.asarray(proxy["proxy_canvas"], dtype=np.uint8)
        solid = rgba[:, :, 3] > 12
        solid_masks.append(solid)
        labels[solid & foreground] = index

    missing = foreground & (labels < 0)
    if not np.any(missing):
        return labels

    # The rejected proxy composite misses roughly 12% of the master area.  Fill
    # only those uncovered master pixels by nearest semantic silhouette.  Do
    # not revisit already-owned pixels with noisy color classification.
    distances: list[np.ndarray] = []
    for proxy, solid in zip(proxies, solid_masks, strict=True):
        distance = cv2.distanceTransform((~solid).astype(np.uint8), cv2.DIST_L2, 5)
        # Prefer the frontmost slot only on exact distance ties.
        distance -= float(proxy["z"]) * 0.0001
        distances.append(distance)
    nearest = np.argmin(np.stack(distances, axis=0), axis=0).astype(np.int16)
    labels[missing] = nearest[missing]
    labels[~foreground] = -1
    return labels


def _remove_tiny_islands(
    labels: np.ndarray,
    iterations: int = 3,
    area_threshold: int = 18,
) -> np.ndarray:
    result = labels.copy()
    for _ in range(iterations):
        changed = 0
        for value in sorted(int(v) for v in np.unique(result) if v >= 0):
            binary = (result == value).astype(np.uint8)
            count, components, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
            for component in range(1, count):
                area = int(stats[component, cv2.CC_STAT_AREA])
                if area >= area_threshold:
                    continue
                island = components == component
                border = cv2.dilate(island.astype(np.uint8), np.ones((3, 3), np.uint8), 1).astype(bool)
                neighbours = result[border & ~island & (result >= 0)]
                if not len(neighbours):
                    continue
                replacement = Counter(map(int, neighbours)).most_common(1)[0][0]
                result[island] = replacement
                changed += area
        if not changed:
            break
    return result


def _consolidate_visible_parts(
    labels: np.ndarray,
    master: np.ndarray,
    proxies: list[dict[str, object]],
) -> tuple[np.ndarray, list[dict[str, object]]]:
    """Remove proxy-only fragments and merge joints with no useful bind pixels.

    The hidden upper-arm/cape-root/shin geometry returns later as generated
    underlap donors.  Keeping contaminated one-pixel islands here would only
    recreate the square-cutout failure the user rejected.
    """

    by_semantic = {str(item["semantic"]): index for index, item in enumerate(proxies)}
    merge_into = {
        "far_shin": "far_boot",
        "near_shin": "near_boot",
        "far_upper_arm": "far_forearm_bracer",
    }
    removed = {"upper_back_cloak"}
    result = labels.copy()
    for source, target in merge_into.items():
        result[result == by_semantic[source]] = by_semantic[target]
    for semantic in removed:
        result[result == by_semantic[semantic]] = -1

    hsv = cv2.cvtColor(master[:, :, :3], cv2.COLOR_RGB2HSV)
    hue, saturation, value = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    yy, xx = np.indices(result.shape)
    foreground = master[:, :, 3] > 0
    material = {
        "magenta": foreground & (hue >= 150) & (saturation >= 48) & (value >= 25),
        "brown": foreground & (hue <= 28) & (saturation >= 42) & (value >= 22),
        "metal": foreground & (saturation <= 48) & (value >= 82),
    }
    material["yellow"] = (
        foreground
        & (hue >= 18)
        & (hue <= 42)
        & (saturation >= 120)
        & (value >= 130)
    )
    material["brown"] &= ~material["yellow"]
    material["dark"] = foreground & ~(
        material["magenta"]
        | material["brown"]
        | material["metal"]
        | material["yellow"]
    )

    # The proxy dagger silhouette swallowed most of the visible dagger hand.
    # Recover the compact skin/leather cluster without taking the metal guard or
    # the dark handle to its right.
    brown_hand = (
        (xx >= 82)
        & (xx <= 132)
        & (yy >= 304)
        & (yy <= 366)
        & (hue <= 22)
        & (saturation >= 48)
        & (value >= 48)
        & (master[:, :, 3] > 0)
    )
    dagger_index = by_semantic["dagger"]
    near_hand_index = by_semantic["near_dagger_hand"]
    result[brown_hand & ((result == dagger_index) | (result == near_hand_index))] = near_hand_index

    # The lower hood proxy includes a strip of the front scarf.  Material hue
    # and the tight head/scarf region separate it deterministically.
    magenta = material["magenta"]
    head_index = by_semantic["hooded_head"]
    scarf_index = by_semantic["scarf"]
    result[(result == head_index) & magenta] = scarf_index

    active_old = [
        index
        for index, item in enumerate(proxies)
        if str(item["semantic"]) not in removed and str(item["semantic"]) not in merge_into
    ]

    preferred_materials = {
        "cloak_tail_far": ("magenta",),
        "cloak_tail_near": ("magenta",),
        "loot_sack": ("brown",),
        "far_boot": ("brown",),
        "sack_strap": ("brown",),
        "far_thigh": ("dark",),
        "near_boot": ("brown",),
        "near_thigh": ("dark",),
        "pelvis_skirt": ("dark",),
        "torso_core": ("dark",),
        "far_forearm_bracer": ("dark", "metal", "brown"),
        "far_strap_hand": ("brown",),
        "belt_and_pouch": ("brown", "metal"),
        "near_upper_arm": ("dark",),
        "near_forearm_bracer": ("dark", "metal", "brown"),
        "near_dagger_hand": ("brown",),
        "far_shoulder_plate": ("metal",),
        "near_shoulder_plate": ("metal",),
        "scarf": ("magenta",),
        "hooded_head": ("dark", "metal"),
        "dagger": ("metal", "dark", "brown"),
    }
    compatible_materials = {
        "cloak_tail_far": ("magenta", "dark"),
        "cloak_tail_near": ("magenta", "dark"),
        "loot_sack": ("brown", "dark"),
        "far_boot": ("brown", "dark"),
        "sack_strap": ("brown", "dark"),
        "far_thigh": ("dark",),
        "near_boot": ("brown", "dark"),
        "near_thigh": ("dark",),
        "pelvis_skirt": ("dark",),
        "torso_core": ("dark",),
        "far_forearm_bracer": ("dark", "metal", "brown"),
        "far_strap_hand": ("brown", "dark"),
        "belt_and_pouch": ("brown", "metal", "dark"),
        "near_upper_arm": ("dark",),
        "near_forearm_bracer": ("dark", "metal", "brown"),
        "near_dagger_hand": ("brown", "dark"),
        "far_shoulder_plate": ("metal", "dark"),
        "near_shoulder_plate": ("metal", "dark"),
        "scarf": ("magenta", "dark"),
        "hooded_head": ("dark", "metal"),
        "dagger": ("metal", "dark", "brown"),
    }

    # Keep the dominant connected visible island for every attachment.  Pixels
    # discarded here are re-owned by the nearest coherent silhouette below.
    coherent = np.full_like(result, -1)
    for index in active_old:
        semantic = str(proxies[index]["semantic"])
        candidate = result == index
        preferred = np.zeros_like(candidate)
        for material_name in preferred_materials[semantic]:
            preferred |= material[material_name]
        core = candidate & preferred
        if np.any(core):
            expanded = cv2.dilate(core.astype(np.uint8), np.ones((5, 5), np.uint8), 1).astype(bool)
            candidate &= expanded
        binary = candidate.astype(np.uint8)
        count, components, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
        if count <= 1:
            continue
        ranked = sorted(
            range(1, count),
            key=lambda component: int(stats[component, cv2.CC_STAT_AREA]),
            reverse=True,
        )
        largest_area = int(stats[ranked[0], cv2.CC_STAT_AREA])
        keep_count = 1
        # A strap may be hidden briefly behind the gripping hand; retain one
        # second substantial segment, never arbitrary confetti.
        if str(proxies[index]["semantic"]) == "sack_strap" and len(ranked) > 1:
            second_area = int(stats[ranked[1], cv2.CC_STAT_AREA])
            if second_area >= max(30, int(largest_area * 0.18)):
                keep_count = 2
        for component in ranked[:keep_count]:
            coherent[components == component] = index

    missing = foreground & (coherent < 0)
    distance_fields: list[np.ndarray] = []
    for index in active_old:
        seed = coherent == index
        if not np.any(seed):
            raise RuntimeError(f"no coherent visible seed for {proxies[index]['semantic']}")
        semantic = str(proxies[index]["semantic"])
        score = cv2.distanceTransform((~seed).astype(np.uint8), cv2.DIST_L2, 5)
        compatible = np.zeros_like(seed)
        for material_name in compatible_materials[semantic]:
            compatible |= material[material_name]
        # A material mismatch must never beat spatial proximity.  The previous
        # soft penalty let scarf/cape slots steal leather and metal pixels,
        # which becomes visibly wrong the moment the bone rotates.
        score = score + (~compatible & foreground).astype(np.float32) * 720.0
        distance_fields.append(score)
    nearest_slot = np.argmin(np.stack(distance_fields, axis=0), axis=0)
    active_array = np.asarray(active_old, dtype=np.int16)
    coherent[missing] = active_array[nearest_slot[missing]]
    coherent[~foreground] = -1
    coherent = _remove_tiny_islands(coherent, iterations=3, area_threshold=100)

    def reassign_to_nearest(mask: np.ndarray, semantics: tuple[str, ...]) -> None:
        target_indices = [by_semantic[name] for name in semantics]
        fields = []
        for target_index in target_indices:
            seed = coherent == target_index
            if not np.any(seed):
                raise RuntimeError(f"missing material target seed: {proxies[target_index]['semantic']}")
            fields.append(cv2.distanceTransform((~seed).astype(np.uint8), cv2.DIST_L2, 5))
        closest = np.argmin(np.stack(fields, axis=0), axis=0)
        targets = np.asarray(target_indices, dtype=np.int16)
        coherent[mask] = targets[closest[mask]]

    # All saturated wine cloth belongs to one of the three soft-cloth slots.
    # This removes cape pixels that the approximate proxy silhouettes handed to
    # the bag, legs, pelvis and torso without globally shuffling other colors.
    cloth_targets = ("cloak_tail_far", "cloak_tail_near", "scarf")
    cloth_indices = {by_semantic[name] for name in cloth_targets}
    wrong_magenta = material["magenta"] & ~np.isin(coherent, list(cloth_indices))
    reassign_to_nearest(wrong_magenta, cloth_targets)

    # The remaining brown pixels on the torso are visible strap/belt/hand
    # material, never torso cloth.  Limit the repair to that one polluted label
    # so distant leather details do not become global nearest-neighbour specks.
    wrong_torso_brown = material["brown"] & (coherent == by_semantic["torso_core"])
    reassign_to_nearest(
        wrong_torso_brown,
        ("loot_sack", "sack_strap", "far_strap_hand", "belt_and_pouch"),
    )

    rename = {
        "far_boot": "far_lower_leg",
        "near_boot": "near_lower_leg",
        "far_forearm_bracer": "far_arm_visible",
    }
    new_proxies: list[dict[str, object]] = []
    remapped = np.full_like(coherent, -1)
    for new_index, old_index in enumerate(active_old):
        proxy = dict(proxies[old_index])
        original_semantic = str(proxy["semantic"])
        proxy["semantic"] = rename.get(original_semantic, original_semantic)
        proxy["index"] = new_index
        new_proxies.append(proxy)
        remapped[coherent == old_index] = new_index
    remapped[~foreground] = -1
    return remapped, new_proxies


def _palette(count: int) -> list[tuple[int, int, int]]:
    result: list[tuple[int, int, int]] = []
    for index in range(count):
        hue = int(round(index * 179 / max(1, count)))
        hsv = np.uint8([[[hue, 185, 245]]])
        rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)[0, 0]
        result.append(tuple(map(int, rgb)))
    return result


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def main() -> None:
    master = np.asarray(Image.open(MASTER_PATH).convert("RGBA"), dtype=np.uint8)
    height, width = master.shape[:2]
    proxies = _load_proxy_parts((width, height))
    labels = _remove_tiny_islands(_initial_labels(master, proxies))
    labels, proxies = _consolidate_visible_parts(labels, master, proxies)

    # Eyes get their own light/flicker attachment after the geometry proxy pass.
    head_index = next(
        index for index, item in enumerate(proxies) if item["semantic"] == "hooded_head"
    )
    eye_mask = _yellow_eye_mask(master, labels == head_index)
    eye_index = len(proxies)
    labels[eye_mask] = eye_index
    proxies.append(
        {
            "index": eye_index,
            "semantic": "eye_glow",
            "z": 41,
            "proxy_path": None,
            "proxy_canvas": np.zeros_like(master),
            "proxy_center": [float(np.where(eye_mask)[1].mean()), float(np.where(eye_mask)[0].mean())],
            "bone": "Head",
        }
    )

    foreground = master[:, :, 3] > 0
    if np.any(labels[foreground] < 0):
        raise RuntimeError("unowned foreground pixels remain")
    counts = np.bincount(labels[foreground], minlength=len(proxies))
    if np.any(counts == 0):
        missing = [proxies[i]["semantic"] for i, count in enumerate(counts) if count == 0]
        raise RuntimeError(f"ownership parts with no visible pixels: {missing}")

    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    for stale in PARTS_DIR.glob("*.png"):
        stale.unlink()

    records: list[dict[str, object]] = []
    reconstructed = np.zeros_like(master)
    palette = _palette(len(proxies))
    label_image = np.zeros((height, width, 4), dtype=np.uint8)
    for index, proxy in enumerate(proxies):
        mask = labels == index
        ys, xs = np.where(mask)
        x0, y0 = int(xs.min()), int(ys.min())
        x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
        crop = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
        local = mask[y0:y1, x0:x1]
        master_crop = master[y0:y1, x0:x1]
        crop[local] = master_crop[local]
        semantic = str(proxy["semantic"])
        filename = f"{index:02d}_{semantic}.png"
        Image.fromarray(crop, "RGBA").save(PARTS_DIR / filename)
        reconstructed[mask] = master[mask]
        label_image[mask] = (*palette[index], 255)
        sha256 = hashlib.sha256((PARTS_DIR / filename).read_bytes()).hexdigest()
        records.append(
            {
                "index": index,
                "semantic": semantic,
                "file": f"parts/{filename}",
                "bone": str(proxy["bone"]),
                "z": int(proxy["z"]),
                "source_bbox": [x0, y0, x1 - x0, y1 - y0],
                "source_center": list(map(float, proxy["proxy_center"])),
                "visible_pixel_count": int(mask.sum()),
                "texture_source": "00_reference/current_master.png",
                "geometric_proxy": (
                    None
                    if proxy["proxy_path"] is None
                    else Path(proxy["proxy_path"]).relative_to(PROJECT).as_posix()
                ),
                "sha256": sha256,
                "status": "visible_ownership_requires_boundary_review",
            }
        )

    if not np.array_equal(reconstructed, master):
        mismatch = int(np.any(reconstructed != master, axis=2).sum())
        raise RuntimeError(f"exact bind reconstruction failed at {mismatch} pixels")
    Image.fromarray(reconstructed, "RGBA").save(RECOMPOSED_PATH)
    Image.fromarray(label_image, "RGBA").save(LABEL_PATH)

    overlay = Image.fromarray(master, "RGBA")
    colored = Image.fromarray(label_image, "RGBA")
    colored.putalpha(Image.fromarray(np.where(foreground, 105, 0).astype(np.uint8), "L"))
    overlay.alpha_composite(colored)
    overlay.save(OVERLAY_PATH)

    tile_w, tile_h = 240, 210
    cols = 5
    rows = math.ceil(len(records) / cols)
    contact = Image.new("RGB", (cols * tile_w, rows * tile_h), (29, 32, 38))
    draw = ImageDraw.Draw(contact)
    font = _font(15)
    for record in records:
        part = Image.open(OUT_ROOT / record["file"]).convert("RGBA")
        part.thumbnail((tile_w - 20, tile_h - 45), Image.Resampling.LANCZOS)
        index = int(record["index"])
        col, row = index % cols, index // cols
        x = col * tile_w + (tile_w - part.width) // 2
        y = row * tile_h + 30 + (tile_h - 35 - part.height) // 2
        contact.paste(part, (x, y), part)
        draw.text(
            (col * tile_w + 7, row * tile_h + 6),
            f"{index:02d} {record['semantic']}",
            fill=(238, 238, 238),
            font=font,
        )
    contact.save(CONTACT_PATH)

    manifest = {
        "schema_version": 1,
        "identity_source": MASTER_PATH.relative_to(ROOT).as_posix(),
        "identity_sha256": hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest(),
        "geometric_proxy_manifest": PROXY_MANIFEST.relative_to(PROJECT).as_posix(),
        "policy": "proxy alpha guides labels only; every output RGBA pixel is copied from the immutable master",
        "canvas": [width, height],
        "part_count": len(records),
        "foreground_pixel_count": int(foreground.sum()),
        "owned_foreground_pixel_count": int(sum(item["visible_pixel_count"] for item in records)),
        "bind_reconstruction": {
            "exact_rgba": True,
            "mismatch_pixels": 0,
            "alpha_iou": 1.0,
        },
        "status": "exact_bind_pass_boundary_review_pending",
        "parts": records,
    }
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        "THIEF_V9_MASTER_OWNERSHIP_PASS "
        f"parts={len(records)} pixels={int(foreground.sum())} rgba_exact=true"
    )


if __name__ == "__main__":
    main()
