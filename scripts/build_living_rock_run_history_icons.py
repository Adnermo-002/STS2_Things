#!/usr/bin/env python3
"""Build the Living Rock boss run-history icon pair from the approved map icons.

Resolves the missing-resource error in the real game:
    ERROR: No loader found for resource:
           res://images/ui/run_history/living_rock_boss_encounter.png

Unlike the Gravetide peers, no ImageGen run-history original exists for Living
Rock (no source_assets/ui/run_history deliverable). This build applies only the
allowed production transforms from the existing approved contract assets:
    images/map/living_rock_boss_icon.png          (779x652 RGBA)
    images/map/living_rock_boss_icon_outline.png  (779x652 RGBA)
to the UI contract the other five boss encounters already satisfy:
    images/ui/run_history/<slug>_boss_encounter.png           (88x88 RGBA)
    images/ui/run_history/<slug>_boss_encounter_outline.png   (88x88 RGBA)
The transform (alpha-bbox crop, alpha-preserving contain fit, transparent
canvas composite) is the same fit used by build_gravetide_ui_assets.py for the
matching 88x88 run-history icons (margin=5), so the result keeps the sibling
style. If an ImageGen original for the run-history icon later becomes
available, replace the source below with it and keep the same transform.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
MAP_ICON = ROOT / "images/map/living_rock_boss_icon.png"
MAP_ICON_OUTLINE = ROOT / "images/map/living_rock_boss_icon_outline.png"
OUTPUT = ROOT / "images/ui/run_history/living_rock_boss_encounter.png"
OUTPUT_OUTLINE = ROOT / "images/ui/run_history/living_rock_boss_encounter_outline.png"
SIZE = (88, 88)
MARGIN = 5


def fit_alpha_source(source: Path, output_size: tuple[int, int], margin: int) -> Image.Image:
    """Crop the alpha bounding box and fit it into the icon canvas."""
    image = Image.open(source).convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise RuntimeError(f"Source has no visible pixels: {source}")
    subject = image.crop(bbox)
    fitted = ImageOps.contain(
        subject,
        (output_size[0] - margin * 2, output_size[1] - margin * 2),
        method=Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", output_size, (0, 0, 0, 0))
    canvas.alpha_composite(
        fitted,
        ((output_size[0] - fitted.width) // 2, (output_size[1] - fitted.height) // 2),
    )
    return canvas


def validate_output(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing output: {path}")
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
        if image.size != SIZE:
            raise RuntimeError(f"{path} has size {image.size}; expected {SIZE}")
        if image.getchannel("A").getbbox() is None:
            raise RuntimeError(f"{path} is fully transparent")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Only validate existing outputs.")
    args = parser.parse_args()

    if not args.check:
        for source, output in ((MAP_ICON, OUTPUT), (MAP_ICON_OUTLINE, OUTPUT_OUTLINE)):
            if not source.is_file():
                raise FileNotFoundError(f"Missing map icon source: {source}")
            output.parent.mkdir(parents=True, exist_ok=True)
            fit_alpha_source(source, SIZE, MARGIN).save(output, optimize=True)
    validate_output(OUTPUT)
    validate_output(OUTPUT_OUTLINE)
    print("LIVING_ROCK_RUN_HISTORY_ICONS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())