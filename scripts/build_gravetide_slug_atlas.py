#!/usr/bin/env python3
"""Assemble a supersampled Gravetide Slug Spine atlas from repaint outputs.

This script does not draw the monster. It crops/scales the accepted repaint
outputs, restores the shipped region alpha masks, and packs them into a
supersampled copy of the version-owned atlas. The atlas coordinates are
scaled together with the page and its ``scale`` value is divided by the
supersample factor, so the Spine skeleton keeps the exact same world size
while receiving more source pixels at runtime.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VANILLA_ATLAS = (
    ROOT.parent / "STS2-V111/animations/monsters/corpse_slug/corpse_slug.png"
)
DEFAULT_SOURCE = ROOT / "source_assets/monsters/gravetide_slug/imagegen"
DEFAULT_OUTPUT = (
    ROOT
    / "STS2_Things/animations/monsters/gravetide_slug/gravetide_slug.png"
)
DEFAULT_ATLAS_TEMPLATE = (
    ROOT.parent / "STS2-V111/animations/monsters/corpse_slug/corpse_slug.atlas"
)
RESOURCE_ATLAS_PATH = (
    "res://STS2_Things/animations/monsters/gravetide_slug/gravetide_slug.atlas"
)
# Keep the currently approved recolor, but give the native Spine rig four
# source pixels for every legacy atlas pixel.  The atlas scale is divided by
# the same factor below, so this changes sampling density only, not gameplay
# placement, skeleton bounds, or animation motion.
DEFAULT_SUPERSAMPLE = 4


@dataclass(frozen=True)
class Region:
    x: int
    y: int
    width: int
    height: int

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)


# Exact bounds from the shipped v0.107.1/v0.109.0 corpse_slug.atlas.  Those
# two versions are byte-identical for this asset.
REGIONS = {
    "body": Region(2, 2, 233, 148),
    "body_top": Region(237, 3, 215, 147),
    "shadow": Region(454, 4, 275, 47),
    "eat": Region(454, 53, 276, 97),
    "small_parts": Region(731, 5, 51, 147),
}


def subject_mask(image: Image.Image) -> np.ndarray:
    """Separate painted content from ImageGen's light checker preview."""

    rgb = np.asarray(image.convert("RGB"), dtype=np.int16)
    mean = rgb.mean(axis=2)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    mask = ((mean < 228) | (chroma > 20)).astype(np.uint8)
    return mask


def components(mask: np.ndarray, min_area: int) -> list[tuple[np.ndarray, tuple]]:
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    result: list[tuple[np.ndarray, tuple]] = []
    for index in range(1, count):
        x, y, width, height, area = (int(value) for value in stats[index])
        if area < min_area:
            continue
        component = (labels == index).astype(np.uint8)
        result.append(
            (
                component,
                (x, y, width, height, area, *map(float, centroids[index])),
            )
        )
    return result


def zoomed_crop(
    image: Image.Image,
    box: tuple[int, int, int, int],
    zoom: float,
) -> Image.Image:
    """Crop slightly inside a subject bbox so painted pixels overfill a mask."""

    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    inset_x = max(0, round(width * (zoom - 1.0) / (2.0 * zoom)))
    inset_y = max(0, round(height * (zoom - 1.0) / (2.0 * zoom)))
    return image.crop(
        (left + inset_x, top + inset_y, right - inset_x, bottom - inset_y)
    )


