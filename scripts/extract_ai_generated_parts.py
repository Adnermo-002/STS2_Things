#!/usr/bin/env python3
"""Extract isolated image-to-image cutout assets from approved sprite sheets.

The source sheets are generated from the original monster paintings.  This
stage only crops already separated objects; it never partitions an assembled
monster canvas, so a crop cannot borrow pixels from a neighbouring body part.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SHEETS = ROOT / "source_assets" / "monsters" / "generated_parts"
OUTPUT = ROOT / "source_assets" / "monsters" / "ai_cutout_parts"


@dataclass(frozen=True)
class SheetSpec:
    key: str
    path: Path
    min_area: int = 140
    alpha_threshold: int = 12


SPECS = (
    SheetSpec("scale_beetle", SHEETS / "scale_beetle" / "parts_sheet.png"),
    SheetSpec("bowlbug_progenitor", SHEETS / "bowlbug_progenitor" / "parts_sheet_v2.png"),
    SheetSpec("origin_fogmog", SHEETS / "origin_fogmog" / "parts_sheet.png"),
    SheetSpec("origin_fogmog_supplement", SHEETS / "origin_fogmog_supplement" / "parts_sheet.png"),
    SheetSpec("thief_raider", SHEETS / "thief_raider" / "parts_sheet.png"),
    SheetSpec("thief_raider_supplement", SHEETS / "thief_raider_supplement" / "parts_sheet.png"),
    SheetSpec("the_legacy", SHEETS / "the_legacy" / "parts_sheet_v2.png"),
    SheetSpec("the_legacy_green", SHEETS / "the_legacy" / "parts_sheet.png"),
    SheetSpec("soul_roes", SHEETS / "soul_roes" / "parts_sheet.png"),
)


def connected_components(spec: SheetSpec) -> list[dict[str, object]]:
    image = Image.open(spec.path).convert("RGBA")
    rgba = np.asarray(image)
    alpha = rgba[:, :, 3]
    mask = (alpha >= spec.alpha_threshold).astype(np.uint8)

    # Join antialiased pixels belonging to one painted object without bridging
    # the generous grid gaps authored in the image-generation prompt.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)

    raw: list[dict[str, object]] = []
    for label in range(1, count):
        x, y, width, height, area = (int(v) for v in stats[label])
        if area < spec.min_area or width < 5 or height < 5:
            continue
        raw.append({
            "label": label,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "area": area,
            "cx": float(centroids[label][0]),
            "cy": float(centroids[label][1]),
        })

    # Stable visual reading order.  A 48px row bucket is small enough for the
    # dense atlas sheets but keeps same-row parts ordered left-to-right.
    raw.sort(key=lambda item: (round(float(item["cy"]) / 48), float(item["cx"])))
    out_dir = OUTPUT / spec.key
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("part_*.png"):
        stale.unlink()

    entries: list[dict[str, object]] = []
    for index, item in enumerate(raw):
        label = int(item["label"])
        x, y = int(item["x"]), int(item["y"])
        width, height = int(item["width"]), int(item["height"])
        pad = 4
        left, top = max(0, x - pad), max(0, y - pad)
        right, bottom = min(image.width, x + width + pad), min(image.height, y + height + pad)
        crop = rgba[top:bottom, left:right].copy()
        local_labels = labels[top:bottom, left:right]
        crop[local_labels != label] = 0
        path = out_dir / f"part_{index:03d}.png"
        Image.fromarray(crop, "RGBA").save(path, optimize=True)
        entries.append({
            "name": path.stem,
            "path": path.relative_to(ROOT).as_posix(),
            "source_bbox": [left, top, right, bottom],
            "source_center": [round(float(item["cx"]), 3), round(float(item["cy"]), 3)],
            "size": [right - left, bottom - top],
            "opaque_area": int(item["area"]),
        })

    shutil.copy2(spec.path, out_dir / "source_sheet.png")
    (out_dir / "components.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return entries


def extract_soul_roe_grid() -> list[dict[str, object]]:
    """Crop the 3x5 generated Soul Roe layout as fixed cells.

    Transparent membrane highlights are intentionally disconnected, so alpha
    connected-components would split one semantic layer into several files.
    The generation contract gives us a deterministic three-row/five-column
    layout instead.
    """

    # v4 is the corrected image-to-image sheet: the cytoplasm, nucleus,
    # membrane ring and vein/specular layer are genuinely independent pieces.
    # (v2's so-called membrane still contained a dark assembled-cell interior.)
    source = SHEETS / "soul_roe_variants" / "parts_sheet_v4_clean.png"
    image = Image.open(source).convert("RGBA")
    out_dir = OUTPUT / "soul_roe_variants"
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("variant_*.png"):
        stale.unlink()

    width, height = image.size
    x_edges = [0, 320, 650, 900, 1215, width]
    y_edges = [0, 340, 680, height]
    semantic = ("rear_glow", "cytoplasm", "nucleus", "membrane_ring", "veins_highlight")
    entries: list[dict[str, object]] = []
    for row in range(3):
        for col in range(5):
            box = (x_edges[col], y_edges[row], x_edges[col + 1], y_edges[row + 1])
            crop = image.crop(box)
            alpha_box = crop.getchannel("A").getbbox()
            if alpha_box is None:
                raise ValueError(f"empty Soul Roe generated grid cell row={row} col={col}")
            pad = 4
            left = max(0, alpha_box[0] - pad)
            top = max(0, alpha_box[1] - pad)
            right = min(crop.width, alpha_box[2] + pad)
            bottom = min(crop.height, alpha_box[3] + pad)
            trimmed = crop.crop((left, top, right, bottom))
            name = f"variant_{row + 1}_{semantic[col]}"
            path = out_dir / f"{name}.png"
            trimmed.save(path, optimize=True)
            entries.append({
                "name": name,
                "path": path.relative_to(ROOT).as_posix(),
                "variant": row + 1,
                "semantic": semantic[col],
                "grid": [row, col],
                "source_bbox": [box[0] + left, box[1] + top, box[0] + right, box[1] + bottom],
                "size": list(trimmed.size),
            })
    shutil.copy2(source, out_dir / "source_sheet.png")
    (out_dir / "components.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return entries


def extract_named_grid(
    *,
    source: Path,
    output_key: str,
    x_edges: list[int],
    y_edges: list[int],
    names: tuple[str, ...],
) -> list[dict[str, object]]:
    """Extract a generated semantic grid without fragmenting disconnected art.

    The image-generation contract fixes both cell order and meaning. Cropping
    cells instead of connected components keeps details such as eye glows,
    buckles and specular accents attached to their intended rig layer.
    """

    image = Image.open(source).convert("RGBA")
    expected = (len(x_edges) - 1) * (len(y_edges) - 1)
    if len(names) != expected:
        raise ValueError(f"{output_key}: expected {expected} semantic names, got {len(names)}")
    out_dir = OUTPUT / output_key
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.png"):
        if stale.name != "source_sheet.png":
            stale.unlink()

    entries: list[dict[str, object]] = []
    index = 0
    for row in range(len(y_edges) - 1):
        for col in range(len(x_edges) - 1):
            box = (x_edges[col], y_edges[row], x_edges[col + 1], y_edges[row + 1])
            crop = image.crop(box)
            alpha_box = crop.getchannel("A").getbbox()
            if alpha_box is None:
                raise ValueError(f"{output_key}: empty grid cell row={row} col={col}")
            pad = 4
            left = max(0, alpha_box[0] - pad)
            top = max(0, alpha_box[1] - pad)
            right = min(crop.width, alpha_box[2] + pad)
            bottom = min(crop.height, alpha_box[3] + pad)
            name = names[index]
            path = out_dir / f"{name}.png"
            crop.crop((left, top, right, bottom)).save(path, optimize=True)
            entries.append({
                "name": name,
                "path": path.relative_to(ROOT).as_posix(),
                "grid": [row, col],
                "source_bbox": [box[0] + left, box[1] + top, box[0] + right, box[1] + bottom],
                "size": [right - left, bottom - top],
                "source_sheet": source.relative_to(ROOT).as_posix(),
            })
            index += 1
    shutil.copy2(source, out_dir / f"source_{source.stem}.png")
    return entries


def extract_thief_raider_v2_grids() -> list[dict[str, object]]:
    base = SHEETS / "thief_raider_v2"
    body_names = (
        "hooded_head", "scarf", "torso_harness", "pelvis_skirt",
        "upper_back_cloak", "cloak_tail_near", "cloak_tail_far", "loot_sack",
        "sack_strap_and_pouch", "belt_and_pouch", "near_shoulder_pauldron", "far_shoulder_pauldron",
    )
    limb_names = (
        "near_upper_arm", "near_forearm_bracer", "near_dagger_hand", "dagger",
        "far_upper_arm", "far_forearm_bracer", "far_strap_hand", "far_elbow_connector",
        "near_thigh", "near_knee_plate", "near_shin", "near_boot",
        "far_thigh", "far_knee_plate", "far_shin", "far_boot",
    )
    out = extract_named_grid(
        source=base / "body_sheet.png",
        output_key="thief_raider_v2",
        x_edges=[0, 313, 627, 940, 1254],
        y_edges=[0, 418, 836, 1254],
        names=body_names,
    )
    # Preserve body output while appending the 4x4 limb sheet.
    limb_temp_key = "thief_raider_v2_limbs"
    limbs = extract_named_grid(
        source=base / "limbs_sheet.png",
        output_key=limb_temp_key,
        x_edges=[0, 313, 627, 940, 1254],
        y_edges=[0, 313, 627, 940, 1254],
        names=limb_names,
    )
    arm_temp_key = "thief_raider_v2_upper_arms"
    upper_arms = extract_named_grid(
        source=base / "upper_arms_sheet.png",
        output_key=arm_temp_key,
        x_edges=[0, 746, 1492],
        y_edges=[0, 1054],
        names=("near_upper_arm_sleeve", "far_upper_arm_sleeve"),
    )
    final_dir = OUTPUT / "thief_raider_v2"
    temp_dir = OUTPUT / limb_temp_key
    for item in limbs:
        src = ROOT / str(item["path"])
        dst = final_dir / src.name
        shutil.copy2(src, dst)
        item["path"] = dst.relative_to(ROOT).as_posix()
    shutil.copy2(base / "limbs_sheet.png", final_dir / "source_limbs_sheet.png")
    shutil.rmtree(temp_dir)
    arm_temp_dir = OUTPUT / arm_temp_key
    for item in upper_arms:
        src = ROOT / str(item["path"])
        dst = final_dir / src.name
        shutil.copy2(src, dst)
        item["path"] = dst.relative_to(ROOT).as_posix()
    shutil.copy2(base / "upper_arms_sheet.png", final_dir / "source_upper_arms_sheet.png")
    shutil.rmtree(arm_temp_dir)
    entries = out + limbs + upper_arms
    (final_dir / "components.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return entries


def extract_thief_raider_v3_grids() -> list[dict[str, object]]:
    """Extract the smooth, compact, left-facing Raider-family redesign."""

    base = SHEETS / "thief_raider_v3"
    body_names = (
        "hooded_head", "scarf", "torso_core", "pelvis_skirt",
        "upper_back_cloak", "cloak_tail_near", "cloak_tail_far", "loot_sack",
        "sack_strap", "belt_and_pouch", "near_shoulder_plate", "far_shoulder_plate",
    )
    limb_names = (
        "near_upper_arm", "near_forearm_bracer", "near_dagger_hand", "dagger",
        "far_upper_arm", "far_forearm_bracer", "far_strap_hand", "far_elbow_connector",
        "near_thigh", "near_shin", "near_boot", "near_knee_connector",
        "far_thigh", "far_shin", "far_boot", "far_knee_connector",
    )
    body_temp = "thief_raider_v3_body"
    limb_temp = "thief_raider_v3_limbs"
    body = extract_named_grid(
        source=base / "body_sheet.png",
        output_key=body_temp,
        x_edges=[0, 362, 724, 1086, 1448],
        y_edges=[0, 362, 724, 1086],
        names=body_names,
    )
    limbs = extract_named_grid(
        source=base / "limbs_sheet.png",
        output_key=limb_temp,
        x_edges=[0, 362, 724, 1086, 1448],
        y_edges=[0, 272, 543, 815, 1086],
        names=limb_names,
    )
    final_dir = OUTPUT / "thief_raider_v3"
    final_dir.mkdir(parents=True, exist_ok=True)
    for stale in final_dir.glob("*.png"):
        stale.unlink()
    entries: list[dict[str, object]] = []
    for group, temp_key in ((body, body_temp), (limbs, limb_temp)):
        for item in group:
            src = ROOT / str(item["path"])
            dst = final_dir / src.name
            shutil.copy2(src, dst)
            item["path"] = dst.relative_to(ROOT).as_posix()
            entries.append(item)
        shutil.rmtree(OUTPUT / temp_key)
    shutil.copy2(base / "body_sheet.png", final_dir / "source_body_sheet.png")
    shutil.copy2(base / "limbs_sheet.png", final_dir / "source_limbs_sheet.png")
    (final_dir / "components.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return entries


def extract_thief_raider_v4_grids() -> list[dict[str, object]]:
    """Extract the facet-free Raider-family repaint used by the production rig."""

    base = SHEETS / "thief_raider_v4"
    body_names = (
        "hooded_head", "scarf", "torso_core", "pelvis_skirt",
        "upper_back_cloak", "cloak_tail_near", "cloak_tail_far", "loot_sack",
        "sack_strap", "belt_and_pouch", "near_shoulder_plate", "far_shoulder_plate",
    )
    limb_names = (
        "near_upper_arm", "near_forearm_bracer", "near_dagger_hand", "dagger",
        "far_upper_arm", "far_forearm_bracer", "far_strap_hand", "far_elbow_connector",
        "near_thigh", "near_shin", "near_boot", "near_knee_connector",
        "far_thigh", "far_shin", "far_boot", "far_knee_connector",
    )
    body_temp = "thief_raider_v4_body"
    limb_temp = "thief_raider_v4_limbs"
    body = extract_named_grid(
        source=base / "body_sheet.png",
        output_key=body_temp,
        x_edges=[0, 362, 724, 1086, 1448],
        y_edges=[0, 362, 724, 1086],
        names=body_names,
    )
    limbs = extract_named_grid(
        source=base / "limbs_sheet.png",
        output_key=limb_temp,
        x_edges=[0, 362, 724, 1086, 1448],
        y_edges=[0, 272, 543, 815, 1086],
        names=limb_names,
    )
    final_dir = OUTPUT / "thief_raider_v4"
    final_dir.mkdir(parents=True, exist_ok=True)
    for stale in final_dir.glob("*.png"):
        stale.unlink()
    entries: list[dict[str, object]] = []
    for group, temp_key in ((body, body_temp), (limbs, limb_temp)):
        for item in group:
            src = ROOT / str(item["path"])
            # A few generated objects cross a grid boundary by only a handful
            # of pixels.  Those pixels belong to the neighbouring cell and
            # would otherwise become detached islands in the rig.  Every v4
            # semantic part is authored as one connected object, so crop to
            # the largest alpha component while retaining antialias padding.
            with Image.open(src).convert("RGBA") as component_image:
                alpha = np.asarray(component_image.getchannel("A"))
                count, _, stats, _ = cv2.connectedComponentsWithStats(
                    (alpha >= 12).astype(np.uint8), connectivity=8
                )
                if count > 1:
                    main = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
                    x = int(stats[main, cv2.CC_STAT_LEFT])
                    y = int(stats[main, cv2.CC_STAT_TOP])
                    width = int(stats[main, cv2.CC_STAT_WIDTH])
                    height = int(stats[main, cv2.CC_STAT_HEIGHT])
                    pad = 3
                    left = max(0, x - pad)
                    top = max(0, y - pad)
                    right = min(component_image.width, x + width + pad)
                    bottom = min(component_image.height, y + height + pad)
                    component_image.crop((left, top, right, bottom)).save(
                        src, optimize=True
                    )
                    old_box = list(item["source_bbox"])
                    item["source_bbox"] = [
                        old_box[0] + left,
                        old_box[1] + top,
                        old_box[0] + right,
                        old_box[1] + bottom,
                    ]
                    item["size"] = [right - left, bottom - top]
            dst = final_dir / src.name
            shutil.copy2(src, dst)
            item["path"] = dst.relative_to(ROOT).as_posix()
            entries.append(item)
        shutil.rmtree(OUTPUT / temp_key)
    shutil.copy2(base / "body_sheet.png", final_dir / "source_body_sheet.png")
    shutil.copy2(base / "limbs_sheet.png", final_dir / "source_limbs_sheet.png")
    (final_dir / "components.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return entries


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report: dict[str, int] = {}
    for spec in SPECS:
        if not spec.path.is_file():
            raise FileNotFoundError(spec.path)
        entries = connected_components(spec)
        report[spec.key] = len(entries)
        print(f"{spec.key}: {len(entries)} generated semantic objects")
    variants = extract_soul_roe_grid()
    report["soul_roe_variants"] = len(variants)
    print(f"soul_roe_variants: {len(variants)} generated semantic objects")
    thief_v2 = extract_thief_raider_v2_grids()
    report["thief_raider_v2"] = len(thief_v2)
    print(f"thief_raider_v2: {len(thief_v2)} generated semantic objects")
    thief_v3 = extract_thief_raider_v3_grids()
    report["thief_raider_v3"] = len(thief_v3)
    print(f"thief_raider_v3: {len(thief_v3)} generated semantic objects")
    thief_v4 = extract_thief_raider_v4_grids()
    report["thief_raider_v4"] = len(thief_v4)
    print(f"thief_raider_v4: {len(thief_v4)} generated semantic objects")
    (OUTPUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
