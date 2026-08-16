from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crop transparent padding from the rendered Corpse Slug death pose."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--padding", type=int, default=12)
    args = parser.parse_args()

    image = Image.open(args.source).convert("RGBA")
    alpha_bounds = image.getchannel("A").getbbox()
    if alpha_bounds is None:
        raise ValueError(f"render is fully transparent: {args.source}")

    left, top, right, bottom = alpha_bounds
    box = (
        max(0, left - args.padding),
        max(0, top - args.padding),
        min(image.width, right + args.padding),
        min(image.height, bottom + args.padding),
    )
    cropped = image.crop(box)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(args.destination, optimize=True)
    alpha_pixels = sum(cropped.getchannel("A").histogram()[1:])
    print(
        f"source={image.size} alpha_bounds={alpha_bounds} crop={box} "
        f"output={cropped.size} alpha_pixels={alpha_pixels}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
