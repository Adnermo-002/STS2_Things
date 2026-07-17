#!/usr/bin/env python3
"""Create a full-character torso/pelvis occlusion-reveal edit guide."""

from pathlib import Path

from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent
MASTER = HERE / "00_reference" / "locked_master.png"
OUT = HERE / "00_reference" / "torso_context"
CANVAS = (1536, 1024)
SCALE = 2
KEY = (0, 255, 0, 255)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master = Image.open(MASTER).convert("RGBA")
    enlarged = master.resize((master.width * SCALE, master.height * SCALE), Image.Resampling.LANCZOS)
    ox = (CANVAS[0] - enlarged.width) // 2
    oy = (CANVAS[1] - enlarged.height) // 2

    target = Image.new("RGBA", CANVAS, KEY)
    target.alpha_composite(enlarged, (ox, oy))
    target.save(OUT / "torso_context_edit_target.png")

    def p(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
        return [(ox + x * SCALE, oy + y * SCALE) for x, y in points]

    upper = p([(155, 175), (290, 150), (365, 165), (390, 205), (375, 267), (315, 291), (195, 286), (145, 250), (140, 205)])
    pelvis = p([(180, 224), (375, 211), (397, 270), (370, 322), (311, 343), (218, 334), (169, 293)])

    mask = Image.new("L", CANVAS, 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon(upper, fill=255)
    draw.polygon(pelvis, fill=255)
    mask.save(OUT / "torso_context_edit_mask.png")

    preview = target.copy()
    overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    overlay_pixels = overlay.load()
    mask_pixels = mask.load()
    for y in range(CANVAS[1]):
        for x in range(CANVAS[0]):
            if mask_pixels[x, y]:
                overlay_pixels[x, y] = (255, 32, 32, 205)
    preview.alpha_composite(overlay)
    outline = ImageDraw.Draw(preview)
    outline.line(upper + [upper[0]], fill="white", width=4)
    outline.line(pelvis + [pelvis[0]], fill="white", width=4)
    preview.save(OUT / "torso_context_edit_preview.png")


if __name__ == "__main__":
    main()
