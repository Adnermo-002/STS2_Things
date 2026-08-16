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
    (OUTPUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
