#!/usr/bin/env python3
"""Build the Thief Raider v10 near-dagger-arm image-to-image guide.

This is a deterministic reference compositor.  It never paints production pixels:
all visible art is copied from the locked current master or the v9 ownership masks,
while cyan dashed curves describe the *shape intent* of concealed overlap only.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
V10_ROOT = HERE.parent
V9_ROOT = V10_ROOT.parent / "thief_raider_v9"
VISIBLE_ROOT = V9_ROOT / "04_production_attachments" / "visible"

MASTER_PATH = HERE / "current_master.png"
GUIDE_PATH = HERE / "near_dagger_arm_i2i_guide_1536x1024.png"
MANIFEST_PATH = HERE / "near_dagger_arm_i2i_guide.manifest.json"

PART_PATHS = {
    "near_upper_arm": VISIBLE_ROOT / "18_near_upper_arm.png",
    "near_forearm": VISIBLE_ROOT / "19_near_forearm.png",
    "near_dagger_hand": VISIBLE_ROOT / "21_near_dagger_hand.png",
    "dagger": VISIBLE_ROOT / "22_dagger.png",
}

CANVAS = (1536, 1024)
BG = (18, 21, 27, 255)
PANEL = (27, 31, 39, 255)
PANEL_EDGE = (71, 79, 94, 255)
TEXT = (237, 240, 244, 255)
MUTED = (155, 166, 181, 255)
CYAN = (65, 224, 221, 255)
AMBER = (255, 188, 86, 255)
GREEN = (106, 231, 160, 255)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


F_TITLE = font(30, True)
F_H2 = font(21, True)
F_BODY = font(16)
F_SMALL = font(13)
F_SLOT = font(18, True)


def checker(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], cell: int = 16) -> None:
    x0, y0, x1, y1 = box
    colors = ((38, 43, 52, 255), (48, 54, 64, 255))
    for y in range(y0, y1, cell):
        for x in range(x0, x1, cell):
            parity = ((x - x0) // cell + (y - y0) // cell) & 1
            draw.rectangle((x, y, min(x + cell - 1, x1 - 1), min(y + cell - 1, y1 - 1)), fill=colors[parity])


def rounded_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 18) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=PANEL, outline=PANEL_EDGE, width=2)


def cubic_points(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    steps: int = 28,
) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for index in range(steps + 1):
        t = index / steps
        u = 1.0 - t
        x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
        result.append((x, y))
    return result


def dashed_polyline(
    draw: ImageDraw.ImageDraw,
    points: Sequence[tuple[float, float]],
    fill: tuple[int, int, int, int],
    width: int = 3,
    dash: float = 9.0,
    gap: float = 7.0,
) -> None:
    """Draw a distance-consistent dashed line through a polyline."""
    drawing = True
    remaining = dash
    for start, end in zip(points, points[1:]):
        x0, y0 = start
        x1, y1 = end
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length == 0:
            continue
        position = 0.0
        while position < length:
            run = min(remaining, length - position)
            if drawing:
                a = position / length
                b = (position + run) / length
                draw.line(
                    (x0 + dx * a, y0 + dy * a, x0 + dx * b, y0 + dy * b),
                    fill=fill,
                    width=width,
                )
            position += run
            remaining -= run
            if remaining <= 1e-6:
                drawing = not drawing
                remaining = dash if drawing else gap


def dashed_closed_beziers(
    draw: ImageDraw.ImageDraw,
    curves: Iterable[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]],
    fill: tuple[int, int, int, int] = CYAN,
    width: int = 3,
) -> None:
    points: list[tuple[float, float]] = []
    for curve in curves:
        segment = cubic_points(*curve)
        if points and points[-1] == segment[0]:
            points.extend(segment[1:])
        else:
            points.extend(segment)
    dashed_polyline(draw, points, fill=fill, width=width)


def contain(image: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    scale = min(max_size[0] / image.width, max_size[1] / image.height)
    return image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)


def paste_center(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    x = x0 + (x1 - x0 - image.width) // 2
    y = y0 + (y1 - y0 - image.height) // 2
    canvas.alpha_composite(image, (x, y))
    return (x, y, x + image.width, y + image.height)


def draw_source_badge(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.rounded_rectangle((x, y, x + 168, y + 27), radius=9, fill=(32, 79, 66, 255))
    draw.ellipse((x + 9, y + 8, x + 19, y + 18), fill=GREEN)
    draw.text((x + 27, y + 5), "MASTER VISIBLE PIXELS", font=F_SMALL, fill=GREEN)


def draw_underlap_key(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    dashed_polyline(draw, [(x, y + 10), (x + 50, y + 10)], CYAN, width=3, dash=8, gap=6)
    draw.text((x + 62, y), "concealed continuation contour", font=F_SMALL, fill=MUTED)


def draw_upper_arm_hint(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    # The shoulder pivot is near the upper-centre of this ownership crop, not at
    # its right edge.  Use a short asymmetric cloth flap beneath the pauldron.
    dashed_polyline(draw, cubic_points(
        (x0 + .22*w, y0 + .08*h), (x0 + .25*w, y0 - 8),
        (x0 + .34*w, y0 - 18), (x0 + .40*w, y0 - 20)), CYAN, width=3)
    dashed_polyline(draw, cubic_points(
        (x0 + .70*w, y0 + .10*h), (x0 + .65*w, y0 - 4),
        (x0 + .57*w, y0 - 15), (x0 + .50*w, y0 - 18)), CYAN, width=3)
    # The elbow flap follows the down-left arm axis and remains deliberately short.
    dashed_polyline(draw, cubic_points(
        (x0 + .05*w, y0 + .58*h), (x0 - 8, y0 + .66*h),
        (x0 - 15, y0 + .72*h), (x0 - 18, y0 + .78*h)), CYAN, width=3)
    dashed_polyline(draw, cubic_points(
        (x0 + .24*w, y0 + .88*h), (x0 + .12*w, y0 + .91*h),
        (x0 - 7, y0 + .85*h), (x0 - 14, y0 + .81*h)), CYAN, width=3)


def draw_forearm_hint(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    # Elbow cloth folds back under the upper sleeve around the actual diagonal joint.
    dashed_polyline(draw, cubic_points(
        (x0 + .38*w, y0 + .13*h), (x0 + .39*w, y0 - 3),
        (x0 + .46*w, y0 - 13), (x0 + .51*w, y0 - 15)), CYAN, width=3)
    dashed_polyline(draw, cubic_points(
        (x0 + .79*w, y0 + .11*h), (x0 + .75*w, y0 - 2),
        (x0 + .67*w, y0 - 11), (x0 + .60*w, y0 - 14)), CYAN, width=3)
    # Bridge only the hidden cuff region behind the hand so the source crescent
    # becomes one semantic attachment without turning the end into a round plug.
    dashed_polyline(draw, cubic_points(
        (x0 + .06*w, y0 + .70*h), (x0 + .20*w, y0 + .77*h),
        (x0 + .39*w, y0 + .75*h), (x0 + .52*w, y0 + .77*h)), CYAN, width=3)
    dashed_polyline(draw, cubic_points(
        (x0 + .12*w, y0 + .84*h), (x0 + .25*w, y0 + .86*h),
        (x0 + .41*w, y0 + .82*h), (x0 + .55*w, y0 + .81*h)), CYAN, width=3)


def draw_hand_hint(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    # Short asymmetric wrist bridge follows the hand plane and disappears below the bracer.
    dashed_polyline(draw, cubic_points(
        (x0 + .72*w, y0 + .08*h), (x0 + .86*w, y0 - 9),
        (x1 + 11, y0 - 10), (x1 + 17, y0 - 4)), CYAN, width=3)
    dashed_polyline(draw, cubic_points(
        (x0 + .93*w, y0 + .40*h), (x1 + 1, y0 + .31*h),
        (x1 + 12, y0 + 12), (x1 + 16, y0 + 4)), CYAN, width=3)


def draw_dagger_hint(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    # Only a narrow aligned tang continues beneath the grip; no second visible handle.
    dashed_polyline(draw, cubic_points(
        (x0 + .82*w, y0 + .12*h), (x0 + .89*w, y0 + .08*h),
        (x1 + 5, y0 - 4), (x1 + 13, y0 - 6)), CYAN, width=3)
    dashed_polyline(draw, cubic_points(
        (x0 + .90*w, y0 + .27*h), (x1 - 2, y0 + .19*h),
        (x1 + 6, y0 + 4), (x1 + 12, y0 + 1)), CYAN, width=3)


def draw_slot(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    panel_box: tuple[int, int, int, int],
    number: int,
    title: str,
    subtitle: str,
    source: Image.Image,
    max_size: tuple[int, int],
    hint,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = panel_box
    rounded_panel(draw, panel_box)
    draw.rounded_rectangle((x0 + 18, y0 + 18, x0 + 51, y0 + 51), radius=9, fill=(65, 78, 98, 255))
    draw.text((x0 + 29, y0 + 21), str(number), font=F_SLOT, fill=TEXT, anchor="ma")
    draw.text((x0 + 64, y0 + 17), title, font=F_SLOT, fill=TEXT)
    draw.text((x0 + 64, y0 + 43), subtitle, font=F_SMALL, fill=MUTED)
    draw_source_badge(draw, x0 + 18, y0 + 73)

    art_box = (x0 + 45, y0 + 115, x1 - 45, y1 - 57)
    checker(draw, art_box, cell=14)
    draw.rounded_rectangle(art_box, radius=12, outline=(58, 66, 78, 255), width=2)
    enlarged = contain(source, max_size)
    placed = paste_center(canvas, enlarged, art_box)
    hint(draw, placed)
    draw_underlap_key(draw, x0 + 25, y1 - 39)
    return placed


def main() -> None:
    missing = [str(path) for path in [MASTER_PATH, *PART_PATHS.values()] if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing locked guide source(s): " + ", ".join(missing))

    master = Image.open(MASTER_PATH).convert("RGBA")
    parts = {key: Image.open(path).convert("RGBA") for key, path in PART_PATHS.items()}

    canvas = Image.new("RGBA", CANVAS, BG)
    draw = ImageDraw.Draw(canvas)

    # Header and the locked full-body reference.
    draw.text((42, 24), "THIEF RAIDER v10  /  NEAR DAGGER ARM", font=F_TITLE, fill=TEXT)
    draw.text((42, 61), "image-to-image input guide — contour hints are not painted production pixels", font=F_BODY, fill=MUTED)

    full_panel = (34, 94, 666, 527)
    rounded_panel(draw, full_panel)
    draw.text((54, 111), "LOCKED IDENTITY MASTER", font=F_H2, fill=TEXT)
    draw.text((54, 141), "compact crouch · left-facing 3/4 · original palette", font=F_SMALL, fill=MUTED)
    full_art = contain(master, (572, 350))
    full_box = paste_center(canvas, full_art, (56, 163, 644, 511))

    # Mark the near-arm region on the scaled full master.
    fx0, fy0, fx1, fy1 = full_box
    sx = (fx1 - fx0) / master.width
    sy = (fy1 - fy0) / master.height
    crop_src = (0, 184, 225, 414)
    crop_on_full = (
        round(fx0 + crop_src[0] * sx),
        round(fy0 + crop_src[1] * sy),
        round(fx0 + crop_src[2] * sx),
        round(fy0 + crop_src[3] * sy),
    )
    draw.rounded_rectangle(crop_on_full, radius=8, outline=AMBER, width=3)
    draw.text((crop_on_full[0] + 8, crop_on_full[1] + 6), "NEAR ARM", font=F_SMALL, fill=AMBER)

    # Enlarged context crop: includes shoulder plate, complete arm, hand, and blade.
    zoom_panel = (34, 545, 666, 986)
    rounded_panel(draw, zoom_panel)
    draw.text((54, 562), "BIND-POSE CONTEXT", font=F_H2, fill=TEXT)
    draw.text((54, 592), "keep camera, scale, light direction, grip and chain angle", font=F_SMALL, fill=MUTED)
    zoom = master.crop(crop_src)
    zoom = contain(zoom, (426, 352))
    zoom_box = (54, 621, 496, 971)
    checker(draw, zoom_box, cell=14)
    draw.rounded_rectangle(zoom_box, radius=12, outline=(58, 66, 78, 255), width=2)
    paste_center(canvas, zoom, zoom_box)

    # Compact legend beside the crop.  This text is guidance only; output prompt bans text.
    legend_x = 514
    draw.text((legend_x, 633), "OUTPUT", font=F_SLOT, fill=TEXT)
    rules = [
        (GREEN, "4 isolated pieces"),
        (GREEN, "same bind angle"),
        (CYAN, "short tapered overlap"),
        (AMBER, "no hollow ends"),
        (AMBER, "no caps / tubes"),
        (AMBER, "no redesign"),
    ]
    for index, (color, label) in enumerate(rules):
        y = 674 + index * 43
        draw.ellipse((legend_x, y + 5, legend_x + 11, y + 16), fill=color)
        draw.text((legend_x + 20, y), label, font=F_SMALL, fill=TEXT)
    draw.text((legend_x, 942), "GUIDE ONLY", font=F_SMALL, fill=MUTED)
    draw.text((legend_x, 960), "not a sprite sheet", font=F_SMALL, fill=MUTED)

    slots = [
        ((690, 94, 1094, 527), 1, "NEAR UPPER ARM", "cloth sleeve · shoulder → elbow", parts["near_upper_arm"], (272, 226), draw_upper_arm_hint),
        ((1110, 94, 1514, 527), 2, "NEAR FOREARM", "bracer + hidden cuff bridge", parts["near_forearm"], (238, 245), draw_forearm_hint),
        ((690, 545, 1094, 986), 3, "DAGGER HAND", "existing grip identity · wrist bridge", parts["near_dagger_hand"], (248, 190), draw_hand_hint),
        ((1110, 545, 1514, 986), 4, "DAGGER", "blade + guard · concealed tang only", parts["dagger"], (308, 191), draw_dagger_hint),
    ]
    placements = {}
    for panel_box, number, title, subtitle, source, max_size, hint in slots:
        placements[title] = draw_slot(canvas, draw, panel_box, number, title, subtitle, source, max_size, hint)

    # A clean dividing rule keeps the identity/context side distinct from the generation slots.
    draw.line((678, 94, 678, 986), fill=(63, 72, 87, 255), width=2)

    GUIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(GUIDE_PATH, format="PNG", optimize=True)

    manifest = {
        "schema_version": 1,
        "artifact": GUIDE_PATH.name,
        "artifact_size": list(CANVAS),
        "artifact_sha256": sha256(GUIDE_PATH),
        "purpose": "image_to_image_guide_only_not_production_art",
        "identity_master": {
            "file": MASTER_PATH.name,
            "sha256": sha256(MASTER_PATH),
            "crop_xyxy": list(crop_src),
        },
        "visible_pixel_sources": {
            semantic: {
                "file": str(path.relative_to(V10_ROOT.parent)).replace("\\", "/"),
                "sha256": sha256(path),
                "size": list(parts[semantic].size),
            }
            for semantic, path in PART_PATHS.items()
        },
        "slot_placements_xyxy": {key: list(value) for key, value in placements.items()},
        "rendering_invariant": "cyan_dashes_are_unfilled_shape_hints_not_sprite_pixels",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"guide={GUIDE_PATH}")
    print(f"manifest={MANIFEST_PATH}")
    print(f"sha256={manifest['artifact_sha256']}")


if __name__ == "__main__":
    main()
