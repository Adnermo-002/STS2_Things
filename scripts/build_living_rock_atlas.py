#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class Region:
    name: str
    source: Path
    x: int
    y: int
    width: int
    height: int
    page: int


def parse_attachment_paths(source_json: Path, source_dir: Path) -> list[tuple[str, Path]]:
    data = json.loads(source_json.read_text(encoding="utf-8"))
    paths: dict[str, Path] = {}
    skins = data.get("skins", [])
    if isinstance(skins, list):
        skin_values = (skin.get("attachments", {}) for skin in skins)
    elif isinstance(skins, dict):
        skin_values = (skin for skin in skins.values())
    else:
        raise ValueError("unsupported Spine skins structure")

    for slots in skin_values:
        for slot in slots.values():
            for attachment_name, attachment in slot.items():
                if not isinstance(attachment, dict):
                    continue
                path_value = str(attachment.get("path", attachment_name))
                if path_value.lower().endswith(".png"):
                    path_value = path_value[:-4]
                image_path = source_dir / f"{path_value}.png"
                if not image_path.is_file():
                    raise FileNotFoundError(image_path)
                paths.setdefault(path_value, image_path)

    if len(paths) != 35:
        raise ValueError(f"expected 35 unique attachment paths, found {len(paths)}")
    return sorted(paths.items(), key=lambda item: item[0])


def pack_images(
    images: list[tuple[str, Path]], page_width: int, page_height: int, padding: int
) -> tuple[list[Image.Image], list[Region]]:
    pages: list[Image.Image] = []
    regions: list[Region] = []
    x = y = row_height = 0
    page_index = 0

    def new_page() -> Image.Image:
        return Image.new("RGBA", (page_width, page_height), (0, 0, 0, 0))

    pages.append(new_page())
    for name, source in images:
        with Image.open(source) as image:
            image = image.convert("RGBA")
            width, height = image.size
            if width + padding * 2 > page_width or height + padding * 2 > page_height:
                raise ValueError(f"attachment {name} does not fit atlas page")
            if x + width + padding > page_width:
                x = 0
                y += row_height + padding
                row_height = 0
            if y + height + padding > page_height:
                page_index += 1
                pages.append(new_page())
                x = y = row_height = 0
            pages[page_index].paste(image, (x, y))
            regions.append(Region(name, source, x, y, width, height, page_index))
            x += width + padding
            row_height = max(row_height, height)

    return pages, regions


def atlas_text(regions: list[Region], page_names: list[str], page_width: int, page_height: int) -> str:
    lines: list[str] = []
    for page_index, page_name in enumerate(page_names):
        lines.extend(
            [
                page_name,
                f"size:{page_width},{page_height}",
                "filter:Linear,Linear",
                "scale:1",
            ]
        )
        for region in (item for item in regions if item.page == page_index):
            lines.extend(
                [
                    region.name,
                    f"bounds:{region.x},{region.y},{region.width},{region.height}",
                ]
            )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-json", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--page-width", type=int, default=2048)
    parser.add_argument("--page-height", type=int, default=2048)
    parser.add_argument("--padding", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    images = parse_attachment_paths(args.source_json, args.source_dir)
    pages, regions = pack_images(
        images, args.page_width, args.page_height, args.padding
    )
    if len(pages) < 2:
        raise ValueError("living_rock atlas must remain multi-page")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    page_names: list[str] = []
    page_hashes: dict[str, str] = {}
    for index, page in enumerate(pages, start=1):
        page_name = f"living_rock_{index:02d}.png"
        page_path = args.output_dir / page_name
        page.save(page_path, format="PNG", optimize=False, compress_level=9)
        page_names.append(page_name)
        page_hashes[page_name] = hashlib.sha256(page_path.read_bytes()).hexdigest()

    text = atlas_text(regions, page_names, args.page_width, args.page_height)
    atlas_path = args.output_dir / "living_rock.atlas"
    atlas_path.write_text(text, encoding="utf-8", newline="\n")
    spatlas_path = args.output_dir / "living_rock.spatlas"
    spatlas_path.write_text(
        json.dumps(
            {
                "atlas_data": text,
                "normal_texture_prefix": "n",
                "source_path": "res://STS2_Things/animations/monsters/living_rock/living_rock.atlas",
                "specular_texture_prefix": "s",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
        newline="\n",
    )

    reopened = [Image.open(args.output_dir / name).convert("RGBA") for name in page_names]
    try:
        for region in regions:
            with Image.open(region.source) as source_image:
                source_rgba = source_image.convert("RGBA")
                packed = reopened[region.page].crop(
                    (region.x, region.y, region.x + region.width, region.y + region.height)
                )
                if packed.tobytes() != source_rgba.tobytes():
                    raise ValueError(f"pixel mismatch for {region.name}")
    finally:
        for image in reopened:
            image.close()

    report = {
        "pages": page_names,
        "page_size": [args.page_width, args.page_height],
        "padding": args.padding,
        "scale": 1,
        "rotated_regions": 0,
        "source_attachment_count": len(images),
        "packed_region_count": len(regions),
        "page_sha256": page_hashes,
        "regions": [
            {
                "name": region.name,
                "source": region.source.name,
                "page": page_names[region.page],
                "bounds": [region.x, region.y, region.width, region.height],
            }
            for region in regions
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    print(
        f"LIVING_ROCK_ATLAS_PASS pages={len(pages)} regions={len(regions)} "
        f"size={args.page_width}x{args.page_height} scale=1 rotated=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
