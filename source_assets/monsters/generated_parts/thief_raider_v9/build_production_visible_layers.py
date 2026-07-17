#!/usr/bin/env python3
"""Map audited master ownership into the final v9 attachment contract.

This stage only rearranges current-master visible pixels.  Empty production
slots are explicit donor requirements, not hidden full-body paint.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
MASTER_PATH = ROOT / "00_reference/current_master.png"
OWNERSHIP_ROOT = ROOT / "03_master_ownership"
OWNERSHIP_MANIFEST = OWNERSHIP_ROOT / "master_ownership.manifest.json"
OUT_ROOT = ROOT / "04_production_attachments"
VISIBLE_DIR = OUT_ROOT / "visible"
MANIFEST_PATH = OUT_ROOT / "production_visible.manifest.json"
CONTACT_PATH = OUT_ROOT / "production_visible.contact.png"
RECONSTRUCTION_PATH = OUT_ROOT / "production_visible.bind.png"


# Back-to-front setup order and bind-pose source-space pivots.
CONTRACT = [
    ("cape_back", "CapeRoot", 1, (350, 160)),
    ("loot_sack", "BagSwing", 2, (365, 125)),
    ("bag_knot", "BagKnot", 3, (365, 105)),
    ("strap_back", "StrapRoot", 4, (300, 145)),
    ("far_boot", "FarFoot", 5, (401, 385)),
    ("far_shin", "FarShin", 6, (382, 345)),
    ("far_thigh", "FarThigh", 7, (354, 282)),
    ("far_upper_arm", "FarUpperArm", 8, (334, 170)),
    ("far_forearm", "FarForearm", 9, (350, 204)),
    ("far_shoulder_plate", "FarClavicle", 10, (331, 161)),
    ("torso_core", "SpineUpper", 11, (291, 242)),
    ("pelvis_tunic", "Pelvis", 12, (292, 282)),
    ("near_boot", "NearFoot", 13, (225, 390)),
    ("near_shin", "NearShin", 14, (215, 344)),
    ("near_thigh", "NearThigh", 15, (221, 279)),
    ("scarf_back", "ScarfRoot", 16, (260, 152)),
    ("hooded_head", "Head", 17, (235, 190)),
    ("eye_glow", "EyeGlow", 18, (182, 157)),
    ("near_upper_arm", "NearUpperArm", 19, (169, 232)),
    ("near_forearm", "NearForearm", 20, (138, 282)),
    ("near_shoulder_plate", "NearClavicle", 21, (171, 214)),
    ("near_dagger_hand", "NearHand", 22, (116, 331)),
    ("dagger", "Dagger", 23, (121, 340)),
    ("belt", "Pelvis", 24, (292, 254)),
    ("pouch", "PouchSwing", 25, (339, 254)),
    ("strap_front", "StrapGrip", 26, (295, 177)),
    ("far_strap_hand", "FarHand", 27, (290, 187)),
    ("scarf_front", "ScarfRoot", 28, (249, 194)),
]


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _ownership_layers(canvas: tuple[int, int]) -> dict[str, np.ndarray]:
    data = json.loads(OWNERSHIP_MANIFEST.read_text(encoding="utf-8"))
    layers: dict[str, np.ndarray] = {}
    for record in data["parts"]:
        x, y, width, height = map(int, record["source_bbox"])
        rgba = np.asarray(
            Image.open(OWNERSHIP_ROOT / record["file"]).convert("RGBA"),
            dtype=np.uint8,
        )
        if rgba.shape[:2] != (height, width):
            raise RuntimeError(f"ownership bbox mismatch: {record['semantic']}")
        full = np.zeros((canvas[1], canvas[0]), dtype=bool)
        full[y:y + height, x:x + width] = rgba[:, :, 3] > 0
        layers[str(record["semantic"])] = full
    return layers


def _empty_layers(shape: tuple[int, int]) -> dict[str, np.ndarray]:
    return {semantic: np.zeros(shape, dtype=bool) for semantic, _, _, _ in CONTRACT}


def main() -> None:
    master = np.asarray(Image.open(MASTER_PATH).convert("RGBA"), dtype=np.uint8)
    height, width = master.shape[:2]
    source = _ownership_layers((width, height))
    result = _empty_layers((height, width))
    yy, xx = np.indices((height, width))

    result["cape_back"] = source["cloak_tail_far"] | source["cloak_tail_near"]

    knot_region = (xx >= 332) & (xx <= 420) & (yy >= 74) & (yy <= 142)
    result["bag_knot"] = source["loot_sack"] & knot_region
    result["loot_sack"] = source["loot_sack"] & ~result["bag_knot"]
    result["strap_back"] = source["sack_strap"]

    far_boot_region = yy >= 376
    result["far_boot"] = source["far_lower_leg"] & far_boot_region
    result["far_shin"] = source["far_lower_leg"] & ~far_boot_region
    result["far_thigh"] = source["far_thigh"]
    # No trustworthy far-upper-arm visible pixels exist in the bind art.  B2
    # supplies a local hidden donor beneath the pauldron/forearm.
    result["far_forearm"] = source["far_arm_visible"]
    result["far_shoulder_plate"] = source["far_shoulder_plate"]

    result["torso_core"] = source["torso_core"]
    result["pelvis_tunic"] = source["pelvis_skirt"]

    near_boot_region = yy >= 377
    result["near_boot"] = source["near_lower_leg"] & near_boot_region
    result["near_shin"] = source["near_lower_leg"] & ~near_boot_region
    result["near_thigh"] = source["near_thigh"]

    result["hooded_head"] = source["hooded_head"]
    result["eye_glow"] = source["eye_glow"]
    result["near_upper_arm"] = source["near_upper_arm"]
    result["near_forearm"] = source["near_forearm_bracer"]
    result["near_shoulder_plate"] = source["near_shoulder_plate"]
    result["near_dagger_hand"] = source["near_dagger_hand"]
    result["dagger"] = source["dagger"]

    pouch_region = (xx >= 319) & (yy >= 239)
    result["pouch"] = source["belt_and_pouch"] & pouch_region
    result["belt"] = source["belt_and_pouch"] & ~result["pouch"]
    result["far_strap_hand"] = source["far_strap_hand"]
    result["scarf_front"] = source["scarf"]

    # Every original semantic must be consumed exactly once by the production
    # mapping.  Empty scarf_back/strap_front/far_upper_arm remain donor-only.
    master_foreground = master[:, :, 3] > 0
    coverage = np.zeros((height, width), dtype=np.uint8)
    for mask in result.values():
        coverage[mask] += 1
    uncovered = int((master_foreground & (coverage == 0)).sum())
    overlap = int((coverage > 1).sum())
    outside = int(((coverage > 0) & ~master_foreground).sum())
    if uncovered or overlap or outside:
        raise RuntimeError(
            f"production mapping invalid: uncovered={uncovered} overlap={overlap} outside={outside}"
        )

    VISIBLE_DIR.mkdir(parents=True, exist_ok=True)
    for stale in VISIBLE_DIR.glob("*.png"):
        stale.unlink()
    records = []
    reconstruction = np.zeros_like(master)
    for index, (semantic, bone, z, pivot) in enumerate(CONTRACT):
        mask = result[semantic]
        visible_pixels = int(mask.sum())
        if visible_pixels:
            ys, xs = np.where(mask)
            x0, y0 = int(xs.min()), int(ys.min())
            x1, y1 = int(xs.max()) + 1, int(ys.max()) + 1
            crop = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
            local = mask[y0:y1, x0:x1]
            source_crop = master[y0:y1, x0:x1]
            crop[local] = source_crop[local]
            reconstruction[mask] = master[mask]
            bbox = [x0, y0, x1 - x0, y1 - y0]
            status = "visible_master_owned_underlap_pending"
        else:
            crop = np.zeros((1, 1, 4), dtype=np.uint8)
            bbox = [0, 0, 1, 1]
            status = "donor_required_no_visible_master_pixels"
        filename = f"{index:02d}_{semantic}.png"
        path = VISIBLE_DIR / filename
        Image.fromarray(crop, "RGBA").save(path)
        records.append(
            {
                "index": index,
                "semantic": semantic,
                "file": f"visible/{filename}",
                "bone": bone,
                "z": z,
                "pivot_source_xy": list(pivot),
                "source_bbox": bbox,
                "visible_pixel_count": visible_pixels,
                "status": status,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )

    if not np.array_equal(reconstruction, master):
        mismatch = int(np.any(reconstruction != master, axis=2).sum())
        raise RuntimeError(f"production visible reconstruction mismatch: {mismatch}")
    Image.fromarray(reconstruction, "RGBA").save(RECONSTRUCTION_PATH)

    tile_w, tile_h, columns = 230, 190, 5
    rows = math.ceil(len(records) / columns)
    contact = Image.new("RGB", (columns * tile_w, rows * tile_h), (29, 32, 38))
    draw = ImageDraw.Draw(contact)
    font, state_font = _font(14), _font(12)
    for record in records:
        image = Image.open(OUT_ROOT / record["file"]).convert("RGBA")
        image.thumbnail((tile_w - 18, tile_h - 52), Image.Resampling.LANCZOS)
        index = int(record["index"])
        col, row = index % columns, index // columns
        x = col * tile_w + (tile_w - image.width) // 2
        y = row * tile_h + 44 + (tile_h - 48 - image.height) // 2
        contact.paste(image, (x, y), image)
        left, top = col * tile_w + 6, row * tile_h + 5
        draw.text((left, top), f"{index:02d} {record['semantic']}", fill=(240, 240, 240), font=font)
        color = (245, 184, 78) if not record["visible_pixel_count"] else (100, 220, 150)
        state = "DONOR REQUIRED" if not record["visible_pixel_count"] else "MASTER PIXELS"
        draw.text((left, top + 20), state, fill=color, font=state_font)
    contact.save(CONTACT_PATH)

    manifest = {
        "schema_version": 1,
        "identity_source": MASTER_PATH.relative_to(ROOT).as_posix(),
        "identity_sha256": hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest(),
        "source_ownership_manifest": OWNERSHIP_MANIFEST.relative_to(ROOT).as_posix(),
        "canvas": [width, height],
        "attachment_count": len(records),
        "visible_attachment_count": sum(bool(item["visible_pixel_count"]) for item in records),
        "donor_only_attachment_count": sum(not item["visible_pixel_count"] for item in records),
        "bind_reconstruction": {
            "exact_rgba": True,
            "uncovered_pixels": 0,
            "overlap_pixels": 0,
            "outside_pixels": 0,
        },
        "status": "production_visible_pass_underlap_pending",
        "parts": records,
    }
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        "THIEF_V9_PRODUCTION_VISIBLE_PASS "
        f"attachments={len(records)} donor_only={manifest['donor_only_attachment_count']} rgba_exact=true"
    )


if __name__ == "__main__":
    main()
