#!/usr/bin/env python3
"""Convert approved v7 linked cutouts into the Spine builder manifest schema."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
LINKED = ROOT / "linked_parts.generated.json"
OUT = ROOT / "thief_v7_spine_manifest.json"
CANVAS_CENTER = (627.0, 627.0)

# Absolute pivots in the 1254x1254 master canvas.
BONES = [
    ("Root", "", (627.0, 627.0)),
    ("Pelvis", "Root", (650.0, 740.0)),
    ("Torso", "Pelvis", (650.0, 620.0)),
    ("Head", "Torso", (530.0, 515.0)),
    ("NearLeg", "Pelvis", (525.0, 705.0)),
    ("NearShinFoot", "NearLeg", (540.0, 855.0)),
    ("NearFoot", "NearShinFoot", (545.0, 925.0)),
    ("FarLeg", "Pelvis", (800.0, 720.0)),
    ("FarShinFoot", "FarLeg", (865.0, 860.0)),
    ("FarFoot", "FarShinFoot", (915.0, 925.0)),
    ("NearArm", "Torso", (445.0, 615.0)),
    ("NearForearm", "NearArm", (390.0, 700.0)),
    ("NearHand", "NearForearm", (315.0, 815.0)),
    ("Dagger", "NearHand", (285.0, 850.0)),
    ("FarArm", "Torso", (790.0, 475.0)),
    ("FarForearm", "FarArm", (820.0, 575.0)),
    ("FarHand", "FarForearm", (705.0, 525.0)),
    ("Bag", "Torso", (820.0, 410.0)),
    ("BagStrap", "Torso", (700.0, 430.0)),
    ("Cloak", "Torso", (700.0, 450.0)),
    ("Scarf", "Torso", (530.0, 515.0)),
]

PART_BONE = {
    "cape_back": "Cloak",
    "loot_sack": "Bag",
    "sack_knot": "Bag",
    "sack_strap": "BagStrap",
    "body_underpaint": "Pelvis",
    "pelvis_waist_cloth": "Pelvis",
    "far_thigh": "FarLeg",
    "far_shin": "FarShinFoot",
    "far_boot": "FarFoot",
    "near_thigh": "NearLeg",
    "near_shin": "NearShinFoot",
    "near_boot": "NearFoot",
    "far_upper_arm": "FarArm",
    "near_upper_arm": "NearArm",
    "torso_core": "Torso",
    "far_shoulder_plate": "FarArm",
    "far_forearm": "FarForearm",
    "hooded_head": "Head",
    "eye_glow": "Head",
    "near_shoulder_plate": "NearArm",
    "near_forearm": "NearForearm",
    "dagger": "Dagger",
    "near_dagger_hand": "NearHand",
    "belt_and_pouch": "Pelvis",
    "far_hand_strap_grip": "FarHand",
    "scarf_front": "Scarf",
}


def centered(point: tuple[float, float]) -> list[float]:
    return [point[0] - CANVAS_CENTER[0], point[1] - CANVAS_CENTER[1]]


def main() -> None:
    linked = json.loads(LINKED.read_text(encoding="utf-8"))
    pivots = {name: point for name, _, point in BONES}
    bone_records = [
        {
            "name": name,
            "parent": parent,
            "pivot": centered(point),
            "source_pivot_xy": list(point),
        }
        for name, parent, point in BONES
    ]
    part_records = []
    for record in linked["parts"]:
        semantic = record["semantic"]
        bone = PART_BONE[semantic]
        texture_rel = record["file"]
        texture_abs = ROOT / texture_rel
        width, height = Image.open(texture_abs).size
        origin_x, origin_y = record["canvas_origin_xy"]
        center_source = (origin_x + width / 2.0, origin_y + height / 2.0)
        pivot_source = pivots[bone]
        part_records.append(
            {
                "name": semantic,
                "bone": bone,
                "texture": "res://source_assets/monsters/generated_parts/thief_raider_v7/" + texture_rel.replace("\\", "/"),
                "pivot": centered(pivot_source),
                "sprite_offset": [
                    center_source[0] - pivot_source[0],
                    center_source[1] - pivot_source[1],
                ],
                "z": int(record["draw_order"]),
                "semantic": semantic,
                "source_center_xy": list(center_source),
                "source_pivot_xy": list(pivot_source),
                "visible_alpha_area": int(record["visible_alpha_area"]),
                "hidden_underlap_area": int(record["hidden_underlap_area"]),
            }
        )
    missing = sorted(set(PART_BONE) - {part["name"] for part in part_records})
    if missing:
        raise RuntimeError(f"Missing linked parts: {missing}")
    manifest = {
        "thief_raider": {
            "source": "source_assets/monsters/generated_parts/thief_raider_v7/master_candidate_01_alpha.png",
            "bind_reference": "source_assets/monsters/generated_parts/thief_raider_v7/master_candidate_01_alpha.png",
            "pipeline": "master_owned_linked_cutout_v7",
            "canvas": [1254, 1254],
            "bones": bone_records,
            "parts": part_records,
            "bind_qa": linked["bind_qa"],
            "status": "isolated_spine_prototype_only"
        }
    }
    OUT.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"THIEF_V7_SPINE_MANIFEST bones={len(bone_records)} parts={len(part_records)} out={OUT}")


if __name__ == "__main__":
    main()
