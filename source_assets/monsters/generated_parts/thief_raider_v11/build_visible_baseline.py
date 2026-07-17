#!/usr/bin/env python3
"""Build the v11 exact visible-pixel baseline without using rejected donors.

The v9 production-visible ownership is copied as the starting partition.  The
near arm chain is replaced by the manually corrected v10 ownership.  Every
opaque output pixel still comes byte-for-byte from the locked identity master.
This stage intentionally contains no generated underlap pixels.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
V9 = HERE.parent / "thief_raider_v9" / "04_production_attachments"
V10 = HERE.parent / "thief_raider_v10" / "00_reference" / "near_arm_ownership_v2"
MASTER = HERE / "00_reference" / "locked_master.png"
OUT = HERE / "00_reference" / "visible_baseline"
PARTS_OUT = OUT / "parts"


V10_REPLACEMENTS = {
    "near_upper_arm": ("near_upper_arm.png", [137, 226, 77, 64]),
    "near_forearm": ("near_forearm.png", [105, 262, 71, 57]),
    "near_shoulder_plate": ("near_shoulder_plate.png", [154, 200, 36, 34]),
    "near_dagger_hand": ("near_dagger_hand.png", [92, 309, 54, 49]),
    "dagger": ("dagger.png", [18, 314, 143, 76]),
}

# The v9 manifest placed the dagger above the gripping fingers.  Corrected v10
# ownership explicitly establishes dagger-under-hand as the production draw
# order, otherwise movement reveals the handle painted over the knuckles.
V10_DRAW_ORDER = {
    "near_upper_arm": 19,
    "near_forearm": 20,
    "near_shoulder_plate": 21,
    "dagger": 22,
    "near_dagger_hand": 23,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contact_sheet(parts: list[dict], output: Path) -> None:
    cols = 5
    cell_w, cell_h = 300, 210
    rows = math.ceil(len(parts) / cols)
    bg = (28, 32, 40, 255)
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), bg)
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for i, part in enumerate(parts):
        x0 = (i % cols) * cell_w
        y0 = (i // cols) * cell_h
        draw.text((x0 + 8, y0 + 7), f"{i:02d} {part['semantic']}", fill=(238, 240, 245, 255), font=font)
        draw.text(
            (x0 + 8, y0 + 23),
            f"visible={part['visible_pixel_count']}  z={part['z']}",
            fill=(125, 224, 177, 255) if part["visible_pixel_count"] else (245, 183, 78, 255),
            font=font,
        )
        image = Image.open(OUT / part["file"]).convert("RGBA")
        max_w, max_h = cell_w - 24, cell_h - 52
        scale = min(max_w / max(1, image.width), max_h / max(1, image.height), 2.0)
        size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        image = image.resize(size, Image.Resampling.LANCZOS)
        px = x0 + (cell_w - image.width) // 2
        py = y0 + 43 + (max_h - image.height) // 2
        sheet.alpha_composite(image, (px, py))

    sheet.convert("RGB").save(output, quality=95)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if PARTS_OUT.exists():
        shutil.rmtree(PARTS_OUT)
    PARTS_OUT.mkdir(parents=True)

    source_manifest = json.loads((V9 / "production_visible.manifest.json").read_text(encoding="utf-8"))
    master = np.array(Image.open(MASTER).convert("RGBA"))
    height, width = master.shape[:2]
    assert [width, height] == source_manifest["canvas"]

    canvas = np.zeros_like(master)
    occupancy = np.zeros((height, width), dtype=np.uint16)
    output_parts: list[dict] = []

    for source_part in source_manifest["parts"]:
        part = dict(source_part)
        semantic = part["semantic"]
        index = int(part["index"])
        out_name = f"{index:02d}_{semantic}.png"
        out_path = PARTS_OUT / out_name

        if semantic in V10_REPLACEMENTS:
            replacement_name, bbox = V10_REPLACEMENTS[semantic]
            source_path = V10 / replacement_name
            part["source_bbox"] = bbox
            part["ownership_source"] = "thief_raider_v10_corrected_near_arm"
        else:
            source_path = V9 / source_part["file"]
            part["ownership_source"] = "thief_raider_v9_exact_visible_partition"

        if semantic in V10_DRAW_ORDER:
            part["z"] = V10_DRAW_ORDER[semantic]

        shutil.copy2(source_path, out_path)
        image = np.array(Image.open(out_path).convert("RGBA"))
        x, y, w, h = map(int, part["source_bbox"])
        if image.shape[1] != w or image.shape[0] != h:
            raise ValueError(f"{semantic}: image {image.shape[1]}x{image.shape[0]} != bbox {w}x{h}")
        if x < 0 or y < 0 or x + w > width or y + h > height:
            raise ValueError(f"{semantic}: bbox outside canvas")

        alpha = image[:, :, 3] > 0
        region_occ = occupancy[y : y + h, x : x + w]
        region_occ[alpha] += 1
        region = canvas[y : y + h, x : x + w]
        region[alpha] = image[alpha]

        part["file"] = f"parts/{out_name}"
        part["visible_pixel_count"] = int(alpha.sum())
        part["sha256"] = sha256(out_path)
        part["status"] = "exact_master_visible_pixels" if alpha.any() else "context_reveal_required"
        output_parts.append(part)

    master_fg = master[:, :, 3] > 0
    uncovered = master_fg & (occupancy == 0)
    overlaps = occupancy > 1
    outside = (~master_fg) & (occupancy > 0)
    mismatch = np.any(canvas != master, axis=2)

    reconstruction_path = OUT / "bind_reconstruction.png"
    Image.fromarray(canvas, "RGBA").save(reconstruction_path)
    contact_sheet(output_parts, OUT / "visible_parts_contact.jpg")

    audit = {
        "foreground_pixels": int(master_fg.sum()),
        "owned_foreground_pixels": int((occupancy > 0).sum()),
        "uncovered_pixels": int(uncovered.sum()),
        "overlap_pixels": int(overlaps.sum()),
        "outside_pixels": int(outside.sum()),
        "mismatch_pixels": int(mismatch.sum()),
        "exact_rgba": bool(not mismatch.any()),
        "pass": bool(not uncovered.any() and not overlaps.any() and not outside.any() and not mismatch.any()),
    }
    if not audit["pass"]:
        raise RuntimeError(f"visible baseline audit failed: {audit}")

    manifest = {
        "schema_version": 1,
        "status": "exact_visible_baseline_pass_context_reveals_pending",
        "identity_source": "00_reference/locked_master.png",
        "identity_sha256": sha256(MASTER),
        "canvas": [width, height],
        "policy": "visible RGBA is copied from the locked master; generated pixels are forbidden in this stage",
        "source_v9_manifest": str((V9 / "production_visible.manifest.json").relative_to(PROJECT)).replace("\\", "/"),
        "source_v10_near_arm_manifest": str((V10 / "near_arm_ownership_v2.manifest.json").relative_to(PROJECT)).replace("\\", "/"),
        "audit": audit,
        "bind_reconstruction": {
            "file": "bind_reconstruction.png",
            "sha256": sha256(reconstruction_path),
        },
        "parts": output_parts,
    }
    (OUT / "visible_baseline.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
