#!/usr/bin/env python3
"""Extract chroma-removed v5 donor sheets by their authored 4x4 grid.

These images are hidden-underlap donors only.  The approved master ownership
map remains the exclusive source of every visible bind-pose pixel.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
PADDING = 4

SHEETS = {
    "body": {
        "path": HERE / "body_sheet_alpha.png",
        "parts": [
            "hooded_head", "scarf_back", "scarf_front", "torso_core",
            "pelvis_skirt", "waist_cloth_front", "upper_back_cloak", "cloak_tail_near",
            "cloak_tail_far", "loot_sack", "bag_knot", "sack_strap_back",
            "sack_strap_front", "belt_and_pouch", "near_shoulder_plate", "far_shoulder_plate",
        ],
    },
    "limbs": {
        "path": HERE / "limbs_sheet_alpha.png",
        "parts": [
            "near_upper_arm", "near_forearm", "near_dagger_hand", "dagger",
            "far_upper_arm", "far_forearm", "far_strap_hand", "strap_grip",
            "near_thigh", "near_shin", "near_foot", "near_knee_cover",
            "far_thigh", "far_shin", "far_foot", "far_knee_cover",
        ],
    },
}


def extract_sheet(key: str, spec: dict) -> list[dict]:
    path: Path = spec["path"]
    if not path.is_file():
        return []
    sheet = Image.open(path).convert("RGBA")
    names: list[str] = spec["parts"]
    output_dir = HERE / key
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    for index, name in enumerate(names):
        row, col = divmod(index, 4)
        left = round(col * sheet.width / 4)
        right = round((col + 1) * sheet.width / 4)
        top = round(row * sheet.height / 4)
        bottom = round((row + 1) * sheet.height / 4)
        cell = sheet.crop((left, top, right, bottom))
        # Image generation occasionally leaves a small fragment from the
        # neighboring cell on a shared grid line.  Keep only the largest
        # alpha-connected semantic object; record the removed donor-only
        # pixels so a clipped sheet can never silently become visible art.
        rgba = np.asarray(cell).copy()
        mask = (rgba[:, :, 3] >= 2).astype(np.uint8)
        component_count, components, stats, _ = cv2.connectedComponentsWithStats(
            mask, connectivity=8
        )
        removed_component_pixels = 0
        if component_count > 2:
            largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            remove = (components != 0) & (components != largest)
            removed_component_pixels = int(np.count_nonzero(remove))
            rgba[remove] = 0
            cell = Image.fromarray(rgba, "RGBA")
        bbox = cell.getchannel("A").getbbox()
        if bbox is None:
            raise RuntimeError(f"{key}/{name}: empty grid cell")
        alpha = cell.getchannel("A")
        edge_pixels = {
            "top": sum(alpha.getpixel((x, 0)) > 0 for x in range(cell.width)),
            "bottom": sum(alpha.getpixel((x, cell.height - 1)) > 0 for x in range(cell.width)),
            "left": sum(alpha.getpixel((0, y)) > 0 for y in range(cell.height)),
            "right": sum(alpha.getpixel((cell.width - 1, y)) > 0 for y in range(cell.height)),
        }
        touches_boundary = any(edge_pixels.values())
        crop_box = (
            max(0, bbox[0] - PADDING),
            max(0, bbox[1] - PADDING),
            min(cell.width, bbox[2] + PADDING),
            min(cell.height, bbox[3] + PADDING),
        )
        part = cell.crop(crop_box)
        output = output_dir / f"{name}.png"
        part.save(output, optimize=True)
        records.append({
            "name": name,
            "sheet": path.name,
            "grid_rc": [row, col],
            "cell_xyxy": [left, top, right, bottom],
            "alpha_bbox_in_cell": list(bbox),
            "crop_xyxy_in_cell": list(crop_box),
            "output": output.relative_to(HERE).as_posix(),
            "size": list(part.size),
            "visible_pixels": sum(1 for value in part.getchannel("A").get_flattened_data() if value),
            "touches_grid_boundary": touches_boundary,
            "boundary_alpha_pixels": edge_pixels,
            "approved_for_underlap": not touches_boundary,
            "removed_neighbor_fragment_pixels": removed_component_pixels,
            "usage": (
                "hidden_underlap_donor_only" if not touches_boundary
                else "reference_only_clipped_at_grid_boundary"
            ),
        })
    return records


def save_montage(records: list[dict]) -> None:
    if not records:
        return
    cell_w, cell_h = 320, 280
    out = Image.new("RGBA", (cell_w * 4, cell_h * 4), (28, 30, 34, 255))
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default(size=15)
    for index, record in enumerate(records):
        part = Image.open(HERE / record["output"]).convert("RGBA")
        part.thumbnail((cell_w - 24, cell_h - 54), Image.Resampling.LANCZOS)
        x = (index % 4) * cell_w + (cell_w - part.width) // 2
        y = (index // 4) * cell_h + 38 + (cell_h - 54 - part.height) // 2
        out.alpha_composite(part, (x, y))
        draw.text(((index % 4) * cell_w + 8, (index // 4) * cell_h + 8), record["name"], fill="white", font=font)
    sheet_key = Path(records[0]["sheet"]).stem.replace("_sheet_alpha", "")
    out.save(HERE / f"{sheet_key}_parts_montage.png", optimize=True)


def main() -> None:
    report = {
        "schema": "thief-raider-v5-hidden-donor-grid/1",
        "visible_payload_rule": "approved_master ownership cutouts only",
        "sheets": {},
    }
    for key, spec in SHEETS.items():
        records = extract_sheet(key, spec)
        if not records:
            continue
        save_montage(records)
        report["sheets"][key] = {
            "source": spec["path"].name,
            "parts": records,
        }
    (HERE / "donor_parts.generated.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: len(value["parts"]) for key, value in report["sheets"].items()}))


if __name__ == "__main__":
    main()
