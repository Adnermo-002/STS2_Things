#!/usr/bin/env python3
"""Restore the custom monsters to one full-texture Sprite2D per scene."""

from __future__ import annotations

from build_spine_monsters import (
    SCENE_PROFILES,
    SCENE_ROOT,
    format_number,
    format_vector,
)


STATIC_SCRIPT = "res://STS2_Things/Visuals/NThingsStaticCreatureVisuals.cs"
TEXTURE_KEYS = {
    "origin_fogmog": "origin_fogmog",
    "bowlbug_progenitor": "bowlbug_progenitor",
    "scale_beetle": "scale_beetle",
    "soul_roe_1": "soul_roe_1",
    "soul_roe_2": "soul_roe_2",
    "soul_roe_3": "soul_roe_3",
    "soul_roes": "soul_roes",
    "the_legacy": "the_legacy",
    "thief_raider": "thief_raider",
}


def write_scene(key: str) -> None:
    profile = SCENE_PROFILES[key]
    texture_key = TEXTURE_KEYS[key]
    left, top, right, bottom = profile.bounds
    text = f'''[gd_scene load_steps=3 format=3]

[ext_resource type="Script" path="{STATIC_SCRIPT}" id="1_script"]
[ext_resource type="Texture2D" path="res://images/monsters/{texture_key}.png" id="2_texture"]

[node name="{profile.root_name}" type="Node2D"]
script = ExtResource("1_script")
metadata/_edit_group_ = true
metadata/_edit_lock_ = true

[node name="Visuals" type="Sprite2D" parent="."]
texture = ExtResource("2_texture")
unique_name_in_owner = true
position = {format_vector(profile.position)}
scale = Vector2({format_number(profile.scale)}, {format_number(profile.scale)})
metadata/_edit_lock_ = true

[node name="Bounds" type="Control" parent="."]
unique_name_in_owner = true
layout_mode = 3
anchors_preset = 0
offset_left = {format_number(left)}
offset_top = {format_number(top)}
offset_right = {format_number(right)}
offset_bottom = {format_number(bottom)}
mouse_filter = 2

[node name="CenterPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = {format_vector(profile.center)}

[node name="IntentPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = {format_vector(profile.intent)}
'''
    SCENE_ROOT.mkdir(parents=True, exist_ok=True)
    (SCENE_ROOT / profile.scene_name).write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    for key in TEXTURE_KEYS:
        write_scene(key)
    print(f"restored {len(TEXTURE_KEYS)} static monster scenes")


if __name__ == "__main__":
    main()
