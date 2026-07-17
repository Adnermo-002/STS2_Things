#!/usr/bin/env python3
"""Fast, deterministic source checks for STS2_Things."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "STS2_Things"


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []

    def source_text(relative: str) -> str:
        return (SOURCE / relative).read_text(encoding="utf-8")

    def require_snippets(relative: str, snippets: list[str], contract: str) -> None:
        text = source_text(relative)
        for snippet in snippets:
            if snippet not in text:
                fail(errors, f"{relative} violates {contract}: missing {snippet!r}")

    root_manifest = json.loads((ROOT / "STS2_Things.json").read_text(encoding="utf-8"))
    target_manifest_paths = {
        "v107.1": ROOT / "manifests" / "v107.1" / "STS2_Things.json",
        "v108": ROOT / "manifests" / "v108" / "STS2_Things.json",
    }
    target_manifests: dict[str, dict] = {}
    for target, path in target_manifest_paths.items():
        if not path.is_file():
            fail(errors, f"target manifest missing: {path.relative_to(ROOT)}")
            continue
        target_manifests[target] = json.loads(path.read_text(encoding="utf-8"))
    project_root = ET.parse(ROOT / "STS2_Things.csproj").getroot()
    godot_project_text = (ROOT / "project.godot").read_text(encoding="utf-8")

    def project_value(name: str) -> str | None:
        node = project_root.find(f".//{name}")
        return node.text.strip() if node is not None and node.text else None

    expected_min_versions = {"v107.1": "v0.107.1", "v108": "v0.108.0"}
    for target, manifest in target_manifests.items():
        if manifest.get("version") != project_value("Version"):
            fail(errors, f"{target} manifest and assembly versions differ")
        if manifest.get("min_game_version") != expected_min_versions[target]:
            fail(errors, f"{target} manifest has the wrong min_game_version")
        if manifest.get("affects_gameplay") is not True:
            fail(errors, f"{target} manifest must set affects_gameplay=true")
        if manifest.get("dependencies"):
            fail(errors, f"{target} native build must not declare third-party dependencies")
    if target_manifests.get("v108") != root_manifest:
        fail(errors, "root development manifest must match manifests/v108")
    if project_value("Nullable") != "enable":
        fail(errors, "Nullable must be enable")
    if project_value("TreatWarningsAsErrors") != "true":
        fail(errors, "TreatWarningsAsErrors must be true")
    project_text = (ROOT / "STS2_Things.csproj").read_text(encoding="utf-8")
    for required in (
        "Sts2TargetVersion",
        "STS2_V107_1",
        "STS2_V108",
        "Unsupported Sts2TargetVersion",
        '<Compile Remove="tools\\**\\*.cs" />',
    ):
        if required not in project_text:
            fail(errors, f"dual-version project contract missing {required!r}")
    if "export/convert_text_resources_to_binary=false" not in godot_project_text:
        fail(
            errors,
            "project.godot must keep text resources unconverted so BackgroundAssets "
            "enumerates .tscn rather than unloadable .tscn.remap entries",
        )

    export_preset = (ROOT / "export_presets.cfg").read_text(encoding="utf-8")
    if "binary_format/convert_text_resources_to_binary=false" not in export_preset:
        fail(
            errors,
            "PCK export must preserve text-resource filenames; BackgroundAssets enumerates "
            "layer directories and cannot load exported .tscn.remap entries",
        )
    if "source_assets/**" not in export_preset:
        fail(errors, "editable monster source art must be excluded from the shipping PCK")
    if not (ROOT / "source_assets" / ".gdignore").is_file():
        fail(errors, "source_assets/.gdignore must prevent Godot from importing build-time art")

    forbidden_patterns = {
        r"\bRandom\.Shared\b": "Random.Shared",
        r"\bSystem\.Random\b": "System.Random",
        r"\bGD\.Rand\w*\b": "Godot global RNG",
        r"\basync\s+void\b": "async void",
        r"\bRitsuLib\b": "RitsuLib dependency",
        r"\bBaseLib\b": "BaseLib dependency",
        r"\bMonsterRegistrar\b": "legacy global MonsterRegistrar",
        r"creature_visuals/fallback": "fallback creature visuals",
    }
    for path in sorted(SOURCE.rglob("*.cs")):
        text = path.read_text(encoding="utf-8")
        for pattern, label in forbidden_patterns.items():
            if re.search(pattern, text):
                fail(errors, f"{path.relative_to(ROOT)} contains forbidden {label}")

    compatibility_text = source_text("Compatibility/Sts2VersionCompatibility.cs")
    for snippet in (
        "#if STS2_V107_1",
        "SavedPropertiesTypeCache.InjectTypeIntoCache(typeof(CurseRemover));",
        "creature.GetCreatureNode()",
        "creature.SetNodeVisible(visible);",
    ):
        if snippet not in compatibility_text:
            fail(errors, f"dual-version compatibility bridge missing {snippet!r}")
    injection_count = sum(
        path.read_text(encoding="utf-8").count(
            "SavedPropertiesTypeCache.InjectTypeIntoCache"
        )
        for path in SOURCE.rglob("*.cs")
    )
    if injection_count != 1:
        fail(errors, "V107.1 SavedProperty injection must exist only in the guarded bridge")

    build_text = (ROOT / "scripts" / "build.ps1").read_text(encoding="utf-8")
    for required in (
        "build_static_monster_scenes.py",
        "Sts2TargetVersion=$TargetVersion",
        "manifests\\$TargetVersion\\STS2_Things.json",
        "verify-harmony-targets.ps1",
        "ReusePck",
    ):
        if required not in build_text:
            fail(errors, f"target-aware build script missing {required!r}")
    for stale in (
        "Building image-generated semantic monster cutout rigs",
        "Building native Spine 4.2 monster assets",
        "SPINE_RUNTIME_PASS",
    ):
        if stale in build_text:
            fail(errors, f"static build script still executes old rig step {stale!r}")

    localization = SOURCE / "localization"

    # Shipping creature scenes use the reviewed full-texture PNGs. The local
    # Spine/cutout pipeline remains available as source material, but none of it
    # is referenced by the runtime scenes or exported into the PCK.
    rig_specs = {
        "origin_fogmog": ("origin_fogmog.tscn", 15, 16, "OriginFogmog", 1.90),
        "bowlbug_progenitor": (
            "bowlbug_progenitor.tscn", 45, 34, "BowlbugProgenitor", 0.92
        ),
        "scale_beetle": ("scale_beetle.tscn", 48, 29, "ScaleBeetle", 1.37),
        "soul_roe_1": ("soul_roe.tscn", 4, 3, "SoulRoe", 0.58),
        "soul_roe_2": ("soul_roe_2.tscn", 4, 3, "SoulRoe", 0.58),
        "soul_roe_3": ("soul_roe_3.tscn", 4, 3, "SoulRoe", 0.58),
        "soul_roes": ("soul_roes.tscn", 12, 16, "SoulRoes", 0.78),
        "the_legacy": ("the_legacy.tscn", 36, 28, "TheLegacy", 0.92),
        # Coherence-first recovery: the rejected v4 semantic sheet is kept out
        # of the shipping rig until a replacement master passes visual review.
        "thief_raider": ("thief_raider.tscn", 1, 1, "ThiefRaider", 0.72),
    }
    expected_total_parts = sum(spec[1] for spec in rig_specs.values())
    expected_total_bones = sum(spec[2] for spec in rig_specs.values())
    required_spine_animations = (
        "idle_loop",
        "attack",
        "cast",
        "hurt",
        "die",
        "summon",
        "power_up",
        "revive",
    )

    for rig_key, (name, _part_count, _bone_count, _model, _death_time) in sorted(
        rig_specs.items()
    ):
        path = ROOT / "scenes" / "creature_visuals" / name
        if not path.is_file():
            fail(errors, f"native creature scene missing: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        script_path = "res://STS2_Things/Visuals/NThingsStaticCreatureVisuals.cs"
        texture_path = f"res://images/monsters/{rig_key}.png"
        if script_path not in text:
            fail(errors, f"{path.relative_to(ROOT)} does not use NThingsStaticCreatureVisuals")
        if texture_path not in text:
            fail(errors, f"{path.relative_to(ROOT)} does not reference {texture_path}")
        sprite_nodes = re.findall(
            r'^\[node name="([^"]+)" type="Sprite2D"[^\]]*\]', text, re.MULTILINE
        )
        if sprite_nodes != ["Visuals"]:
            fail(
                errors,
                f"{path.relative_to(ROOT)} must contain exactly one Sprite2D named "
                f"%Visuals; got {sprite_nodes!r}",
            )
        visuals_block = re.search(
            r'^\[node name="Visuals" type="Sprite2D"[^\]]*\]\s*\n'
            r'(.*?)(?=^\[node |\Z)',
            text,
            re.MULTILINE | re.DOTALL,
        )
        if visuals_block is None or "texture = ExtResource" not in visuals_block.group(1):
            fail(errors, f"{path.relative_to(ROOT)} %Visuals lacks its full texture resource")
        for forbidden_node_type in ("SpineSprite", "Polygon2D", "Skeleton2D", "Bone2D"):
            if re.search(rf'type="{forbidden_node_type}"', text):
                fail(
                    errors,
                    f"{path.relative_to(ROOT)} reintroduces {forbidden_node_type} animation",
                )
        if re.search(r"^z_(?:index|as_relative)\s*=", text, re.MULTILINE):
            fail(errors, f"{path.relative_to(ROOT)} overrides the creature canvas z-order")
        bounds_block = re.search(
            r'\[node name="Bounds"[^\]]*\](.*?)(?=\n\[node |\Z)', text, re.DOTALL
        )
        if bounds_block is None or "offset_bottom" not in bounds_block.group(1):
            fail(errors, f"{path.relative_to(ROOT)} does not include texture bounds padding")
        for node_name in ("Visuals", "Bounds", "CenterPos", "IntentPos"):
            node_block = re.search(
                rf'^\[node name="{node_name}"[^\]]*\]\s*\n'
                r'(.*?)(?=^\[node |\Z)',
                text,
                re.MULTILINE | re.DOTALL,
            )
            if node_block is None or not re.search(
                r"^unique_name_in_owner\s*=\s*true\s*$",
                node_block.group(1),
                re.MULTILINE,
            ):
                fail(errors, f"{path.relative_to(ROOT)} lacks unique %{node_name}")
        if rig_key == "thief_raider":
            for profile_value in (
                "position = Vector2(0, -95)",
                "scale = Vector2(0.47, 0.47)",
                "offset_left = -130",
                "offset_top = -180",
                "offset_right = 130",
                "offset_bottom = 12",
                "position = Vector2(0, -85)",
                "position = Vector2(0, -204)",
            ):
                if profile_value not in text:
                    fail(
                        errors,
                        f"{path.relative_to(ROOT)} lost Thief Raider profile "
                        f"{profile_value!r}",
                    )

    # Every self-owned shipping monster texture is an exact RGBA mirror of its
    # editable source.  No edge, grain, brightness, outline or palette pass may
    # alter even transparent-canvas pixels.
    source_monsters = ROOT / "source_assets" / "monsters"
    shipping_monsters = ROOT / "images" / "monsters"
    source_names = {path.name for path in source_monsters.glob("*.png")}
    shipping_names = {path.name for path in shipping_monsters.glob("*.png")}
    expected_textures = {
        "bowlbug_progenitor.png",
        "origin_fogmog.png",
        "scale_beetle.png",
        "soul_roe_1.png",
        "soul_roe_2.png",
        "soul_roe_3.png",
        "soul_roes.png",
        "the_legacy.png",
        "thief_raider.png",
    }
    if source_names != expected_textures:
        fail(errors, f"monster source-art set differs: {sorted(source_names ^ expected_textures)}")
    if shipping_names != expected_textures:
        fail(errors, f"shipping monster-texture set differs: {sorted(shipping_names ^ expected_textures)}")
    for name in sorted(source_names & shipping_names):
        source_path = source_monsters / name
        shipping_path = shipping_monsters / name
        with Image.open(source_path) as source_image, Image.open(shipping_path) as shipping_image:
            source_image.load()
            shipping_image.load()
            if source_image.size != shipping_image.size:
                fail(errors, f"{shipping_path.relative_to(ROOT)} changed the scene canvas size")
                continue
            if source_image.mode != "RGBA":
                fail(errors, f"{source_path.relative_to(ROOT)} must be encoded as RGBA")
                continue
            if shipping_image.mode != "RGBA":
                fail(errors, f"{shipping_path.relative_to(ROOT)} must be encoded as RGBA")
                continue
            if source_image.getchannel("A").getbbox() is None:
                fail(errors, f"{source_path.relative_to(ROOT)} has no non-transparent pixels")
                continue
            if shipping_image.getchannel("A").getbbox() is None:
                fail(errors, f"{shipping_path.relative_to(ROOT)} must be a non-empty RGBA texture")
                continue
            source_pixels = source_image.tobytes()
            shipping_pixels = shipping_image.tobytes()
            if shipping_pixels != source_pixels:
                first_pixel = next(
                    pixel_index
                    for pixel_index, offset in enumerate(range(0, len(source_pixels), 4))
                    if source_pixels[offset : offset + 4] != shipping_pixels[offset : offset + 4]
                )
                x = first_pixel % source_image.width
                y = first_pixel // source_image.width
                offset = first_pixel * 4
                fail(
                    errors,
                    f"{shipping_path.relative_to(ROOT)} changes source RGBA pixel "
                    f"({x}, {y}) from {tuple(source_pixels[offset : offset + 4])} "
                    f"to {tuple(shipping_pixels[offset : offset + 4])}",
                )

    # Spine source pipeline: semantic cutout inputs are build-time data only.
    # The shipping creature scene consumes the generated atlas/skeleton pair.
    spine_required_visual_files = (
        ROOT / "scripts" / "build_ai_cutout_rigs.py",
        ROOT / "scripts" / "build_spine_monsters.py",
        ROOT / "scripts" / "build_static_monster_scenes.py",
        ROOT / "source_assets" / "monsters" / "ai_cutout_rigs.generated.json",
        ROOT / "source_assets" / "monsters" / "ai_cutout_rigs.qa.generated.json",
        ROOT / "source_assets" / "monsters" / "spine_monsters.generated.json",
        ROOT / "STS2_Things" / "Visuals" / "NThingsStaticCreatureVisuals.cs",
        ROOT / "STS2_Things" / "Visuals" / "NThingsSpineCreatureVisuals.cs",
        ROOT / "STS2_Things" / "Monsters" / "ThingsSpineMonster.cs",
    )
    for path in spine_required_visual_files:
        if not path.is_file():
            fail(errors, f"monster Spine pipeline file missing: {path.relative_to(ROOT)}")

    expected_rig_keys = set(rig_specs)
    ai_cutout_manifest_path = (
        ROOT / "source_assets" / "monsters" / "ai_cutout_rigs.generated.json"
    )
    ai_cutout_manifest: dict[str, dict] = {}
    if ai_cutout_manifest_path.is_file():
        parsed_ai_cutout_manifest = json.loads(
            ai_cutout_manifest_path.read_text(encoding="utf-8")
        )
        if not isinstance(parsed_ai_cutout_manifest, dict):
            fail(errors, "AI cutout rig manifest root must be an object")
        else:
            ai_cutout_manifest = parsed_ai_cutout_manifest
            if set(ai_cutout_manifest) != expected_rig_keys:
                fail(
                    errors,
                    "AI cutout rig key set differs: "
                    f"{sorted(set(ai_cutout_manifest) ^ expected_rig_keys)}",
                )

    required_parent_edges = {
        "origin_fogmog": {
            "Body": "Root",
            "Face": "Body",
            "CapUnder": "Body",
            "CapTop": "CapUnder",
            "CapNeck": "Body",
            "LeftArm": "Body",
            "LeftForearm": "LeftArm",
            "LeftHand": "LeftForearm",
            "RightArm": "Body",
            "RightForearm": "RightArm",
            "RightHand": "RightForearm",
            "LeftLeg": "Body",
            "LeftFoot": "LeftLeg",
            "RightLeg": "Body",
            "RightFoot": "RightLeg",
        },
        "bowlbug_progenitor": {
            "Head": "FrontShell",
            "Mandible": "Head",
            "MandibleLower": "Head",
            "Crest": "Head",
            "FrontLeg": "FrontShell",
            "FrontLegLower": "FrontLeg",
            "FrontFoot": "FrontLegLower",
            "MidLegA": "MidShell",
            "MidLegALower": "MidLegA",
            "MidFootA": "MidLegALower",
            "MidLegB": "EggSac",
            "MidLegBLower": "MidLegB",
            "MidFootB": "MidLegBLower",
            "RearLegA": "RearShell",
            "RearLegALower": "RearLegA",
            "RearFootA": "RearLegALower",
            "RearLegB": "RearShell",
            "RearLegBLower": "RearLegB",
            "RearFootB": "RearLegBLower",
        },
        "scale_beetle": {
            "Head": "FrontShell",
            "JawUpper": "Head",
            "JawLower": "Head",
            "ForeClaw": "FrontShell",
            "ForeClawLower": "ForeClaw",
            "FrontLeg": "FrontShell",
            "FrontLegLower": "FrontLeg",
            "MidLeg": "Core",
            "MidLegLower": "MidLeg",
            "RearLeg": "RearShell",
            "RearLegLower": "RearLeg",
            "AntennaFrontBase": "Head",
            "AntennaFront1": "AntennaFrontBase",
            "AntennaFront2": "AntennaFront1",
            "AntennaFront3": "AntennaFront2",
            "AntennaFront4": "AntennaFront3",
            "AntennaFront5": "AntennaFront4",
            "AntennaFrontTip": "AntennaFront5",
            "AntennaBackBase": "Head",
            "AntennaBack1": "AntennaBackBase",
            "AntennaBack2": "AntennaBack1",
            "AntennaBack3": "AntennaBack2",
            "AntennaBack4": "AntennaBack3",
            "AntennaBack5": "AntennaBack4",
            "AntennaBackTip": "AntennaBack5",
        },
        "soul_roe_1": {"Core": "Root", "Nucleus": "Core"},
        "soul_roe_2": {"Core": "Root", "Nucleus": "Core"},
        "soul_roe_3": {"Core": "Root", "Nucleus": "Core"},
        "soul_roes": {
            "ClusterTop": "Root",
            "ClusterMiddle": "Root",
            "ClusterBottom": "Root",
            "RoeTop": "ClusterTop",
            "RoeCore": "ClusterMiddle",
            "RoeBottom": "ClusterBottom",
        },
        "the_legacy": {
            "HeartAnchor": "Root",
            "HeartCore": "HeartAnchor",
            "LeftLobe": "HeartAnchor",
            "RightLobe": "HeartAnchor",
            "TopPurple": "HeartAnchor",
            "RightTubes": "HeartAnchor",
            "RightTubesFar": "RightTubes",
            "RightTubesLower": "RightTubes",
        },
        "thief_raider": {},
    }

    total_ai_parts = 0
    total_ai_bones = 0
    manifest_ai_textures: set[Path] = set()
    bone_maps: dict[str, dict[str, str]] = {}
    expected_slot_orders: dict[str, list[str]] = {}
    for rig_key in sorted(expected_rig_keys):
        rig = ai_cutout_manifest.get(rig_key)
        if not isinstance(rig, dict):
            fail(errors, f"AI cutout rig {rig_key} is missing or invalid")
            continue
        if rig.get("pipeline") != "ai_generated_complete_cutout_v1":
            fail(errors, f"AI cutout rig {rig_key} has the wrong pipeline provenance")
        bones = rig.get("bones")
        parts = rig.get("parts")
        if not isinstance(bones, list) or not isinstance(parts, list):
            fail(errors, f"AI cutout rig {rig_key} lacks bone/part arrays")
            continue

        _scene, expected_parts, expected_bones, _model, _death_time = rig_specs[rig_key]
        if len(parts) != expected_parts:
            fail(
                errors,
                f"cutout rig {rig_key} has {len(parts)} parts; expected {expected_parts}",
            )
        if len(bones) != expected_bones:
            fail(
                errors,
                f"cutout rig {rig_key} has {len(bones)} bones; expected {expected_bones}",
            )
        total_ai_parts += len(parts)
        total_ai_bones += len(bones)

        bone_by_name: dict[str, dict] = {}
        for bone in bones:
            if not isinstance(bone, dict):
                fail(errors, f"cutout rig {rig_key} contains a non-object bone")
                continue
            bone_name = bone.get("name")
            if (
                not isinstance(bone_name, str)
                or not bone_name
                or bone_name in bone_by_name
            ):
                fail(
                    errors,
                    f"cutout rig {rig_key} has an invalid/duplicate bone: {bone_name!r}",
                )
                continue
            parent_name = bone.get("parent")
            if not isinstance(parent_name, str):
                fail(
                    errors,
                    f"cutout rig {rig_key}/{bone_name} has invalid parent {parent_name!r}",
                )
            pivot = bone.get("pivot")
            if (
                not isinstance(pivot, list)
                or len(pivot) != 2
                or not all(isinstance(value, (int, float)) for value in pivot)
            ):
                fail(errors, f"cutout rig {rig_key}/{bone_name} has invalid bind pivot")
            bone_by_name[bone_name] = bone

        roots = [
            name for name, bone in bone_by_name.items() if bone.get("parent") == ""
        ]
        if roots != ["Root"]:
            fail(
                errors,
                f"cutout rig {rig_key} must have exactly one logical Root; got {roots!r}",
            )
        for bone_name, bone in bone_by_name.items():
            parent_name = bone.get("parent", "")
            if parent_name and parent_name not in bone_by_name:
                fail(
                    errors,
                    f"cutout rig {rig_key}/{bone_name} has missing parent {parent_name!r}",
                )
            if parent_name == bone_name:
                fail(errors, f"cutout rig {rig_key}/{bone_name} parents itself")
            visited: set[str] = set()
            cursor = bone_name
            while cursor:
                if cursor in visited:
                    fail(
                        errors,
                        f"cutout rig {rig_key} hierarchy cycle reaches {cursor!r}",
                    )
                    break
                visited.add(cursor)
                cursor = str(bone_by_name.get(cursor, {}).get("parent", ""))

        actual_parents = {
            name: str(bone.get("parent", "")) for name, bone in bone_by_name.items()
        }
        bone_maps[rig_key] = actual_parents
        for child, expected_parent in required_parent_edges.get(rig_key, {}).items():
            if actual_parents.get(child) != expected_parent:
                fail(
                    errors,
                    f"cutout rig {rig_key}/{child} parent is "
                    f"{actual_parents.get(child)!r}; expected {expected_parent!r}",
                )

        seen_parts: set[str] = set()
        indexed_parts: list[tuple[int, dict]] = []
        for source_index, part in enumerate(parts):
            if not isinstance(part, dict):
                fail(errors, f"cutout rig {rig_key} contains a non-object part")
                continue
            part_name = part.get("name")
            if (
                not isinstance(part_name, str)
                or not part_name
                or part_name in seen_parts
            ):
                fail(
                    errors,
                    f"cutout rig {rig_key} has an invalid/duplicate part: {part_name!r}",
                )
                continue
            seen_parts.add(part_name)
            indexed_parts.append((source_index, part))
            if not part_name.startswith("ai_"):
                fail(errors, f"AI cutout rig {rig_key}/{part_name} lacks the ai_ prefix")
            if part.get("ai_generated_complete_component") is not True:
                fail(
                    errors,
                    f"AI cutout rig {rig_key}/{part_name} is not a complete generated component",
                )
            source_component = part.get("source_component_path")
            if not isinstance(source_component, str) or not source_component.startswith(
                "res://source_assets/monsters/ai_cutout_parts/"
            ):
                fail(
                    errors,
                    f"AI cutout rig {rig_key}/{part_name} has invalid source provenance "
                    f"{source_component!r}",
                )
            bone_name = part.get("bone")
            if bone_name not in bone_by_name:
                fail(
                    errors,
                    f"cutout rig {rig_key}/{part_name} references unknown bone "
                    f"{bone_name!r}",
                )
            elif part.get("pivot") != bone_by_name[bone_name].get("pivot"):
                fail(
                    errors,
                    f"cutout rig {rig_key}/{part_name} pivot differs from bone "
                    f"{bone_name!r}",
                )
            if not isinstance(part.get("z"), int):
                fail(errors, f"cutout rig {rig_key}/{part_name} has invalid z order")
            for vector_name in ("pivot", "sprite_offset"):
                vector = part.get(vector_name)
                if (
                    not isinstance(vector, list)
                    or len(vector) != 2
                    or not all(isinstance(value, (int, float)) for value in vector)
                ):
                    fail(
                        errors,
                        f"cutout rig {rig_key}/{part_name} has invalid {vector_name}",
                    )

            texture = part.get("texture")
            if not isinstance(texture, str) or not texture.startswith(
                f"res://images/monsters/ai_rig_parts/{rig_key}/"
            ):
                fail(
                    errors,
                    f"cutout rig {rig_key}/{part_name} has invalid intermediate "
                    f"texture path {texture!r}",
                )
                continue
            texture_path = (ROOT / texture.removeprefix("res://")).resolve()
            manifest_ai_textures.add(texture_path)
            if not texture_path.is_file():
                fail(
                    errors,
                    f"cutout texture missing: {texture_path.relative_to(ROOT)}",
                )
                continue
            with Image.open(texture_path) as cutout_image:
                cutout_image.load()
                if (
                    cutout_image.mode != "RGBA"
                    or cutout_image.getchannel("A").getbbox() is None
                ):
                    fail(
                        errors,
                        "cutout texture is not a non-empty RGBA image: "
                        f"{texture_path.relative_to(ROOT)}",
                    )

        expected_slot_orders[rig_key] = [
            str(part["name"])
            for _source_index, part in sorted(
                indexed_parts,
                key=lambda item: (int(item[1].get("z", 0)), item[0]),
            )
        ]

    if total_ai_parts != expected_total_parts:
        fail(
            errors,
            f"AI cutout rig total is {total_ai_parts} parts; "
            f"expected {expected_total_parts} from per-rig contracts",
        )
    if total_ai_bones != expected_total_bones:
        fail(
            errors,
            f"AI cutout rig total is {total_ai_bones} bones; "
            f"expected {expected_total_bones} from per-rig contracts",
        )

    rig_parts_root = shipping_monsters / "ai_rig_parts"
    actual_ai_textures = {
        path.resolve() for path in rig_parts_root.rglob("*.png")
    }
    # The AI directory is build-time-only and excluded from the PCK.  Previous
    # approved iterations may remain for visual comparison, so only referenced
    # textures are authoritative and required to exist.
    for path in sorted(manifest_ai_textures - actual_ai_textures):
        fail(errors, f"manifest AI cutout texture missing: {path.relative_to(ROOT)}")

    ai_qa_path = (
        ROOT / "source_assets" / "monsters" / "ai_cutout_rigs.qa.generated.json"
    )
    if ai_qa_path.is_file():
        ai_qa = json.loads(ai_qa_path.read_text(encoding="utf-8"))
        if not isinstance(ai_qa, dict):
            fail(errors, "AI cutout QA report root must be an object")
        else:
            if ai_qa.get("pipeline") != "ai_generated_complete_cutout_v1":
                fail(errors, "AI cutout QA report has the wrong pipeline")
            if ai_qa.get("manifest") != (
                "source_assets/monsters/ai_cutout_rigs.generated.json"
            ):
                fail(errors, "AI cutout QA report references the wrong manifest")
            if ai_qa.get("output_root") != "images/monsters/ai_rig_parts":
                fail(errors, "AI cutout QA report references the wrong output root")

            qa_monsters = ai_qa.get("monsters")
            if not isinstance(qa_monsters, dict) or set(qa_monsters) != expected_rig_keys:
                actual_keys = set(qa_monsters) if isinstance(qa_monsters, dict) else set()
                fail(
                    errors,
                    "AI cutout QA key set differs: "
                    f"{sorted(actual_keys ^ expected_rig_keys)}",
                )
            else:
                for rig_key in sorted(expected_rig_keys):
                    entry = qa_monsters.get(rig_key, {})
                    _scene, part_count, bone_count, _model, _death_time = rig_specs[
                        rig_key
                    ]
                    if entry.get("written_parts") != part_count:
                        fail(errors, f"AI cutout QA {rig_key} part count differs")
                    if entry.get("mapped_parts") != part_count:
                        fail(errors, f"AI cutout QA {rig_key} did not write every mapped part")
                    if entry.get("bones") != bone_count:
                        fail(errors, f"AI cutout QA {rig_key} bone count differs")
                    if entry.get("errors") != []:
                        fail(errors, f"AI cutout QA {rig_key} contains build errors")
                    if entry.get("canvas") != ai_cutout_manifest.get(rig_key, {}).get("canvas"):
                        fail(errors, f"AI cutout QA {rig_key} canvas differs")
                    qa_parts = entry.get("parts")
                    if not isinstance(qa_parts, list) or len(qa_parts) != part_count:
                        fail(errors, f"AI cutout QA {rig_key} part evidence differs")

            summary = ai_qa.get("summary")
            if not isinstance(summary, dict):
                fail(errors, "AI cutout QA report lacks a summary")
            else:
                if summary.get("monsters") != len(expected_rig_keys):
                    fail(errors, "AI cutout QA monster total differs")
                if summary.get("parts") != expected_total_parts:
                    fail(errors, "AI cutout QA part total differs")
                if summary.get("bones") != expected_total_bones:
                    fail(errors, "AI cutout QA bone total differs")
                if summary.get("errors") != 0:
                    fail(errors, "AI cutout QA reports build errors")

            newest_input = max(
                (
                    path.stat().st_mtime_ns
                    for path in (ai_cutout_manifest_path, *manifest_ai_textures)
                    if path.is_file()
                ),
                default=0,
            )
            if ai_qa_path.stat().st_mtime_ns < newest_input:
                fail(errors, "AI cutout QA report is older than its generated inputs")

    def collect_frame_times(value: object) -> list[float]:
        times: list[float] = []
        if isinstance(value, dict):
            frame_time = value.get("time")
            if isinstance(frame_time, (int, float)):
                times.append(float(frame_time))
            for child in value.values():
                times.extend(collect_frame_times(child))
        elif isinstance(value, list):
            for child in value:
                times.extend(collect_frame_times(child))
        return times

    def animation_duration(animation: object) -> float:
        return max(collect_frame_times(animation), default=0.0)

    spine_report_path = (
        ROOT / "source_assets" / "monsters" / "spine_monsters.generated.json"
    )
    spine_report_entries: dict[str, dict] = {}
    if spine_report_path.is_file():
        spine_report = json.loads(spine_report_path.read_text(encoding="utf-8"))
        if not isinstance(spine_report, dict):
            fail(errors, "Spine generation report root must be an object")
        else:
            report_version = str(spine_report.get("spine_version", ""))
            if re.fullmatch(r"4\.2(?:\.\d+)?", report_version) is None:
                fail(
                    errors,
                    f"Spine generation report targets {report_version!r}, not 4.2",
                )
            if spine_report.get("source_manifest") != (
                "source_assets/monsters/ai_cutout_rigs.generated.json"
            ):
                fail(errors, "Spine generation report was not built from the AI cutout rig")
            report_rigs = spine_report.get("rigs")
            if not isinstance(report_rigs, list):
                fail(errors, "Spine generation report lacks a rigs array")
            else:
                for entry in report_rigs:
                    if not isinstance(entry, dict):
                        fail(errors, "Spine report contains a non-object rig")
                        continue
                    key = entry.get("key")
                    if not isinstance(key, str) or key in spine_report_entries:
                        fail(errors, f"Spine report has invalid/duplicate key {key!r}")
                        continue
                    spine_report_entries[key] = entry
                if set(spine_report_entries) != expected_rig_keys:
                    fail(
                        errors,
                        "Spine generation report key set differs: "
                        f"{sorted(set(spine_report_entries) ^ expected_rig_keys)}",
                    )

    total_spine_slots = 0
    total_spine_bones = 0
    for rig_key in sorted(expected_rig_keys):
        _scene, expected_parts, expected_bones, _model, expected_death = rig_specs[
            rig_key
        ]
        directory = ROOT / "animations" / "monsters" / "sts2_things" / rig_key
        spjson_path = directory / f"{rig_key}.spjson"
        atlas_path = directory / f"{rig_key}.atlas"
        spatlas_path = directory / f"{rig_key}.spatlas"
        atlas_png_path = directory / f"{rig_key}.png"
        tres_path = directory / f"{rig_key}_skel_data.tres"
        asset_paths = (
            spjson_path,
            atlas_path,
            spatlas_path,
            atlas_png_path,
            tres_path,
        )
        for path in asset_paths:
            if not path.is_file():
                fail(errors, f"Spine asset missing: {path.relative_to(ROOT)}")
        if not all(path.is_file() for path in asset_paths):
            continue

        report_entry = spine_report_entries.get(rig_key, {})
        for field, expected_path in {
            "spjson": spjson_path.relative_to(ROOT).as_posix(),
            "spatlas": spatlas_path.relative_to(ROOT).as_posix(),
            "tres": tres_path.relative_to(ROOT).as_posix(),
        }.items():
            if report_entry.get(field) != expected_path:
                fail(
                    errors,
                    f"Spine report {rig_key}/{field} does not reference {expected_path}",
                )
        if report_entry.get("bones") != expected_bones:
            fail(errors, f"Spine report {rig_key} bone count differs")
        if report_entry.get("slots") != expected_parts:
            fail(errors, f"Spine report {rig_key} slot count differs")
        if tuple(report_entry.get("animations", ())) != required_spine_animations:
            fail(errors, f"Spine report {rig_key} animation list differs")

        spine_json = json.loads(spjson_path.read_text(encoding="utf-8"))
        if not isinstance(spine_json, dict):
            fail(errors, f"{spjson_path.relative_to(ROOT)} root is not an object")
            continue
        spine_version = str(spine_json.get("skeleton", {}).get("spine", ""))
        if re.fullmatch(r"4\.2(?:\.\d+)?", spine_version) is None:
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} targets Spine {spine_version!r}",
            )

        json_bones = spine_json.get("bones")
        json_slots = spine_json.get("slots")
        if not isinstance(json_bones, list) or not isinstance(json_slots, list):
            fail(errors, f"{spjson_path.relative_to(ROOT)} lacks bone/slot arrays")
            continue
        total_spine_bones += len(json_bones)
        total_spine_slots += len(json_slots)
        if len(json_bones) != expected_bones:
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} has {len(json_bones)} bones; "
                f"expected {expected_bones}",
            )
        if len(json_slots) != expected_parts:
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} has {len(json_slots)} slots; "
                f"expected {expected_parts}",
            )

        expected_parents = bone_maps.get(rig_key, {})
        actual_parents: dict[str, str] = {}
        seen_bones: set[str] = set()
        for bone in json_bones:
            if not isinstance(bone, dict) or not isinstance(bone.get("name"), str):
                fail(errors, f"{spjson_path.relative_to(ROOT)} has an invalid bone")
                continue
            bone_name = str(bone["name"])
            parent = str(bone.get("parent", ""))
            if bone_name in seen_bones:
                fail(errors, f"{spjson_path.relative_to(ROOT)} repeats {bone_name!r}")
            if parent and parent not in seen_bones:
                fail(
                    errors,
                    f"{spjson_path.relative_to(ROOT)} bone {bone_name!r} appears "
                    f"before parent {parent!r}",
                )
            seen_bones.add(bone_name)
            actual_parents[bone_name] = parent
        if actual_parents != expected_parents:
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} bone hierarchy differs from cutout rig",
            )
        roots = [name for name, parent in actual_parents.items() if not parent]
        root_bone = roots[0] if len(roots) == 1 else ""
        if roots != ["Root"]:
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} must have one Root; got {roots!r}",
            )

        expected_slot_order = expected_slot_orders.get(rig_key, [])
        actual_slot_order = [
            str(slot.get("name", "")) if isinstance(slot, dict) else ""
            for slot in json_slots
        ]
        if actual_slot_order != expected_slot_order:
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} slot draw order is not "
                "back-to-front (z, source order)",
            )
        part_by_name = {
            str(part.get("name")): part
            for part in ai_cutout_manifest.get(rig_key, {}).get("parts", [])
            if isinstance(part, dict)
        }
        for slot in json_slots:
            if not isinstance(slot, dict):
                continue
            slot_name = str(slot.get("name", ""))
            expected_part = part_by_name.get(slot_name, {})
            if slot.get("bone") != expected_part.get("bone"):
                fail(
                    errors,
                    f"{spjson_path.relative_to(ROOT)} slot {slot_name!r} "
                    "uses the wrong bone",
                )
            if slot.get("attachment") != slot_name:
                fail(
                    errors,
                    f"{spjson_path.relative_to(ROOT)} slot {slot_name!r} "
                    "does not use its same-name attachment",
                )

        skins = spine_json.get("skins")
        default_skin = None
        if isinstance(skins, list):
            default_skin = next(
                (
                    skin
                    for skin in skins
                    if isinstance(skin, dict) and skin.get("name") == "default"
                ),
                None,
            )
        attachments = (
            default_skin.get("attachments")
            if isinstance(default_skin, dict)
            else None
        )
        if not isinstance(attachments, dict):
            fail(errors, f"{spjson_path.relative_to(ROOT)} lacks the default skin")
        elif set(attachments) != set(expected_slot_order):
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} default-skin attachments differ "
                "from slots",
            )

        animations = spine_json.get("animations")
        if not isinstance(animations, dict):
            fail(errors, f"{spjson_path.relative_to(ROOT)} lacks animations")
            continue
        if set(animations) != set(required_spine_animations):
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} animation set differs: "
                f"{sorted(set(animations) ^ set(required_spine_animations))}",
            )
        durations: dict[str, float] = {}
        non_root_times: dict[str, list[float]] = {}
        recovery_parts = ai_cutout_manifest.get(rig_key, {}).get("parts", [])
        is_intact_recovery = (
            rig_key == "thief_raider"
            and len(recovery_parts) == 1
            and recovery_parts[0].get("semantic") == "intact_character_recovery"
        )
        for animation_name in required_spine_animations:
            animation = animations.get(animation_name)
            duration = animation_duration(animation)
            durations[animation_name] = duration
            if duration <= 0.0:
                fail(
                    errors,
                    f"{spjson_path.relative_to(ROOT)} animation "
                    f"{animation_name!r} has no positive duration",
                )
            animation_bones = (
                animation.get("bones") if isinstance(animation, dict) else {}
            )
            if not isinstance(animation_bones, dict):
                animation_bones = {}
            action_times = [
                time
                for bone_name, timelines in animation_bones.items()
                if bone_name != root_bone
                for time in collect_frame_times(timelines)
            ]
            non_root_times[animation_name] = action_times
            if not action_times and not is_intact_recovery:
                fail(
                    errors,
                    f"{spjson_path.relative_to(ROOT)} animation "
                    f"{animation_name!r} only contains its duration sentinel",
                )

        if not is_intact_recovery and not any(
            0.45 - 1e-6 <= value <= 0.50 + 1e-6
            for value in non_root_times.get("attack", [])
        ):
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} attack lacks a 0.45-0.50s "
                "contact keyframe",
            )
        if not is_intact_recovery:
            for animation_name, release_time in (
                ("cast", 0.50),
                ("power_up", 0.50),
                ("summon", 0.75),
            ):
                if not any(
                    abs(value - release_time) <= 1e-6
                    for value in non_root_times.get(animation_name, [])
                ):
                    fail(
                        errors,
                        f"{spjson_path.relative_to(ROOT)} {animation_name} lacks its "
                        f"{release_time:.2f}s release keyframe",
                    )
        if abs(durations.get("die", 0.0) - expected_death) > 1e-6:
            fail(
                errors,
                f"{spjson_path.relative_to(ROOT)} die duration is "
                f"{durations.get('die', 0.0):.3f}s; expected {expected_death:.2f}s",
            )
        if rig_key == "origin_fogmog" and abs(
            durations.get("hurt", 0.0) - 0.34
        ) > 1e-6:
            fail(errors, "Origin Fogmog Spine hurt must remain a short 0.34s")

        if rig_key == "thief_raider" and not is_intact_recovery:
            animated_bones = {
                bone_name
                for animation in animations.values()
                if isinstance(animation, dict)
                for bone_name in animation.get("bones", {})
            }
            required_thief_bones = {
                "NearArm", "NearForearm", "NearHand", "Dagger",
                "FarArm", "FarForearm", "FarHand",
                "Cloak", "CloakFarTail", "CloakNearTail",
                "NearShinFoot", "FarShinFoot",
            }
            missing_thief_bones = required_thief_bones - animated_bones
            if missing_thief_bones:
                fail(
                    errors,
                    "Thief Raider animation profile omits AI rig bones: "
                    f"{sorted(missing_thief_bones)}",
                )
            legacy_thief_bones = {
                "DaggerUpperArm", "DaggerForearm", "DaggerHand", "GuardArm",
                "CloakLeftTail", "CloakRightTail", "LeftLeg", "RightLeg",
            }
            if animated_bones & legacy_thief_bones:
                fail(
                    errors,
                    "Thief Raider animation profile still targets legacy bones: "
                    f"{sorted(animated_bones & legacy_thief_bones)}",
                )
            for action in ("attack", "die", "revive"):
                action_data = animations.get(action, {})
                action_bones = set(
                    action_data.get("bones", {})
                    if isinstance(action_data, dict)
                    else {}
                )
                if not {"NearShinFoot", "FarShinFoot"} <= action_bones:
                    fail(errors, f"Thief Raider {action} does not articulate both boots")

        if rig_key == "the_legacy":
            idle_bones = animations.get("idle_loop", {}).get("bones", {})
            scale_bones = sorted(
                bone_name
                for bone_name, timelines in idle_bones.items()
                if isinstance(timelines, dict) and "scale" in timelines
            )
            if scale_bones != ["HeartAnchor"]:
                fail(
                    errors,
                    "The Legacy heartbeat must scale HeartAnchor exactly once; "
                    f"got {scale_bones!r}",
                )
            heartbeat = idle_bones.get("HeartAnchor", {}).get("scale", [])
            expected_heartbeat = {
                0.00: 1.0000,
                0.10: 0.9940,
                0.17: 1.0010,
                0.28: 0.9925,
                0.37: 1.0010,
                0.62: 1.0000,
                1.50: 1.0000,
            }
            actual_heartbeat = {
                round(float(frame.get("time", 0.0)), 4): float(frame.get("x", 0.0))
                for frame in heartbeat
                if isinstance(frame, dict)
            }
            for time_value, scale_value in expected_heartbeat.items():
                if abs(actual_heartbeat.get(time_value, -1.0) - scale_value) > 1e-6:
                    fail(
                        errors,
                        "The Legacy lost its restrained 1.5s lub-dub key at "
                        f"{time_value:.2f}s",
                    )

        atlas_text = atlas_path.read_text(encoding="utf-8")
        region_names = re.findall(
            r"^([^\s:\r\n][^:\r\n]*)\r?\n  rotate:",
            atlas_text,
            re.MULTILINE,
        )
        if set(region_names) != set(expected_slot_order) or len(
            region_names
        ) != expected_parts:
            fail(
                errors,
                f"{atlas_path.relative_to(ROOT)} regions differ from Spine slots",
            )
        if (
            not atlas_text.startswith(f"{rig_key}.png\n")
            or "format: RGBA8888" not in atlas_text
            or "filter: Linear,Linear" not in atlas_text
        ):
            fail(errors, f"{atlas_path.relative_to(ROOT)} has an invalid page header")

        spatlas = json.loads(spatlas_path.read_text(encoding="utf-8"))
        expected_atlas_resource = (
            f"res://animations/monsters/sts2_things/{rig_key}/{rig_key}.atlas"
        )
        if spatlas.get("source_path") != expected_atlas_resource:
            fail(
                errors,
                f"{spatlas_path.relative_to(ROOT)} has the wrong atlas source",
            )
        if spatlas.get("atlas_data") != atlas_text:
            fail(errors, f"{spatlas_path.relative_to(ROOT)} atlas data is stale")

        with Image.open(atlas_png_path) as atlas_image:
            atlas_image.load()
            if (
                atlas_image.mode != "RGBA"
                or atlas_image.getchannel("A").getbbox() is None
            ):
                fail(
                    errors,
                    f"{atlas_png_path.relative_to(ROOT)} is not a non-empty RGBA atlas",
                )
            atlas_size = list(atlas_image.size)
        if report_entry.get("atlas_size") != atlas_size:
            fail(errors, f"Spine report {rig_key} atlas size differs")

        tres_text = tres_path.read_text(encoding="utf-8")
        for resource_path in (
            f"res://animations/monsters/sts2_things/{rig_key}/{rig_key}.spatlas",
            f"res://animations/monsters/sts2_things/{rig_key}/{rig_key}.spjson",
        ):
            if resource_path not in tres_text:
                fail(
                    errors,
                    f"{tres_path.relative_to(ROOT)} does not reference {resource_path}",
                )
        mix_match = re.search(
            r"^default_mix\s*=\s*([0-9.]+)\s*$", tres_text, re.MULTILINE
        )
        if mix_match is None or abs(float(mix_match.group(1)) - 0.05) > 1e-6:
            fail(errors, f"{tres_path.relative_to(ROOT)} default_mix must be 0.05")

    if total_spine_slots != expected_total_parts:
        fail(
            errors,
            f"Spine skeleton total is {total_spine_slots} slots; "
            f"expected {expected_total_parts} from the AI rig set",
        )
    if total_spine_bones != expected_total_bones:
        fail(
            errors,
            f"Spine skeleton total is {total_spine_bones} bones; "
            f"expected {expected_total_bones} from the AI rig set",
        )

    require_snippets(
        "Visuals/NThingsSpineCreatureVisuals.cs",
        [
            "public partial class NThingsSpineCreatureVisuals : NCreatureVisuals",
            "SpineBody.HasAnimation(animation)",
            "SpineBody.TryGetAnimationState()",
            'state.AddAnimation("idle_loop", delay: 0f, loop: true);',
        ],
        "single-CanvasItem native Spine creature-visual contract",
    )
    spine_visuals_text = source_text("Visuals/NThingsSpineCreatureVisuals.cs")
    animation_array = re.search(
        r"_requiredAnimations\s*=\s*\[(.*?)\];",
        spine_visuals_text,
        re.DOTALL,
    )
    declared_animations = (
        tuple(re.findall(r'"([^"]+)"', animation_array.group(1)))
        if animation_array is not None
        else ()
    )
    if declared_animations != required_spine_animations:
        fail(
            errors,
            "NThingsSpineCreatureVisuals animation list differs from generated Spine",
        )
    for legacy_canvas_type in ("Skeleton2D", "Bone2D", "Sprite2D", "Polygon2D"):
        if legacy_canvas_type in spine_visuals_text:
            fail(
                errors,
                "NThingsSpineCreatureVisuals reintroduced "
                f"{legacy_canvas_type} rendering",
            )

    require_snippets(
        "Monsters/ThingsSpineMonster.cs",
        [
            'var idle = new AnimState("idle_loop", isLooping: true);',
            'var attack = ReturnToIdle("attack", idle);',
            'var cast = ReturnToIdle("cast", idle);',
            'var hurt = ReturnToIdle("hurt", idle);',
            'var summon = ReturnToIdle("summon", idle);',
            'var powerUp = ReturnToIdle("power_up", idle);',
            'var revive = ReturnToIdle("revive", idle);',
            'var die = new AnimState("die");',
            "animator.AddAnyState(CreatureAnimator.idleTrigger, idle);",
            "animator.AddAnyState(CreatureAnimator.attackTrigger, attack);",
            "animator.AddAnyState(CreatureAnimator.castTrigger, cast);",
            "animator.AddAnyState(CreatureAnimator.hitTrigger, hurt);",
            "animator.AddAnyState(CreatureAnimator.deathTrigger, die);",
            'animator.AddAnyState("Summon", summon);',
            "animator.AddAnyState(CreatureAnimator.powerUpTrigger, powerUp);",
            "animator.AddAnyState(CreatureAnimator.reviveTrigger, revive);",
        ],
        "eight-trigger native CreatureAnimator-to-Spine mapping contract",
    )

    static_models = (
        "OriginFogmog",
        "BowlbugProgenitor",
        "ScaleBeetle",
        "SoulRoe",
        "SoulRoes",
        "TheLegacy",
        "ThiefRaider",
    )
    for model_name in static_models:
        relative = f"Monsters/{model_name}.cs"
        model_text = source_text(relative)
        if re.search(
            rf"public sealed class\s+{re.escape(model_name)}\s*:\s*MonsterModel\b",
            model_text,
        ) is None:
            fail(errors, f"{relative} does not inherit MonsterModel directly")
        if "ThingsSpineMonster" in model_text:
            fail(errors, f"{relative} still references ThingsSpineMonster")
        if "DeathAnimLengthOverride" in model_text:
            fail(errors, f"{relative} still waits for a removed death animation")

    death_padding_contracts = {
        "Monsters/OriginFogmog.cs": "new(1.45f, 1.75f)",
        "Monsters/BowlbugProgenitor.cs": "new(1.35f, 1.8f)",
        "Monsters/ScaleBeetle.cs": "new(2.3f, 2.1f)",
        "Monsters/SoulRoe.cs": "new(2.2f, 5.0f)",
        "Monsters/SoulRoes.cs": "new(1.6f, 3.0f)",
        "Monsters/TheLegacy.cs": "new(1.4f, 1.7f)",
        "Monsters/ThiefRaider.cs": "new(1.5f, 1.8f)",
    }
    for relative, value in death_padding_contracts.items():
        require_snippets(
            relative,
            ["ExtraDeathVfxPadding", value],
            "static texture death VFX padding contract",
        )

    ai_cutout_builder_text = (
        ROOT / "scripts" / "build_ai_cutout_rigs.py"
    ).read_text(encoding="utf-8")
    for required_builder_snippet in (
        "never crops an assembled monster painting",
        'DEFAULT_OUTPUT_ROOT = ROOT / "images" / "monsters" / "ai_rig_parts"',
        'OUTPUT_PREFIX = "ai_"',
        '"ai_generated_complete_component": True',
        "validate_manifest_subset",
    ):
        if required_builder_snippet not in ai_cutout_builder_text:
            fail(
                errors,
                "AI cutout builder lost complete-component provenance contract: "
                f"{required_builder_snippet!r}",
            )

    exclude_match = re.search(
        r'^exclude_filter="([^"]*)"', export_preset, re.MULTILINE
    )
    export_excludes = (
        {item.strip() for item in exclude_match.group(1).split(",") if item.strip()}
        if exclude_match is not None
        else set()
    )
    for required_exclude in (
        "tools/**",
        "manifests/**",
        "source_assets/**",
        "addons/spine/**",
        "animations/monsters/sts2_things/**",
        "images/monsters/ai_rig_parts/**",
    ):
        if required_exclude not in export_excludes:
            fail(
                errors,
                f"PCK export must exclude build-time asset {required_exclude}",
            )

    # Origin Fogmog's summoned eyes intentionally retain the shipped native
    # Spine scene and animator rather than joining the nine custom atlases.
    require_snippets(
        "Monsters/OriginEyeWithTeeth.cs",
        [
            'SceneHelper.GetScenePath("creature_visuals/eye_with_teeth")',
            "visuals.Modulate = Colors.White;",
            'new AnimState("idle_loop", true)',
            'creatureAnimator.AddAnyState("Attack"',
            'creatureAnimator.AddAnyState("Dead"',
        ],
        "native Spine Eye material/animation contract",
    )

    # EncounterModel scene/slot contract. Exact equality catches both missing runtime markers and
    # stale markers that are not represented by EncounterModel.Slots.
    encounter_slots = {
        "origin_fogmog_boss_encounter.tscn": {"fogmog", "illusion1", "illusion2"},
        "soul_roes_encounter.tscn": {"soul_roes", *(f"soul_roe_{i}" for i in range(1, 9))},
        "the_legacy_boss_encounter.tscn": {"the_legacy"},
        "scale_beetle_boss_encounter.tscn": {"scale_beetle"},
        "raid_party.tscn": {"thief_raider", *(f"raider_{i}" for i in range(1, 6))},
        "bowlbug_progenitor_boss_encounter.tscn": {
            "bowlbug_progenitor",
            *(f"bowlbug_{i}" for i in range(1, 17)),
        },
    }
    for name, expected in encounter_slots.items():
        path = ROOT / "scenes" / "encounters" / name
        if not path.is_file():
            fail(errors, f"encounter scene missing: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        root_block = text.split("[node name=", 2)[1]
        if (
            "anchors_preset = 15" not in root_block
            or "anchor_right = 1.0" not in root_block
            or "anchor_bottom = 1.0" not in root_block
            or re.search(r"^offset_(?:left|top|right|bottom)\s*=", root_block, re.MULTILINE)
        ):
            fail(errors, f"{path.relative_to(ROOT)} root Control is not full-rect")
        actual = set(re.findall(r'\[node name="([^"]+)" type="Marker2D"', text))
        if actual != expected:
            fail(
                errors,
                f"{path.relative_to(ROOT)} marker mismatch: "
                f"missing={sorted(expected - actual)} extra={sorted(actual - expected)}",
            )

    # Native custom background contract used by EncounterModel.CreateBackground/BackgroundAssets.
    boss_backgrounds = {
        "origin_fogmog_boss_encounter",
        "scale_beetle_boss_encounter",
        "the_legacy_boss_encounter",
        "bowlbug_progenitor_boss_encounter",
    }
    for slug in sorted(boss_backgrounds):
        directory = ROOT / "scenes" / "backgrounds" / slug
        main_scene = directory / f"{slug}_background.tscn"
        layer_dir = directory / "layers"
        bg_layers = sorted(layer_dir.glob(f"{slug}_bg_*.tscn")) if layer_dir.is_dir() else []
        if not main_scene.is_file():
            fail(errors, f"native background scene missing: {main_scene.relative_to(ROOT)}")
        elif "NThingsCombatBackground.cs" not in main_scene.read_text(encoding="utf-8"):
            fail(errors, f"{main_scene.relative_to(ROOT)} does not use NThingsCombatBackground")
        if not bg_layers:
            fail(errors, f"native background layers missing for {slug}")

    # Native background foregrounds rely on tree ordering. Explicit z-index values
    # raise them above the creature containers and obscure the monsters.
    for path in sorted((ROOT / "scenes" / "backgrounds").rglob("*.tscn")):
        if path.name.endswith("_background.tscn") or "_fg_" in path.name:
            if re.search(r"^z_index\s*=", path.read_text(encoding="utf-8"), re.MULTILINE):
                fail(errors, f"{path.relative_to(ROOT)} overrides native background z-order")

    # Bestiary strips the _MOVE suffix before localization lookup. Verify every concrete
    # MoveState has an eng/zhs title under that normalized key and reject stale title keys.
    monster_loc_paths = [localization / lang / "monsters.json" for lang in ("eng", "zhs")]
    monster_locs = [json.loads(path.read_text(encoding="utf-8")) for path in monster_loc_paths]
    expected_move_keys: set[str] = set()
    for path in sorted((SOURCE / "Monsters").glob("*.cs")):
        text = path.read_text(encoding="utf-8")
        class_match = re.search(r"public sealed class\s+(\w+)\s*:\s*MonsterModel", text)
        if not class_match:
            continue
        entry = re.sub(r"(?<!^)(?=[A-Z])", "_", class_match.group(1)).upper()
        string_constants = dict(
            re.findall(
                r'(?:public|private|protected|internal)\s+const\s+string\s+(\w+)\s*=\s*"([A-Z0-9_]+)"',
                text,
            )
        )
        state_args = re.findall(r'new MoveState\(\s*(?:"([A-Z0-9_]+)"|(\w+))', text)
        for literal, identifier in state_args:
            state_id = literal or string_constants.get(identifier)
            if not state_id:
                continue
            move_id = state_id[:-5] if state_id.endswith("_MOVE") else state_id
            expected_move_keys.add(f"{entry}.moves.{move_id}.title")
    for key in sorted(expected_move_keys):
        for lang, table in zip(("eng", "zhs"), monster_locs, strict=True):
            if key not in table:
                fail(errors, f"{lang}/monsters.json missing bestiary move key {key}")
    custom_entries = {key.split(".moves.", 1)[0] for key in expected_move_keys}
    for lang, table in zip(("eng", "zhs"), monster_locs, strict=True):
        stale = {
            key
            for key in table
            if key.endswith(".title")
            and ".moves." in key
            and key.split(".moves.", 1)[0] in custom_entries
            and key not in expected_move_keys
        }
        if stale:
            fail(errors, f"{lang}/monsters.json has stale move title keys: {sorted(stale)}")

    catalog = SOURCE / "Hooks" / "MonsterContentPatches.cs"
    catalog_text = catalog.read_text(encoding="utf-8") if catalog.is_file() else ""
    for encounter_type in (
        "OriginFogmogBossEncounter",
        "RaidParty",
        "ScaleBeetleBossEncounter",
        "SoulRoesEncounter",
        "TheLegacyBossEncounter",
        "BowlbugProgenitorBossEncounter",
    ):
        if f"ModelDb.Encounter<{encounter_type}>()" not in catalog_text:
            fail(errors, f"Act encounter catalog is missing {encounter_type}")

    # Dynamic summons must preload every possible model through the summoner AssetPaths.
    dynamic_preload_contracts = {
        "Monsters/OriginFogmog.cs": ["ModelDb.Monster<OriginEyeWithTeeth>().AssetPaths"],
        "Monsters/SoulRoes.cs": ["ModelDb.Monster<SoulRoe>().AssetPaths"],
        "Monsters/ThiefRaider.cs": [
            f"ModelDb.Monster<{name}>().AssetPaths"
            for name in ("AxeRubyRaider", "AssassinRubyRaider", "BruteRubyRaider", "CrossbowRubyRaider", "TrackerRubyRaider")
        ],
        "Monsters/BowlbugProgenitor.cs": [
            f"ModelDb.Monster<{name}>().AssetPaths"
            for name in ("BowlbugEgg", "BowlbugNectar", "BowlbugRock", "BowlbugSilk")
        ],
    }
    for relative, snippets in dynamic_preload_contracts.items():
        text = source_text(relative)
        for snippet in snippets:
            if snippet not in text:
                fail(errors, f"{relative} does not preload dynamic summon asset: {snippet}")

    # Power hover tips request the unpacked big icon through PreloadManager.Cache.
    # Mod textures are not part of the vanilla common set, so each owning monster
    # must contribute every visible custom power icon to the combat-room asset set.
    power_icon_preload_contracts = {
        "Monsters/OriginFogmog.cs": [
            "OriginPower", "OriginGainEnergyPower", "IllusionPower", "MinionPower", "StrengthPower"
        ],
        "Monsters/SoulRoes.cs": ["SoulRoesPower", "IntangiblePower", "StrengthPower"],
        "Monsters/ThiefRaider.cs": ["ThiefRaiderPower", "WeakPower"],
        "Monsters/ScaleBeetle.cs": ["ScaleBeetlePower", "ScaleUpPower", "ScaleDownPower"],
        "Monsters/TheLegacy.cs": [
            "LegacyBeatOfDeathPower", "DazedPower", "HardenedShellPower",
            "ArtifactPower", "StrengthPower"
        ],
        "Monsters/BowlbugProgenitor.cs": [
            "BowlbugProgenitorPower", "ProtectTheMasterPower", "MinionPower",
            "WeakPower", "StrengthPower"
        ],
    }
    for relative, power_types in power_icon_preload_contracts.items():
        text = source_text(relative)
        for power_type in power_types:
            snippet = f"ModelDb.Power<{power_type}>().ResolvedBigIconPath"
            if snippet not in text:
                fail(errors, f"{relative} does not preload visible custom power icon: {power_type}")

    # Stateful monster-chain regressions. These assertions intentionally pin the
    # V108 lifecycle details that previously produced lost summons or skipped phases.
    require_snippets(
        "Powers/SoulRoesPower.cs",
        [
            "i < SoulRoesEncounter.SoulRoeSlotCount && spawned < spawnCount",
            "c.IsAlive && c.SlotName == slotName",
            "soulRoe.StartMovePhase = spawned % 3",
            "spawned++;",
            "TaskHelper.RunSafely(RevealAfterDeathAnimation",
        ],
        "eight-slot/alive-only Soul Roes death-wave contract",
    )
    require_snippets(
        "Powers/OriginPower.cs",
        [
            "target != Owner || Owner.CurrentHp > Amount",
            "result.UnblockedDamage <= 0",
            "origin.NextMove.StateId == OriginFogmog.IllusionMoveId",
            "origin.PerformInterruptedOpeningIllusionMove",
            "CreatureCmd.Stun(Owner, phaseSummon, OriginFogmog.SwipeMoveId)",
            "origin.NextMove.StateId != MonsterModel.stunnedMoveId",
            "origin.NextMove.FollowUpStateId != OriginFogmog.SwipeMoveId",
        ],
        "current-HP/interrupted-opening Origin phase threshold contract",
    )
    origin_transition = source_text("Monsters/OriginEyeWithTeeth.cs")
    if not re.search(
        r"__instance is OriginFogmog\s*"
        r"&& state\.StateId == MonsterModel\.stunnedMoveId\s*"
        r"&& state\.FollowUpStateId == OriginFogmog\.SwipeMoveId\)\s*"
        r"forceTransition = true;",
        origin_transition,
    ):
        fail(errors, "Origin Fogmog forced phase-two stun transition contract is missing")
    require_snippets(
        "Monsters/OriginFogmog.cs",
        [
            'private const string _trackName = "the_kin_progress";',
            "return SummonIllusions(2);",
            "combatState.Enemies.All(c => c.SlotName != s)",
        ],
        "The Kin music, interrupted-opening double summon and revive-reserved slot contract",
    )
    require_snippets(
        "Monsters/SoulRoes.cs",
        ["CombatState.Enemies.Any(c => c.IsAlive && c.SlotName == slotName)"],
        "alive-only Soul Roe summon-slot contract",
    )
    require_snippets(
        "Monsters/ThiefRaider.cs",
        ["combatState!.Enemies.All(c => !c.IsAlive || c.SlotName != s)"],
        "alive-only replacement-raider slot contract",
    )
    require_snippets(
        "Monsters/BowlbugProgenitor.cs",
        ["enemy => !enemy.IsAlive || enemy.SlotName != candidate"],
        "alive-only Bowlbug summon-slot contract",
    )

    # V108 MultiplayerScalingModel scales enemy ValueProp.Move block. Supplying an
    # already player-count-scaled amount would multiply it a second time, while
    # ValueProp.Unpowered would skip the native 3/4-player act scaling entirely.
    for relative in (
        "Monsters/OriginFogmog.cs",
        "Monsters/ThiefRaider.cs",
        "Monsters/BowlbugProgenitor.cs",
        "Monsters/ScaleBeetle.cs",
    ):
        text = source_text(relative)
        if re.search(
            r"GainBlock\([^;\n]*(?:Players\.Count|PlayerCount)[^;\n]*ValueProp\.Move",
            text,
        ):
            fail(errors, f"{relative} pre-scales native enemy move block by player count")
    require_snippets(
        "Monsters/BowlbugProgenitor.cs",
        [
            "GainBlock(Creature, 20, ValueProp.Move",
            "GainBlock(Creature, 16, ValueProp.Move",
        ],
        "native multiplayer enemy-block scaling contract",
    )
    require_snippets(
        "Monsters/ScaleBeetle.cs",
        ["GainBlock(Creature, MoltBlock, ValueProp.Move"],
        "native multiplayer Scale Beetle move-block scaling contract",
    )
    require_snippets(
        "Monsters/TheLegacy.cs",
        ["var target = Creature.MaxHp / divisor;"],
        "integer Hardened Shell divisor contract",
    )

    # Sprite2D creature scenes do not create a CreatureAnimator, so vanilla never
    # reaches SfxCmd.PlayDeath. Keep the narrow mod-only fallback and verified V108
    # event reuse explicit; invented event names fail silently at runtime.
    require_snippets(
        "Audio/SfxHooks.cs",
        [
            "monster.GetType().Assembly == typeof(SfxHooks).Assembly",
            "!monster.HasDeathSfx || __instance.HasSpineAnimation",
            "SfxCmd.PlayDeath(monster);",
            "private const float OriginFogmogHurtChance = 0.35f;",
            "NativeSfxPlayer.RollChance(OriginFogmogHurtChance)",
        ],
        "no-Spine death lifecycle and probabilistic Origin Fogmog hurt-SFX contract",
    )
    require_snippets(
        "Audio/NativeSfxPlayer.cs",
        [
            "public static bool RollChance(float chance)",
            "if (!float.IsFinite(chance) || chance <= 0f) return false;",
            "if (chance >= 1f) return true;",
            "_variantRng.Randf() < chance",
        ],
        "presentation-only audio probability contract",
    )
    if not re.search(
        r'if \(entry == "origin_fogmog" && '
        r'!NativeSfxPlayer\.RollChance\(OriginFogmogHurtChance\)\)\s*'
        r'return true;',
        source_text("Audio/SfxHooks.cs"),
    ):
        fail(errors, "Origin Fogmog hurt-SFX miss must fall back to its native material impact")

    verified_death_sfx = {
        "Monsters/OriginFogmog.cs": "origin_fogmog/origin_fogmog_die",
        "Monsters/SoulRoe.cs": "soul_fysh/soul_fysh_die",
        "Monsters/SoulRoes.cs": "soul_fysh/soul_fysh_die",
        "Monsters/ThiefRaider.cs": "axe_ruby_raider/axe_ruby_raider_die",
        "Monsters/TheLegacy.cs": "vantom/vantom_die",
        "Monsters/ScaleBeetle.cs": "shrinker_beetle/shrinker_beetle_die",
        "Monsters/BowlbugProgenitor.cs": "egg_layer/egg_layer_die",
    }
    for relative, event_suffix in verified_death_sfx.items():
        text = source_text(relative)
        if not re.search(
            r"public override string DeathSfx\s*=>\s*"
            + re.escape(f'"event:/sfx/enemy/enemy_attacks/{event_suffix}"'),
            text,
        ):
            fail(errors, f"{relative} lacks its verified explicit V108 DeathSfx event")
    for invalid_event in ("kaiser_crab/kaiser_crab_die", "soul_fysh/soul_fysh_summon"):
        for path in sorted((SOURCE / "Monsters").glob("*.cs")):
            if invalid_event in path.read_text(encoding="utf-8"):
                fail(errors, f"{path.relative_to(ROOT)} references nonexistent V108 event {invalid_event}")

    require_snippets(
        "Monsters/BowlbugProgenitor.cs",
        [
            "egg_layer/egg_layer_attack",
            "egg_layer/egg_layer_lay",
            "egg_layer/egg_layer_die",
        ],
        "Bowlbug Progenitor insect egg-layer sound palette",
    )
    require_snippets(
        "Monsters/ScaleBeetle.cs",
        [
            "shrinker_beetle/shrinker_beetle_attack",
            "shrinker_beetle/shrinker_beetle_cast",
            "shrinker_beetle/shrinker_beetle_die",
        ],
        "Scale Beetle vanilla beetle sound palette",
    )
    if "soul_fysh/" in source_text("Monsters/BowlbugProgenitor.cs"):
        fail(errors, "Bowlbug Progenitor still reuses the spectral Soul Fysh sound palette")
    if "kaiser_crab/" in source_text("Monsters/ScaleBeetle.cs"):
        fail(errors, "Scale Beetle still reuses the oversized Kaiser Crab sound palette")

    verified_damage_sfx = {
        "Monsters/OriginFogmog.cs": "Plant",
        "Monsters/OriginEyeWithTeeth.cs": "Magic",
        "Monsters/SoulRoe.cs": "Magic",
        "Monsters/SoulRoes.cs": "Magic",
        "Monsters/ThiefRaider.cs": "Armor",
        "Monsters/TheLegacy.cs": "Magic",
        "Monsters/ScaleBeetle.cs": "Insect",
        "Monsters/BowlbugProgenitor.cs": "Insect",
    }
    for relative, damage_type in verified_damage_sfx.items():
        if not re.search(
            r"public override DamageSfxType TakeDamageSfxType\s*=>\s*"
            + re.escape(f"DamageSfxType.{damage_type}"),
            source_text(relative),
        ):
            fail(errors, f"{relative} lacks its style-matched {damage_type} impact sound")

    eng_files = {path.name: path for path in (localization / "eng").glob("*.json")}
    zhs_files = {path.name: path for path in (localization / "zhs").glob("*.json")}
    if eng_files.keys() != zhs_files.keys():
        fail(errors, "eng/zhs localization table sets differ")
    for name in sorted(eng_files.keys() & zhs_files.keys()):
        eng = json.loads(eng_files[name].read_text(encoding="utf-8"))
        zhs = json.loads(zhs_files[name].read_text(encoding="utf-8"))
        if eng.keys() != zhs.keys():
            fail(errors, f"eng/zhs keys differ in {name}")
        for lang, table in (("eng", eng), ("zhs", zhs)):
            placeholders = sorted(
                key
                for key, value in table.items()
                if isinstance(value, str)
                and (re.fullmatch(r"\?+", value.strip()) or "TODO" in value.upper())
            )
            if placeholders:
                fail(errors, f"{lang}/{name} has placeholder values: {placeholders}")

    required_assets = [
        ROOT / "images/map/scale_beetle_boss_icon.png",
        ROOT / "images/map/scale_beetle_boss_icon_outline.png",
        ROOT / "images/atlases/relic_atlas.sprites/almond_water.tres",
        ROOT / "STS2_Things/Visuals/NThingsStaticCreatureVisuals.cs",
        ROOT / "STS2_Things/Visuals/NThingsCombatBackground.cs",
    ]
    for path in required_assets:
        if not path.is_file():
            fail(errors, f"required asset missing: {path.relative_to(ROOT)}")

    for icon_name in ("origin_fogmog", "scale_beetle", "the_legacy", "bowlbug_progenitor"):
        icon = ROOT / "images" / "map" / f"{icon_name}_boss_icon.png"
        outline = ROOT / "images" / "map" / f"{icon_name}_boss_icon_outline.png"
        if icon.is_file() and outline.is_file():
            if hashlib.sha256(icon.read_bytes()).digest() == hashlib.sha256(outline.read_bytes()).digest():
                fail(errors, f"{outline.relative_to(ROOT)} duplicates the icon and cannot render an outline")

    stale_paths = [
        ROOT / "images/map/scale_bettle_boss_icon.png",
        ROOT / "images/map/scale_bettle_boss_icon_outline.png",
        ROOT / "images/atlases/relic_atlas.sprites/almod_water.tres",
        SOURCE / ".godot",
        SOURCE / "Monsters/MonsterRegistrar.cs",
    ]
    for path in stale_paths:
        if path.exists():
            fail(errors, f"stale path must not exist: {path.relative_to(ROOT)}")

    if errors:
        print("STS2_Things source audit failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("STS2_Things source audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
