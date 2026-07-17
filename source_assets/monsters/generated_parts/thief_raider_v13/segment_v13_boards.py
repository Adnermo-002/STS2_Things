#!/usr/bin/env python3
"""Extract irregular semantic meshes from the v13 image-to-image boards.

This intentionally segments alpha silhouettes, not rectangular source-image
tiles.  Cropping is storage-only: every pixel outside each semantic silhouette
remains transparent.
"""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
BOARD_DIR = HERE / "01_imagegen_boards"
OUT = HERE / "02_semantic_parts"

BOARD_SPECS = {
    "body": {
        "file": BOARD_DIR / "body_semantic_meshes_v02_alpha.png",
        "expected": {
            "hooded_head_donor": (296, 255),
            "torso_pelvis_donor": (768, 262),
            "near_full_arm_donor": (1235, 284),
            "far_full_arm_donor": (319, 659),
            "near_full_leg_donor": (747, 716),
            "far_full_leg_donor": (1181, 712),
        },
    },
    "accessory": {
        "file": BOARD_DIR / "accessory_semantic_meshes_v01_alpha.png",
        "expected": {
            "scarf_front_donor": (237, 226),
            "scarf_back_donor": (557, 240),
            "cape_large_donor": (922, 271),
            "cape_far_donor": (1299, 282),
            "loot_sack_donor": (220, 571),
            "rope_back_donor": (537, 551),
            "rope_front_with_hand_rejected": (865, 598),
            "dagger_donor": (1288, 602),
            "shoulder_near_donor": (183, 834),
            "shoulder_far_donor": (497, 837),
            "forearm_near_donor": (729, 838),
            "forearm_far_donor": (957, 838),
            "belt_pouch_donor": (1298, 839),
        },
    },
}


def extract_components(path: Path, min_area: int = 300) -> list[dict]:
    image = np.asarray(Image.open(path).convert("RGBA"), dtype=np.uint8)
    mask = (image[:, :, 3] > 8).astype(np.uint8)
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask, 8)
    result = []
    for label in range(1, count):
        x, y, width, height, area = map(int, stats[label])
        if area < min_area:
            continue
        result.append(
            {
                "label": label,
                "bbox": [x, y, width, height],
                "area": area,
                "centroid": [float(centers[label][0]), float(centers[label][1])],
                "labels": labels,
                "image": image,
            }
        )
    return result


def assign(components: list[dict], expected: dict[str, tuple[float, float]]) -> dict[str, dict]:
    remaining = set(range(len(components)))
    assigned: dict[str, dict] = {}
    for name, target in expected.items():
        index = min(
            remaining,
            key=lambda i: math.dist(components[i]["centroid"], target),
        )
        assigned[name] = components[index]
        remaining.remove(index)
    if remaining:
        raise RuntimeError(f"unassigned connected components: {remaining}")
    return assigned


def save_component(component: dict, output: Path, padding: int = 14) -> dict:
    image = component["image"]
    labels = component["labels"]
    label = component["label"]
    x, y, width, height = component["bbox"]
    left = max(0, x - padding)
    top = max(0, y - padding)
    right = min(image.shape[1], x + width + padding)
    bottom = min(image.shape[0], y + height + padding)
    crop = image[top:bottom, left:right].copy()
    owned = labels[top:bottom, left:right] == label
    crop[~owned] = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(crop, "RGBA").save(output)
    return {
        "file": output.name,
        "source_bbox_xywh": [left, top, right - left, bottom - top],
        "foreground_area": int(owned.sum()),
        "centroid_xy": component["centroid"],
    }


def make_contact(records: list[dict], directory: Path, output: Path) -> None:
    cols = 4
    cell_w, cell_h = 390, 300
    rows = math.ceil(len(records) / cols)
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (27, 31, 39, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, record in enumerate(records):
        x0 = (index % cols) * cell_w
        y0 = (index // cols) * cell_h
        draw.text((x0 + 10, y0 + 8), record["semantic"], fill=(245, 246, 248, 255), font=font)
        part = Image.open(directory / record["file"]).convert("RGBA")
        scale = min(350 / max(1, part.width), 245 / max(1, part.height), 1.0)
        part = part.resize(
            (max(1, round(part.width * scale)), max(1, round(part.height * scale))),
            Image.Resampling.LANCZOS,
        )
        sheet.alpha_composite(part, (x0 + (cell_w - part.width) // 2, y0 + 38 + (245 - part.height) // 2))
    sheet.convert("RGB").save(output, quality=95)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 1, "boards": {}, "status": "donor_review_required"}
    for board_name, spec in BOARD_SPECS.items():
        board_out = OUT / board_name
        if board_out.exists():
            shutil.rmtree(board_out)
        board_out.mkdir(parents=True)
        components = extract_components(spec["file"])
        if len(components) != len(spec["expected"]):
            raise RuntimeError(
                f"{board_name}: expected {len(spec['expected'])} components, got {len(components)}"
            )
        matched = assign(components, spec["expected"])
        records = []
        for semantic, component in matched.items():
            record = {"semantic": semantic}
            record.update(save_component(component, board_out / f"{semantic}.png"))
            record["status"] = "rejected_embedded_hand" if semantic.endswith("_rejected") else "donor_only"
            records.append(record)
        make_contact(records, board_out, OUT / f"{board_name}_parts_contact.jpg")
        manifest["boards"][board_name] = {
            "source": str(spec["file"].relative_to(HERE)).replace("\\", "/"),
            "component_count": len(records),
            "parts": records,
        }
    (OUT / "semantic_parts.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "ok", "manifest": str(OUT / 'semantic_parts.manifest.json')}, indent=2))


if __name__ == "__main__":
    main()
