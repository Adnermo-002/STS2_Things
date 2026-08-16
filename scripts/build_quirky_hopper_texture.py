#!/usr/bin/env python3
"""Build the Quirky Hopper's blue/orange Spine atlas and rear pink bow.

Only the four ``bod`` atlas regions are recolored.  Their original alpha,
linework, luminance and painted shading are retained, so the result remains
compatible with the native Thieving Hopper skeleton and animation set.  The bow
is emitted as a separate transparent texture for a ``SpineBoneNode`` bound to
the native ``head`` bone.  That node renders behind the SpineSprite, keeping the
whole bow visible without painting over the face.
"""

from __future__ import annotations

import argparse
import colorsys
import hashlib
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    ROOT
    / "source_assets"
    / "monsters"
    / "quirky_hopper_bow"
    / "thievinghopper_source.png"
)
DEFAULT_BOW_SOURCE = (
    ROOT
    / "source_assets"
    / "monsters"
    / "quirky_hopper_bow"
    / "bow_transparent_full.png"
)
DEFAULT_DESTINATION = (
    ROOT
    / "STS2_Things"
    / "animations"
    / "monsters"
    / "quirky_hopper"
    / "quirkyhopper.png"
)
DEFAULT_BOW_DESTINATION = (
    ROOT
    / "STS2_Things"
    / "animations"
    / "monsters"
    / "quirky_hopper"
    / "quirky_hopper_bow.png"
)
NATIVE_SOURCE_SHA256 = "af9800cc5b70ea7f6efa8f0fa346169ce03d62d4a1ff0c7748128e3df9b07636"
BOW_SOURCE_SHA256 = "73eca8ec0d1b77f564b97fd9f4eb1b0f94bf03fa559e2795b9c729c7de476111"
ATLAS_SIZE = (1269, 269)
BOW_WIDTH = 140
BOW_ROTATION_DEGREES = -8


# Physical pixel rectangles in the 1269x269 native atlas.  ``bod 1`` is stored
# rotated 90 degrees, hence its on-page width/height are swapped.
SEGMENTS = (
    ("bod 1", (931, 54, 1055, 112), 0.585, 0.82, 0.88),  # cobalt blue
    ("bod 2", (1205, 47, 1244, 79), 0.065, 0.90, 1.00),  # vivid orange
    ("bod 3", (1216, 81, 1261, 119), 0.585, 0.82, 0.88),
    ("bod 4", (1211, 184, 1259, 223), 0.065, 0.90, 1.00),
)


def recolor_region(
    image: Image.Image,
    box: tuple[int, int, int, int],
    hue: float,
    minimum_saturation: float,
    value_scale: float,
) -> None:
    pixels = image.load()
    left, top, right, bottom = box
    for y in range(top, bottom):
        for x in range(left, right):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                continue

            _, saturation, value = colorsys.rgb_to_hsv(
                red / 255.0,
                green / 255.0,
                blue / 255.0,
            )
            saturation = max(saturation, minimum_saturation)
            value = min(1.0, value * value_scale)
            out_red, out_green, out_blue = colorsys.hsv_to_rgb(
                hue,
                saturation,
                value,
            )
            pixels[x, y] = (
                round(out_red * 255),
                round(out_green * 255),
                round(out_blue * 255),
                alpha,
            )


def build_bow(source: Path, destination: Path) -> None:
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_digest != BOW_SOURCE_SHA256:
        raise ValueError(
            f"expected canonical pink bow source {BOW_SOURCE_SHA256}, "
            f"got {source_digest}"
        )

    with Image.open(source) as source_image:
        bow = source_image.convert("RGBA")
    alpha_box = bow.getchannel("A").getbbox()
    if alpha_box is None:
        raise ValueError("pink bow source is fully transparent")

    bow = bow.crop(alpha_box)
    target_height = max(1, round(bow.height * BOW_WIDTH / bow.width))
    bow = bow.resize((BOW_WIDTH, target_height), Image.Resampling.LANCZOS)
    bow = bow.rotate(
        BOW_ROTATION_DEGREES,
        resample=Image.Resampling.BICUBIC,
        expand=True,
    )
    rotated_alpha_box = bow.getchannel("A").getbbox()
    if rotated_alpha_box is None:
        raise ValueError("generated pink bow is fully transparent")
    bow = bow.crop(rotated_alpha_box)

    destination.parent.mkdir(parents=True, exist_ok=True)
    bow.save(destination, optimize=True)


def build(
    source: Path,
    destination: Path,
    bow_source: Path = DEFAULT_BOW_SOURCE,
    bow_destination: Path = DEFAULT_BOW_DESTINATION,
) -> None:
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_digest != NATIVE_SOURCE_SHA256:
        raise ValueError(
            f"expected native Thieving Hopper atlas {NATIVE_SOURCE_SHA256}, "
            f"got {source_digest}"
        )

    with Image.open(source) as source_image:
        image = source_image.convert("RGBA")
    if image.size != ATLAS_SIZE:
        raise ValueError(f"expected native {ATLAS_SIZE} atlas, got {image.size}")

    for _, box, hue, saturation, value_scale in SEGMENTS:
        recolor_region(image, box, hue, saturation, value_scale)

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, optimize=True)
    build_bow(bow_source, bow_destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, nargs="?", default=DEFAULT_SOURCE)
    parser.add_argument("destination", type=Path, nargs="?", default=DEFAULT_DESTINATION)
    parser.add_argument("--bow-source", type=Path, default=DEFAULT_BOW_SOURCE)
    parser.add_argument("--bow-destination", type=Path, default=DEFAULT_BOW_DESTINATION)
    args = parser.parse_args()
    build(args.source, args.destination, args.bow_source, args.bow_destination)
    print(f"wrote {args.destination}")
    print(f"wrote {args.bow_destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
