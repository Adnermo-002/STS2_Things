#!/usr/bin/env python3
"""Create the full-character far-arm occlusion-reveal edit target and map."""

from pathlib import Path

from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent
MASTER = HERE / "00_reference" / "locked_master.png"
OUT = HERE / "00_reference" / "far_arm_context"
SCALE = 2
CANVAS = (1536, 1024)
KEY = (0, 255, 0, 255)


def source_to_target(x: int, y: int) -> tuple[int, int]:
    master = Image.open(MASTER)
    offset_x = (CANVAS[0] - master.width * SCALE) // 2
    offset_y = (CANVAS[1] - master.height * SCALE) // 2
    return offset_x + x * SCALE, offset_y + y * SCALE


def poly(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    return [source_to_target(x, y) for x, y in points]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master = Image.open(MASTER).convert("RGBA")
    enlarged = master.resize((master.width * SCALE, master.height * SCALE), Image.Resampling.LANCZOS)
    x0 = (CANVAS[0] - enlarged.width) // 2
    y0 = (CANVAS[1] - enlarged.height) // 2

    target = Image.new("RGBA", CANVAS, KEY)
    target.alpha_composite(enlarged, (x0, y0))
    target.save(OUT / "far_arm_context_edit_target.png")

    mask = Image.new("L", CANVAS, 0)
    draw = ImageDraw.Draw(mask)
    # Far shoulder pauldron and the hidden upper-arm volume directly beneath it.
    draw.polygon(
        poly([(286, 98), (350, 94), (381, 122), (376, 178), (351, 202), (300, 190), (282, 149)]),
        fill=255,
    )
    # Far forearm silver bracer and its cloth/leather elbow and wrist overlaps.
    draw.polygon(
        poly([(292, 161), (357, 158), (392, 179), (389, 224), (348, 235), (294, 218), (278, 187)]),
        fill=255,
    )
    mask.save(OUT / "far_arm_context_edit_mask.png")

    preview = target.copy()
    overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    overlay_pixels = overlay.load()
    mask_pixels = mask.load()
    for y in range(CANVAS[1]):
        for x in range(CANVAS[0]):
            if mask_pixels[x, y]:
                overlay_pixels[x, y] = (255, 32, 32, 210)
    preview.alpha_composite(overlay)
    outline = ImageDraw.Draw(preview)
    outline.line(poly([(286, 98), (350, 94), (381, 122), (376, 178), (351, 202), (300, 190), (282, 149), (286, 98)]), fill="white", width=4)
    outline.line(poly([(292, 161), (357, 158), (392, 179), (389, 224), (348, 235), (294, 218), (278, 187), (292, 161)]), fill="white", width=4)
    preview.save(OUT / "far_arm_context_edit_preview.png")


if __name__ == "__main__":
    main()
