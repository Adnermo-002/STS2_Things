#!/usr/bin/env python3
"""Create coordinate reference views for manual approved-master segmentation."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
MASTER = HERE.parent / "approved_master.png"


def main() -> None:
    image = Image.open(MASTER).convert("RGBA")
    grid = image.convert("RGB")
    draw = ImageDraw.Draw(grid)
    font = ImageFont.load_default()
    for x in range(0, image.width, 32):
        color = (0, 255, 255) if x % 64 else (255, 255, 0)
        draw.line((x, 0, x, image.height - 1), fill=color, width=1)
        draw.text((x + 2, 2), str(x), fill=color, font=font)
    for y in range(0, image.height, 32):
        color = (0, 255, 255) if y % 64 else (255, 255, 0)
        draw.line((0, y, image.width - 1, y), fill=color, width=1)
        draw.text((2, y + 2), str(y), fill=color, font=font)
    grid.save(HERE / "approved_master_grid32.png")

    crops = {
        "upper": (190, 80, 700, 470),
        "lower": (210, 330, 640, 790),
        "near_arm_weapon": (60, 300, 365, 610),
        "far_arm_sack": (350, 90, 690, 430),
        "waist_layers": (240, 290, 540, 575),
    }
    for name, box in crops.items():
        crop = image.crop(box).convert("RGB").resize(
            ((box[2] - box[0]) * 2, (box[3] - box[1]) * 2),
            Image.Resampling.NEAREST,
        )
        d = ImageDraw.Draw(crop)
        for x in range(((box[0] + 15) // 16) * 16, box[2], 16):
            xx = (x - box[0]) * 2
            d.line((xx, 0, xx, crop.height - 1), fill=(0, 255, 255), width=1)
            d.text((xx + 2, 2), str(x), fill=(255, 255, 0), font=font)
        for y in range(((box[1] + 15) // 16) * 16, box[3], 16):
            yy = (y - box[1]) * 2
            d.line((0, yy, crop.width - 1, yy), fill=(0, 255, 255), width=1)
            d.text((2, yy + 2), str(y), fill=(255, 255, 0), font=font)
        crop.save(HERE / f"reference_{name}_2x.png")


if __name__ == "__main__":
    main()
