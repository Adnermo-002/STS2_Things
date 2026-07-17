#!/usr/bin/env python3
"""Mirror the original RGBA monster artwork into the shipping asset tree.

The source PNG is the complete visual contract.  This build step intentionally
performs no edge filtering, grain, brightness adjustment, outline generation,
palette conversion, or other pixel processing.  Copying the encoded PNG bytes
also makes repeated builds deterministic while preserving every RGBA pixel.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "source_assets" / "monsters"
DEFAULT_OUTPUT = ROOT / "images" / "monsters"


def _load_rgba(path: Path) -> tuple[tuple[int, int], bytes]:
    """Load and validate one source/shipping texture without transforming it."""

    with Image.open(path) as image:
        image.load()
        if image.mode != "RGBA":
            raise ValueError(f"monster texture must be encoded as RGBA: {path}")
        if image.getchannel("A").getbbox() is None:
            raise ValueError(f"monster texture has no non-transparent pixels: {path}")
        return image.size, image.tobytes()


def build(source_dir: Path, output_dir: Path) -> list[Path]:
    """Copy every root monster PNG byte-for-byte and verify decoded RGBA identity."""

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for source_path in sorted(source_dir.glob("*.png")):
        source_size, source_pixels = _load_rgba(source_path)
        destination = output_dir / source_path.name
        destination.write_bytes(source_path.read_bytes())

        shipping_size, shipping_pixels = _load_rgba(destination)
        if shipping_size != source_size or shipping_pixels != source_pixels:
            raise RuntimeError(
                f"shipping monster texture differs from its RGBA source: {destination}"
            )
        outputs.append(destination)
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.source.is_dir():
        raise SystemExit(f"monster source directory missing: {args.source}")
    outputs = build(args.source.resolve(), args.output.resolve())
    if not outputs:
        raise SystemExit(f"no PNG sources found under {args.source}")
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
