#!/usr/bin/env python3
"""Compare coherent generated-body assembly against exact locked overlays."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "thief_raider_v11" / "00_reference" / "visible_baseline"
SOURCE = HERE / "02_semantic_parts" / "master_mesh_sources_v01"
UNDER = SOURCE / "generated_hidden_underpaint"
OUT = HERE / "03_bind_review" / "static_assembly_probe_v01"
MASTER = HERE / "00_reference" / "thief_raider_locked_master.png"


def over(bottom: np.ndarray, top: np.ndarray) -> np.ndarray:
    image = Image.fromarray(bottom, "RGBA")
    image.alpha_composite(Image.fromarray(top, "RGBA"))
    return np.asarray(image, dtype=np.uint8)


def load_exact() -> tuple[list[dict], dict[str, np.ndarray]]:
    manifest = json.loads((BASE / "visible_baseline.manifest.json").read_text(encoding="utf-8"))
    width, height = manifest["canvas"]
    parts = {}
    for record in manifest["parts"]:
        canvas = np.zeros((height, width, 4), dtype=np.uint8)
        crop = np.asarray(Image.open(BASE / record["file"]).convert("RGBA"), dtype=np.uint8)
        x, y, w, h = map(int, record["source_bbox"])
        canvas[y : y + h, x : x + w] = crop
        parts[record["semantic"]] = canvas
    return manifest["parts"], parts


def load_generated(name: str) -> np.ndarray:
    return np.asarray(Image.open(UNDER / f"{name}_warped_full_debug.png").convert("RGBA"), dtype=np.uint8)


def render_generated_body(parts: dict[str, np.ndarray]) -> np.ndarray:
    shape = next(iter(parts.values())).shape
    result = np.zeros(shape, dtype=np.uint8)
    # Exact background identity layers.
    for semantic in ("cape_back", "loot_sack", "bag_knot", "strap_back"):
        result = over(result, parts[semantic])
    # Coherent continuous generated anatomy, in true back-to-front order.
    for semantic in ("far_leg", "far_arm", "torso", "near_leg"):
        result = over(result, load_generated(semantic))
    # Exact identity pieces that do not create limb joints.
    for semantic in (
        "far_shoulder_plate",
        "hooded_head",
        "eye_glow",
        "near_arm",
        "near_shoulder_plate",
        "dagger",
        "belt",
        "pouch",
        "far_strap_hand",
        "scarf_front",
    ):
        if semantic == "near_arm":
            result = over(result, load_generated("near_arm"))
        else:
            result = over(result, parts[semantic])
    return result


def render_generated_plus_exact(records: list[dict], parts: dict[str, np.ndarray]) -> np.ndarray:
    result = render_generated_body(parts)
    # Repaint all locked ownership last only for identity comparison.  This is
    # not the planned draw order; it proves the generated anatomy can remain a
    # hidden continuity layer without altering bind pixels.
    for record in sorted(records, key=lambda item: (int(item["z"]), int(item["index"]))):
        result = over(result, parts[record["semantic"]])
    return result


def contact(images: list[tuple[str, np.ndarray]], output: Path) -> None:
    cell_w, cell_h = 620, 500
    sheet = Image.new("RGBA", (len(images) * cell_w, cell_h), (27, 31, 39, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (label, array) in enumerate(images):
        x0 = index * cell_w
        draw.text((x0 + 10, 9), label, fill=(245, 247, 250, 255), font=font)
        shown = Image.fromarray(array, "RGBA")
        bbox = shown.getchannel("A").getbbox()
        if bbox:
            shown = shown.crop(bbox)
        scale = min(570 / max(1, shown.width), 420 / max(1, shown.height), 1.25)
        shown = shown.resize((max(1, round(shown.width * scale)), max(1, round(shown.height * scale))), Image.Resampling.LANCZOS)
        sheet.alpha_composite(shown, (x0 + (cell_w - shown.width) // 2, 48 + (420 - shown.height) // 2))
    sheet.convert("RGB").save(output, quality=96)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records, parts = load_exact()
    master = np.asarray(Image.open(MASTER).convert("RGBA"), dtype=np.uint8)
    generated = render_generated_body(parts)
    covered = render_generated_plus_exact(records, parts)
    Image.fromarray(generated, "RGBA").save(OUT / "generated_body_exact_accessories.png")
    Image.fromarray(covered, "RGBA").save(OUT / "generated_continuity_beneath_exact_bind.png")
    contact(
        [
            ("LOCKED MASTER", master),
            ("GENERATED CONTINUOUS BODY + EXACT ACCESSORIES", generated),
            ("GENERATED CONTINUITY UNDER EXACT MASTER", covered),
        ],
        OUT / "static_assembly_comparison.jpg",
    )
    report = {
        "generated_visible_mismatch_pixels": int(np.any(generated != master, axis=2).sum()),
        "covered_bind_mismatch_pixels": int(np.any(covered != master, axis=2).sum()),
        "status": "visual_probe_only",
        "shipping_allowed": False,
    }
    (OUT / "audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
