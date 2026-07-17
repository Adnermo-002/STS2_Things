#!/usr/bin/env python3
"""Build a visual-only bind mockup from the v7 donor sheet.

This does not feed the runtime. It exists to reject bad part semantics before
master ownership masks and Spine data are authored.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
PARTS = ROOT / "donor_parts"
OUT = ROOT / "donor_bind_mockup.png"

# center x/y in the 1254 master canvas, uniform scale, clockwise degrees.
POSE = {
    "01_cape_upper": ((680, 485), 1.18, -7),
    "02_cape_mid": ((850, 620), 1.24, -8),
    "03_cape_tail": ((1032, 760), 1.18, -4),
    "06_loot_sack": ((883, 505), 1.05, 0),
    "08_sack_knot": ((833, 350), 0.95, 0),
    "09_sack_strap_free": ((700, 425), 1.10, -8),
    "20_far_thigh": ((805, 790), 0.95, -8),
    "22_far_shin": ((885, 888), 0.82, 3),
    "24_far_boot": ((934, 968), 0.95, 0),
    "12_far_upper_arm": ((815, 515), 0.82, -18),
    "18_far_shoulder_plate": ((766, 453), 1.00, 5),
    "14_far_forearm": ((785, 580), 0.74, -32),
    "05_torso_core": ((650, 600), 1.13, 0),
    "07_pelvis_waist_cloth": ((650, 742), 1.30, 0),
    "21_near_thigh": ((525, 778), 0.98, 3),
    "23_near_shin": ((540, 892), 0.90, 0),
    "25_near_boot": ((540, 970), 1.05, 0),
    "00_hooded_head": ((490, 405), 1.22, -2),
    "11_near_upper_arm": ((420, 625), 0.80, 15),
    "15_near_forearm": ((350, 735), 0.88, 18),
    "16_near_dagger_hand": ((302, 827), 0.90, 12),
    "19_dagger": ((205, 885), 1.02, 9),
    "10_belt_and_pouch": ((675, 696), 1.14, 0),
    "13_far_hand_strap_grip": ((685, 514), 0.72, -3),
    "04_scarf_front": ((530, 506), 1.23, -1),
}

DRAW_ORDER = [
    "01_cape_upper", "02_cape_mid", "03_cape_tail",
    "06_loot_sack", "08_sack_knot", "09_sack_strap_free",
    "20_far_thigh", "22_far_shin", "24_far_boot",
    "12_far_upper_arm", "18_far_shoulder_plate", "14_far_forearm",
    "05_torso_core", "07_pelvis_waist_cloth",
    "21_near_thigh", "23_near_shin", "25_near_boot",
    "00_hooded_head",
    "11_near_upper_arm", "15_near_forearm", "16_near_dagger_hand",
    "19_dagger", "10_belt_and_pouch", "13_far_hand_strap_grip",
    "04_scarf_front",
]


def find_part(stem: str) -> Path:
    path = PARTS / f"{stem}.png"
    if not path.is_file():
        raise RuntimeError(f"Missing donor file for {stem}: {path}")
    return path


def transformed(path: Path, scale: float, clockwise_deg: float) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    image = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    return image.rotate(clockwise_deg, resample=Image.Resampling.BICUBIC, expand=True)


def main() -> None:
    canvas = Image.new("RGBA", (1254, 1254), (0, 0, 0, 0))
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((390, 965, 1020, 1038), fill=(2, 4, 7, 95))
    canvas.alpha_composite(shadow)
    for stem in DRAW_ORDER:
        (cx, cy), scale, angle = POSE[stem]
        image = transformed(find_part(stem), scale, angle)
        canvas.alpha_composite(image, (round(cx - image.width / 2), round(cy - image.height / 2)))
    canvas.save(OUT)
    print(f"THIEF_V7_DONOR_BIND_WRITTEN {OUT}")


if __name__ == "__main__":
    main()
