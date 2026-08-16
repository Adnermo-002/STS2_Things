#!/usr/bin/env python3
"""Inventory vanilla STS2 asset families and render reference contact sheets."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VANILLA = ROOT.parent / "STS2-V110"
BACKGROUND_FOLDERS = (
    "ceremonial_beast_boss",
    "kaiser_crab_boss",
    "knowledge_demon_boss",
    "lagavulin_matriarch_boss",
    "queen_boss",
    "soul_fysh_boss",
    "test_subject_boss",
    "the_insatiable_boss",
    "the_kin_boss",
    "vantom_boss",
    "waterfall_giant_boss",
    "underdocks",
)


def image_record(path: Path, root: Path) -> dict[str, object]:
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
        rgb = image.convert("RGB").resize((128, 128), Image.Resampling.BILINEAR)
        quantized = rgb.quantize(colors=16, method=Image.Quantize.FASTOCTREE)
        palette = quantized.getpalette() or []
        counts = Counter(quantized.get_flattened_data())
        dominant = []
        for index, count in counts.most_common(8):
            start = index * 3
            dominant.append(
                {
                    "rgb": palette[start : start + 3],
                    "share": round(count / (128 * 128), 4),
                }
            )
        alpha = image.getchannel("A")
        opaque = sum(alpha.histogram()[1:])
        return {
            "path": path.relative_to(root).as_posix(),
            "size": list(image.size),
            "mode": opened.mode,
            "alpha_bbox": list(alpha.getbbox() or (0, 0, 0, 0)),
            "nonzero_alpha_share": round(opaque / (image.width * image.height), 4),
            "dominant_palette": dominant,
        }


def collect_backgrounds(root: Path) -> list[dict[str, object]]:
    records = []
    scene_root = root / "scenes/backgrounds"
    path_pattern = re.compile(r'path="res://([^"]+\.png)"')
    for name in BACKGROUND_FOLDERS:
        folder = scene_root / name
        texture_paths: list[Path] = []
        for scene in sorted(folder.rglob("*.tscn")):
            for relative in path_pattern.findall(scene.read_text(encoding="utf-8")):
                path = root / relative
                if path.is_file() and path not in texture_paths:
                    texture_paths.append(path)
        records.append(
            {
                "family": name,
                "scene_count": len(list(folder.rglob("*.tscn"))),
                "textures": [image_record(path, root) for path in texture_paths],
            }
        )
    return records


def collect_monsters(root: Path) -> list[dict[str, object]]:
    records = []
    animation_root = root / "animations/monsters"
    for folder in sorted(path for path in animation_root.iterdir() if path.is_dir()):
        pngs = sorted(folder.glob("*.png"))
        atlases = sorted(folder.glob("*.atlas"))
        if not pngs or not atlases:
            continue
        records.append(
            {
                "family": folder.name,
                "atlas_files": [path.name for path in atlases],
                "textures": [image_record(path, root) for path in pngs],
            }
        )
    return records


def collect_icons(root: Path) -> list[dict[str, object]]:
    groups = {
        "boss_map": root / "images/map/placeholder",
        "boss_history": root / "images/ui/run_history",
        "powers": root / "images/powers",
    }
    records = []
    for name, folder in groups.items():
        if name == "boss_map":
            paths = sorted(folder.glob("*_boss_icon*.png"))
        elif name == "boss_history":
            paths = sorted(folder.glob("*_boss*.png"))
        else:
            paths = sorted(folder.glob("*_power.png"))
        records.append(
            {"family": name, "textures": [image_record(path, root) for path in paths]}
        )
    return records


def resolve_paths(records: list[dict[str, object]], root: Path) -> list[tuple[str, Path]]:
    resolved = []
    for family in records:
        name = str(family["family"])
        textures = family.get("textures", [])
        for texture in textures:
            relative = str(texture["path"])
            resolved.append((name, root / relative))
    return resolved


def representative_backgrounds(
    records: list[dict[str, object]],
    limit: int = 3,
) -> list[dict[str, object]]:
    curated = []
    excluded_tokens = ("vfx/", "noise", "mask", "particle", "gradient", "light.png")
    for family in records:
        textures = [
            texture
            for texture in family.get("textures", [])
            if "images/rooms/" in str(texture["path"])
            and not any(token in str(texture["path"]).lower() for token in excluded_tokens)
        ]
        textures.sort(
            key=lambda texture: (
                int(texture["size"][0])
                * int(texture["size"][1])
                * float(texture["nonzero_alpha_share"])
            ),
            reverse=True,
        )
        curated.append({"family": family["family"], "textures": textures[:limit]})
    return curated


def render_contact_sheet(
    records: list[dict[str, object]],
    root: Path,
    output: Path,
    cell: tuple[int, int] = (360, 230),
    columns: int = 4,
) -> None:
    items = resolve_paths(records, root)
    rows = (len(items) + columns - 1) // columns
    sheet = Image.new("RGB", (cell[0] * columns, cell[1] * rows), (25, 25, 31))
    draw = ImageDraw.Draw(sheet)
    for index, (family, path) in enumerate(items):
        x = (index % columns) * cell[0]
        y = (index // columns) * cell[1]
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
        preview = ImageOps.contain(
            image,
            (cell[0] - 20, cell[1] - 40),
            method=Image.Resampling.LANCZOS,
        )
        frame = Image.new("RGBA", preview.size, (42, 42, 51, 255))
        frame.alpha_composite(preview)
        sheet.paste(frame.convert("RGB"), (x + (cell[0] - preview.width) // 2, y + 24))
        label = f"{family} / {path.name}"
        draw.text((x + 8, y + 5), label[:54], fill=(225, 225, 220))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vanilla-root", type=Path, default=DEFAULT_VANILLA)
    parser.add_argument(
        "--category",
        choices=("backgrounds", "monsters", "icons", "all"),
        default="all",
    )
    parser.add_argument("--out", type=Path, default=ROOT / "build/style_audit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.vanilla_root.resolve()
    output = args.out.resolve()
    collectors = {
        "backgrounds": collect_backgrounds,
        "monsters": collect_monsters,
        "icons": collect_icons,
    }
    categories = collectors if args.category == "all" else {args.category: collectors[args.category]}
    for name, collector in categories.items():
        records = collector(root)
        output.mkdir(parents=True, exist_ok=True)
        (output / f"{name}.json").write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        render_contact_sheet(records, root, output / f"{name}_contact.png")
        if name == "backgrounds":
            render_contact_sheet(
                representative_backgrounds(records),
                root,
                output / "backgrounds_representative_contact.png",
                cell=(480, 290),
                columns=3,
            )
        print(
            f"{name}: families={len(records)} "
            f"textures={sum(len(record.get('textures', [])) for record in records)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
