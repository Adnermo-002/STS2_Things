#!/usr/bin/env python3
"""Normalize Gravetide UI assets from approved ImageGen source images.

This script deliberately has no drawing, recoloring, silhouette expansion, or
procedural-icon code.  It is limited to the allowed production transforms for
ImageGen originals: crop, alpha-preserving fit, resize, PNG format conversion,
and output-contract validation.

The Power source is already available.  The map and run-history sources are
separate ImageGen deliverables; until they arrive, their previously exported
runtime files are validated but never regenerated from the creature atlas.
Use --require-direct-ui-sources in the release gate to reject that temporary
state.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
POWER_SOURCE = (
    ROOT / "source_assets/powers/gravetide_digestion_simple_imagegen_alpha.png"
)


@dataclass(frozen=True)
class DirectAsset:
    source: Path
    output: Path
    size: tuple[int, int]
    margin: int


DIRECT_ASSETS = (
    DirectAsset(
        ROOT / "source_assets/map/gravetide_slug_boss_icon_imagegen.png",
        ROOT / "images/map/gravetide_slug_boss_icon.png",
        (352, 300),
        18,
    ),
    DirectAsset(
        ROOT / "source_assets/map/gravetide_slug_boss_icon_outline_imagegen.png",
        ROOT / "images/map/gravetide_slug_boss_icon_outline.png",
        (352, 300),
        18,
    ),
    DirectAsset(
        ROOT / "source_assets/ui/run_history/gravetide_slug_boss_encounter_imagegen.png",
        ROOT / "images/ui/run_history/gravetide_slug_boss_encounter.png",
        (88, 88),
        5,
    ),
    DirectAsset(
        ROOT / "source_assets/ui/run_history/gravetide_slug_boss_encounter_outline_imagegen.png",
        ROOT / "images/ui/run_history/gravetide_slug_boss_encounter_outline.png",
        (88, 88),
        5,
    ),
)


def require_imagegen_source(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing ImageGen source: {path}")
    if "imagegen" not in path.stem.lower():
        raise RuntimeError(f"UI source is not named as an ImageGen deliverable: {path}")


def fit_alpha_source(
    source: Path,
    output_size: tuple[int, int],
    margin: int,
    crop_box: tuple[int, int, int, int] | None = None,
) -> Image.Image:
    """Crop and fit an ImageGen cutout without changing its painted pixels."""

    require_imagegen_source(source)
    image = Image.open(source).convert("RGBA")
    if crop_box is not None:
        image = image.crop(crop_box)

    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise RuntimeError(f"ImageGen source has no visible pixels: {source}")
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


def save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)


def validate_output(path: Path, expected_size: tuple[int, int]) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing UI output: {path}")
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
        if image.size != expected_size:
            raise RuntimeError(
                f"{path} has size {image.size}; expected {expected_size}"
            )
        if image.getchannel("A").getbbox() is None:
            raise RuntimeError(f"{path} is fully transparent")


def build_power() -> None:
    # This crop intentionally retains only the stomach vortex and one pale bone.
    # The discarded antennae and gold body marking were the source of the old
    # icon's noisy, multi-symbol read at 64 pixels.
    power = fit_alpha_source(
        POWER_SOURCE,
        (256, 256),
        margin=10,
        crop_box=(350, 620, 1940, 2220),
    )
    power_path = ROOT / "images/powers/gravetide_digestion_power.png"
    packed_path = ROOT / "images/powers/gravetide_digestion_power_packed.png"
    save_png(power, power_path)
    save_png(power.resize((64, 64), Image.Resampling.LANCZOS), packed_path)
    validate_output(power_path, (256, 256))
    validate_output(packed_path, (64, 64))


def build_direct_assets(require_all: bool) -> list[str]:
    missing = [asset.source for asset in DIRECT_ASSETS if not asset.source.is_file()]
    if missing:
        if require_all:
            rendered = "\n  ".join(str(path) for path in missing)
            raise FileNotFoundError(f"Missing direct ImageGen UI sources:\n  {rendered}")
        for asset in DIRECT_ASSETS:
            validate_output(asset.output, asset.size)
        return [str(path.relative_to(ROOT)) for path in missing]

    for asset in DIRECT_ASSETS:
        save_png(
            fit_alpha_source(asset.source, asset.size, asset.margin),
            asset.output,
        )
        validate_output(asset.output, asset.size)
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-direct-ui-sources",
        action="store_true",
        help="Fail until map and run-history ImageGen originals are available.",
    )
    args = parser.parse_args()

    build_power()
    pending = build_direct_assets(args.require_direct_ui_sources)
    if pending:
        print("GRAVETIDE_UI_ASSET_BUILD_PENDING_DIRECT_IMAGEGEN=" + ";".join(pending))
    print("GRAVETIDE_UI_ASSET_BUILD_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
