#!/usr/bin/env python3
"""Build pixel-linked semantic cutouts from one approved RGBA master.

This tool deliberately does *not* invent visible pixels and does not use
rectangular crops as ownership.  An ownership label map assigns every visible
master pixel to exactly one semantic part.  Each part image is then made from
those exact RGBA pixels.  Optional hand-painted hidden underlaps may be merged
into a part, but are audited separately from the approved visible payload.

Minimal contract (numeric/index label map)::

    {
      "version": 1,
      "label_mode": "index",
      "background": 0,
      "draw_order": ["body", "eye"],
      "parts": [
        {"name": "body", "label": 1, "z": 0},
        {"name": "eye", "label": 2, "z": 10,
         "hidden_underlap": "underlaps/eye.png"}
      ]
    }

Color maps use ``"label_mode": "color"`` and labels such as ``"#ff0000"``
or ``[255, 0, 0, 255]``.  ``parts`` may also be an object keyed by semantic
name.  A hidden-underlap image normally has the same canvas size as the
master.  A cropped image can be placed with ``{"path": "x.png", "origin":
[x, y]}``.

Outputs (under --output-dir):

* ``parts/<semantic>.png`` -- tight RGBA part crops (or full canvases with
  ``--full-canvas-parts``);
* ``linked_cutouts.qa.json`` -- hashes, areas, origins and all audit counts;
* ``recomposed_visible.png`` -- exact visible-payload reconstruction;
* ``recomposed_with_underlaps.png`` -- normal back-to-front bind-pose render;
* ``qa_diagnostics.png`` and ``qa_comparison.png`` -- deterministic QA views.

``--strict`` returns 1 when any hard invariant fails.  Structural/input errors
always return 2.  Non-strict mode still writes the complete diagnostic bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from PIL import Image


REPORT_NAME = "linked_cutouts.qa.json"
VISIBLE_PREVIEW_NAME = "recomposed_visible.png"
FULL_PREVIEW_NAME = "recomposed_with_underlaps.png"
DIAGNOSTIC_NAME = "qa_diagnostics.png"
COMPARISON_NAME = "qa_comparison.png"


class InputError(RuntimeError):
    """The input set is malformed and cannot be audited meaningfully."""


@dataclass(frozen=True)
class LabelToken:
    """Normalized ownership token.

    ``kind`` is ``index``, ``rgb`` or ``rgba``.  Keeping RGB and RGBA distinct
    lets a contract explicitly decide whether label-map alpha participates in
    color identity.
    """

    kind: str
    value: int | tuple[int, ...]

    def display(self) -> str | int:
        if self.kind == "index":
            return int(self.value)
        values = tuple(int(v) for v in self.value)  # type: ignore[arg-type]
        return "#" + "".join(f"{v:02X}" for v in values)


@dataclass
class HiddenSpec:
    path: Path
    origin: tuple[int, int] | None = None


@dataclass
class PartSpec:
    name: str
    tokens: list[LabelToken]
    z: float
    order_hint: int
    filename: str
    allow_empty: bool = False
    hidden: HiddenSpec | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Contract:
    path: Path
    raw: dict[str, Any]
    mode: str
    parts: list[PartSpec]
    background: list[LabelToken]
    draw_order: list[str]
    map_alpha_zero_is_background: bool
    index_channel: int | None


@dataclass
class LabelData:
    path: Path
    pil_mode: str
    rgba: np.ndarray
    indices: np.ndarray | None
    index_invalid_color: np.ndarray


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _array_hash(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    header = f"{contiguous.dtype.str}|{','.join(map(str, contiguous.shape))}|".encode(
        "ascii"
    )
    return _sha256_bytes(header + contiguous.tobytes(order="C"))


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise InputError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InputError(f"contract root must be an object: {path}")
    return value


def _load_rgba(path: Path, what: str) -> np.ndarray:
    try:
        with Image.open(path) as image:
            rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    except FileNotFoundError as exc:
        raise InputError(f"{what} not found: {path}") from exc
    except OSError as exc:
        raise InputError(f"cannot read {what} {path}: {exc}") from exc
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise InputError(f"{what} did not decode as RGBA: {path}")
    return rgba


def _save_png(path: Path, rgba: np.ndarray) -> None:
    if rgba.dtype != np.uint8 or rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("PNG payload must be uint8 RGBA")
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray(np.ascontiguousarray(rgba), mode="RGBA")
    # Explicit settings and no metadata make bytes repeatable for a fixed Pillow
    # encoder version; pixel hashes in the report remain encoder-independent.
    image.save(path, format="PNG", optimize=False, compress_level=9)


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    raise InputError(f"expected boolean, got {value!r}")


def _first(mapping: dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _parse_color(value: Any) -> tuple[int, ...]:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("#"):
            text = text[1:]
        elif text.lower().startswith("0x"):
            text = text[2:]
        text = re.sub(r"[\s,_-]", "", text)
        if len(text) not in {6, 8} or not re.fullmatch(r"[0-9a-fA-F]+", text):
            raise InputError(f"invalid RGB/RGBA label color: {value!r}")
        return tuple(int(text[i : i + 2], 16) for i in range(0, len(text), 2))
    if isinstance(value, dict):
        channels = [value.get("r"), value.get("g"), value.get("b")]
        if any(channel is None for channel in channels):
            raise InputError(f"color object needs r/g/b: {value!r}")
        if "a" in value:
            channels.append(value["a"])
        value = channels
    if isinstance(value, (list, tuple)) and len(value) in {3, 4}:
        try:
            color = tuple(int(channel) for channel in value)
        except (TypeError, ValueError) as exc:
            raise InputError(f"invalid RGB/RGBA label color: {value!r}") from exc
        if any(channel < 0 or channel > 255 for channel in color):
            raise InputError(f"color channel outside 0..255: {value!r}")
        return color
    raise InputError(f"invalid RGB/RGBA label color: {value!r}")


def _parse_token(value: Any, mode: str) -> LabelToken:
    if isinstance(value, dict) and "color" in value:
        value = value["color"]
    elif isinstance(value, dict) and any(key in value for key in ("index", "value", "label")):
        value = _first(value, ("index", "value", "label"))

    if mode == "index":
        if isinstance(value, bool):
            raise InputError(f"boolean is not an index label: {value!r}")
        try:
            index = int(value)
        except (TypeError, ValueError) as exc:
            raise InputError(f"invalid integer label: {value!r}") from exc
        if index < 0 or index > 0xFFFFFFFF:
            raise InputError(f"index label outside 0..4294967295: {index}")
        return LabelToken("index", index)

    color = _parse_color(value)
    return LabelToken("rgba" if len(color) == 4 else "rgb", color)


def _looks_like_color(value: Any) -> bool:
    if isinstance(value, (list, tuple)) and len(value) in {3, 4}:
        return True
    if isinstance(value, dict) and (
        "color" in value or all(key in value for key in ("r", "g", "b"))
    ):
        return True
    if isinstance(value, str):
        text = value.strip().replace("#", "").replace("0x", "")
        return len(re.sub(r"[\s,_-]", "", text)) in {6, 8}
    return False


def _safe_filename(name: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_name).strip("._-")
    if not stem:
        stem = fallback
    if stem.lower().endswith(".png"):
        stem = stem[:-4]
    return stem + ".png"


def _parse_origin(value: Any, context: str) -> tuple[int, int] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = [value.get("x"), value.get("y")]
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise InputError(f"{context} origin must be [x, y]")
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError) as exc:
        raise InputError(f"{context} origin must contain integers") from exc


def _parse_hidden_spec(
    value: Any, contract_dir: Path, context: str, inherited_origin: Any = None
) -> HiddenSpec | None:
    if value in (None, "", False):
        return None
    origin = _parse_origin(inherited_origin, context)
    if isinstance(value, str):
        path_text = value
    elif isinstance(value, dict):
        path_text = _first(value, ("path", "file", "png", "source"))
        if not isinstance(path_text, str) or not path_text.strip():
            raise InputError(f"{context} hidden underlap needs a path")
        local_origin = _first(value, ("origin", "offset", "position"))
        if local_origin is None and ("x" in value or "y" in value):
            local_origin = [value.get("x", 0), value.get("y", 0)]
        if local_origin is not None:
            origin = _parse_origin(local_origin, context)
    else:
        raise InputError(f"{context} hidden underlap must be a path or object")
    path = Path(path_text)
    if not path.is_absolute():
        path = contract_dir / path
    return HiddenSpec(path.resolve(), origin)


def _part_entries(raw_parts: Any) -> list[tuple[str | None, dict[str, Any]]]:
    entries: list[tuple[str | None, dict[str, Any]]] = []
    if isinstance(raw_parts, dict):
        for key, value in raw_parts.items():
            if isinstance(value, dict):
                entries.append((str(key), dict(value)))
            else:
                entries.append((str(key), {"label": value}))
        return entries
    if isinstance(raw_parts, list):
        for index, value in enumerate(raw_parts):
            if isinstance(value, str):
                entries.append((value, {}))
            elif isinstance(value, dict):
                entries.append((None, dict(value)))
            else:
                raise InputError(f"parts[{index}] must be an object")
        return entries
    raise InputError("contract 'parts' must be an array or object")


def _infer_mode(raw: dict[str, Any], entries: list[tuple[str | None, dict[str, Any]]]) -> str:
    explicit = _first(raw, ("label_mode", "ownership_mode", "map_mode"))
    ownership = raw.get("ownership")
    if explicit is None and isinstance(ownership, dict):
        explicit = _first(ownership, ("mode", "label_mode"))
    if explicit is not None:
        mode = str(explicit).strip().lower()
        aliases = {"indexed": "index", "palette": "index", "rgb": "color", "rgba": "color"}
        mode = aliases.get(mode, mode)
        if mode not in {"index", "color"}:
            raise InputError(f"unsupported label_mode: {explicit!r}")
        return mode

    candidates: list[Any] = []
    for _, entry in entries:
        value = _first(entry, ("color", "label", "index", "value", "ownership_id"))
        if value is not None:
            if isinstance(value, list) and value and not _looks_like_color(value):
                candidates.extend(value)
            else:
                candidates.append(value)
    return "color" if any(_looks_like_color(value) for value in candidates) else "index"


def _parse_contract(path: Path, underlap_dir: Path | None) -> Contract:
    raw = _load_json(path)
    entries = _part_entries(raw.get("parts"))
    if not entries:
        raise InputError("contract must contain at least one part")
    mode = _infer_mode(raw, entries)
    contract_dir = path.resolve().parent

    top_hidden = raw.get("hidden_underlaps", {})
    if top_hidden is None:
        top_hidden = {}
    if not isinstance(top_hidden, dict):
        raise InputError("hidden_underlaps must be an object keyed by part name")

    parts: list[PartSpec] = []
    names: set[str] = set()
    filenames: set[str] = set()
    for index, (key_name, entry) in enumerate(entries):
        name_value = _first(entry, ("name", "semantic", "part"), key_name)
        if name_value is None and isinstance(entry.get("id"), str):
            name_value = entry["id"]
        if not isinstance(name_value, str) or not name_value.strip():
            raise InputError(f"parts[{index}] needs a semantic name")
        name = name_value.strip()
        if name in names:
            raise InputError(f"duplicate part name: {name!r}")
        names.add(name)

        token_value: Any
        if "labels" in entry:
            token_values = entry["labels"]
            if not isinstance(token_values, list) or not token_values:
                raise InputError(f"part {name!r}: labels must be a non-empty array")
        else:
            token_value = _first(entry, ("color", "label", "index", "value", "ownership_id"))
            if token_value is None and isinstance(entry.get("id"), (int, float)):
                token_value = entry["id"]
            if token_value is None:
                raise InputError(f"part {name!r}: missing ownership label/color")
            token_values = [token_value]
        tokens = [_parse_token(value, mode) for value in token_values]
        if len(set(tokens)) != len(tokens):
            raise InputError(f"part {name!r}: duplicate ownership token")

        z_raw = _first(entry, ("z", "z_index", "layer", "draw_index"), index)
        try:
            z = float(z_raw)
        except (TypeError, ValueError) as exc:
            raise InputError(f"part {name!r}: z must be numeric") from exc
        if not math.isfinite(z):
            raise InputError(f"part {name!r}: z must be finite")

        requested_filename = _first(entry, ("filename", "output", "output_name"), name)
        filename = _safe_filename(str(requested_filename), f"part_{index:03d}")
        folded = filename.casefold()
        if folded in filenames:
            raise InputError(f"part output filename collision: {filename!r}")
        filenames.add(folded)

        hidden_value = _first(entry, ("hidden_underlap", "underlap", "hidden"))
        if hidden_value is None:
            hidden_value = top_hidden.get(name)
        hidden_origin = _first(entry, ("hidden_underlap_origin", "underlap_origin"))
        hidden = _parse_hidden_spec(hidden_value, contract_dir, f"part {name!r}", hidden_origin)

        # A directory is a convenient convention for generated underlap sheets.
        if hidden is None and underlap_dir is not None:
            candidates = [underlap_dir / filename, underlap_dir / f"{name}.png"]
            hidden_path = next((candidate for candidate in candidates if candidate.is_file()), None)
            if hidden_path is not None:
                hidden = HiddenSpec(hidden_path.resolve(), None)

        allow_empty = _as_bool(
            _first(entry, ("allow_empty", "allow_empty_visible", "underlap_only")), False
        )
        parts.append(
            PartSpec(
                name=name,
                tokens=tokens,
                z=z,
                order_hint=index,
                filename=filename,
                allow_empty=allow_empty,
                hidden=hidden,
                raw=entry,
            )
        )

    draw_order_raw = _first(raw, ("draw_order", "z_order", "layer_order"))
    if draw_order_raw is None:
        draw_order = [part.name for part in sorted(parts, key=lambda part: (part.z, part.order_hint))]
    else:
        if not isinstance(draw_order_raw, list) or not all(
            isinstance(value, str) for value in draw_order_raw
        ):
            raise InputError("draw_order must be an array of part names")
        draw_order = [str(value) for value in draw_order_raw]
        duplicate_order = [name for name, count in Counter(draw_order).items() if count > 1]
        unknown_order = [name for name in draw_order if name not in names]
        missing_order = [name for name in names if name not in draw_order]
        if duplicate_order or unknown_order or missing_order:
            raise InputError(
                "draw_order must name every part exactly once; "
                f"duplicates={sorted(duplicate_order)}, unknown={sorted(unknown_order)}, "
                f"missing={sorted(missing_order)}"
            )

    background_value = _first(raw, ("background", "background_label", "background_index", "background_color"))
    ownership = raw.get("ownership")
    if background_value is None and isinstance(ownership, dict):
        background_value = _first(
            ownership,
            ("background", "background_label", "background_index", "background_color"),
        )
    if background_value is None:
        background_values: list[Any] = [0] if mode == "index" else [[0, 0, 0]]
    elif isinstance(background_value, dict) and "labels" in background_value:
        background_values = background_value["labels"]
    elif isinstance(background_value, list) and background_value and not _looks_like_color(background_value):
        background_values = background_value
    else:
        background_values = [background_value]
    background = [_parse_token(value, mode) for value in background_values]

    alpha_zero_bg = _as_bool(
        _first(raw, ("map_alpha_zero_is_background", "alpha_zero_is_background")), True
    )
    index_channel_value = _first(raw, ("index_channel", "label_channel"))
    if index_channel_value is None:
        index_channel = None
    elif isinstance(index_channel_value, str):
        channel_names = {"r": 0, "red": 0, "g": 1, "green": 1, "b": 2, "blue": 2, "a": 3, "alpha": 3}
        try:
            index_channel = channel_names[index_channel_value.strip().lower()]
        except KeyError as exc:
            raise InputError(f"invalid index_channel: {index_channel_value!r}") from exc
    else:
        try:
            index_channel = int(index_channel_value)
        except (TypeError, ValueError) as exc:
            raise InputError(f"invalid index_channel: {index_channel_value!r}") from exc
        if index_channel not in {0, 1, 2, 3}:
            raise InputError("index_channel must be 0, 1, 2 or 3")

    return Contract(
        path=path.resolve(),
        raw=raw,
        mode=mode,
        parts=parts,
        background=background,
        draw_order=draw_order,
        map_alpha_zero_is_background=alpha_zero_bg,
        index_channel=index_channel,
    )


def _load_label_data(path: Path, contract: Contract) -> LabelData:
    try:
        with Image.open(path) as image:
            pil_mode = image.mode
            rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
            indices: np.ndarray | None = None
            invalid = np.zeros(rgba.shape[:2], dtype=bool)
            if contract.mode == "index":
                if pil_mode == "P":
                    indices = np.asarray(image, dtype=np.uint32).copy()
                elif pil_mode in {"1", "L", "I", "I;16", "I;16B", "I;16L"}:
                    indices = np.asarray(image, dtype=np.uint32).copy()
                elif pil_mode == "LA":
                    indices = np.asarray(image, dtype=np.uint8)[:, :, 0].astype(np.uint32)
                else:
                    raw_rgba = rgba
                    if contract.index_channel is not None:
                        indices = raw_rgba[:, :, contract.index_channel].astype(np.uint32)
                    else:
                        indices = raw_rgba[:, :, 0].astype(np.uint32)
                        invalid = ~(
                            (raw_rgba[:, :, 0] == raw_rgba[:, :, 1])
                            & (raw_rgba[:, :, 0] == raw_rgba[:, :, 2])
                        )
    except FileNotFoundError as exc:
        raise InputError(f"ownership label map not found: {path}") from exc
    except OSError as exc:
        raise InputError(f"cannot read ownership label map {path}: {exc}") from exc
    return LabelData(path.resolve(), pil_mode, rgba, indices, invalid)


def _token_mask(data: LabelData, token: LabelToken) -> np.ndarray:
    if token.kind == "index":
        if data.indices is None:
            raise InputError("internal error: index label data is unavailable")
        return (data.indices == int(token.value)) & ~data.index_invalid_color
    values = tuple(int(value) for value in token.value)  # type: ignore[arg-type]
    channels = 3 if token.kind == "rgb" else 4
    expected = np.asarray(values, dtype=np.uint8)
    return np.all(data.rgba[:, :, :channels] == expected, axis=2)


def _union_token_masks(data: LabelData, tokens: Sequence[LabelToken]) -> np.ndarray:
    mask = np.zeros(data.rgba.shape[:2], dtype=bool)
    for token in tokens:
        mask |= _token_mask(data, token)
    return mask


def _bbox(mask: np.ndarray) -> dict[str, int] | None:
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return None
    x0 = int(xs.min())
    y0 = int(ys.min())
    x1 = int(xs.max()) + 1
    y1 = int(ys.max()) + 1
    return {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0, "x2": x1, "y2": y1}


def _samples(mask: np.ndarray, limit: int) -> list[list[int]]:
    if limit <= 0:
        return []
    ys, xs = np.nonzero(mask)
    count = min(limit, xs.size)
    return [[int(xs[index]), int(ys[index])] for index in range(count)]


def _mask_report(mask: np.ndarray, limit: int) -> dict[str, Any]:
    return {"count": int(np.count_nonzero(mask)), "bbox": _bbox(mask), "samples_xy": _samples(mask, limit)}


def _alpha_area(rgba: np.ndarray) -> dict[str, Any]:
    alpha = rgba[:, :, 3]
    alpha_sum = int(alpha.astype(np.uint64).sum())
    return {
        "nonzero_pixels": int(np.count_nonzero(alpha)),
        "opaque_pixels": int(np.count_nonzero(alpha == 255)),
        "partial_pixels": int(np.count_nonzero((alpha > 0) & (alpha < 255))),
        "alpha_sum": alpha_sum,
        "alpha_equivalent_pixels": round(alpha_sum / 255.0, 6),
        "bbox": _bbox(alpha > 0),
    }


def _place_hidden(
    spec: HiddenSpec,
    canvas_size: tuple[int, int],
    sample_limit: int,
) -> tuple[np.ndarray, dict[str, Any], np.ndarray]:
    """Place a hidden image on the master canvas without silently clipping.

    Returns canvas RGBA, metadata, and a mask representing non-transparent
    input pixels that fell outside the canvas.
    """

    source = _load_rgba(spec.path, "hidden underlap")
    canvas_w, canvas_h = canvas_size
    source_h, source_w = source.shape[:2]
    if spec.origin is None:
        if (source_w, source_h) != (canvas_w, canvas_h):
            raise InputError(
                f"hidden underlap {spec.path} is {source_w}x{source_h}, expected "
                f"{canvas_w}x{canvas_h}; provide an explicit origin for a cropped image"
            )
        origin_x, origin_y = 0, 0
    else:
        origin_x, origin_y = spec.origin

    canvas = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
    source_alpha = source[:, :, 3] > 0
    outside_source = np.zeros((source_h, source_w), dtype=bool)

    src_x0 = max(0, -origin_x)
    src_y0 = max(0, -origin_y)
    src_x1 = min(source_w, canvas_w - origin_x)
    src_y1 = min(source_h, canvas_h - origin_y)
    if src_x0 < src_x1 and src_y0 < src_y1:
        dst_x0 = origin_x + src_x0
        dst_y0 = origin_y + src_y0
        dst_x1 = origin_x + src_x1
        dst_y1 = origin_y + src_y1
        canvas[dst_y0:dst_y1, dst_x0:dst_x1] = source[src_y0:src_y1, src_x0:src_x1]
        inside = np.zeros((source_h, source_w), dtype=bool)
        inside[src_y0:src_y1, src_x0:src_x1] = True
        outside_source = source_alpha & ~inside
    else:
        outside_source = source_alpha.copy()

    # Fully transparent RGB is not artwork and can vary between encoders.  Keep
    # output part payloads canonical while retaining the raw source hash above.
    canvas[canvas[:, :, 3] == 0] = 0

    metadata = {
        "path": str(spec.path),
        "file_sha256": _sha256_file(spec.path),
        "pixel_sha256": _array_hash(source),
        "source_size": {"width": source_w, "height": source_h},
        "origin": {"x": origin_x, "y": origin_y},
        "source_area": _alpha_area(source),
        "out_of_canvas": _mask_report(outside_source, sample_limit),
    }
    return canvas, metadata, outside_source


def _source_over(bottom: np.ndarray, top: np.ndarray) -> np.ndarray:
    """Integer-stable straight-alpha source-over via Pillow."""

    bottom_image = Image.fromarray(np.ascontiguousarray(bottom), mode="RGBA")
    top_image = Image.fromarray(np.ascontiguousarray(top), mode="RGBA")
    return np.asarray(Image.alpha_composite(bottom_image, top_image), dtype=np.uint8).copy()


def _crop_or_canvas(
    rgba: np.ndarray, full_canvas: bool
) -> tuple[np.ndarray, tuple[int, int], dict[str, int] | None]:
    area_bbox = _bbox(rgba[:, :, 3] > 0)
    if full_canvas:
        return rgba.copy(), (0, 0), area_bbox
    if area_bbox is None:
        return np.zeros((1, 1, 4), dtype=np.uint8), (0, 0), None
    x = area_bbox["x"]
    y = area_bbox["y"]
    x2 = area_bbox["x2"]
    y2 = area_bbox["y2"]
    return rgba[y:y2, x:x2].copy(), (x, y), area_bbox


def _restore_crop(crop: np.ndarray, origin: tuple[int, int], canvas: np.ndarray) -> np.ndarray:
    x, y = origin
    h, w = crop.shape[:2]
    if x < 0 or y < 0 or x + w > canvas.shape[1] or y + h > canvas.shape[0]:
        raise InputError("generated part crop lies outside master canvas")
    restored = canvas.copy()
    restored[y : y + h, x : x + w] = crop
    return restored


def _foreign_values(
    labels: LabelData,
    contract: Contract,
    mask: np.ndarray,
    max_values: int = 32,
) -> list[dict[str, Any]]:
    if not np.any(mask):
        return []
    if contract.mode == "index":
        assert labels.indices is not None
        invalid_mask = mask & labels.index_invalid_color
        regular_mask = mask & ~labels.index_invalid_color
        values, counts = np.unique(labels.indices[regular_mask], return_counts=True)
        pairs = sorted(
            ((int(count), int(value)) for value, count in zip(values, counts)),
            key=lambda item: (-item[0], item[1]),
        )
        result = [{"label": value, "pixels": count} for count, value in pairs[:max_values]]
        invalid_count = int(np.count_nonzero(invalid_mask))
        if invalid_count:
            result.insert(0, {"label": "non-grayscale-index-color", "pixels": invalid_count})
        return result[:max_values]

    rgba = labels.rgba[mask]
    values, counts = np.unique(rgba, axis=0, return_counts=True)
    pairs = sorted(
        ((int(count), tuple(int(channel) for channel in value)) for value, count in zip(values, counts)),
        key=lambda item: (-item[0], item[1]),
    )
    return [
        {"label": "#" + "".join(f"{channel:02X}" for channel in value), "pixels": count}
        for count, value in pairs[:max_values]
    ]


def _make_diagnostic(
    master: np.ndarray,
    missing: np.ndarray,
    overlap: np.ndarray,
    foreign: np.ndarray,
    transparent_labeled: np.ndarray,
    extraction_mismatch: np.ndarray,
    hidden_invalid: np.ndarray,
) -> np.ndarray:
    diagnostic = master.copy()
    # Dim valid master pixels so failures remain legible without losing shape.
    rgb = diagnostic[:, :, :3].astype(np.uint16)
    diagnostic[:, :, :3] = ((rgb * 80) // 255).astype(np.uint8)
    diagnostic[:, :, 3] = np.where(master[:, :, 3] > 0, 150, 0).astype(np.uint8)
    # Later classes win, matching their severity/specificity.
    classes = [
        (transparent_labeled, (0, 220, 255, 255)),
        (foreign, (255, 215, 0, 255)),
        (missing, (255, 32, 32, 255)),
        (overlap, (255, 0, 220, 255)),
        (hidden_invalid, (255, 128, 0, 255)),
        (extraction_mismatch, (0, 128, 255, 255)),
    ]
    for mask, color in classes:
        diagnostic[mask] = np.asarray(color, dtype=np.uint8)
    return diagnostic


def _comparison_strip(images: Sequence[np.ndarray]) -> np.ndarray:
    if not images:
        raise ValueError("comparison strip needs at least one image")
    height = max(image.shape[0] for image in images)
    gutter = 4
    widths = [image.shape[1] for image in images]
    result = np.zeros((height, sum(widths) + gutter * (len(images) - 1), 4), dtype=np.uint8)
    result[:, :, :3] = 24
    result[:, :, 3] = 255
    x = 0
    for index, image in enumerate(images):
        result[: image.shape[0], x : x + image.shape[1]] = image
        x += image.shape[1]
        if index != len(images) - 1:
            result[:, x : x + gutter, :3] = 96
            result[:, x : x + gutter, 3] = 255
            x += gutter
    return result


def _clean_parts_dir(parts_dir: Path) -> None:
    if parts_dir.exists() and not parts_dir.is_dir():
        raise InputError(f"parts output exists but is not a directory: {parts_dir}")
    parts_dir.mkdir(parents=True, exist_ok=True)
    for child in parts_dir.iterdir():
        if child.is_file() and child.suffix.lower() == ".png":
            child.unlink()


def build(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    master_path = Path(args.master).resolve()
    labels_path = Path(args.labels).resolve()
    contract_path = Path(args.contract).resolve()
    output_dir = Path(args.output_dir).resolve()
    underlap_dir = Path(args.hidden_underlap_dir).resolve() if args.hidden_underlap_dir else None
    if underlap_dir is not None and not underlap_dir.is_dir():
        raise InputError(f"hidden underlap directory not found: {underlap_dir}")

    master = _load_rgba(master_path, "approved master")
    contract = _parse_contract(contract_path, underlap_dir)
    labels = _load_label_data(labels_path, contract)
    master_h, master_w = master.shape[:2]
    if labels.rgba.shape[:2] != (master_h, master_w):
        raise InputError(
            f"ownership map size {labels.rgba.shape[1]}x{labels.rgba.shape[0]} does not "
            f"match master {master_w}x{master_h}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    parts_dir = output_dir / "parts"
    if not args.no_clean:
        protected_inputs = {master_path, labels_path, contract_path}
        protected_inputs.update(
            part.hidden.path for part in contract.parts if part.hidden is not None
        )
        endangered = sorted(
            str(path)
            for path in protected_inputs
            if path.parent == parts_dir.resolve() and path.suffix.lower() == ".png"
        )
        if endangered:
            raise InputError(
                "output-dir/parts cleanup would delete input PNGs: "
                + ", ".join(endangered)
            )
        _clean_parts_dir(parts_dir)
    else:
        parts_dir.mkdir(parents=True, exist_ok=True)

    master_visible = master[:, :, 3] > 0
    canonical_master = master.copy()
    canonical_master[~master_visible] = 0
    transparent_rgb_residue = (~master_visible) & np.any(master[:, :, :3] != 0, axis=2)

    part_masks: dict[str, np.ndarray] = {}
    coverage = np.zeros((master_h, master_w), dtype=np.uint16)
    for part in contract.parts:
        mask = _union_token_masks(labels, part.tokens)
        if contract.map_alpha_zero_is_background:
            mask &= labels.rgba[:, :, 3] > 0
        part_masks[part.name] = mask
        coverage += mask.astype(np.uint16)

    background_mask = _union_token_masks(labels, contract.background)
    if contract.map_alpha_zero_is_background:
        background_mask |= labels.rgba[:, :, 3] == 0
    # Non-grayscale colors in inferred RGB index maps are always unknown unless
    # a channel was explicitly selected.
    if contract.mode == "index" and contract.index_channel is None:
        background_mask &= ~labels.index_invalid_color

    foreign = (~background_mask) & (coverage == 0)
    if contract.mode == "index" and contract.index_channel is None:
        foreign |= labels.index_invalid_color & (labels.rgba[:, :, 3] > 0)
    label_active = (coverage > 0) | foreign
    missing = master_visible & (coverage == 0)
    overlap = master_visible & (coverage > 1)
    overlap_anywhere = coverage > 1
    transparent_labeled = (~master_visible) & label_active
    foreign_visible = foreign & master_visible
    foreign_transparent = foreign & ~master_visible

    order_rank = {name: index for index, name in enumerate(contract.draw_order)}
    owner_rank = np.full((master_h, master_w), -1, dtype=np.int32)
    unique_owner = coverage == 1
    for name, mask in part_masks.items():
        owner_rank[unique_owner & mask] = order_rank[name]

    visible_layers: dict[str, np.ndarray] = {}
    combined_layers: dict[str, np.ndarray] = {}
    part_reports: list[dict[str, Any]] = []
    all_extraction_mismatch = np.zeros((master_h, master_w), dtype=bool)
    all_hidden_invalid = np.zeros((master_h, master_w), dtype=bool)
    empty_required_parts: list[str] = []
    hidden_out_of_canvas_total = 0

    part_lookup = {part.name: part for part in contract.parts}
    ordered_parts = [part_lookup[name] for name in contract.draw_order]
    for part in ordered_parts:
        ownership_mask = part_masks[part.name]
        visible_mask = ownership_mask & master_visible
        visible = np.zeros_like(master)
        visible[visible_mask] = master[visible_mask]
        visible_layers[part.name] = visible
        if not np.any(visible_mask) and not part.allow_empty:
            empty_required_parts.append(part.name)

        hidden_canvas = np.zeros_like(master)
        hidden_metadata: dict[str, Any] | None = None
        hidden_invalid = np.zeros((master_h, master_w), dtype=bool)
        hidden_allowed_outside = np.zeros((master_h, master_w), dtype=bool)
        hidden_allowed_occluded = np.zeros((master_h, master_w), dtype=bool)
        hidden_self_or_back = np.zeros((master_h, master_w), dtype=bool)
        hidden_partial_front = np.zeros((master_h, master_w), dtype=bool)

        if part.hidden is not None:
            hidden_canvas, hidden_metadata, outside_source = _place_hidden(
                part.hidden, (master_w, master_h), args.max_samples
            )
            hidden_out_of_canvas_total += int(np.count_nonzero(outside_source))
            hidden_alpha = hidden_canvas[:, :, 3] > 0
            hidden_allowed_outside = hidden_alpha & ~master_visible
            front_owner = owner_rank > order_rank[part.name]
            fully_opaque_front = master[:, :, 3] == 255
            hidden_allowed_occluded = hidden_alpha & master_visible & front_owner & fully_opaque_front
            hidden_partial_front = hidden_alpha & master_visible & front_owner & ~fully_opaque_front
            hidden_self_or_back = hidden_alpha & master_visible & ~front_owner
            hidden_invalid = hidden_alpha & ~(hidden_allowed_outside | hidden_allowed_occluded)
            all_hidden_invalid |= hidden_invalid

        # Visible approved payload always wins within its own layer.  This
        # preserves exact source pixels even in non-strict diagnostic runs.
        combined = hidden_canvas.copy()
        combined[visible_mask] = master[visible_mask]
        combined_layers[part.name] = combined

        crop, origin, canvas_bbox = _crop_or_canvas(combined, args.full_canvas_parts)
        output_path = parts_dir / part.filename
        _save_png(output_path, crop)
        reloaded_crop = _load_rgba(output_path, "generated part")
        restored = _restore_crop(reloaded_crop, origin, np.zeros_like(master))

        extraction_mismatch = visible_mask & np.any(restored != master, axis=2)
        unexpected_visible = (restored[:, :, 3] > 0) & ownership_mask & ~visible_mask
        all_extraction_mismatch |= extraction_mismatch

        part_report: dict[str, Any] = {
            "name": part.name,
            "draw_rank": order_rank[part.name],
            "z": part.z,
            "labels": [token.display() for token in part.tokens],
            "allow_empty_visible": part.allow_empty,
            "output": str(output_path.relative_to(output_dir)).replace("\\", "/"),
            "output_origin": {"x": origin[0], "y": origin[1]},
            "output_size": {"width": crop.shape[1], "height": crop.shape[0]},
            "canvas_bbox": canvas_bbox,
            "visible_area": _alpha_area(visible),
            "hidden_area": _alpha_area(hidden_canvas),
            "combined_area": _alpha_area(combined),
            "ownership_pixels_total": int(np.count_nonzero(ownership_mask)),
            "ownership_pixels_on_master_alpha": int(np.count_nonzero(visible_mask)),
            "ownership_pixels_on_master_transparent": int(
                np.count_nonzero(ownership_mask & ~master_visible)
            ),
            "extraction_mismatch": _mask_report(extraction_mismatch, args.max_samples),
            "unexpected_visible_payload": _mask_report(unexpected_visible, args.max_samples),
            "hashes": {
                "visible_canvas_rgba_sha256": _array_hash(visible),
                "combined_canvas_rgba_sha256": _array_hash(combined),
                "output_pixel_sha256": _array_hash(reloaded_crop),
                "output_file_sha256": _sha256_file(output_path),
            },
            "hidden_underlap": None,
        }
        if hidden_metadata is not None:
            hidden_metadata.update(
                {
                    "allowed_outside_master_alpha": _mask_report(
                        hidden_allowed_outside, args.max_samples
                    ),
                    "allowed_behind_opaque_front_part": _mask_report(
                        hidden_allowed_occluded, args.max_samples
                    ),
                    "invalid_on_self_or_back_visible_part": _mask_report(
                        hidden_self_or_back, args.max_samples
                    ),
                    "invalid_behind_partial_alpha_front_part": _mask_report(
                        hidden_partial_front, args.max_samples
                    ),
                    "invalid_total": _mask_report(hidden_invalid, args.max_samples),
                    "canvas_pixel_sha256": _array_hash(hidden_canvas),
                }
            )
            part_report["hidden_underlap"] = hidden_metadata
        part_reports.append(part_report)

    # Visible-only reconstruction is deliberately independent of hidden art.
    recomposed_visible = np.zeros_like(master)
    for part in ordered_parts:
        mask = part_masks[part.name] & master_visible
        recomposed_visible[mask] = visible_layers[part.name][mask]
    visible_recomposition_mismatch = np.any(recomposed_visible != canonical_master, axis=2)

    # This is the actual bind-pose source-over result of the output part PNGs.
    recomposed_full = np.zeros_like(master)
    for part in ordered_parts:
        recomposed_full = _source_over(recomposed_full, combined_layers[part.name])
    full_master_footprint_mismatch = master_visible & np.any(
        recomposed_full != canonical_master, axis=2
    )
    full_outside_master = (~master_visible) & (recomposed_full[:, :, 3] > 0)

    diagnostic = _make_diagnostic(
        canonical_master,
        missing,
        overlap_anywhere,
        foreign,
        transparent_labeled,
        all_extraction_mismatch,
        all_hidden_invalid,
    )
    visible_preview_path = output_dir / VISIBLE_PREVIEW_NAME
    full_preview_path = output_dir / FULL_PREVIEW_NAME
    diagnostic_path = output_dir / DIAGNOSTIC_NAME
    comparison_path = output_dir / COMPARISON_NAME
    _save_png(visible_preview_path, recomposed_visible)
    _save_png(full_preview_path, recomposed_full)
    _save_png(diagnostic_path, diagnostic)
    _save_png(
        comparison_path,
        _comparison_strip([canonical_master, recomposed_visible, recomposed_full, diagnostic]),
    )

    # Contract tokens assigned to multiple parts are a deterministic source of
    # overlap and deserve an explicit human-readable entry in addition to the
    # pixel mask.
    token_owners: dict[LabelToken, list[str]] = {}
    for part in contract.parts:
        for token in part.tokens:
            token_owners.setdefault(token, []).append(part.name)
    duplicate_tokens = [
        {"label": token.display(), "parts": owners}
        for token, owners in sorted(
            token_owners.items(), key=lambda item: (str(item[0].display()), item[1])
        )
        if len(owners) > 1
    ]
    background_collisions = [
        {"label": token.display(), "parts": owners}
        for token, owners in token_owners.items()
        if token in set(contract.background)
    ]

    issue_counts = {
        "missing_pixels": int(np.count_nonzero(missing)),
        "overlap_pixels_on_master": int(np.count_nonzero(overlap)),
        "overlap_pixels_anywhere": int(np.count_nonzero(overlap_anywhere)),
        "foreign_label_pixels": int(np.count_nonzero(foreign)),
        "transparent_region_labeled_pixels": int(np.count_nonzero(transparent_labeled)),
        "extraction_mismatch_pixels": int(np.count_nonzero(all_extraction_mismatch)),
        "visible_recomposition_mismatch_pixels": int(
            np.count_nonzero(visible_recomposition_mismatch)
        ),
        "hidden_invalid_pixels": int(np.count_nonzero(all_hidden_invalid)),
        "hidden_out_of_canvas_pixels": hidden_out_of_canvas_total,
        "full_composite_master_footprint_mismatch_pixels": int(
            np.count_nonzero(full_master_footprint_mismatch)
        ),
        "required_parts_with_no_visible_pixels": len(empty_required_parts),
        "duplicate_contract_label_tokens": len(duplicate_tokens),
        "part_labels_colliding_with_background": len(background_collisions),
    }
    valid = all(count == 0 for count in issue_counts.values())

    report: dict[str, Any] = {
        "schema": "sts2-master-linked-cutouts-qa/v1",
        "status": "pass" if valid else "fail",
        "strict_requested": bool(args.strict),
        "inputs": {
            "master": str(master_path),
            "ownership_map": str(labels_path),
            "part_contract": str(contract_path),
            "hidden_underlap_dir": str(underlap_dir) if underlap_dir else None,
            "master_size": {"width": master_w, "height": master_h},
            "ownership_map_mode": labels.pil_mode,
            "label_mode": contract.mode,
            "map_alpha_zero_is_background": contract.map_alpha_zero_is_background,
            "index_channel": contract.index_channel,
            "background_labels": [token.display() for token in contract.background],
            "draw_order_back_to_front": contract.draw_order,
            "hashes": {
                "master_file_sha256": _sha256_file(master_path),
                "master_rgba_sha256": _array_hash(master),
                "master_visible_canonical_rgba_sha256": _array_hash(canonical_master),
                "ownership_map_file_sha256": _sha256_file(labels_path),
                "ownership_map_rgba_sha256": _array_hash(labels.rgba),
                "part_contract_file_sha256": _sha256_file(contract_path),
            },
        },
        "areas": {
            "canvas_pixels": master_w * master_h,
            "master": _alpha_area(master),
            "ownership_labeled_pixels": int(np.count_nonzero(label_active)),
            "coverage_exactly_one_pixels": int(np.count_nonzero(coverage == 1)),
            "coverage_zero_pixels": int(np.count_nonzero(coverage == 0)),
            "coverage_multiple_pixels": int(np.count_nonzero(coverage > 1)),
            "master_transparent_nonzero_rgb_pixels": int(
                np.count_nonzero(transparent_rgb_residue)
            ),
        },
        "issues": {
            "counts": issue_counts,
            "missing": _mask_report(missing, args.max_samples),
            "overlap_on_master": _mask_report(overlap, args.max_samples),
            "overlap_anywhere": _mask_report(overlap_anywhere, args.max_samples),
            "foreign": _mask_report(foreign, args.max_samples),
            "foreign_on_master": _mask_report(foreign_visible, args.max_samples),
            "foreign_on_transparent": _mask_report(foreign_transparent, args.max_samples),
            "foreign_values": _foreign_values(labels, contract, foreign),
            "transparent_region_labeled": _mask_report(
                transparent_labeled, args.max_samples
            ),
            "extraction_mismatch": _mask_report(
                all_extraction_mismatch, args.max_samples
            ),
            "visible_recomposition_mismatch": _mask_report(
                visible_recomposition_mismatch, args.max_samples
            ),
            "hidden_invalid": _mask_report(all_hidden_invalid, args.max_samples),
            "full_composite_master_footprint_mismatch": _mask_report(
                full_master_footprint_mismatch, args.max_samples
            ),
            "required_parts_with_no_visible_pixels": empty_required_parts,
            "duplicate_contract_label_tokens": duplicate_tokens,
            "part_labels_colliding_with_background": background_collisions,
        },
        "parts": part_reports,
        "outputs": {
            "parts_directory": "parts",
            "visible_recomposition": VISIBLE_PREVIEW_NAME,
            "full_underlap_composite": FULL_PREVIEW_NAME,
            "diagnostic": DIAGNOSTIC_NAME,
            "comparison_panels": [
                "canonical_master",
                "visible_recomposition",
                "full_underlap_composite",
                "diagnostic",
            ],
            "comparison": COMPARISON_NAME,
            "full_composite_outside_master_alpha": _mask_report(
                full_outside_master, args.max_samples
            ),
            "hashes": {
                "visible_recomposition_rgba_sha256": _array_hash(recomposed_visible),
                "visible_recomposition_file_sha256": _sha256_file(visible_preview_path),
                "full_underlap_composite_rgba_sha256": _array_hash(recomposed_full),
                "full_underlap_composite_file_sha256": _sha256_file(full_preview_path),
                "diagnostic_rgba_sha256": _array_hash(diagnostic),
                "diagnostic_file_sha256": _sha256_file(diagnostic_path),
                "comparison_file_sha256": _sha256_file(comparison_path),
            },
        },
        "invariants": {
            "all_master_alpha_pixels_labeled": issue_counts["missing_pixels"] == 0,
            "master_transparent_region_has_no_labels": issue_counts[
                "transparent_region_labeled_pixels"
            ]
            == 0,
            "every_visible_pixel_owned_by_exactly_one_part": issue_counts[
                "missing_pixels"
            ]
            == 0
            and issue_counts["overlap_pixels_on_master"] == 0,
            "extracted_visible_rgba_is_byte_exact": issue_counts[
                "extraction_mismatch_pixels"
            ]
            == 0,
            "hidden_underlaps_only_in_allowed_regions": issue_counts[
                "hidden_invalid_pixels"
            ]
            == 0
            and issue_counts["hidden_out_of_canvas_pixels"] == 0,
            "visible_recomposition_is_byte_exact": issue_counts[
                "visible_recomposition_mismatch_pixels"
            ]
            == 0,
            "full_bind_pose_matches_master_on_master_footprint": issue_counts[
                "full_composite_master_footprint_mismatch_pixels"
            ]
            == 0,
        },
    }

    report_path = output_dir / REPORT_NAME
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report, valid


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract exact visible semantic cutouts from an approved RGBA master "
            "using an index/color ownership map, then audit optional hidden underlaps."
        )
    )
    parser.add_argument("--master", required=True, help="Approved full RGBA master PNG")
    parser.add_argument(
        "--labels",
        "--ownership-map",
        dest="labels",
        required=True,
        help="Same-size index or exact-color ownership label map",
    )
    parser.add_argument("--contract", required=True, help="Semantic part contract JSON")
    parser.add_argument(
        "--output-dir", "--output", dest="output_dir", required=True, help="Output directory"
    )
    parser.add_argument(
        "--hidden-underlap-dir",
        "--underlap-dir",
        dest="hidden_underlap_dir",
        default=None,
        help="Optional directory containing <part>.png hidden-underlap images",
    )
    parser.add_argument(
        "--full-canvas-parts",
        action="store_true",
        help="Write every part at master canvas size instead of deterministic tight crops",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Keep unrelated old PNGs in output-dir/parts (current outputs are overwritten)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=32,
        help="Maximum row-major x/y samples stored per issue (default: 32)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 1 when any audited invariant fails",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.max_samples < 0:
        parser.error("--max-samples must be >= 0")
    try:
        report, valid = build(args)
    except InputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    status = "PASS" if valid else "FAIL"
    counts = report["issues"]["counts"]
    print(
        f"[{status}] linked cutouts: {len(report['parts'])} parts, "
        f"missing={counts['missing_pixels']}, overlap={counts['overlap_pixels_anywhere']}, "
        f"foreign={counts['foreign_label_pixels']}, "
        f"hidden_invalid={counts['hidden_invalid_pixels']}, "
        f"recompose_mismatch={counts['visible_recomposition_mismatch_pixels']}"
    )
    print(f"QA: {Path(args.output_dir).resolve() / REPORT_NAME}")
    if args.strict and not valid:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