def repaint_region(
    canvas: Image.Image,
    vanilla: Image.Image,
    generated_path: Path,
    region: Region,
    factor: int,
) -> None:
    generated = Image.open(generated_path).convert("RGB")
    candidates = components(subject_mask(generated), min_area=500)
    if not candidates:
        raise RuntimeError(f"No painted subject found in {generated_path}")
    _, stats = max(candidates, key=lambda item: item[1][4])
    x, y, width, height, *_ = stats
    crop = zoomed_crop(generated, (x, y, x + width, y + height), zoom=1.025)
    output_size = (region.width * factor, region.height * factor)
    repaint = ImageOps.fit(
        crop,
        output_size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    alpha = vanilla.crop(region.box).getchannel("A").resize(
        output_size, Image.Resampling.LANCZOS
    )
    canvas.paste(repaint, (region.x * factor, region.y * factor), alpha)


def repaint_small_parts(
    canvas: Image.Image,
    vanilla: Image.Image,
    generated_path: Path,
    region: Region,
    factor: int,
) -> None:
    generated = Image.open(generated_path).convert("RGB")
    generated_components = components(subject_mask(generated), min_area=500)
    generated_components.sort(key=lambda item: (item[1][6], item[1][5]))

    original_alpha = np.asarray(vanilla.crop(region.box).getchannel("A"))
    original_components = components((original_alpha > 0).astype(np.uint8), 2)
    original_components.sort(key=lambda item: (item[1][6], item[1][5]))

    if len(generated_components) != len(original_components):
        raise RuntimeError(
            "Small-part count drifted: "
            f"ImageGen={len(generated_components)} vanilla={len(original_components)}"
        )

    for (_, source_stats), (target_component, target_stats) in zip(
        generated_components,
        original_components,
        strict=True,
    ):
        sx, sy, sw, sh, *_ = source_stats
        tx, ty, tw, th, *_ = target_stats
        source = zoomed_crop(
            generated,
            (sx, sy, sx + sw, sy + sh),
            zoom=1.06,
        )
        output_size = (tw * factor, th * factor)
        repaint = ImageOps.fit(
            source,
            output_size,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        local_alpha = Image.fromarray(
            (target_component[ty : ty + th, tx : tx + tw] * 255).astype(np.uint8),
            mode="L",
        )
        # Preserve the shipped antialiasing instead of replacing it with the
        # binary connected-component mask.
        shipped_alpha = vanilla.crop(
            (
                region.x + tx,
                region.y + ty,
                region.x + tx + tw,
                region.y + ty + th,
            )
        ).getchannel("A")
        local_alpha = Image.fromarray(
            np.minimum(np.asarray(local_alpha), np.asarray(shipped_alpha)).astype(
                np.uint8
            ),
            mode="L",
        ).resize(output_size, Image.Resampling.LANCZOS)
        canvas.paste(
            repaint,
            ((region.x + tx) * factor, (region.y + ty) * factor),
            local_alpha,
        )


def scale_atlas_text(atlas_text: str, factor: int) -> str:
    """Scale page geometry while preserving all Spine region names."""

    lines: list[str] = []
    for line in atlas_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("size:"):
            values = stripped.removeprefix("size:").split(",")
            line = f"size:{int(values[0]) * factor},{int(values[1]) * factor}"
        elif stripped.startswith("scale:"):
            value = float(stripped.removeprefix("scale:")) / factor
            line = f"scale:{value:.6f}".rstrip("0").rstrip(".")
        elif stripped.startswith("bounds:") or stripped.startswith("offsets:"):
            key, value_text = stripped.split(":", 1)
            values = [int(value) for value in value_text.split(",")]
            line = key + ":" + ",".join(str(value * factor) for value in values)
        lines.append(line)
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vanilla-atlas", type=Path, default=DEFAULT_VANILLA_ATLAS)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--atlas-template", type=Path, default=DEFAULT_ATLAS_TEMPLATE
    )
    parser.add_argument(
        "--supersample",
        type=int,
        default=DEFAULT_SUPERSAMPLE,
        choices=(1, 2, 3, 4),
        help="Atlas supersample factor; 4 keeps the vanilla world size and quadruples source pixels.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vanilla = Image.open(args.vanilla_atlas).convert("RGBA")
    factor = args.supersample
    canvas = Image.new(
        "RGBA", (vanilla.width * factor, vanilla.height * factor), (0, 0, 0, 0)
    )

    repaint_region(
        canvas,
        vanilla,
        args.source_dir / "body_imagegen.png",
        REGIONS["body"],
        factor,
    )
    repaint_region(
        canvas,
        vanilla,
        args.source_dir / "body_top_imagegen.png",
        REGIONS["body_top"],
        factor,
    )
    repaint_region(
        canvas,
        vanilla,
        args.source_dir / "eat_imagegen.png",
        REGIONS["eat"],
        factor,
    )
    repaint_small_parts(
        canvas,
        vanilla,
        args.source_dir / "small_parts_imagegen.png",
        REGIONS["small_parts"],
        factor,
    )

    # The shadow is not character paint and already matches both supported
    # versions, so retain its exact shipped pixels.
    shadow = REGIONS["shadow"]
    canvas.alpha_composite(
        vanilla.crop(shadow.box)
        .resize((shadow.width * factor, shadow.height * factor), Image.Resampling.LANCZOS),
        (shadow.x * factor, shadow.y * factor),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, optimize=True)

    atlas_text = scale_atlas_text(
        args.atlas_template.read_text(encoding="utf-8").replace(
            "corpse_slug.png", "gravetide_slug.png", 1
        ),
        factor,
    )
    atlas_path = args.output.with_suffix(".atlas")
    atlas_path.write_text(atlas_text, encoding="utf-8", newline="\n")
    spatlas_path = args.output.with_suffix(".spatlas")
    spatlas_path.write_text(
        json.dumps(
            {
                "atlas_data": atlas_text,
                "normal_texture_prefix": "n",
                "source_path": RESOURCE_ATLAS_PATH,
                "specular_texture_prefix": "s",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
        newline="\n",
    )
    uid_path = spatlas_path.with_suffix(spatlas_path.suffix + ".uid")
    uid_path.write_text("uid://c2kgm7t6j9a4p\n", encoding="ascii", newline="\n")

    print(
        f"wrote {args.output} size={canvas.size} mode={canvas.mode}; "
        f"supersample={factor}; atlas={atlas_path.name}; runtime={spatlas_path.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
