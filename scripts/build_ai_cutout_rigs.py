#!/usr/bin/env python3
"""Build bind-pose rigs from image-generated, alpha-isolated monster parts.

This is intentionally a separate pipeline from ``build_cutout_rigs.py``.  It
never crops an assembled monster painting.  Every attachment originates from
an approved component in ``ai_cutout_parts`` and is scaled/rotated as a whole.

The generated manifest uses the subset consumed by ``build_spine_monsters.py``
(``canvas``, ``bones`` and ``parts``), while retaining provenance fields for
visual QA.  Output names use an ``ai_`` prefix so the older cutout experiment
is left untouched.

Registered mappings may provide ``local_pivot_xy`` and
``local_child_joint_xy`` in component pixels plus ``bind_pivot_source_xy`` in
assembled-canvas pixels.  Their affine is baked around the local pivot; older
centre/pivot mappings remain byte-compatible.  The approved bind master and
fidelity thresholds are selected per monster by the mapping document's
top-level ``bind_qa`` contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAPPING_DIR = ROOT / "source_assets" / "monsters" / "ai_cutout_parts"
DEFAULT_OUTPUT_ROOT = ROOT / "images" / "monsters" / "ai_rig_parts"
DEFAULT_MANIFEST = (
    ROOT / "source_assets" / "monsters" / "ai_cutout_rigs.generated.json"
)
DEFAULT_QA_REPORT = (
    ROOT / "source_assets" / "monsters" / "ai_cutout_rigs.qa.generated.json"
)
DEFAULT_PREVIEW_DIR = ROOT / "build" / "ai_cutout_rig_previews"
SOURCE_IMAGE_ROOT = ROOT / "source_assets" / "monsters"
REFERENCE_RIG_MANIFEST = SOURCE_IMAGE_ROOT / "cutout_rigs.generated.json"

OUTPUT_PREFIX = "ai_"
OUTPUT_ALPHA_PADDING = 3
ALPHA_VISIBLE_THRESHOLD = 2
FLOAT_EPSILON = 0.01


class MappingError(ValueError):
    """Raised when a semantic mapping cannot be converted deterministically."""


@dataclass(frozen=True)
class BindQaThresholds:
    """Hard limits for comparing a rebuilt bind pose with its approved master."""

    alpha_iou_min: float
    alpha_area_ratio_min: float
    alpha_area_ratio_max: float
    centroid_delta_max_px: float
    reference_path: Path | None = None

    def as_dict(self) -> dict[str, float]:
        return {
            "alpha_iou_min": self.alpha_iou_min,
            "alpha_area_ratio_min": self.alpha_area_ratio_min,
            "alpha_area_ratio_max": self.alpha_area_ratio_max,
            "centroid_delta_max_px": self.centroid_delta_max_px,
        }


# Monsters opt into the hard bind gate independently.  Mapping documents may
# override these values with a top-level ``bind_qa`` object.
DEFAULT_BIND_QA_THRESHOLDS: dict[str, BindQaThresholds] = {
    "thief_raider": BindQaThresholds(
        0.93,
        0.97,
        1.03,
        2.0,
        SOURCE_IMAGE_ROOT / "thief_raider.png",
    ),
}


@dataclass(frozen=True)
class MappingDocument:
    path: Path
    raw: dict[str, Any] | list[Any]
    records: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ExpandedPart:
    monster: str
    semantic: str
    bone: str
    parent_bone: str
    component_path: Path
    component_resource: str
    pivot_source: tuple[float, float]
    center_source: tuple[float, float]
    registration_source: tuple[float, float]
    local_pivot: tuple[float, float] | None
    local_child_joint: tuple[float, float] | None
    uses_local_registration: bool
    rotation_deg: float
    scale_xy: tuple[float, float]
    z: int
    mapping_path: Path
    mapping_entry_index: int
    instance_index: int | None
    component: str
    notes: str
    order: int


@dataclass(frozen=True)
class BoneCandidate:
    name: str
    parent: str
    pivot_source: tuple[float, float]
    semantic: str
    order: int


@dataclass(frozen=True)
class CanonicalBone:
    name: str
    parent: str
    pivot_source: tuple[float, float]
    pivot_centered: tuple[float, float]
    source_semantic: str
    order: int


@dataclass
class TransformResult:
    image: Image.Image
    source_size: tuple[int, int]
    output_size: tuple[int, int]
    alpha_bbox: tuple[int, int, int, int]
    opaque_pixels: int
    local_pivot: tuple[float, float]
    registration_output: tuple[float, float]
    child_joint_offset: tuple[float, float] | None
    child_joint_output: tuple[float, float] | None
    sha256: str = ""


@dataclass
class MonsterBuild:
    key: str
    source_image: Path
    canvas: tuple[int, int]
    parts: list[ExpandedPart]
    bones: list[CanonicalBone]
    manifest_parts: list[dict[str, Any]] = field(default_factory=list)
    preview_parts: list[tuple[int, int, ExpandedPart, Path]] = field(default_factory=list)
    notices: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    part_qa: list[dict[str, Any]] = field(default_factory=list)
    bind_qa: dict[str, Any] = field(default_factory=dict)


def _as_pair(value: Any, label: str) -> tuple[float, float]:
    if isinstance(value, (int, float)):
        number = float(value)
        return number, number
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise MappingError(f"{label} must contain exactly two numbers")
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError) as exc:
        raise MappingError(f"{label} must contain exactly two numbers") from exc


def _first(mapping: dict[str, Any], names: Sequence[str], default: Any = None) -> Any:
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return default


def _safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_").lower()
    token = re.sub(r"_+", "_", token)
    if not token:
        raise MappingError(f"semantic name does not contain a filename-safe token: {value!r}")
    if token[0].isdigit():
        token = f"part_{token}"
    return token


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _resource_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(ROOT)
    except ValueError as exc:
        raise MappingError(f"component is outside the project root: {resolved}") from exc
    return f"res://{relative.as_posix()}"


def _resolve_project_path(value: str, mapping_path: Path) -> Path:
    if value.startswith("res://"):
        return (ROOT / value.removeprefix("res://")).resolve()
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve()
    project_relative = (ROOT / candidate).resolve()
    if project_relative.exists():
        return project_relative
    return (mapping_path.parent / candidate).resolve()


def _records_from_document(raw: Any, path: Path) -> list[dict[str, Any]]:
    """Accept the current ``entries`` schema plus compact ``items`` variants."""

    if isinstance(raw, list):
        records = raw
    elif isinstance(raw, dict):
        direct = _first(raw, ("entries", "items"))
        if direct is not None:
            if not isinstance(direct, list):
                raise MappingError(f"{path}: entries/items must be a list")
            records = direct
        elif isinstance(raw.get("monsters"), dict):
            records = []
            for monster, group in raw["monsters"].items():
                if isinstance(group, list):
                    values = group
                elif isinstance(group, dict):
                    values = _first(group, ("entries", "items", "parts"), [])
                else:
                    raise MappingError(f"{path}: monsters.{monster} is not a mapping/list")
                if not isinstance(values, list):
                    raise MappingError(
                        f"{path}: monsters.{monster}.entries/items/parts must be a list"
                    )
                for value in values:
                    if not isinstance(value, dict):
                        raise MappingError(f"{path}: monster item is not an object")
                    record = dict(value)
                    record.setdefault("monster", str(monster))
                    records.append(record)
        else:
            raise MappingError(
                f"{path}: expected entries, items, monsters, or a root list"
            )
    else:
        raise MappingError(f"{path}: mapping root must be an object or list")

    converted: list[dict[str, Any]] = []
    for index, value in enumerate(records):
        if not isinstance(value, dict):
            raise MappingError(f"{path}: mapping record {index} is not an object")
        converted.append(dict(value))
    return converted


def load_mapping_documents(paths: Sequence[Path]) -> list[MappingDocument]:
    documents: list[MappingDocument] = []
    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        records = _records_from_document(raw, path)
        documents.append(MappingDocument(path.resolve(), raw, tuple(records)))
    return documents


def _bind_qa_thresholds_from_value(
    value: Any,
    label: str,
    mapping_path: Path,
    base: BindQaThresholds | None = None,
) -> BindQaThresholds:
    if not isinstance(value, dict):
        raise MappingError(f"{label} must be an object")
    defaults = base or BindQaThresholds(0.0, 0.0, 1_000_000.0, 1_000_000.0)
    reference_value = _first(
        value, ("reference_path", "reference", "approved_master"))
    if reference_value is None:
        reference_path = defaults.reference_path
    elif not isinstance(reference_value, str) or not reference_value.strip():
        raise MappingError(f"{label}.reference_path must be a non-empty path")
    else:
        reference_path = _resolve_project_path(reference_value, mapping_path)
        if not reference_path.is_file():
            raise FileNotFoundError(reference_path)
    try:
        thresholds = BindQaThresholds(
            float(value.get("alpha_iou_min", defaults.alpha_iou_min)),
            float(value.get(
                "alpha_area_ratio_min", defaults.alpha_area_ratio_min)),
            float(value.get(
                "alpha_area_ratio_max", defaults.alpha_area_ratio_max)),
            float(value.get(
                "centroid_delta_max_px", defaults.centroid_delta_max_px)),
            reference_path,
        )
    except (TypeError, ValueError) as exc:
        raise MappingError(f"{label} values must be numeric") from exc
    if not 0.0 <= thresholds.alpha_iou_min <= 1.0:
        raise MappingError(f"{label}.alpha_iou_min must be within [0, 1]")
    if thresholds.alpha_area_ratio_min < 0.0:
        raise MappingError(f"{label}.alpha_area_ratio_min must be non-negative")
    if thresholds.alpha_area_ratio_max < thresholds.alpha_area_ratio_min:
        raise MappingError(
            f"{label}.alpha_area_ratio_max must be >= alpha_area_ratio_min")
    if thresholds.centroid_delta_max_px < 0.0:
        raise MappingError(f"{label}.centroid_delta_max_px must be non-negative")
    return thresholds


def load_bind_qa_thresholds(
    documents: Sequence[MappingDocument],
) -> dict[str, BindQaThresholds]:
    """Merge built-in gates with optional top-level per-monster overrides.

    Example mapping fragment::

        "bind_qa": {
          "thief_raider": {
            "reference_path": "source_assets/monsters/thief_raider_v5/approved_master.png",
            "alpha_iou_min": 0.93,
            "alpha_area_ratio_min": 0.97,
            "alpha_area_ratio_max": 1.03,
            "centroid_delta_max_px": 2.0
          }
        }
    """

    result = dict(DEFAULT_BIND_QA_THRESHOLDS)
    for document in documents:
        if not isinstance(document.raw, dict) or "bind_qa" not in document.raw:
            continue
        raw = document.raw["bind_qa"]
        if not isinstance(raw, dict):
            raise MappingError(f"{document.path}: bind_qa must be an object")
        for monster, value in raw.items():
            key = str(monster).strip()
            if not key:
                raise MappingError(f"{document.path}: bind_qa monster key is empty")
            result[key] = _bind_qa_thresholds_from_value(
                value,
                f"{document.path}: bind_qa.{key}",
                document.path,
                result.get(key),
            )
    return result


def discover_mapping_paths(mapping_dir: Path, explicit: Sequence[Path]) -> list[Path]:
    if explicit:
        paths = [path.resolve() for path in explicit]
    else:
        paths = sorted(mapping_dir.resolve().glob("mapping_*.json"))
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing[0])
    if not paths:
        raise FileNotFoundError(f"no mapping_*.json files under {mapping_dir}")
    return paths


def _expand_record(
    record: dict[str, Any],
    *,
    mapping_path: Path,
    entry_index: int,
    first_order: int,
) -> list[ExpandedPart]:
    monster = str(_first(record, ("monster", "rig", "key"), "")).strip()
    if not monster:
        raise MappingError(f"{mapping_path}: entry {entry_index} is missing monster")

    component_value = _first(record, ("component_path", "texture", "path"))
    if not isinstance(component_value, str) or not component_value:
        raise MappingError(
            f"{mapping_path}: entry {entry_index} is missing component_path"
        )
    component_path = _resolve_project_path(component_value, mapping_path)
    if not component_path.is_file():
        raise FileNotFoundError(component_path)
    if not component_path.is_relative_to(DEFAULT_MAPPING_DIR.resolve()):
        raise MappingError(
            f"{mapping_path}: entry {entry_index} references {component_path}, "
            "which is outside ai_cutout_parts; assembled-image crops are not accepted"
        )
    component = str(_first(record, ("component", "component_name"), component_path.stem))

    raw_instances = _first(record, ("instances", "copies"), [])
    if raw_instances is None:
        raw_instances = []
    if not isinstance(raw_instances, list):
        raise MappingError(
            f"{mapping_path}: entry {entry_index}.instances/copies must be a list"
        )
    values: list[tuple[dict[str, Any], int | None]]
    if raw_instances:
        values = []
        for instance_index, instance in enumerate(raw_instances):
            if not isinstance(instance, dict):
                raise MappingError(
                    f"{mapping_path}: entry {entry_index} instance {instance_index} "
                    "is not an object"
                )
            merged = dict(record)
            merged.update(instance)
            values.append((merged, instance_index))
    else:
        values = [(record, None)]

    expanded: list[ExpandedPart] = []
    for local_order, (value, instance_index) in enumerate(values):
        suffix = (
            f"entry {entry_index}"
            if instance_index is None
            else f"entry {entry_index} instance {instance_index}"
        )
        semantic = str(_first(value, ("semantic", "name"), "")).strip()
        bone = str(_first(value, ("bone", "bone_name"), "")).strip()
        parent = str(_first(value, ("parent_bone", "parent"), "")).strip()
        if not semantic or not bone:
            raise MappingError(f"{mapping_path}: {suffix} needs semantic and bone")
        if bone != "Root" and not parent:
            raise MappingError(f"{mapping_path}: {suffix} needs parent_bone")

        bind_pivot_value = _first(value, ("bind_pivot_source_xy",))
        pivot_value = bind_pivot_value
        if pivot_value is None:
            pivot_value = _first(
                value,
                ("pivot_source_xy", "suggested_pivot_source_xy", "pivot"),
            )
        center_value = _first(
            value,
            ("center_source_xy", "suggested_center_source_xy", "center"),
        )
        pivot = _as_pair(pivot_value, f"{mapping_path}: {suffix}.pivot")
        local_pivot_value = _first(value, ("local_pivot_xy",))
        local_child_joint_value = _first(value, ("local_child_joint_xy",))
        uses_local_registration = any(candidate is not None for candidate in (
            bind_pivot_value, local_pivot_value, local_child_joint_value,
        ))
        if center_value is None:
            if not uses_local_registration:
                raise MappingError(f"{mapping_path}: {suffix} is missing center")
            # In the registered schema the local pivot, rather than the crop's
            # geometric centre, is placed at the bind pivot.
            center = pivot
        else:
            center = _as_pair(center_value, f"{mapping_path}: {suffix}.center")
        local_pivot = (
            None if local_pivot_value is None
            else _as_pair(local_pivot_value, f"{mapping_path}: {suffix}.local_pivot_xy")
        )
        local_child_joint = (
            None if local_child_joint_value is None
            else _as_pair(
                local_child_joint_value,
                f"{mapping_path}: {suffix}.local_child_joint_xy",
            )
        )
        registration_source = pivot if uses_local_registration else center
        scale = _as_pair(
            _first(value, ("scale_xy", "scale"), [1.0, 1.0]),
            f"{mapping_path}: {suffix}.scale",
        )
        if abs(scale[0]) <= 1e-8 or abs(scale[1]) <= 1e-8:
            raise MappingError(f"{mapping_path}: {suffix}.scale must be non-zero")
        rotation = float(_first(value, ("rotation_deg", "rotation"), 0.0))
        z = int(_first(value, ("z", "draw_order"), 0))
        expanded.append(ExpandedPart(
            monster=monster,
            semantic=semantic,
            bone=bone,
            parent_bone=parent,
            component_path=component_path,
            component_resource=_resource_path(component_path),
            pivot_source=pivot,
            center_source=center,
            registration_source=registration_source,
            local_pivot=local_pivot,
            local_child_joint=local_child_joint,
            uses_local_registration=uses_local_registration,
            rotation_deg=rotation,
            scale_xy=scale,
            z=z,
            mapping_path=mapping_path,
            mapping_entry_index=entry_index,
            instance_index=instance_index,
            component=component,
            notes=str(record.get("notes", "")),
            order=first_order + local_order,
        ))
    return expanded


def expand_documents(documents: Sequence[MappingDocument]) -> list[ExpandedPart]:
    parts: list[ExpandedPart] = []
    order = 0
    for document in documents:
        for entry_index, record in enumerate(document.records):
            expanded = _expand_record(
                record,
                mapping_path=document.path,
                entry_index=entry_index,
                first_order=order,
            )
            parts.extend(expanded)
            order += len(expanded)
    return parts


def resolve_source_image(monster: str) -> Path:
    path = SOURCE_IMAGE_ROOT / f"{monster}.png"
    if not path.is_file():
        raise FileNotFoundError(
            f"source image for '{monster}' was not found at {path}; "
            "the canvas cannot be inferred safely"
        )
    return path


def _centered(
    source_xy: tuple[float, float], canvas: tuple[int, int]
) -> tuple[float, float]:
    return source_xy[0] - canvas[0] / 2.0, source_xy[1] - canvas[1] / 2.0


def _different_pair(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1])) > FLOAT_EPSILON


def canonicalize_bones(
    monster: str,
    canvas: tuple[int, int],
    parts: Sequence[ExpandedPart],
    reference_bones: dict[str, tuple[str, tuple[float, float]]],
) -> tuple[list[CanonicalBone], list[dict[str, Any]], list[dict[str, Any]]]:
    """Use the first authored driver as a bone's setup pivot.

    Decorations and seam covers often reuse a shell bone but carry their own
    placement pivot in the mapping.  Their candidate pivot is deliberately not
    allowed to redefine that already-authored bone; attachments instead use
    their desired center relative to the canonical setup pivot.
    """

    root_centered = reference_bones.get("Root", ("", (0.0, 0.0)))[1]
    root_source = (
        root_centered[0] + canvas[0] / 2.0,
        root_centered[1] + canvas[1] / 2.0,
    )
    by_name: dict[str, CanonicalBone] = {
        "Root": CanonicalBone("Root", "", root_source, root_centered, "", -1)
    }
    notices: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for part in parts:
        candidate = CanonicalBone(
            part.bone,
            "" if part.bone == "Root" else part.parent_bone,
            part.pivot_source,
            _centered(part.pivot_source, canvas),
            part.semantic,
            part.order,
        )
        existing = by_name.get(part.bone)
        if existing is None:
            by_name[part.bone] = candidate
            continue
        if existing.parent != candidate.parent:
            errors.append({
                "code": "bone_parent_conflict",
                "bone": part.bone,
                "canonical_parent": existing.parent,
                "candidate_parent": candidate.parent,
                "canonical_semantic": existing.source_semantic,
                "candidate_semantic": part.semantic,
            })
        if _different_pair(existing.pivot_source, candidate.pivot_source):
            notices.append({
                "code": "attachment_pivot_does_not_redefine_shared_bone",
                "bone": part.bone,
                "canonical_pivot_source_xy": list(existing.pivot_source),
                "ignored_candidate_pivot_source_xy": list(candidate.pivot_source),
                "canonical_semantic": existing.source_semantic,
                "attachment_semantic": part.semantic,
            })

    referenced_parents = {bone.parent for bone in by_name.values() if bone.parent}
    # Some semantic maps name an attachment-free control bone (for example
    # HeartAnchor or a cell-cluster controller) only as the parent of visible
    # bones.  Synthesize that control at the mean of its direct children.  The
    # decision is recorded rather than silently turning it into a typo fix.
    for parent in sorted(referenced_parents - by_name.keys()):
        children = [bone for bone in by_name.values() if bone.parent == parent]
        if not children:
            errors.append({"code": "missing_parent_bone", "bone": parent})
            continue
        reference = reference_bones.get(parent)
        if reference is not None:
            control_parent, pivot_centered = reference
            pivot_source = (
                pivot_centered[0] + canvas[0] / 2.0,
                pivot_centered[1] + canvas[1] / 2.0,
            )
            control_parent = control_parent or "Root"
            notice_code = "reused_reference_attachment_free_control_bone"
        else:
            pivot_source = (
                sum(bone.pivot_source[0] for bone in children) / len(children),
                sum(bone.pivot_source[1] for bone in children) / len(children),
            )
            pivot_centered = _centered(pivot_source, canvas)
            control_parent = "Root"
            notice_code = "synthesized_attachment_free_control_bone"
        order = min(bone.order for bone in children) - 1
        by_name[parent] = CanonicalBone(
            parent,
            control_parent,
            pivot_source,
            pivot_centered,
            "<synthesized-control-bone>",
            order,
        )
        notices.append({
            "code": notice_code,
            "bone": parent,
            "parent": control_parent,
            "pivot_source_xy": [_round(value) for value in pivot_source],
            "direct_children": [bone.name for bone in children],
        })

    # Parent-first deterministic ordering, while retaining mapping order among siblings.
    ordered: list[CanonicalBone] = []
    visiting: set[str] = set()
    emitted: set[str] = set()

    def emit(name: str) -> None:
        if name in emitted:
            return
        if name in visiting:
            errors.append({"code": "bone_cycle", "bone": name})
            return
        bone = by_name.get(name)
        if bone is None:
            return
        visiting.add(name)
        if bone.parent:
            emit(bone.parent)
        visiting.remove(name)
        if name not in emitted:
            emitted.add(name)
            ordered.append(bone)

    for bone in sorted(by_name.values(), key=lambda item: (item.order, item.name)):
        emit(bone.name)
    return ordered, notices, errors


def load_reference_bones(
    monster: str, canvas: tuple[int, int]
) -> dict[str, tuple[str, tuple[float, float]]]:
    """Load setup-only anchors from the previous manifest when available.

    Visible AI attachments always use the new semantic mapping.  Reusing Root
    and attachment-free controller pivots keeps existing animation profiles
    rotating/scaling around the same anatomical anchor.
    """

    if not REFERENCE_RIG_MANIFEST.is_file():
        return {}
    raw = json.loads(REFERENCE_RIG_MANIFEST.read_text(encoding="utf-8"))
    rig = raw.get(monster) if isinstance(raw, dict) else None
    if not isinstance(rig, dict) or list(rig.get("canvas", [])) != list(canvas):
        return {}
    result: dict[str, tuple[str, tuple[float, float]]] = {}
    for value in rig.get("bones", []):
        if not isinstance(value, dict) or not value.get("name"):
            continue
        result[str(value["name"])] = (
            str(value.get("parent", "")),
            _as_pair(value.get("pivot"), f"reference bone {value.get('name')}.pivot"),
        )
    return result


def _center_alpha_about_registration(
    image: Image.Image,
    registration: tuple[float, float],
    padding: int,
) -> Image.Image:
    """Crop alpha while keeping ``registration`` at the exact image center."""

    rgba = image.convert("RGBA")
    alpha = np.asarray(rgba.getchannel("A"))
    ys, xs = np.nonzero(alpha >= ALPHA_VISIBLE_THRESHOLD)
    if len(xs) == 0:
        raise MappingError("component has no visible alpha pixels")
    left, right = int(xs.min()), int(xs.max()) + 1
    top, bottom = int(ys.min()), int(ys.max()) + 1
    reg_x, reg_y = registration
    half_width = int(math.ceil(max(reg_x - left, right - reg_x))) + padding
    half_height = int(math.ceil(max(reg_y - top, bottom - reg_y))) + padding
    width = max(2, half_width * 2)
    height = max(2, half_height * 2)
    output = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    paste_x = int(round(width / 2.0 - reg_x))
    paste_y = int(round(height / 2.0 - reg_y))
    output.alpha_composite(rgba, (paste_x, paste_y))
    return output


def _premultiply(image: Image.Image) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
    alpha = rgba[:, :, 3:4] / 255.0
    rgba[:, :, :3] *= alpha
    return Image.fromarray(np.clip(np.rint(rgba), 0, 255).astype(np.uint8), "RGBA")


def _unpremultiply(image: Image.Image) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
    alpha = rgba[:, :, 3]
    visible = alpha > 0.5
    for channel in range(3):
        values = rgba[:, :, channel]
        values[visible] = values[visible] * 255.0 / alpha[visible]
        values[~visible] = 0.0
    rgba[~visible, 3] = 0.0
    return Image.fromarray(np.clip(np.rint(rgba), 0, 255).astype(np.uint8), "RGBA")


def transform_component(part: ExpandedPart) -> TransformResult:
    source = Image.open(part.component_path).convert("RGBA")
    source_size = source.size
    if source.getchannel("A").getbbox() is None:
        raise MappingError(f"empty component: {part.component_path}")

    # Registered mappings author the actual joint in component-local pixels.
    # Legacy mappings fall back to the crop's geometric centre, reproducing the
    # v1 output exactly.  The registration is recentered before every affine
    # operation so flips, scaling and rotation all happen around the joint.
    local_pivot = part.local_pivot or (source.width / 2.0, source.height / 2.0)
    if not (-source.width <= local_pivot[0] <= source.width * 2.0
            and -source.height <= local_pivot[1] <= source.height * 2.0):
        raise MappingError(
            f"local pivot is implausibly far outside component: {part.component_path}")
    working = _center_alpha_about_registration(
        source,
        local_pivot,
        OUTPUT_ALPHA_PADDING,
    )
    working = _premultiply(working)

    scale_x, scale_y = part.scale_xy
    # Negative scale is an explicitly authored mirror used by paired limbs.
    # The flip is baked into the texture because the downstream manifest has
    # no setup-scale field on attachments.
    if scale_x < 0:
        working = working.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if scale_y < 0:
        working = working.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    pre_scale_size = working.size
    target_size = (
        max(2, int(round(working.width * abs(scale_x)))),
        max(2, int(round(working.height * abs(scale_y)))),
    )
    if target_size != working.size:
        working = working.resize(target_size, Image.Resampling.LANCZOS)

    # Track the optional child joint with the exact rasterized scale.  This is
    # emitted as rigging metadata and lets a later skeleton stage place the next
    # bone at the transformed endpoint without re-deriving the affine.
    child_joint_offset: tuple[float, float] | None = None
    if part.local_child_joint is not None:
        child_dx = part.local_child_joint[0] - local_pivot[0]
        child_dy = part.local_child_joint[1] - local_pivot[1]
        effective_scale_x = target_size[0] / pre_scale_size[0]
        effective_scale_y = target_size[1] / pre_scale_size[1]
        child_dx *= effective_scale_x * (-1.0 if scale_x < 0.0 else 1.0)
        child_dy *= effective_scale_y * (-1.0 if scale_y < 0.0 else 1.0)
        angle = math.radians(part.rotation_deg)
        cosine, sine = math.cos(angle), math.sin(angle)
        child_joint_offset = (
            cosine * child_dx - sine * child_dy,
            sine * child_dx + cosine * child_dy,
        )

    # Mapping coordinates are x-right/y-down.  Positive authored angles are
    # therefore clockwise on screen; PIL's positive angle is counter-clockwise.
    if abs(part.rotation_deg) > 1e-8:
        working = working.rotate(
            -part.rotation_deg,
            resample=Image.Resampling.BICUBIC,
            expand=True,
        )

    working = _unpremultiply(working)
    working = _center_alpha_about_registration(
        working,
        (working.width / 2.0, working.height / 2.0),
        OUTPUT_ALPHA_PADDING,
    )
    registration_output = (working.width / 2.0, working.height / 2.0)
    child_joint_output = (
        None if child_joint_offset is None
        else (
            registration_output[0] + child_joint_offset[0],
            registration_output[1] + child_joint_offset[1],
        )
    )
    alpha = np.asarray(working.getchannel("A"))
    visible = alpha >= ALPHA_VISIBLE_THRESHOLD
    ys, xs = np.nonzero(visible)
    alpha_bbox = (
        int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    )
    return TransformResult(
        image=working,
        source_size=source_size,
        output_size=working.size,
        alpha_bbox=alpha_bbox,
        opaque_pixels=int(np.count_nonzero(alpha >= 128)),
        local_pivot=local_pivot,
        registration_output=registration_output,
        child_joint_offset=child_joint_offset,
        child_joint_output=child_joint_output,
    )


def _round(value: float) -> float:
    rounded = round(float(value), 4)
    return 0.0 if rounded == -0.0 else rounded


def _unique_output_names(parts: Sequence[ExpandedPart]) -> dict[int, str]:
    base_counts = Counter(_safe_token(part.semantic) for part in parts)
    emitted: Counter[str] = Counter()
    names: dict[int, str] = {}
    for part in parts:
        base = _safe_token(part.semantic)
        emitted[base] += 1
        suffix = f"_{emitted[base]:02d}" if base_counts[base] > 1 else ""
        names[part.order] = f"{OUTPUT_PREFIX}{base}{suffix}"
    return names


def _alpha_boundary_clear(result: TransformResult) -> bool:
    alpha = np.asarray(result.image.getchannel("A"))
    return bool(
        np.all(alpha[0, :] < ALPHA_VISIBLE_THRESHOLD)
        and np.all(alpha[-1, :] < ALPHA_VISIBLE_THRESHOLD)
        and np.all(alpha[:, 0] < ALPHA_VISIBLE_THRESHOLD)
        and np.all(alpha[:, -1] < ALPHA_VISIBLE_THRESHOLD)
    )


def build_monster(
    key: str,
    parts: Sequence[ExpandedPart],
    output_root: Path,
    bind_reference: Path | None = None,
) -> MonsterBuild:
    source_image = (bind_reference or resolve_source_image(key)).resolve()
    if not source_image.is_file():
        raise FileNotFoundError(source_image)
    canvas = Image.open(source_image).size
    ordered_parts = sorted(parts, key=lambda item: item.order)
    reference_bones = load_reference_bones(key, canvas)
    bones, notices, errors = canonicalize_bones(
        key, canvas, ordered_parts, reference_bones
    )
    build = MonsterBuild(
        key=key,
        source_image=source_image,
        canvas=canvas,
        parts=list(ordered_parts),
        bones=bones,
        notices=notices,
        errors=errors,
    )
    if errors:
        return build

    bone_map = {bone.name: bone for bone in bones}
    names = _unique_output_names(ordered_parts)
    out_dir = output_root / key
    out_dir.mkdir(parents=True, exist_ok=True)

    for part in ordered_parts:
        bone = bone_map[part.bone]
        output_name = names[part.order]
        output_path = out_dir / f"{output_name}.png"
        result = transform_component(part)
        result.image.save(output_path, optimize=True)
        result.sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()

        centered_registration = _centered(part.registration_source, canvas)
        sprite_offset = (
            centered_registration[0] - bone.pivot_centered[0],
            centered_registration[1] - bone.pivot_centered[1],
        )
        child_joint_source = (
            None if result.child_joint_offset is None
            else (
                part.registration_source[0] + result.child_joint_offset[0],
                part.registration_source[1] + result.child_joint_offset[1],
            )
        )
        texture = _resource_path(output_path)
        manifest_part = {
            "name": output_name,
            "bone": part.bone,
            "texture": texture,
            "pivot": [_round(v) for v in bone.pivot_centered],
            "sprite_offset": [_round(v) for v in sprite_offset],
            "z": part.z,
            "semantic": part.semantic,
            "source_component": part.component,
            "source_component_path": part.component_resource,
            "source_center_xy": [_round(v) for v in part.center_source],
            "source_pivot_xy": [_round(v) for v in part.pivot_source],
            "bind_pivot_source_xy": [_round(v) for v in part.pivot_source],
            "attachment_registration_source_xy": [
                _round(v) for v in part.registration_source
            ],
            "attachment_registration_output_xy": [
                _round(v) for v in result.registration_output
            ],
            "local_pivot_xy": (
                None if part.local_pivot is None
                else [_round(v) for v in part.local_pivot]
            ),
            "local_child_joint_xy": (
                None if part.local_child_joint is None
                else [_round(v) for v in part.local_child_joint]
            ),
            "transformed_child_joint_offset_xy": (
                None if result.child_joint_offset is None
                else [_round(v) for v in result.child_joint_offset]
            ),
            "transformed_child_joint_source_xy": (
                None if child_joint_source is None
                else [_round(v) for v in child_joint_source]
            ),
            "registration_mode": (
                "local_pivot" if part.uses_local_registration
                else "legacy_geometric_center"
            ),
            "baked_rotation_deg_clockwise": _round(part.rotation_deg),
            "baked_scale_xy": [_round(v) for v in part.scale_xy],
            "ai_generated_complete_component": True,
        }
        build.manifest_parts.append(manifest_part)
        build.preview_parts.append((part.z, part.order, part, output_path))

        left = part.registration_source[0] - result.output_size[0] / 2.0
        top = part.registration_source[1] - result.output_size[1] / 2.0
        right = left + result.output_size[0]
        bottom = top + result.output_size[1]
        overflow = {
            "left": max(0.0, -left),
            "top": max(0.0, -top),
            "right": max(0.0, right - canvas[0]),
            "bottom": max(0.0, bottom - canvas[1]),
        }
        if any(value > 1.0 for value in overflow.values()):
            build.warnings.append({
                "code": "attachment_extends_outside_canvas",
                "semantic": part.semantic,
                "overflow_pixels": {name: _round(value) for name, value in overflow.items()},
            })

        boundary_clear = _alpha_boundary_clear(result)
        if not boundary_clear:
            build.errors.append({
                "code": "alpha_touches_output_boundary",
                "semantic": part.semantic,
                "output": _relative(output_path),
            })
        build.part_qa.append({
            "name": output_name,
            "semantic": part.semantic,
            "bone": part.bone,
            "parent_bone": part.parent_bone,
            "z": part.z,
            "source_component": part.component,
            "source_component_path": _relative(part.component_path),
            "output": _relative(output_path),
            "source_size": list(result.source_size),
            "output_size": list(result.output_size),
            "alpha_bbox": list(result.alpha_bbox),
            "opaque_pixels": result.opaque_pixels,
            "alpha_boundary_clear": boundary_clear,
            "center_source_xy": [_round(v) for v in part.center_source],
            "registration_source_xy": [
                _round(v) for v in part.registration_source
            ],
            "registration_output_xy": [
                _round(v) for v in result.registration_output
            ],
            "authored_pivot_source_xy": [_round(v) for v in part.pivot_source],
            "local_pivot_xy": (
                None if part.local_pivot is None
                else [_round(v) for v in part.local_pivot]
            ),
            "local_child_joint_xy": (
                None if part.local_child_joint is None
                else [_round(v) for v in part.local_child_joint]
            ),
            "transformed_child_joint_offset_xy": (
                None if result.child_joint_offset is None
                else [_round(v) for v in result.child_joint_offset]
            ),
            "transformed_child_joint_source_xy": (
                None if child_joint_source is None
                else [_round(v) for v in child_joint_source]
            ),
            "registration_mode": (
                "local_pivot" if part.uses_local_registration
                else "legacy_geometric_center"
            ),
            "canonical_bone_pivot_source_xy": [_round(v) for v in bone.pivot_source],
            "sprite_offset": [_round(v) for v in sprite_offset],
            "rotation_deg_clockwise": _round(part.rotation_deg),
            "scale_xy": [_round(v) for v in part.scale_xy],
            "sha256": result.sha256,
        })
    return build


def _composite_clipped(
    canvas: Image.Image, sprite: Image.Image, left: int, top: int
) -> None:
    right = left + sprite.width
    bottom = top + sprite.height
    dst_left, dst_top = max(0, left), max(0, top)
    dst_right, dst_bottom = min(canvas.width, right), min(canvas.height, bottom)
    if dst_left >= dst_right or dst_top >= dst_bottom:
        return
    src = sprite.crop((
        dst_left - left,
        dst_top - top,
        dst_right - left,
        dst_bottom - top,
    ))
    canvas.alpha_composite(src, (dst_left, dst_top))


def _checkerboard(size: tuple[int, int], cell: int = 24) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size, (41, 43, 48, 255))
    draw = ImageDraw.Draw(image)
    colors = ((41, 43, 48, 255), (54, 57, 63, 255))
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            color = colors[((x // cell) + (y // cell)) & 1]
            draw.rectangle((x, y, min(width, x + cell), min(height, y + cell)), fill=color)
    return image


def _bind_alpha_metrics(
    reference: Image.Image, rebuilt: Image.Image,
) -> dict[str, Any]:
    reference_alpha = np.asarray(reference.convert("RGBA").getchannel("A"))
    rebuilt_alpha = np.asarray(rebuilt.convert("RGBA").getchannel("A"))
    reference_mask = reference_alpha >= ALPHA_VISIBLE_THRESHOLD
    rebuilt_mask = rebuilt_alpha >= ALPHA_VISIBLE_THRESHOLD
    reference_area = int(np.count_nonzero(reference_mask))
    rebuilt_area = int(np.count_nonzero(rebuilt_mask))
    intersection = int(np.count_nonzero(reference_mask & rebuilt_mask))
    union = int(np.count_nonzero(reference_mask | rebuilt_mask))
    alpha_iou = 1.0 if union == 0 else intersection / union
    alpha_area_ratio = (
        1.0 if reference_area == 0 and rebuilt_area == 0
        else (0.0 if reference_area == 0 else rebuilt_area / reference_area)
    )

    def centroid(mask: np.ndarray) -> tuple[float, float] | None:
        ys, xs = np.nonzero(mask)
        if len(xs) == 0:
            return None
        return float(xs.mean()), float(ys.mean())

    reference_centroid = centroid(reference_mask)
    rebuilt_centroid = centroid(rebuilt_mask)
    if reference_centroid is None and rebuilt_centroid is None:
        centroid_delta = 0.0
    elif reference_centroid is None or rebuilt_centroid is None:
        centroid_delta = math.hypot(reference.width, reference.height)
    else:
        centroid_delta = math.hypot(
            rebuilt_centroid[0] - reference_centroid[0],
            rebuilt_centroid[1] - reference_centroid[1],
        )
    return {
        "alpha_threshold": ALPHA_VISIBLE_THRESHOLD,
        "reference_alpha_area_px": reference_area,
        "rebuilt_alpha_area_px": rebuilt_area,
        "alpha_intersection_px": intersection,
        "alpha_union_px": union,
        "alpha_iou": _round(alpha_iou),
        "alpha_area_ratio": _round(alpha_area_ratio),
        "reference_centroid_xy": (
            None if reference_centroid is None
            else [_round(v) for v in reference_centroid]
        ),
        "rebuilt_centroid_xy": (
            None if rebuilt_centroid is None
            else [_round(v) for v in rebuilt_centroid]
        ),
        "centroid_delta_px": _round(centroid_delta),
    }


def _apply_bind_qa_gate(
    build: MonsterBuild,
    reference: Image.Image,
    rebuilt: Image.Image,
    thresholds: BindQaThresholds | None,
) -> None:
    metrics = _bind_alpha_metrics(reference, rebuilt)
    failures: list[dict[str, Any]] = []
    if thresholds is not None:
        checks = (
            (
                "alpha_iou_min",
                float(metrics["alpha_iou"]),
                ">=",
                thresholds.alpha_iou_min,
                float(metrics["alpha_iou"]) >= thresholds.alpha_iou_min,
            ),
            (
                "alpha_area_ratio_min",
                float(metrics["alpha_area_ratio"]),
                ">=",
                thresholds.alpha_area_ratio_min,
                float(metrics["alpha_area_ratio"])
                >= thresholds.alpha_area_ratio_min,
            ),
            (
                "alpha_area_ratio_max",
                float(metrics["alpha_area_ratio"]),
                "<=",
                thresholds.alpha_area_ratio_max,
                float(metrics["alpha_area_ratio"])
                <= thresholds.alpha_area_ratio_max,
            ),
            (
                "centroid_delta_max_px",
                float(metrics["centroid_delta_px"]),
                "<=",
                thresholds.centroid_delta_max_px,
                float(metrics["centroid_delta_px"])
                <= thresholds.centroid_delta_max_px,
            ),
        )
        for name, actual, operator, limit, passed in checks:
            if not passed:
                failures.append({
                    "threshold": name,
                    "actual": _round(actual),
                    "operator": operator,
                    "limit": _round(limit),
                })
    build.bind_qa = {
        "status": (
            "not_configured" if thresholds is None
            else ("fail" if failures else "pass")
        ),
        "reference_path": _relative(build.source_image),
        "thresholds": None if thresholds is None else thresholds.as_dict(),
        "metrics": metrics,
        "failures": failures,
    }
    if failures:
        build.errors.append({
            "code": "bind_pose_fidelity_gate_failed",
            "thresholds": thresholds.as_dict() if thresholds is not None else None,
            "metrics": metrics,
            "failures": failures,
        })


def render_previews(
    build: MonsterBuild,
    preview_dir: Path,
    thresholds: BindQaThresholds | None = None,
) -> dict[str, str]:
    preview_dir.mkdir(parents=True, exist_ok=True)
    composite = Image.new("RGBA", build.canvas, (0, 0, 0, 0))
    for _, _, part, path in sorted(build.preview_parts, key=lambda value: (value[0], value[1])):
        sprite = Image.open(path).convert("RGBA")
        left = int(round(part.registration_source[0] - sprite.width / 2.0))
        top = int(round(part.registration_source[1] - sprite.height / 2.0))
        _composite_clipped(composite, sprite, left, top)

    bind_path = preview_dir / f"{OUTPUT_PREFIX}{build.key}_bind.png"
    composite.save(bind_path, optimize=True)

    overlay = _checkerboard(build.canvas)
    overlay.alpha_composite(composite)
    draw = ImageDraw.Draw(overlay)
    bone_map = {bone.name: bone for bone in build.bones}
    for bone in build.bones:
        x = bone.pivot_source[0]
        y = bone.pivot_source[1]
        if bone.parent and bone.parent in bone_map:
            parent = bone_map[bone.parent]
            draw.line(
                (parent.pivot_source[0], parent.pivot_source[1], x, y),
                fill=(74, 220, 255, 210),
                width=2,
            )
        radius = 4 if bone.name != "Root" else 6
        draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                     fill=(255, 72, 180, 235), outline=(255, 255, 255, 235), width=1)
    bone_path = preview_dir / f"{OUTPUT_PREFIX}{build.key}_bones.png"
    overlay.save(bone_path, optimize=True)

    reference = Image.open(build.source_image).convert("RGBA")
    _apply_bind_qa_gate(build, reference, composite, thresholds)
    rebuilt_bg = _checkerboard(build.canvas)
    rebuilt_bg.alpha_composite(composite)
    gap = 12
    header = 30
    comparison = Image.new(
        "RGBA",
        (build.canvas[0] * 2 + gap, build.canvas[1] + header),
        (24, 25, 29, 255),
    )
    comparison.alpha_composite(reference, (0, header))
    comparison.alpha_composite(rebuilt_bg, (build.canvas[0] + gap, header))
    draw = ImageDraw.Draw(comparison)
    font = ImageFont.load_default()
    draw.text((8, 8), "ORIGINAL REFERENCE", fill=(235, 235, 235, 255), font=font)
    draw.text(
        (build.canvas[0] + gap + 8, 8),
        "AI CUTOUT BIND POSE",
        fill=(235, 235, 235, 255),
        font=font,
    )
    comparison_path = preview_dir / f"{OUTPUT_PREFIX}{build.key}_comparison.png"
    comparison.save(comparison_path, optimize=True)
    return {
        "bind": _relative(bind_path),
        "bones": _relative(bone_path),
        "comparison": _relative(comparison_path),
    }


def build_manifest_entry(build: MonsterBuild) -> dict[str, Any]:
    return {
        "source": _relative(build.source_image),
        "bind_reference": _relative(build.source_image),
        "pipeline": "ai_generated_complete_cutout_v1",
        "canvas": list(build.canvas),
        "bones": [
            {
                "name": bone.name,
                "parent": bone.parent,
                "pivot": [_round(value) for value in bone.pivot_centered],
                "source_pivot_xy": [_round(value) for value in bone.pivot_source],
            }
            for bone in build.bones
        ],
        "parts": build.manifest_parts,
    }


def validate_manifest_subset(manifest: dict[str, Any]) -> list[str]:
    """Mirror the structural contract consumed by build_spine_monsters.py."""

    errors: list[str] = []
    for key, rig in manifest.items():
        if not isinstance(rig.get("canvas"), list) or len(rig["canvas"]) != 2:
            errors.append(f"{key}: invalid canvas")
        bones = rig.get("bones", [])
        parts = rig.get("parts", [])
        names = {bone.get("name") for bone in bones}
        roots = [bone for bone in bones if not bone.get("parent")]
        if len(roots) != 1:
            errors.append(f"{key}: expected one root")
        if len(names) != len(bones):
            errors.append(f"{key}: duplicate bone")
        bone_pivots = {bone["name"]: bone["pivot"] for bone in bones}
        seen_parts: set[str] = set()
        for part in parts:
            if part.get("name") in seen_parts:
                errors.append(f"{key}: duplicate part {part.get('name')}")
            seen_parts.add(str(part.get("name")))
            bone = part.get("bone")
            if bone not in names:
                errors.append(f"{key}: part {part.get('name')} has unknown bone {bone}")
            elif part.get("pivot") != bone_pivots[bone]:
                errors.append(f"{key}: part {part.get('name')} pivot differs from bone")
            texture = str(part.get("texture", ""))
            if not texture.startswith("res://") or not (ROOT / texture[6:]).is_file():
                errors.append(f"{key}: missing texture {texture}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping-dir", type=Path, default=DEFAULT_MAPPING_DIR)
    parser.add_argument(
        "--mapping",
        type=Path,
        action="append",
        default=[],
        help="explicit mapping JSON (repeatable); default scans mapping_*.json",
    )
    parser.add_argument(
        "--monster",
        action="append",
        default=[],
        help="build only this mapped monster (repeatable)",
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--qa-report", type=Path, default=DEFAULT_QA_REPORT)
    parser.add_argument("--preview-dir", type=Path, default=DEFAULT_PREVIEW_DIR)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return an error when the QA report contains warnings",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = discover_mapping_paths(args.mapping_dir, args.mapping)
    documents = load_mapping_documents(paths)
    bind_qa_thresholds = load_bind_qa_thresholds(documents)
    expanded = expand_documents(documents)
    grouped: dict[str, list[ExpandedPart]] = defaultdict(list)
    for part in expanded:
        grouped[part.monster].append(part)

    selected = set(args.monster)
    unknown = selected - grouped.keys()
    if unknown:
        raise MappingError(f"requested monsters are not mapped: {sorted(unknown)}")
    keys = sorted(selected or grouped.keys())

    output_root = args.output_root.resolve()
    preview_dir = args.preview_dir.resolve()
    builds: list[MonsterBuild] = []
    for key in keys:
        bind_contract = bind_qa_thresholds.get(key)
        build = build_monster(
            key,
            grouped[key],
            output_root,
            None if bind_contract is None else bind_contract.reference_path,
        )
        builds.append(build)

    # Render and gate the bind before constructing the manifest.  A failed
    # fidelity gate therefore excludes that monster from shipping output.
    preview_paths: dict[str, dict[str, str]] = {}
    for build in builds:
        if not build.errors and build.preview_parts:
            preview_paths[build.key] = render_previews(
                build,
                preview_dir,
                bind_qa_thresholds.get(build.key),
            )
        print(
            f"AI_RIG key={build.key} parts={len(build.manifest_parts)}/{len(build.parts)} "
            f"bones={len(build.bones)} notices={len(build.notices)} "
            f"warnings={len(build.warnings)} "
            f"errors={len(build.errors)}"
        )

    manifest = {
        build.key: build_manifest_entry(build)
        for build in builds
        if not build.errors and build.manifest_parts
    }
    compatibility_errors = validate_manifest_subset(manifest)
    for message in compatibility_errors:
        key = message.split(":", 1)[0]
        target = next((build for build in builds if build.key == key), None)
        if target is not None:
            target.errors.append({"code": "manifest_compatibility", "message": message})

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    report = {
        "schema_version": 2,
        "pipeline": "ai_generated_complete_cutout_v1",
        "coordinate_contract": {
            "mapping": "top-left origin, x-right, y-down, source pixels",
            "manifest": "canvas-centred origin, x-right, y-down, source pixels",
            "formula": {
                "centered_x": "source_x - canvas_width / 2",
                "centered_y": "source_y - canvas_height / 2",
                "sprite_offset": (
                    "centered_attachment_registration - canonical_bone_pivot"
                ),
            },
            "registration": (
                "local_pivot_xy is component-local; bind_pivot_source_xy places "
                "that registration on the assembled source canvas. Legacy entries "
                "register the crop geometric centre at center_source_xy."
            ),
            "child_joint": (
                "local_child_joint_xy is transformed around local_pivot_xy and "
                "retained as endpoint metadata"
            ),
            "rotation": (
                "rotation_deg is baked clockwise in source/image space around "
                "the attachment registration"
            ),
        },
        "mapping_files": [_relative(path) for path in paths],
        "bind_qa_configuration": {
            key: {
                "reference_path": (
                    None if value.reference_path is None
                    else _relative(value.reference_path)
                ),
                **value.as_dict(),
            }
            for key, value in sorted(bind_qa_thresholds.items())
        },
        "reference_setup_anchors": {
            "manifest": _relative(REFERENCE_RIG_MANIFEST),
            "policy": (
                "reuse only Root and otherwise unmapped attachment-free control "
                "bone pivots; never reuse legacy part textures"
            ),
        },
        "manifest": _relative(args.manifest),
        "output_root": _relative(output_root),
        "monsters": {},
    }
    for build in builds:
        status = "error" if build.errors else ("warning" if build.warnings else "pass")
        report["monsters"][build.key] = {
            "status": status,
            "source_image": _relative(build.source_image),
            "canvas": list(build.canvas),
            "mapped_parts": len(build.parts),
            "written_parts": len(build.manifest_parts),
            "bones": len(build.bones),
            "source_components": dict(sorted(Counter(
                part.component for part in build.parts
            ).items())),
            "warnings": build.warnings,
            "notices": build.notices,
            "errors": build.errors,
            "bind_qa": build.bind_qa,
            "parts": build.part_qa,
            "previews": preview_paths.get(build.key, {}),
        }
    all_warnings = sum(len(build.warnings) for build in builds)
    all_errors = sum(len(build.errors) for build in builds)
    report["summary"] = {
        "monsters": len(builds),
        "parts": sum(len(build.manifest_parts) for build in builds),
        "bones": sum(len(build.bones) for build in builds),
        "warnings": all_warnings,
        "errors": all_errors,
        "status": "error" if all_errors else ("warning" if all_warnings else "pass"),
    }
    args.qa_report.parent.mkdir(parents=True, exist_ok=True)
    args.qa_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(
        f"AI_RIG_REPORT status={report['summary']['status']} "
        f"manifest={_relative(args.manifest)} qa={_relative(args.qa_report)}"
    )
    if all_errors or compatibility_errors:
        return 1
    if args.strict and all_warnings:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"AI_RIG_ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
