#!/usr/bin/env python3
"""Build native Spine 4.2 monster assets from the generated cutout manifest.

The cutout generator owns segmentation and bind-pose data.  This script is a
strict downstream consumer: it packs those lossless RGBA parts into an atlas,
emits runtime-loadable ``.spjson``/``.spatlas`` resources, and writes the
creature-visual scenes expected by the monster model ABI.

No gameplay state or RNG is read here.  Animation profiles are deterministic
visual data and deliberately avoid whole-character attack/hurt translations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT / "source_assets" / "monsters" / "ai_cutout_rigs.generated.json"
)
ASSET_ROOT = ROOT / "animations" / "monsters" / "sts2_things"
SCENE_ROOT = ROOT / "scenes" / "creature_visuals"

SPINE_VERSION = "4.2.0"
SPINE_SCRIPT = "res://STS2_Things/Visuals/NThingsSpineCreatureVisuals.cs"
ATLAS_EXTRUDE = 2
ATLAS_GUTTER = 3
MAX_ATLAS_SIZE = 4096
REQUIRED_ANIMATIONS = (
    "idle_loop",
    "attack",
    "cast",
    "hurt",
    "die",
    "summon",
    "power_up",
    "revive",
)
RIG_KEYS = (
    "origin_fogmog",
    "bowlbug_progenitor",
    "scale_beetle",
    "soul_roe_1",
    "soul_roe_2",
    "soul_roe_3",
    "soul_roes",
    "the_legacy",
    "thief_raider",
)


@dataclass(frozen=True)
class Bone:
    name: str
    parent: str
    pivot: tuple[float, float]


@dataclass(frozen=True)
class Part:
    name: str
    bone: str
    texture_path: str
    pivot: tuple[float, float]
    offset: tuple[float, float]
    z: int
    source_index: int


@dataclass(frozen=True)
class Rig:
    key: str
    canvas: tuple[int, int]
    bones: tuple[Bone, ...]
    parts: tuple[Part, ...]


@dataclass(frozen=True)
class PackedRegion:
    part: Part
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class SceneProfile:
    scene_name: str
    root_name: str
    position: tuple[float, float]
    scale: float
    bounds: tuple[float, float, float, float]
    center: tuple[float, float]
    intent: tuple[float, float]


SCENE_PROFILES: dict[str, SceneProfile] = {
    "origin_fogmog": SceneProfile(
        "origin_fogmog.tscn", "OriginFogmog", (0.0, -248.04), 0.52,
        (-250.36, -516.08, 250.36, 12.0), (0.0, -248.04), (0.0, -506.08)),
    "bowlbug_progenitor": SceneProfile(
        "bowlbug_progenitor.tscn", "BowlbugProgenitor", (0.0, -203.32), 0.52,
        (-393.62, -426.64, 393.62, 12.0), (0.0, -203.32), (0.0, -416.64)),
    "scale_beetle": SceneProfile(
        "scale_beetle.tscn", "ScaleBeetle", (0.0, -229.58), 0.52,
        (-313.02, -479.16, 313.02, 12.0), (0.0, -229.58), (0.0, -469.16)),
    "soul_roe_1": SceneProfile(
        "soul_roe.tscn", "SoulRoe", (0.0, -27.04), 0.52,
        (-39.04, -66.08, 39.04, 8.0), (0.0, -27.04), (0.0, -64.08)),
    "soul_roe_2": SceneProfile(
        "soul_roe_2.tscn", "SoulRoe2", (0.0, -27.04), 0.52,
        (-39.04, -66.08, 39.04, 8.0), (0.0, -27.04), (0.0, -64.08)),
    "soul_roe_3": SceneProfile(
        "soul_roe_3.tscn", "SoulRoe3", (0.0, -27.04), 0.52,
        (-39.04, -66.08, 39.04, 8.0), (0.0, -27.04), (0.0, -64.08)),
    "soul_roes": SceneProfile(
        "soul_roes.tscn", "SoulRoes", (0.0, -72.54), 0.52,
        (-108.82, -161.08, 108.82, 10.0), (0.0, -72.54), (0.0, -155.08)),
    "the_legacy": SceneProfile(
        "the_legacy.tscn", "TheLegacy", (0.0, -179.14), 0.52,
        (-373.08, -378.28, 373.08, 12.0), (0.0, -179.14), (0.0, -368.28)),
    "thief_raider": SceneProfile(
        "thief_raider.tscn", "ThiefRaider", (0.0, -95.0), 0.47,
        (-130.0, -180.0, 130.0, 12.0), (0.0, -85.0), (0.0, -204.0)),
}


def _pair(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must contain exactly two numbers")
    return float(value[0]), float(value[1])


def load_rigs(
    manifest_path: Path, selected_keys: Sequence[str] = RIG_KEYS,
) -> dict[str, Rig]:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("cutout rig manifest root must be an object")

    rigs: dict[str, Rig] = {}
    for key in selected_keys:
        entry = raw.get(key)
        if not isinstance(entry, dict):
            raise ValueError(f"manifest is missing rig '{key}'")
        canvas_raw = entry.get("canvas")
        if not isinstance(canvas_raw, list) or len(canvas_raw) != 2:
            raise ValueError(f"{key}.canvas must contain width and height")
        canvas = int(canvas_raw[0]), int(canvas_raw[1])
        if canvas[0] <= 0 or canvas[1] <= 0:
            raise ValueError(f"{key}.canvas is invalid: {canvas}")

        bones: list[Bone] = []
        for index, value in enumerate(entry.get("bones", [])):
            if not isinstance(value, dict):
                raise ValueError(f"{key}.bones[{index}] is not an object")
            bones.append(Bone(
                str(value["name"]),
                str(value.get("parent", "")),
                _pair(value["pivot"], f"{key}.bones[{index}].pivot"),
            ))

        parts: list[Part] = []
        for index, value in enumerate(entry.get("parts", [])):
            if not isinstance(value, dict):
                raise ValueError(f"{key}.parts[{index}] is not an object")
            parts.append(Part(
                str(value["name"]),
                str(value["bone"]),
                str(value["texture"]),
                _pair(value.get("pivot", [0, 0]), f"{key}.parts[{index}].pivot"),
                _pair(value.get("sprite_offset", [0, 0]),
                      f"{key}.parts[{index}].sprite_offset"),
                int(value.get("z", 0)),
                index,
            ))

        rig = Rig(key, canvas, tuple(bones), tuple(parts))
        validate_rig(rig)
        rigs[key] = rig
    return rigs


def validate_rig(rig: Rig) -> None:
    if not rig.bones:
        raise ValueError(f"{rig.key}: no bones")
    if not rig.parts:
        raise ValueError(f"{rig.key}: no parts")
    bone_map: dict[str, Bone] = {}
    for bone in rig.bones:
        if not bone.name or bone.name in bone_map:
            raise ValueError(f"{rig.key}: duplicate/empty bone name '{bone.name}'")
        bone_map[bone.name] = bone
    roots = [bone.name for bone in rig.bones if not bone.parent]
    if len(roots) != 1:
        raise ValueError(f"{rig.key}: expected one logical root, found {roots}")
    for bone in rig.bones:
        if bone.parent and bone.parent not in bone_map:
            raise ValueError(f"{rig.key}: bone '{bone.name}' has unknown parent '{bone.parent}'")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise ValueError(f"{rig.key}: cycle in bone hierarchy at '{name}'")
        visiting.add(name)
        parent = bone_map[name].parent
        if parent:
            visit(parent)
        visiting.remove(name)
        visited.add(name)

    for name in bone_map:
        visit(name)

    part_names: set[str] = set()
    for part in rig.parts:
        if not part.name or part.name in part_names:
            raise ValueError(f"{rig.key}: duplicate/empty part name '{part.name}'")
        part_names.add(part.name)
        if part.bone not in bone_map:
            raise ValueError(f"{rig.key}: part '{part.name}' uses unknown bone '{part.bone}'")
        bind = bone_map[part.bone].pivot
        if max(abs(bind[0] - part.pivot[0]), abs(bind[1] - part.pivot[1])) > 0.01:
            raise ValueError(
                f"{rig.key}: part '{part.name}' pivot {part.pivot} differs from "
                f"bone '{part.bone}' bind pivot {bind}")
        resolve_resource_path(part.texture_path)


def resolve_resource_path(resource_path: str) -> Path:
    if not resource_path.startswith("res://"):
        raise ValueError(f"texture path is not a Godot resource path: {resource_path}")
    path = ROOT / resource_path.removeprefix("res://")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def topo_bones(rig: Rig) -> list[Bone]:
    by_name = {bone.name: bone for bone in rig.bones}
    result: list[Bone] = []
    emitted: set[str] = set()

    def emit(bone: Bone) -> None:
        if bone.name in emitted:
            return
        if bone.parent:
            emit(by_name[bone.parent])
        emitted.add(bone.name)
        result.append(bone)

    for bone in rig.bones:
        emit(bone)
    return result


def alpha_bleed(image: Image.Image, iterations: int = 3) -> Image.Image:
    """Fill RGB below fully transparent pixels without changing any alpha."""
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    rgb = rgba[:, :, :3].astype(np.float32)
    alpha = rgba[:, :, 3]
    known = alpha > 0
    height, width = known.shape
    for _ in range(iterations):
        if known.all():
            break
        sums = np.zeros((height, width, 3), dtype=np.float32)
        counts = np.zeros((height, width), dtype=np.float32)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
            sy0, sy1 = max(0, -dy), min(height, height - dy)
            sx0, sx1 = max(0, -dx), min(width, width - dx)
            dy0, dy1 = sy0 + dy, sy1 + dy
            dx0, dx1 = sx0 + dx, sx1 + dx
            mask = known[sy0:sy1, sx0:sx1]
            sums[dy0:dy1, dx0:dx1] += rgb[sy0:sy1, sx0:sx1] * mask[:, :, None]
            counts[dy0:dy1, dx0:dx1] += mask
        frontier = (~known) & (counts > 0)
        if not frontier.any():
            break
        rgb[frontier] = sums[frontier] / counts[frontier, None]
        known[frontier] = True
    rgba[:, :, :3] = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def _shelf_layout(
    sizes: Sequence[tuple[str, int, int]], width: int,
) -> tuple[dict[str, tuple[int, int]], int] | None:
    border = ATLAS_EXTRUDE + ATLAS_GUTTER
    ordered = sorted(sizes, key=lambda item: (-item[2], -item[1], item[0]))
    x = border
    y = border
    row_height = 0
    placements: dict[str, tuple[int, int]] = {}
    for name, item_width, item_height in ordered:
        cell_width = item_width + border * 2
        cell_height = item_height + border * 2
        if cell_width > width:
            return None
        if x + cell_width > width:
            y += row_height
            x = border
            row_height = 0
        if y + cell_height > MAX_ATLAS_SIZE:
            return None
        placements[name] = (x + border, y + border)
        x += cell_width
        row_height = max(row_height, cell_height)
    return placements, y + row_height


def pack_atlas(rig: Rig, output_dir: Path) -> tuple[Path, str, list[PackedRegion]]:
    images: dict[str, Image.Image] = {}
    sizes: list[tuple[str, int, int]] = []
    for part in rig.parts:
        image = Image.open(resolve_resource_path(part.texture_path)).convert("RGBA")
        if image.width <= 0 or image.height <= 0 or image.getbbox() is None:
            raise ValueError(f"{rig.key}: empty part texture '{part.texture_path}'")
        image = alpha_bleed(image)
        images[part.name] = image
        sizes.append((part.name, image.width, image.height))

    minimum = max(width + 2 * (ATLAS_EXTRUDE + ATLAS_GUTTER)
                  for _, width, _ in sizes)
    candidates = [value for value in (256, 512, 1024, 2048, 4096) if value >= minimum]
    best: tuple[int, int, dict[str, tuple[int, int]]] | None = None
    for width in candidates:
        layout = _shelf_layout(sizes, width)
        if layout is None:
            continue
        placements, used_height = layout
        used_width = max(x + images[name].width + ATLAS_EXTRUDE + ATLAS_GUTTER
                         for name, (x, _) in placements.items())
        area = used_width * used_height
        if best is None or (area, max(used_width, used_height), width) < (
                best[0] * best[1], max(best[0], best[1]), best[0]):
            best = used_width, used_height, placements
    if best is None:
        raise ValueError(f"{rig.key}: parts do not fit a {MAX_ATLAS_SIZE}px atlas")

    atlas_width, atlas_height, placements = best
    atlas = Image.new("RGBA", (atlas_width, atlas_height), (0, 0, 0, 0))
    regions: list[PackedRegion] = []
    for part in rig.parts:
        image = images[part.name]
        x, y = placements[part.name]
        atlas.alpha_composite(image, (x, y))
        pixels = np.asarray(image, dtype=np.uint8)
        # Duplicate the rectangular edge into the atlas padding.  The source
        # region remains byte-identical; transparent RGB has already received
        # a local colour bleed to prevent dark/grey filtering fringes.
        for distance in range(1, ATLAS_EXTRUDE + 1):
            atlas.paste(Image.fromarray(pixels[0:1, :, :], "RGBA"), (x, y - distance))
            atlas.paste(Image.fromarray(pixels[-1:, :, :], "RGBA"),
                        (x, y + image.height - 1 + distance))
            atlas.paste(Image.fromarray(pixels[:, 0:1, :], "RGBA"), (x - distance, y))
            atlas.paste(Image.fromarray(pixels[:, -1:, :], "RGBA"),
                        (x + image.width - 1 + distance, y))
        corner_values = {
            (-1, -1): tuple(int(v) for v in pixels[0, 0]),
            (1, -1): tuple(int(v) for v in pixels[0, -1]),
            (-1, 1): tuple(int(v) for v in pixels[-1, 0]),
            (1, 1): tuple(int(v) for v in pixels[-1, -1]),
        }
        for (sx, sy), colour in corner_values.items():
            for dx in range(1, ATLAS_EXTRUDE + 1):
                for dy in range(1, ATLAS_EXTRUDE + 1):
                    px = x - dx if sx < 0 else x + image.width - 1 + dx
                    py = y - dy if sy < 0 else y + image.height - 1 + dy
                    atlas.putpixel((px, py), colour)
        regions.append(PackedRegion(part, x, y, image.width, image.height))

    output_dir.mkdir(parents=True, exist_ok=True)
    page_path = output_dir / f"{rig.key}.png"
    atlas.save(page_path, optimize=True)

    lines = [
        page_path.name,
        f"size: {atlas_width},{atlas_height}",
        "format: RGBA8888",
        "filter: Linear,Linear",
        "repeat: none",
    ]
    for region in regions:
        lines.extend([
            region.part.name,
            "  rotate: false",
            f"  xy: {region.x}, {region.y}",
            f"  size: {region.width}, {region.height}",
            f"  orig: {region.width}, {region.height}",
            "  offset: 0, 0",
            "  index: -1",
        ])
    atlas_text = "\n".join(lines) + "\n"
    return page_path, atlas_text, regions


def _natural_key(name: str) -> tuple[Any, ...]:
    return tuple(int(token) if token.isdigit() else token.lower()
                 for token in re.split(r"(\d+)", name))


def _round(value: float) -> float:
    value = round(float(value), 4)
    return 0.0 if abs(value) < 0.00005 else value


def _curve_scalar(
    t0: float, v0: float, t1: float, v1: float,
) -> list[float]:
    delta = t1 - t0
    return [_round(t0 + delta * 0.32), _round(v0),
            _round(t0 + delta * 0.68), _round(v1)]


def _curve_vector(
    t0: float, v0: tuple[float, float], t1: float, v1: tuple[float, float],
) -> list[float]:
    delta = t1 - t0
    c1 = _round(t0 + delta * 0.32)
    c2 = _round(t0 + delta * 0.68)
    return [c1, _round(v0[0]), c2, _round(v1[0]),
            c1, _round(v0[1]), c2, _round(v1[1])]


def rotate_frames(values: Sequence[tuple[float, float]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, (time, value) in enumerate(values):
        frame: dict[str, Any] = {"time": _round(time), "value": _round(value)}
        if index + 1 < len(values):
            next_time, next_value = values[index + 1]
            frame["curve"] = _curve_scalar(time, value, next_time, next_value)
        result.append(frame)
    return result


def vector_frames(
    values: Sequence[tuple[float, float, float]], *, scale: bool = False,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, (time, x, y) in enumerate(values):
        frame: dict[str, Any] = {"time": _round(time), "x": _round(x), "y": _round(y)}
        if index + 1 < len(values):
            nt, nx, ny = values[index + 1]
            frame["curve"] = _curve_vector(time, (x, y), nt, (nx, ny))
        result.append(frame)
    return result


class AnimationSet:
    def __init__(self, bone_names: Iterable[str]) -> None:
        self.bones = tuple(bone_names)
        self.by_lower = {name.lower(): name for name in self.bones}
        self.animations: dict[str, dict[str, Any]] = {
            name: {"bones": {}} for name in REQUIRED_ANIMATIONS
        }
        self.durations: dict[str, float] = {}

    def exact(self, *names: str) -> list[str]:
        result: list[str] = []
        for name in names:
            actual = self.by_lower.get(name.lower())
            if actual is not None and actual not in result:
                result.append(actual)
        return result

    def containing(self, *tokens: str) -> list[str]:
        lowered = tuple(token.lower() for token in tokens)
        return sorted(
            [name for name in self.bones if any(token in name.lower() for token in lowered)],
            key=_natural_key,
        )

    def set_rotate(
        self, animation: str, bone: str,
        values: Sequence[tuple[float, float]],
    ) -> None:
        self.animations[animation]["bones"].setdefault(bone, {})["rotate"] = rotate_frames(values)

    def set_translate(
        self, animation: str, bone: str,
        values: Sequence[tuple[float, float, float]],
    ) -> None:
        self.animations[animation]["bones"].setdefault(bone, {})["translate"] = vector_frames(values)

    def set_scale(
        self, animation: str, bone: str,
        values: Sequence[tuple[float, float, float]],
    ) -> None:
        self.animations[animation]["bones"].setdefault(bone, {})["scale"] = vector_frames(
            values, scale=True)

    def mark_duration(self, animation: str, duration: float) -> None:
        self.durations[animation] = max(duration, self.durations.get(animation, 0.0))

    def finish(self, root: str) -> dict[str, dict[str, Any]]:
        defaults = {
            "idle_loop": 4.0, "attack": 0.95, "cast": 0.95, "hurt": 0.42,
            "die": 1.1, "summon": 0.9, "power_up": 0.95, "revive": 0.9,
        }
        for name in REQUIRED_ANIMATIONS:
            duration = self.durations.get(name, defaults[name])
            bones = self.animations[name]["bones"]
            root_timelines = bones.setdefault(root, {})
            if "rotate" not in root_timelines:
                root_timelines["rotate"] = rotate_frames(((0.0, 0.0), (duration, 0.0)))
            else:
                frames = root_timelines["rotate"]
                if float(frames[-1].get("time", 0.0)) < duration:
                    # Rebuild to keep a valid final Bezier segment.
                    values = [(float(frame.get("time", 0.0)),
                               float(frame.get("value", 0.0))) for frame in frames]
                    values.append((duration, values[-1][1]))
                    root_timelines["rotate"] = rotate_frames(values)
        return self.animations


def _joint_action(
    animations: AnimationSet,
    animation: str,
    bones: Iterable[str],
    duration: float,
    impact: float,
    amount: float,
    alternating: bool = False,
) -> None:
    selected = list(dict.fromkeys(bones))
    for index, bone in enumerate(selected):
        sign = -1.0 if alternating and index % 2 else 1.0
        animations.set_rotate(animation, bone, (
            (0.0, 0.0),
            (max(0.08, impact * 0.42), -amount * 0.28 * sign),
            (impact, amount * sign),
            (min(duration, impact + 0.16), -amount * 0.18 * sign),
            (duration, 0.0),
        ))
    animations.mark_duration(animation, duration)


def profile_scale_beetle(a: AnimationSet) -> None:
    duration = 8.4
    for chain_index, token in enumerate(("AntennaFront", "AntennaBack")):
        chain = a.containing(token)
        for index, bone in enumerate(chain):
            amplitude = 0.5 + 0.8 * index / max(1, len(chain) - 1)
            phase = chain_index * 1.75 + index * 0.13
            frames = []
            for sample in range(17):
                time = duration * sample / 16
                value = amplitude * math.sin(math.tau * time / duration + phase)
                frames.append((time, value))
            a.set_rotate("idle_loop", bone, frames)
    legs = a.exact("ForeClaw", "FrontLeg", "MidLeg", "RearLeg")
    for index, bone in enumerate(legs):
        phase = index * math.pi * 0.62
        frames = []
        for sample in range(9):
            time = duration * sample / 8
            frames.append((time, 0.65 * math.sin(math.tau * time / duration + phase)))
        a.set_rotate("idle_loop", bone, frames)
    a.mark_duration("idle_loop", duration)

    jaws = a.exact("JawUpper", "JawLower", "ForeClaw")
    for bone in jaws:
        # The cut pieces carry hidden socket art, but the contact pose remains
        # restrained so no joint ever outruns that painted overlap.
        amount = {"JawUpper": -3.5, "JawLower": 9.0, "ForeClaw": 5.5}[bone]
        a.set_rotate("attack", bone, (
            (0.0, 0.0), (0.18, -amount * 0.28), (0.48, amount),
            (0.61, -amount * 0.12), (1.03, 0.0)))
    a.mark_duration("attack", 1.03)

    _joint_action(a, "cast", a.containing("Antenna"), 1.15, 0.50, 2.0, True)
    _joint_action(a, "summon", a.exact("JawLower", "ForeClaw", "FrontLeg"),
                  0.92, 0.75, 5.0, True)
    _joint_action(a, "power_up", a.containing("Antenna"), 1.12, 0.50, 2.7, True)
    _joint_action(a, "hurt", a.exact("JawLower", "ForeClaw", "FrontLeg"),
                  0.46, 0.16, 3.0, True)
    _joint_action(a, "die", a.exact("ForeClaw", "FrontLeg", "MidLeg", "RearLeg"),
                  1.37, 0.58, 8.0, True)
    _joint_action(a, "revive", legs, 1.0, 0.48, 4.0, True)


def profile_origin_fogmog(a: AnimationSet) -> None:
    duration = 4.8
    # Body, cap, and feet stay structurally rigid.  Life is concentrated in
    # hand tips and a tiny delayed facial response, matching vanilla Fogmog.
    limb_specs = (
        ("LeftArm", 0.45, 0.0), ("LeftForearm", 0.85, 0.13),
        ("LeftHand", 1.35, 0.27), ("RightArm", -0.45, 0.35),
        ("RightForearm", -0.85, 0.48), ("RightHand", -1.35, 0.62),
    )
    for requested, amplitude, phase in limb_specs:
        matches = a.exact(requested)
        if not matches:
            continue
        bone = matches[0]
        frames = []
        for sample in range(9):
            time = duration * sample / 8
            frames.append((time, amplitude * math.sin(math.tau * time / duration + phase)))
        a.set_rotate("idle_loop", bone, frames)
    for bone in a.exact("Face"):
        a.set_rotate("idle_loop", bone, (
            (0.0, 0.0), (1.35, 0.38), (2.55, 0.0), (3.75, -0.26), (duration, 0.0)))
    a.mark_duration("idle_loop", duration)
    tips = a.exact("LeftForearm", "LeftHand", "RightForearm", "RightHand", "Face")
    _joint_action(a, "attack", tips, 0.78, 0.50, 6.0, True)
    _joint_action(a, "cast", tips, 0.95, 0.50, 4.5, True)
    _joint_action(a, "summon", tips, 1.02, 0.75, 6.5, True)
    _joint_action(a, "power_up", tips, 0.88, 0.50, 4.8, True)
    _joint_action(a, "hurt", a.exact("Face", "LeftHand", "RightHand"),
                  0.34, 0.12, 2.8, True)
    _joint_action(a, "die", tips + a.exact("LeftFoot", "RightFoot"),
                  1.90, 0.55, 6.5, True)
    _joint_action(a, "revive", tips, 0.9, 0.42, 3.8, True)


def profile_bowlbug(a: AnimationSet) -> None:
    duration = 5.2
    legs = a.exact("FrontLeg", "MidLegA", "MidLegB", "RearLegA", "RearLegB")
    for index, bone in enumerate(legs):
        phase = index * math.tau / max(1, len(legs))
        frames = []
        for sample in range(11):
            time = duration * sample / 10
            frames.append((time, 0.85 * math.sin(math.tau * time / duration + phase)))
        a.set_rotate("idle_loop", bone, frames)
    for bone in a.exact("EggSac"):
        a.set_scale("idle_loop", bone, (
            (0.0, 1.0, 1.0), (2.6, 1.006, 1.006), (duration, 1.0, 1.0)))
    a.mark_duration("idle_loop", duration)
    for bone in a.exact("Mandible", "MandibleLower"):
        amount = 11.0 if bone == "Mandible" else -11.0
        a.set_rotate("attack", bone, (
            (0.0, 0.0), (0.20, -amount * 0.28), (0.47, amount),
            (0.57, -amount * 0.16), (0.92, 0.0)))
    a.mark_duration("attack", 0.92)
    mouth = a.exact("Mandible", "MandibleLower", "Crest")
    _joint_action(a, "cast", mouth + legs,
                  0.94, 0.50, 4.2, True)
    _joint_action(a, "summon", mouth + legs,
                  1.0, 0.75, 4.8, True)
    _joint_action(a, "power_up", mouth + legs,
                  0.9, 0.50, 4.0, True)
    _joint_action(a, "hurt", a.exact("Mandible", "MandibleLower") + legs,
                  0.43, 0.15, 3.0, True)
    _joint_action(a, "die", a.exact("Mandible", "MandibleLower", "Crest") + legs,
                  0.92, 0.52, 7.0, True)
    _joint_action(a, "revive", legs + mouth, 0.95, 0.46, 3.5, True)


def profile_soul_roe(a: AnimationSet) -> None:
    root = a.exact("Root")[0]
    core = a.exact("Core")
    duration = 3.6
    a.set_translate("idle_loop", root, (
        (0.0, 0.0, 0.0), (0.9, 0.6, 1.8), (1.8, 0.0, 2.5),
        (2.7, -0.5, 1.2), (duration, 0.0, 0.0)))
    a.set_rotate("idle_loop", root, (
        (0.0, 0.0), (0.9, 0.55), (1.8, 0.0), (2.7, -0.45), (duration, 0.0)))
    for bone in core:
        # The nucleus trails the membrane rather than stretching in four axes.
        a.set_translate("idle_loop", bone, (
            (0.0, 0.0, 0.0), (1.08, -0.8, -1.0), (1.98, 0.0, -1.5),
            (2.88, 0.7, -0.6), (duration, 0.0, 0.0)))
        a.set_rotate("idle_loop", bone, (
            (0.0, 0.0), (1.08, -0.8), (1.98, 0.0), (2.88, 0.65), (duration, 0.0)))
    for bone in a.exact("Nucleus"):
        a.set_translate("idle_loop", bone, (
            (0.0, 0.0, 0.0), (1.22, -0.55, -0.7), (2.12, 0.0, -0.9),
            (3.02, 0.48, -0.35), (duration, 0.0, 0.0)))
        a.set_rotate("idle_loop", bone, (
            (0.0, 0.0), (1.22, -0.45), (2.12, 0.0), (3.02, 0.38), (duration, 0.0)))
    a.mark_duration("idle_loop", duration)
    nucleus = a.exact("Nucleus")
    _joint_action(a, "attack", core + nucleus, 0.72, 0.50, 5.0, True)
    _joint_action(a, "cast", core + nucleus, 0.82, 0.50, 3.8, True)
    _joint_action(a, "summon", core + nucleus, 0.88, 0.75, 4.2, True)
    _joint_action(a, "power_up", core + nucleus, 0.82, 0.50, 3.8, True)
    _joint_action(a, "hurt", core + nucleus, 0.32, 0.11, 3.2, True)
    _joint_action(a, "die", core + nucleus, 0.58, 0.28, 7.0, True)
    _joint_action(a, "revive", core + nucleus, 0.66, 0.34, 3.8, True)


def profile_soul_roes(a: AnimationSet) -> None:
    duration = 4.8
    clusters = a.exact("ClusterTop", "ClusterMiddle", "ClusterBottom")
    roe_bones = [name for name in a.bones if name.startswith("Roe")]
    for index, bone in enumerate(clusters):
        phase = index * 1.95
        values = []
        translations = []
        for sample in range(13):
            time = duration * sample / 12
            wave = math.sin(math.tau * time / duration + phase)
            scale = 1.0 + 0.0025 * wave
            values.append((time, scale, scale))
            translations.append((time, 0.0, 0.7 * wave))
        a.set_scale("idle_loop", bone, values)
        a.set_translate("idle_loop", bone, translations)
    for index, bone in enumerate(roe_bones):
        lower = bone.lower()
        cluster_phase = 0.0 if "top" in lower else (2.0 if "middle" in lower or "core" in lower else 4.0)
        phase = cluster_phase + index * 0.17
        amplitude = 0.0020 + (index % 3) * 0.00045
        values = []
        rotations = []
        for sample in range(13):
            time = duration * sample / 12
            wave = math.sin(math.tau * time / duration + phase)
            scale = 1.0 + amplitude * wave
            values.append((time, scale, scale))
            rotations.append((time, 0.45 * wave))
        a.set_scale("idle_loop", bone, values)
        a.set_rotate("idle_loop", bone, rotations)
    a.mark_duration("idle_loop", duration)
    _joint_action(a, "attack", roe_bones[::2], 0.78, 0.50, 3.0, True)
    _joint_action(a, "cast", roe_bones[1::2], 0.86, 0.50, 2.4, True)
    _joint_action(a, "summon", roe_bones, 0.96, 0.75, 2.8, True)
    _joint_action(a, "power_up", roe_bones, 0.88, 0.50, 2.3, True)
    _joint_action(a, "hurt", roe_bones[::3], 0.38, 0.13, 2.6, True)
    _joint_action(a, "die", roe_bones, 0.78, 0.42, 5.0, True)
    _joint_action(a, "revive", roe_bones, 0.82, 0.40, 2.8, True)


def profile_legacy(a: AnimationSet) -> None:
    anchors = a.exact("HeartAnchor") or a.exact("HeartCore")
    duration = 1.5
    for bone in anchors:
        # Restrained, anatomical lub-dub: two brief contractions and a long
        # diastolic rest.  Descendant lobes inherit this once; they receive no
        # additional scale timeline.
        a.set_scale("idle_loop", bone, (
            (0.0, 1.0, 1.0), (0.10, 0.994, 0.994), (0.17, 1.001, 1.001),
            (0.28, 0.9925, 0.9925), (0.37, 1.001, 1.001),
            (0.62, 1.0, 1.0), (duration, 1.0, 1.0)))
    a.mark_duration("idle_loop", duration)
    for name, length, impact, minimum in (
        ("attack", 0.9, 0.50, 0.986), ("cast", 0.94, 0.50, 0.987),
        ("summon", 1.02, 0.75, 0.988), ("power_up", 0.94, 0.50, 0.986),
        ("hurt", 0.40, 0.13, 0.984), ("die", 0.92, 0.48, 0.978),
        ("revive", 0.9, 0.42, 0.988)):
        for bone in anchors:
            a.set_scale(name, bone, (
                (0.0, 1.0, 1.0), (impact, minimum, minimum),
                (min(length, impact + 0.10), 1.002, 1.002), (length, 1.0, 1.0)))
        a.mark_duration(name, length)


def profile_thief(a: AnimationSet) -> None:
    def rotate(
        animation: str, bone: str, values: Sequence[tuple[float, float]],
    ) -> None:
        for actual in a.exact(bone):
            a.set_rotate(animation, actual, values)

    # The crouched Ruby Raider silhouette should feel alert, not rubbery.  The
    # torso barely breathes; cloth follows with delayed, sub-degree settling and
    # the two planted boots only counter-rotate enough to preserve their stance.
    duration = 4.8
    idle_tracks = {
        "Pelvis": ((0.0, 0.0), (1.2, 0.14), (2.4, 0.0), (3.6, -0.10), (duration, 0.0)),
        "Torso": ((0.0, 0.0), (1.2, 0.34), (2.4, 0.0), (3.6, -0.24), (duration, 0.0)),
        "Head": ((0.0, 0.0), (1.34, -0.22), (2.54, 0.0), (3.74, 0.16), (duration, 0.0)),
        "Cloak": ((0.0, 0.0), (1.42, 0.42), (2.62, 0.0), (3.82, -0.30), (duration, 0.0)),
        "CloakFarTail": ((0.0, 0.0), (1.56, 0.68), (2.76, 0.08), (3.96, -0.48), (duration, 0.0)),
        "CloakNearTail": ((0.0, 0.0), (1.68, -0.60), (2.88, -0.06), (4.08, 0.42), (duration, 0.0)),
        "Scarf": ((0.0, 0.0), (1.52, 0.62), (2.72, 0.05), (3.92, -0.44), (duration, 0.0)),
        "Bag": ((0.0, 0.0), (1.48, -0.28), (2.68, 0.0), (3.88, 0.20), (duration, 0.0)),
        "BagStrap": ((0.0, 0.0), (1.38, -0.20), (2.58, 0.0), (3.78, 0.14), (duration, 0.0)),
        "FarArm": ((0.0, 0.0), (1.3, -0.18), (2.5, 0.0), (3.7, 0.13), (duration, 0.0)),
        "FarForearm": ((0.0, 0.0), (1.42, 0.22), (2.62, 0.0), (3.82, -0.16), (duration, 0.0)),
        "NearArm": ((0.0, 0.0), (1.26, 0.20), (2.46, 0.0), (3.66, -0.14), (duration, 0.0)),
        "NearForearm": ((0.0, 0.0), (1.40, -0.24), (2.60, 0.0), (3.80, 0.17), (duration, 0.0)),
        "FarLeg": ((0.0, 0.0), (1.2, -0.12), (2.4, 0.0), (3.6, 0.08), (duration, 0.0)),
        "FarShinFoot": ((0.0, 0.0), (1.2, 0.18), (2.4, 0.0), (3.6, -0.12), (duration, 0.0)),
        "NearLeg": ((0.0, 0.0), (1.2, 0.10), (2.4, 0.0), (3.6, -0.07), (duration, 0.0)),
        "NearShinFoot": ((0.0, 0.0), (1.2, -0.16), (2.4, 0.0), (3.6, 0.11), (duration, 0.0)),
    }
    for bone, frames in idle_tracks.items():
        rotate("idle_loop", bone, frames)
    a.mark_duration("idle_loop", duration)

    # Near-hand dagger attack: anticipation travels shoulder -> wrist, the
    # planted near boot braces at contact, and the cloak settles after the arm.
    attack_tracks = {
        "Pelvis": ((0.0, 0.0), (0.20, -1.2), (0.48, 1.8), (0.64, 1.0), (0.96, 0.0)),
        "Torso": ((0.0, 0.0), (0.20, -2.4), (0.48, 3.8), (0.64, 2.1), (0.96, 0.0)),
        "Head": ((0.0, 0.0), (0.22, 1.0), (0.48, -1.8), (0.68, -0.7), (0.96, 0.0)),
        "NearArm": ((0.0, 0.0), (0.16, -7.0), (0.32, -11.0), (0.48, 17.0), (0.62, 12.0), (0.96, 0.0)),
        "NearForearm": ((0.0, 0.0), (0.18, 8.0), (0.34, 13.0), (0.48, -24.0), (0.62, -16.0), (0.96, 0.0)),
        "NearHand": ((0.0, 0.0), (0.22, -3.0), (0.36, -6.0), (0.48, 10.0), (0.64, 5.0), (0.96, 0.0)),
        "Dagger": ((0.0, 0.0), (0.24, 2.0), (0.38, 4.0), (0.48, -6.0), (0.64, -2.0), (0.96, 0.0)),
        "NearLeg": ((0.0, 0.0), (0.22, -1.2), (0.48, 2.2), (0.68, 1.0), (0.96, 0.0)),
        "NearShinFoot": ((0.0, 0.0), (0.22, 1.8), (0.48, -3.0), (0.68, -1.2), (0.96, 0.0)),
        "FarLeg": ((0.0, 0.0), (0.22, 0.7), (0.48, -1.2), (0.68, -0.5), (0.96, 0.0)),
        "FarShinFoot": ((0.0, 0.0), (0.22, -1.0), (0.48, 1.6), (0.68, 0.6), (0.96, 0.0)),
        "Cloak": ((0.0, 0.0), (0.26, 1.6), (0.52, -2.4), (0.72, -1.1), (0.96, 0.0)),
        "CloakFarTail": ((0.0, 0.0), (0.30, 2.6), (0.56, -4.2), (0.76, -1.8), (0.96, 0.0)),
        "CloakNearTail": ((0.0, 0.0), (0.32, -2.2), (0.58, 3.6), (0.78, 1.5), (0.96, 0.0)),
        "Scarf": ((0.0, 0.0), (0.28, 1.8), (0.54, -3.0), (0.74, -1.1), (0.96, 0.0)),
    }
    for bone, frames in attack_tracks.items():
        rotate("attack", bone, frames)
    a.mark_duration("attack", 0.96)

    cast_tracks = {
        "FarArm": ((0.0, 0.0), (0.20, -6.0), (0.50, 13.0), (0.66, 8.0), (0.92, 0.0)),
        "FarForearm": ((0.0, 0.0), (0.22, 8.0), (0.50, -17.0), (0.68, -8.0), (0.92, 0.0)),
        "FarHand": ((0.0, 0.0), (0.26, -3.0), (0.50, 7.0), (0.70, 2.5), (0.92, 0.0)),
        "Torso": ((0.0, 0.0), (0.22, -1.6), (0.50, 2.8), (0.68, 1.1), (0.92, 0.0)),
        "Bag": ((0.0, 0.0), (0.24, 1.2), (0.50, -2.0), (0.70, -0.8), (0.92, 0.0)),
        "CloakFarTail": ((0.0, 0.0), (0.28, 1.8), (0.54, -2.8), (0.74, -1.0), (0.92, 0.0)),
        "CloakNearTail": ((0.0, 0.0), (0.30, -1.5), (0.56, 2.3), (0.76, 0.8), (0.92, 0.0)),
    }
    for bone, frames in cast_tracks.items():
        rotate("cast", bone, frames)
    a.mark_duration("cast", 0.92)

    summon_tracks = {
        "Torso": ((0.0, 0.0), (0.26, -2.0), (0.52, -3.2), (0.75, 2.6), (1.02, 0.0)),
        "NearArm": ((0.0, 0.0), (0.28, -6.0), (0.54, -10.0), (0.75, 11.0), (1.02, 0.0)),
        "NearForearm": ((0.0, 0.0), (0.30, 7.0), (0.56, 12.0), (0.75, -14.0), (1.02, 0.0)),
        "FarArm": ((0.0, 0.0), (0.28, 5.0), (0.54, 9.0), (0.75, -10.0), (1.02, 0.0)),
        "FarForearm": ((0.0, 0.0), (0.30, -6.0), (0.56, -11.0), (0.75, 13.0), (1.02, 0.0)),
        "NearShinFoot": ((0.0, 0.0), (0.32, 1.4), (0.58, 2.0), (0.75, -1.4), (1.02, 0.0)),
        "FarShinFoot": ((0.0, 0.0), (0.32, -1.1), (0.58, -1.7), (0.75, 1.2), (1.02, 0.0)),
        "CloakFarTail": ((0.0, 0.0), (0.34, 2.0), (0.62, 3.2), (0.79, -2.4), (1.02, 0.0)),
        "CloakNearTail": ((0.0, 0.0), (0.36, -1.8), (0.64, -2.8), (0.81, 2.1), (1.02, 0.0)),
    }
    for bone, frames in summon_tracks.items():
        rotate("summon", bone, frames)
    a.mark_duration("summon", 1.02)

    power_tracks = {
        "Pelvis": ((0.0, 0.0), (0.24, 1.6), (0.50, -2.4), (0.68, -1.0), (0.94, 0.0)),
        "Torso": ((0.0, 0.0), (0.24, 2.4), (0.50, -3.6), (0.68, -1.5), (0.94, 0.0)),
        "NearLeg": ((0.0, 0.0), (0.24, -2.0), (0.50, 3.2), (0.68, 1.3), (0.94, 0.0)),
        "NearShinFoot": ((0.0, 0.0), (0.24, 2.8), (0.50, -4.0), (0.68, -1.7), (0.94, 0.0)),
        "FarLeg": ((0.0, 0.0), (0.24, 1.7), (0.50, -2.7), (0.68, -1.1), (0.94, 0.0)),
        "FarShinFoot": ((0.0, 0.0), (0.24, -2.4), (0.50, 3.5), (0.68, 1.4), (0.94, 0.0)),
        "NearArm": ((0.0, 0.0), (0.24, 4.0), (0.50, -6.5), (0.68, -2.5), (0.94, 0.0)),
        "FarArm": ((0.0, 0.0), (0.24, -3.5), (0.50, 5.8), (0.68, 2.2), (0.94, 0.0)),
        "CloakFarTail": ((0.0, 0.0), (0.28, -1.8), (0.54, 3.0), (0.72, 1.2), (0.94, 0.0)),
        "CloakNearTail": ((0.0, 0.0), (0.30, 1.6), (0.56, -2.6), (0.74, -1.0), (0.94, 0.0)),
    }
    for bone, frames in power_tracks.items():
        rotate("power_up", bone, frames)
    a.mark_duration("power_up", 0.94)

    hurt_tracks = {
        "Pelvis": ((0.0, 0.0), (0.13, 2.4), (0.22, -1.0), (0.40, 0.0)),
        "Torso": ((0.0, 0.0), (0.13, 5.2), (0.22, -2.0), (0.40, 0.0)),
        "Head": ((0.0, 0.0), (0.13, -4.2), (0.24, 1.4), (0.40, 0.0)),
        "NearArm": ((0.0, 0.0), (0.13, -3.8), (0.24, 1.2), (0.40, 0.0)),
        "FarArm": ((0.0, 0.0), (0.13, 3.2), (0.24, -1.0), (0.40, 0.0)),
        "NearShinFoot": ((0.0, 0.0), (0.13, -2.8), (0.24, 1.0), (0.40, 0.0)),
        "FarShinFoot": ((0.0, 0.0), (0.13, 2.2), (0.24, -0.8), (0.40, 0.0)),
        "CloakFarTail": ((0.0, 0.0), (0.16, -5.2), (0.27, 1.8), (0.40, 0.0)),
        "CloakNearTail": ((0.0, 0.0), (0.17, 4.4), (0.28, -1.5), (0.40, 0.0)),
    }
    for bone, frames in hurt_tracks.items():
        rotate("hurt", bone, frames)
    a.mark_duration("hurt", 0.40)

    die_tracks = {
        "Pelvis": ((0.0, 0.0), (0.16, 3.0), (0.38, -10.0), (0.58, -17.0), (0.72, -18.0)),
        "Torso": ((0.0, 0.0), (0.16, -4.0), (0.38, 12.0), (0.58, 21.0), (0.72, 22.0)),
        "Head": ((0.0, 0.0), (0.18, 3.0), (0.40, -10.0), (0.60, -17.0), (0.72, -18.0)),
        "NearArm": ((0.0, 0.0), (0.18, -5.0), (0.42, 16.0), (0.62, 25.0), (0.72, 26.0)),
        "NearForearm": ((0.0, 0.0), (0.20, 6.0), (0.44, -18.0), (0.64, -28.0), (0.72, -29.0)),
        "FarArm": ((0.0, 0.0), (0.18, 4.0), (0.42, -14.0), (0.62, -22.0), (0.72, -23.0)),
        "FarForearm": ((0.0, 0.0), (0.20, -5.0), (0.44, 16.0), (0.64, 25.0), (0.72, 26.0)),
        "NearLeg": ((0.0, 0.0), (0.20, 3.0), (0.44, -10.0), (0.64, -16.0), (0.72, -17.0)),
        "NearShinFoot": ((0.0, 0.0), (0.22, -4.0), (0.46, 14.0), (0.66, 21.0), (0.72, 22.0)),
        "FarLeg": ((0.0, 0.0), (0.20, -2.5), (0.44, 9.0), (0.64, 14.0), (0.72, 15.0)),
        "FarShinFoot": ((0.0, 0.0), (0.22, 3.5), (0.46, -12.0), (0.66, -18.0), (0.72, -19.0)),
        "CloakFarTail": ((0.0, 0.0), (0.24, 5.0), (0.48, -16.0), (0.68, -25.0), (0.72, -26.0)),
        "CloakNearTail": ((0.0, 0.0), (0.26, -4.0), (0.50, 14.0), (0.70, 22.0), (0.72, 23.0)),
        "Scarf": ((0.0, 0.0), (0.22, 4.0), (0.46, -12.0), (0.66, -18.0), (0.72, -19.0)),
    }
    for bone, frames in die_tracks.items():
        rotate("die", bone, frames)
    a.mark_duration("die", 0.72)

    revive_tracks = {
        "Pelvis": ((0.0, -12.0), (0.22, -8.0), (0.42, 2.2), (0.62, -0.8), (0.88, 0.0)),
        "Torso": ((0.0, 16.0), (0.22, 10.0), (0.42, -3.4), (0.62, 1.2), (0.88, 0.0)),
        "Head": ((0.0, -13.0), (0.24, -8.0), (0.42, 2.8), (0.64, -0.8), (0.88, 0.0)),
        "NearArm": ((0.0, 18.0), (0.24, 11.0), (0.42, -3.6), (0.64, 1.0), (0.88, 0.0)),
        "FarArm": ((0.0, -16.0), (0.24, -10.0), (0.42, 3.2), (0.64, -0.9), (0.88, 0.0)),
        "NearLeg": ((0.0, -12.0), (0.24, -7.0), (0.42, 2.4), (0.64, -0.7), (0.88, 0.0)),
        "NearShinFoot": ((0.0, 17.0), (0.24, 10.0), (0.42, -3.2), (0.64, 0.9), (0.88, 0.0)),
        "FarLeg": ((0.0, 11.0), (0.24, 6.5), (0.42, -2.2), (0.64, 0.6), (0.88, 0.0)),
        "FarShinFoot": ((0.0, -15.0), (0.24, -9.0), (0.42, 2.9), (0.64, -0.8), (0.88, 0.0)),
        "CloakFarTail": ((0.0, -20.0), (0.28, -12.0), (0.46, 4.0), (0.68, -1.1), (0.88, 0.0)),
        "CloakNearTail": ((0.0, 18.0), (0.30, 11.0), (0.48, -3.6), (0.70, 1.0), (0.88, 0.0)),
    }
    for bone, frames in revive_tracks.items():
        rotate("revive", bone, frames)
    a.mark_duration("revive", 0.88)


def build_animations(rig: Rig) -> dict[str, dict[str, Any]]:
    ordered = topo_bones(rig)
    root = next(bone.name for bone in ordered if not bone.parent)
    animations = AnimationSet(bone.name for bone in ordered)
    if rig.key == "scale_beetle":
        profile_scale_beetle(animations)
    elif rig.key == "origin_fogmog":
        profile_origin_fogmog(animations)
    elif rig.key == "bowlbug_progenitor":
        profile_bowlbug(animations)
    elif rig.key.startswith("soul_roe_"):
        profile_soul_roe(animations)
    elif rig.key == "soul_roes":
        profile_soul_roes(animations)
    elif rig.key == "the_legacy":
        profile_legacy(animations)
    elif rig.key == "thief_raider":
        profile_thief(animations)
    else:
        raise ValueError(f"no animation profile for {rig.key}")
    return animations.finish(root)


def build_spine_json(rig: Rig, regions: Sequence[PackedRegion]) -> dict[str, Any]:
    ordered_bones = topo_bones(rig)
    bone_map = {bone.name: bone for bone in rig.bones}
    json_bones: list[dict[str, Any]] = []
    for bone in ordered_bones:
        parent = bone_map.get(bone.parent)
        if parent is None:
            x, y = bone.pivot[0], -bone.pivot[1]
        else:
            x = bone.pivot[0] - parent.pivot[0]
            y = -(bone.pivot[1] - parent.pivot[1])
        entry: dict[str, Any] = {"name": bone.name, "x": _round(x), "y": _round(y)}
        if bone.parent:
            entry["parent"] = bone.parent
        json_bones.append(entry)

    # Setup draw order only: lower Z first (behind), higher Z last (in front).
    ordered_parts = sorted(rig.parts, key=lambda part: (part.z, part.source_index))
    slots = [{"name": part.name, "bone": part.bone, "attachment": part.name}
             for part in ordered_parts]
    attachments: dict[str, dict[str, dict[str, Any]]] = {}
    region_map = {region.part.name: region for region in regions}
    for part in ordered_parts:
        region = region_map[part.name]
        attachments[part.name] = {
            part.name: {
                "x": _round(part.offset[0]),
                "y": _round(-part.offset[1]),
                "width": region.width,
                "height": region.height,
            }
        }

    width, height = rig.canvas
    digest = hashlib.sha256()
    digest.update(rig.key.encode("utf-8"))
    for part in rig.parts:
        digest.update(resolve_resource_path(part.texture_path).read_bytes())
    return {
        "skeleton": {
            "hash": digest.hexdigest()[:20],
            "spine": SPINE_VERSION,
            "x": _round(-width / 2),
            "y": _round(-height / 2),
            "width": width,
            "height": height,
            "images": "./",
            "audio": "",
        },
        "bones": json_bones,
        "slots": slots,
        "skins": [{"name": "default", "attachments": attachments}],
        "animations": build_animations(rig),
    }


def format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return (f"{value:.4f}").rstrip("0").rstrip(".")


def format_vector(value: tuple[float, float]) -> str:
    return f"Vector2({format_number(value[0])}, {format_number(value[1])})"


def write_scene(rig: Rig, skeleton_resource_path: str) -> Path:
    profile = SCENE_PROFILES[rig.key]
    left, top, right, bottom = profile.bounds
    text = f'''[gd_scene load_steps=3 format=3]\n\n[ext_resource type="Script" path="{SPINE_SCRIPT}" id="1_script"]\n[ext_resource type="SpineSkeletonDataResource" path="{skeleton_resource_path}" id="2_spine"]\n\n[node name="{profile.root_name}" type="Node2D"]\nscript = ExtResource("1_script")\nmetadata/_edit_group_ = true\nmetadata/_edit_lock_ = true\n\n[node name="Visuals" type="SpineSprite" parent="."]\nskeleton_data_res = ExtResource("2_spine")\npreview_skin = "default"\npreview_animation = "idle_loop"\npreview_frame = false\npreview_time = 0.0\nunique_name_in_owner = true\nposition = {format_vector(profile.position)}\nscale = Vector2({format_number(profile.scale)}, {format_number(profile.scale)})\nmetadata/_edit_lock_ = true\n\n[node name="Bounds" type="Control" parent="."]\nunique_name_in_owner = true\nlayout_mode = 3\nanchors_preset = 0\noffset_left = {format_number(left)}\noffset_top = {format_number(top)}\noffset_right = {format_number(right)}\noffset_bottom = {format_number(bottom)}\nmouse_filter = 2\n\n[node name="CenterPos" type="Marker2D" parent="."]\nunique_name_in_owner = true\nposition = {format_vector(profile.center)}\n\n[node name="IntentPos" type="Marker2D" parent="."]\nunique_name_in_owner = true\nposition = {format_vector(profile.intent)}\n'''
    SCENE_ROOT.mkdir(parents=True, exist_ok=True)
    path = SCENE_ROOT / profile.scene_name
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def build_rig(rig: Rig, *, write_scenes: bool = True) -> dict[str, Any]:
    output_dir = ASSET_ROOT / rig.key
    output_dir.mkdir(parents=True, exist_ok=True)
    page_path, atlas_text, regions = pack_atlas(rig, output_dir)
    atlas_path = output_dir / f"{rig.key}.atlas"
    atlas_path.write_text(atlas_text, encoding="utf-8", newline="\n")

    spine_json = build_spine_json(rig, regions)
    spjson_path = output_dir / f"{rig.key}.spjson"
    spjson_path.write_text(
        json.dumps(spine_json, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8", newline="\n")

    atlas_resource_path = f"res://animations/monsters/sts2_things/{rig.key}/{rig.key}.atlas"
    spatlas_path = output_dir / f"{rig.key}.spatlas"
    spatlas_path.write_text(json.dumps({
        "source_path": atlas_resource_path,
        "atlas_data": atlas_text,
        "normal_texture_prefix": "n",
        "specular_texture_prefix": "s",
    }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")

    spjson_resource_path = f"res://animations/monsters/sts2_things/{rig.key}/{rig.key}.spjson"
    spatlas_resource_path = f"res://animations/monsters/sts2_things/{rig.key}/{rig.key}.spatlas"
    tres_path = output_dir / f"{rig.key}_skel_data.tres"
    tres_path.write_text(
        f'''[gd_resource type="SpineSkeletonDataResource" load_steps=3 format=3]\n\n[ext_resource type="SpineAtlasResource" path="{spatlas_resource_path}" id="1_atlas"]\n[ext_resource type="SpineSkeletonFileResource" path="{spjson_resource_path}" id="2_json"]\n\n[resource]\natlas_res = ExtResource("1_atlas")\nskeleton_file_res = ExtResource("2_json")\ndefault_mix = 0.05\n''',
        encoding="utf-8", newline="\n")
    tres_resource_path = f"res://animations/monsters/sts2_things/{rig.key}/{rig.key}_skel_data.tres"
    scene_path = write_scene(rig, tres_resource_path) if write_scenes else None
    return {
        "key": rig.key,
        "bones": len(rig.bones),
        "slots": len(rig.parts),
        "atlas_size": list(Image.open(page_path).size),
        "animations": list(spine_json["animations"]),
        "spjson": spjson_path.relative_to(ROOT).as_posix(),
        "spatlas": spatlas_path.relative_to(ROOT).as_posix(),
        "tres": tres_path.relative_to(ROOT).as_posix(),
        "scene": scene_path.relative_to(ROOT).as_posix() if scene_path else None,
    }


def static_verify(result: dict[str, Any]) -> None:
    spjson = json.loads((ROOT / result["spjson"]).read_text(encoding="utf-8"))
    if not str(spjson["skeleton"]["spine"]).startswith("4.2"):
        raise ValueError(f"{result['key']}: wrong Spine version")
    animations = spjson.get("animations", {})
    missing = [name for name in REQUIRED_ANIMATIONS if name not in animations]
    if missing:
        raise ValueError(f"{result['key']}: missing animations {missing}")
    if len(spjson.get("slots", [])) != result["slots"]:
        raise ValueError(f"{result['key']}: slot count changed while writing")
    wrapper = json.loads((ROOT / result["spatlas"]).read_text(encoding="utf-8"))
    if wrapper.get("atlas_data", "") == "" or not wrapper.get("source_path", "").startswith("res://"):
        raise ValueError(f"{result['key']}: invalid .spatlas wrapper")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--rig", action="append", choices=RIG_KEYS,
                        help="build only this rig (repeatable); default builds all nine")
    parser.add_argument("--no-scenes", action="store_true",
                        help="leave creature ABI scenes untouched")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    selected = tuple(args.rig) if args.rig else RIG_KEYS
    rigs = load_rigs(manifest_path, selected)
    results = []
    for key in selected:
        result = build_rig(rigs[key], write_scenes=not args.no_scenes)
        static_verify(result)
        results.append(result)
        print(
            f"SPINE_BUILD key={key} bones={result['bones']} slots={result['slots']} "
            f"atlas={result['atlas_size'][0]}x{result['atlas_size'][1]} "
            f"animations={len(result['animations'])}")
    report_path = ROOT / "source_assets" / "monsters" / "spine_monsters.generated.json"
    report_path.write_text(json.dumps({
        "spine_version": SPINE_VERSION,
        "source_manifest": manifest_path.relative_to(ROOT).as_posix(),
        "rigs": results,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"SPINE_BUILD_OK rigs={len(results)} report={report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # compact CLI failure with the responsible stage
        print(f"SPINE_BUILD_ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
