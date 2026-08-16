#!/usr/bin/env python3
"""Build the Cutting It Close event art and ThingsSplit enchantment icon.

The shipping event plate is an image-generated single thin saw rolling from
the right-hand vanishing point directly toward the camera along an expanded
harbor path with a hard polygonal event-art boundary.
This script deterministically normalizes it to the game's event texture contract.
The older procedural environment renderer remains available as an explicit
fallback for development, while icon cleanup is always deterministic.
"""

from __future__ import annotations

import argparse
import math
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "source_assets/events/cutting_it_close/environment_01.png"
DEFAULT_IMAGEGEN_EVENT_SOURCE = (
    ROOT
    / "source_assets/events/cutting_it_close/imagegen_rolling_saw_organic_right_edge_v9.png"
)
DEFAULT_EVENT_OUT = ROOT / "images/events/cutting_it_close.png"
DEFAULT_ICON_CHROMA = (
    ROOT / "source_assets/enchantments/things_split/things_split_chroma.png"
)
DEFAULT_ICON_OUT = ROOT / "images/enchantments/things_split.png"
CHROMA_HELPER = (
    Path.home()
    / ".codex/skills/.system/imagegen/scripts/remove_chroma_key.py"
)

EVENT_SIZE = (3440, 1616)
SCENE_SIZE = (2150, EVENT_SIZE[1])
# The vanilla portrait TextureRect is intentionally overscanned by 1.04.
# Keep a larger inset than the first pass so the authored hard silhouette is
# still visible on the physical screen at 100% UI scale.
IMAGEGEN_CONTENT_SCALE = 0.72
IMAGEGEN_CONTENT_LEFT = 520
IMAGEGEN_CONTENT_TOP = 220
EVENT_TEXT_BLACK_START = 1920
SEED = 0xC0771A6

# Vanilla default_event_layout.tscn and project.godot framing contract.  The
# event root is shifted up by 39 px, while the Portrait rect's asymmetric
# vertical offsets move its center down by 44 px.  Keep these values explicit so
# the validation below measures the final edge clearance in logical screen
# pixels rather than relying on hand-tuned source-image coordinates.
VANILLA_VIEWPORT_SIZE = (1920, 1080)
VANILLA_EVENT_ROOT_OFFSET = (0.0, -39.0)
VANILLA_PORTRAIT_OFFSETS = (-1280.0, -556.0, 1280.0, 644.0)
VANILLA_PORTRAIT_SIZE = (2560, 1200)
VANILLA_PORTRAIT_SCALE = 1.04
MIN_VISIBLE_PAINT_PIXELS = 800_000
MIN_ROBUST_EDGE_SPAN = 100
MIN_EDGE_CLEARANCE_SCREEN = 70.0
MAX_EDGE_CLEARANCE_SCREEN = 210.0
MIN_EDGE_PROFILE_VARIATION = 25


def clamp(value: int, minimum: int = 0, maximum: int = 255) -> int:
    return max(minimum, min(maximum, value))


def adjust_colour(rgb: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    return tuple(clamp(channel + amount) for channel in rgb)


def polar_point(cx: float, cy: float, radius: float, angle: float) -> tuple[int, int]:
    return (
        round(cx + math.cos(angle) * radius),
        round(cy + math.sin(angle) * radius),
    )


def stylize_environment(source: Path) -> Image.Image:
    """Turn the generated plate into broad, hand-painted STS2 value masses.

    The source deliberately remains the original harbour composition, but it is
    rebuilt at a much coarser working resolution and quantised twice.  That
    removes photographic stone, water, and foliage micro-detail instead of
    merely laying translucent polygons over it.  A small number of large,
    irregular paint planes then restore authored lighting and silhouettes.
    """

    with Image.open(source) as opened:
        plate = opened.convert("RGB")

    # Work very small first so individual stones, planks, leaves, and foam stop
    # reading as photographic texture.  Median filtering and a locked palette
    # merge neighbouring values into the shipped event paintings' broad shapes.
    plate = ImageEnhance.Color(plate).enhance(0.66)
    plate = ImageEnhance.Contrast(plate).enhance(1.21)
    plate = ImageEnhance.Brightness(plate).enhance(0.79)
    plate = ImageOps.fit(
        plate,
        (640, 481),
        method=Image.Resampling.LANCZOS,
        centering=(0.54, 0.52),
    )
    plate = plate.filter(ImageFilter.MedianFilter(5))
    plate = ImageOps.posterize(plate, 6)
    plate = plate.quantize(
        colors=34,
        method=Image.Quantize.FASTOCTREE,
        dither=Image.Dither.NONE,
    ).convert("RGB")
    plate = plate.resize(SCENE_SIZE, Image.Resampling.LANCZOS)
    # Re-quantising after the smooth resize converts the interpolation bands
    # back into deliberate, hard-edged paint shapes rather than pixel blocks.
    plate = plate.quantize(
        colors=44,
        method=Image.Quantize.FASTOCTREE,
        dither=Image.Dither.NONE,
    ).convert("RGB")

    # Large deterministic planes replace the previous field of small facets.
    # Their scale is intentionally architectural: sky, cliff, path, and dock
    # receive readable value groupings instead of surface noise.
    rng = random.Random(SEED)
    facet_layer = Image.new("RGBA", SCENE_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(facet_layer, "RGBA")
    for _ in range(44):
        x = rng.randrange(30, SCENE_SIZE[0] - 30)
        y = rng.randrange(30, SCENE_SIZE[1] - 30)
        width = rng.randrange(190, 560)
        height = rng.randrange(125, 390)
        points = [
            (x - width // 2, y + rng.randrange(height // 5, height // 2 + 1)),
            (x - rng.randrange(width // 5, width // 2 + 1), y - height // 3),
            (x + rng.randrange(-width // 8, width // 4 + 1), y - height // 2),
            (x + width // 2, y + rng.randrange(-height // 5, height // 2 + 1)),
        ]
        sample = plate.getpixel((x, y))
        colour = adjust_colour(sample, rng.randrange(-14, 13))
        draw.polygon(points, fill=(*colour, rng.randrange(18, 47)))

    # Authored washes make the focal route read in three values: pale hostile
    # sky, mid-value harbour, and near-black trap corridor.
    draw.polygon(
        [(0, 0), (1030, 0), (860, 264), (504, 365), (0, 505)],
        fill=(154, 157, 148, 18),
    )
    draw.polygon(
        [(985, 0), (2150, 0), (2150, 1220), (1770, 1050), (1430, 630)],
        fill=(8, 14, 17, 18),
    )
    draw.polygon(
        [(0, 1050), (460, 915), (1040, 1010), (1435, 1510), (0, 1616)],
        fill=(5, 9, 11, 20),
    )
    draw.polygon(
        [(500, 1510), (1020, 1110), (1530, 705), (1745, 770), (1220, 1300)],
        fill=(105, 108, 96, 18),
    )

    merged = Image.alpha_composite(plate.convert("RGBA"), facet_layer)
    # One final palette lock ensures every added plane shares the same hard
    # colour vocabulary as the environment beneath it.
    return merged.convert("RGB").quantize(
        colors=48,
        method=Image.Quantize.FASTOCTREE,
        dither=Image.Dither.NONE,
    ).convert("RGBA")


def event_art_mask() -> Image.Image:
    """Create the irregular black-edged silhouette used by event art."""

    mask = Image.new("L", SCENE_SIZE, 0)
    draw = ImageDraw.Draw(mask)
    outline = [
        (0, 214),
        (64, 143),
        (182, 121),
        (256, 67),
        (401, 82),
        (525, 35),
        (684, 64),
        (840, 21),
        (1002, 68),
        (1174, 42),
        (1316, 88),
        (1475, 73),
        (1584, 126),
        (1712, 173),
        (1808, 265),
        (1870, 379),
        (1836, 508),
        (1924, 622),
        (1872, 755),
        (1944, 890),
        (1854, 1002),
        (1898, 1141),
        (1805, 1249),
        (1738, 1370),
        (1586, 1407),
        (1491, 1494),
        (1317, 1482),
        (1170, 1558),
        (982, 1524),
        (822, 1597),
        (645, 1561),
        (482, 1608),
        (337, 1554),
        (210, 1571),
        (119, 1504),
        (31, 1472),
        (0, 1390),
    ]
    draw.polygon(outline, fill=255)
    return mask


def draw_polyline_with_outline(
    layer: Image.Image,
    points: list[tuple[int, int]],
    outline: tuple[int, int, int, int],
    fill: tuple[int, int, int, int],
    outline_width: int,
    width: int,
) -> None:
    draw = ImageDraw.Draw(layer, "RGBA")
    draw.line(points, fill=outline, width=outline_width, joint="curve")
    draw.line(points, fill=fill, width=width, joint="curve")


def draw_broken_ink_outline(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[int, int]],
    rng: random.Random,
    colour: tuple[int, int, int, int],
    minimum_width: int,
    maximum_width: int,
    coverage: float = 0.82,
    closed: bool = True,
) -> None:
    """Ink a polygon with uneven, partly missing hand-painted edge strokes."""

    sequence = points + [points[0]] if closed else points
    for index in range(len(sequence) - 1):
        if rng.random() > coverage:
            continue
        ax, ay = sequence[index]
        bx, by = sequence[index + 1]
        start = rng.uniform(0.0, 0.16)
        end = rng.uniform(0.78, 1.0)
        jitter_x = rng.randrange(-3, 4)
        jitter_y = rng.randrange(-3, 4)
        segment = [
            (
                round(ax + (bx - ax) * start) + jitter_x,
                round(ay + (by - ay) * start) + jitter_y,
            ),
            (
                round(ax + (bx - ax) * end) - jitter_x,
                round(ay + (by - ay) * end) - jitter_y,
            ),
        ]
        draw.line(
            segment,
            fill=colour,
            width=rng.randrange(minimum_width, maximum_width + 1),
        )


def draw_oncoming_blade(canvas: Image.Image) -> None:
    """Paint a front-facing, hard-polygon saw rushing toward the viewer.

    The suspension rope deliberately continues beyond the top edge: the event
    illustration never shows (or implies) an on-canvas support.  Approach is
    communicated by two smaller hard-edged afterimages, tapered speed planes,
    unequal near/far tooth size, and the shadow travelling back up the path.
    The disc itself stays face-on rather than exposing a side profile.
    """

    rng = random.Random(SEED + 1701)
    cx, cy = 1015, 700
    root_radius = 276
    outer_radius = 360
    # An odd count and per-tooth angular offsets stop the blade reading as a
    # clean UI gear.  Every tooth is a separate hand-cut polygon.
    teeth = 19
    step = math.tau / teeth
    rotation = -math.pi / 2 + 0.04
    tooth_jitter = [rng.randrange(-17, 18) for _ in range(teeth)]
    tooth_angle_jitter = [rng.uniform(-step * 0.075, step * 0.075) for _ in range(teeth)]
    tooth_hook = [rng.uniform(0.36, 0.57) for _ in range(teeth)]

    def hard_ring(
        center_x: float,
        center_y: float,
        radius: float,
        sides: int,
        angle_offset: float = 0.0,
    ) -> list[tuple[int, int]]:
        return [
            polar_point(
                center_x,
                center_y,
                radius,
                angle_offset + index * math.tau / sides,
            )
            for index in range(sides)
        ]

    def saw_outline(
        center_x: float,
        center_y: float,
        scale: float,
    ) -> list[tuple[int, int]]:
        points: list[tuple[int, int]] = []
        for index in range(teeth):
            angle = rotation + index * step + tooth_angle_jitter[index]
            # Bottom-half teeth are subtly larger.  The face remains circular,
            # but this small forced-perspective cue makes it advance toward us.
            near_bias = max(0.0, math.sin(angle + step * 0.5)) * 0.055
            root = root_radius * scale
            tip = (outer_radius * (1.0 + near_bias) + tooth_jitter[index]) * scale
            points.extend(
                [
                    polar_point(center_x, center_y, root - 5 * scale, angle),
                    polar_point(center_x, center_y, root + 10 * scale, angle + step * 0.15),
                    polar_point(center_x, center_y, tip, angle + step * tooth_hook[index]),
                    polar_point(
                        center_x,
                        center_y,
                        (outer_radius - 48 + tooth_jitter[index] // 3) * scale,
                        angle + step * 0.67,
                    ),
                    polar_point(center_x, center_y, root - 8 * scale, angle + step * 0.91),
                ]
            )
        return points

    # Two smaller, offset silhouettes are hard-edged positional afterimages.
    # They establish the travel vector: upper-right background -> viewer.
    motion = Image.new("RGBA", EVENT_SIZE, (0, 0, 0, 0))
    motion_draw = ImageDraw.Draw(motion, "RGBA")
    for dx, dy, scale, fill, edge in [
        (177, -130, 0.75, (91, 96, 90, 58), (105, 108, 98, 112)),
        (323, -238, 0.53, (102, 98, 83, 30), (103, 99, 84, 68)),
    ]:
        outline = saw_outline(cx + dx, cy + dy, scale)
        motion_draw.polygon(outline, fill=fill)
        draw_broken_ink_outline(
            motion_draw,
            outline,
            rng,
            edge,
            minimum_width=7,
            maximum_width=14,
            coverage=0.52,
        )

    speed_planes = [
        [(1195, 500), (1538, 226), (1570, 246), (1224, 535)],
        [(1240, 557), (1600, 327), (1624, 354), (1260, 590)],
        [(1207, 618), (1518, 458), (1540, 485), (1224, 646)],
        [(1135, 444), (1415, 190), (1434, 204), (1155, 470)],
    ]
    speed_colours = [
        (139, 132, 106, 68),
        (103, 111, 104, 55),
        (158, 109, 62, 46),
        (86, 99, 99, 50),
    ]
    for polygon, colour in zip(speed_planes, speed_colours, strict=True):
        motion_draw.polygon(polygon, fill=colour)
    canvas.alpha_composite(motion)

    # One broad path shadow trails behind the advancing blade.
    shadow = Image.new("RGBA", EVENT_SIZE, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow, "RGBA")
    shadow_draw.polygon(
        [(650, 985), (1190, 908), (1570, 616), (1450, 760), (1100, 1050), (700, 1115)],
        fill=(4, 7, 8, 112),
    )
    canvas.alpha_composite(shadow)

    # The only suspension is a heavy rope continuing beyond the top of frame.
    # It is painted behind the disc and reappears as a knot over the hub.
    rope = Image.new("RGBA", EVENT_SIZE, (0, 0, 0, 0))
    rope_points = [
        (804, -52),
        (829, 92),
        (864, 232),
        (907, 365),
        (960, 512),
        (cx, cy),
    ]
    draw_polyline_with_outline(
        rope,
        rope_points,
        outline=(14, 14, 13, 255),
        fill=(84, 64, 43, 255),
        outline_width=52,
        width=29,
    )
    rope_draw = ImageDraw.Draw(rope, "RGBA")
    # Uneven dark edge fragments and offset ochre planes stop the suspension
    # reading like a clean vector stroke while retaining its top-edge origin.
    draw_broken_ink_outline(
        rope_draw,
        rope_points,
        rng,
        (7, 9, 9, 235),
        minimum_width=8,
        maximum_width=15,
        coverage=0.76,
        closed=False,
    )
    for index in range(15):
        t = (index + 0.45) / 15.0
        segment_float = t * (len(rope_points) - 1)
        segment = min(int(segment_float), len(rope_points) - 2)
        local = segment_float - segment
        ax, ay = rope_points[segment]
        bx, by = rope_points[segment + 1]
        x = round(ax + (bx - ax) * local)
        y = round(ay + (by - ay) * local)
        rope_draw.line(
            [
                (x - 17 + rng.randrange(-3, 4), y - 8),
                (x + 15, y + 8 + rng.randrange(-3, 4)),
            ],
            fill=(151, 111, 67, rng.randrange(165, 226)),
            width=rng.randrange(4, 8),
        )
    canvas.alpha_composite(rope)

    blade = Image.new("RGBA", EVENT_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(blade, "RGBA")
    outline = saw_outline(cx, cy, 1.0)
    offset_shadow = [(x + 17, y + 20) for x, y in outline]
    draw.polygon(offset_shadow, fill=(4, 6, 7, 190))
    draw.polygon(outline, fill=(74, 78, 75, 255))

    # Shade every hand-cut tooth as its own paint plane.  Upper-left teeth pick
    # up the same cold sky light as the harbour; lower-right teeth fall into the
    # cliff's near-black shadow.  Small dark root wedges break the gear-like
    # repetition of a uniformly coloured silhouette.
    for index in range(teeth):
        tooth = outline[index * 5 : index * 5 + 5]
        angle = rotation + index * step + tooth_angle_jitter[index]
        light = math.cos(angle - 3.95)
        amount = round(15 * light) - rng.randrange(0, 8)
        tooth_colour = adjust_colour((76, 80, 76), amount)
        draw.polygon(tooth, fill=(*tooth_colour, 255))
        if index % 3 != 1:
            draw.polygon(
                [tooth[0], tooth[1], tooth[4]],
                fill=(26, 32, 32, rng.randrange(80, 145)),
            )
        if light > 0.15:
            draw.line(
                [tooth[1], tooth[2]],
                fill=(171, 168, 142, rng.randrange(72, 128)),
                width=rng.randrange(5, 10),
            )

    # A restrained continuous under-stroke preserves the silhouette; the
    # variable fragments over it create the uneven ink weight of event art.
    draw.line(outline + [outline[0]], fill=(12, 16, 17, 238), width=10)
    draw_broken_ink_outline(
        draw,
        outline,
        rng,
        (7, 10, 11, 250),
        minimum_width=11,
        maximum_width=23,
        coverage=0.74,
    )

    face_points = [
        polar_point(
            cx,
            cy,
            root_radius - 7 + rng.randrange(-12, 13),
            rotation + index * math.tau / 37,
        )
        for index in range(37)
    ]
    draw.polygon(face_points, fill=(67, 74, 72, 255))

    # Broad clipped polygons build the steel face.  The first planes are
    # authored to match the scene light; a few deterministic secondary planes
    # keep the surface irregular without turning it into low-poly noise.
    face_mask = Image.new("L", EVENT_SIZE, 0)
    ImageDraw.Draw(face_mask).polygon(face_points, fill=255)
    facets = Image.new("RGBA", EVENT_SIZE, (0, 0, 0, 0))
    facet_draw = ImageDraw.Draw(facets, "RGBA")
    facet_draw.polygon(
        [
            (cx - 288, cy - 115),
            (cx - 175, cy - 286),
            (cx + 25, cy - 250),
            (cx - 30, cy + 4),
            (cx - 238, cy + 90),
        ],
        fill=(158, 158, 139, 115),
    )
    facet_draw.polygon(
        [
            (cx + 18, cy - 276),
            (cx + 260, cy - 88),
            (cx + 120, cy + 35),
            (cx - 30, cy + 4),
        ],
        fill=(91, 100, 96, 112),
    )
    facet_draw.polygon(
        [
            (cx - 30, cy + 4),
            (cx + 120, cy + 35),
            (cx + 274, cy + 172),
            (cx + 44, cy + 286),
            (cx - 94, cy + 168),
        ],
        fill=(26, 34, 36, 154),
    )
    facet_draw.polygon(
        [
            (cx - 255, cy + 54),
            (cx - 30, cy + 4),
            (cx - 94, cy + 168),
            (cx - 188, cy + 250),
        ],
        fill=(93, 75, 56, 102),
    )
    facet_draw.polygon(
        [
            (cx - 226, cy - 156),
            (cx - 70, cy - 222),
            (cx - 124, cy - 94),
            (cx - 264, cy - 18),
        ],
        fill=(194, 185, 153, 58),
    )
    facet_colours = [
        (128, 130, 117, 62),
        (42, 53, 54, 78),
        (99, 77, 57, 58),
        (88, 101, 98, 64),
    ]
    for index in range(8):
        angle = rng.random() * math.tau
        radius = math.sqrt(rng.random()) * 205
        x = round(cx + math.cos(angle) * radius)
        y = round(cy + math.sin(angle) * radius)
        width = rng.randrange(165, 350)
        height = rng.randrange(120, 275)
        polygon = [
            (x - width // 2, y + height // 3),
            (x - width // 5, y - height // 2),
            (x + width // 2, y - height // 5),
            (x + width // 3, y + height // 2),
        ]
        facet_draw.polygon(polygon, fill=facet_colours[index % len(facet_colours)])

    rust = Image.new("RGBA", EVENT_SIZE, (0, 0, 0, 0))
    rust_draw = ImageDraw.Draw(rust, "RGBA")
    for _ in range(11):
        angle = rng.random() * math.tau
        radius = math.sqrt(rng.random()) * 232
        x = round(cx + math.cos(angle) * radius)
        y = round(cy + math.sin(angle) * radius)
        poly_radius = rng.randrange(22, 58)
        sides = rng.randrange(4, 7)
        polygon = hard_ring(x, y, poly_radius, sides, rng.random() * math.tau)
        rust_draw.polygon(polygon, fill=(117, 66, 37, rng.randrange(48, 94)))

    zero_alpha = Image.new("L", EVENT_SIZE, 0)
    facets.putalpha(Image.composite(facets.getchannel("A"), zero_alpha, face_mask))
    rust.putalpha(Image.composite(rust.getchannel("A"), zero_alpha, face_mask))
    blade = Image.alpha_composite(blade, facets)
    blade = Image.alpha_composite(blade, rust)
    draw = ImageDraw.Draw(blade, "RGBA")
    draw.line(face_points + [face_points[0]], fill=(22, 28, 28, 220), width=9)
    draw_broken_ink_outline(
        draw,
        face_points,
        rng,
        (13, 18, 19, 245),
        minimum_width=10,
        maximum_width=19,
        coverage=0.68,
    )

    outer_ring = [
        polar_point(
            cx,
            cy,
            242 + rng.randrange(-5, 6),
            rotation + index * math.tau / 33,
        )
        for index in range(33)
    ]
    draw_broken_ink_outline(
        draw,
        outer_ring,
        rng,
        (24, 31, 31, 220),
        minimum_width=10,
        maximum_width=18,
        coverage=0.71,
    )
    # Broken inner marks look painted rather than mechanically concentric.
    for start, end, colour in [
        (1, 8, (141, 117, 82, 86)),
        (12, 19, (30, 37, 37, 145)),
        (23, 30, (126, 101, 70, 68)),
    ]:
        segment = [
            polar_point(
                cx,
                cy,
                202 + rng.randrange(-7, 8),
                rotation + index * math.tau / 33,
            )
            for index in range(start, end + 1)
        ]
        draw_broken_ink_outline(
            draw,
            segment,
            rng,
            colour,
            minimum_width=7,
            maximum_width=12,
            coverage=0.73,
            closed=False,
        )

    for _ in range(12):
        angle = rng.random() * math.tau
        radius = rng.randrange(75, 235)
        x = round(cx + math.cos(angle) * radius)
        y = round(cy + math.sin(angle) * radius)
        length = rng.randrange(45, 120)
        scratch_angle = rng.uniform(-0.45, 0.45)
        dx = round(math.cos(scratch_angle) * length / 2)
        dy = round(math.sin(scratch_angle) * length / 2)
        draw.line(
            [(x - dx, y - dy), (x + dx, y + dy)],
            fill=(185, 176, 148, rng.randrange(36, 74)),
            width=rng.randrange(3, 7),
        )

    hub_outer = hard_ring(cx, cy, 82, 13, 0.08)
    hub_inner = hard_ring(cx, cy, 45, 9, -0.04)
    draw.polygon(hub_outer, fill=(32, 35, 34, 255))
    draw.line(hub_outer + [hub_outer[0]], fill=(9, 11, 12, 240), width=9)
    draw_broken_ink_outline(
        draw,
        hub_outer,
        rng,
        (7, 9, 10, 255),
        minimum_width=10,
        maximum_width=18,
        coverage=0.72,
    )
    draw.polygon(hub_inner, fill=(82, 74, 59, 255))
    draw_broken_ink_outline(
        draw,
        hub_inner,
        rng,
        (18, 21, 21, 255),
        minimum_width=7,
        maximum_width=12,
        coverage=0.78,
    )

    # Knot on top of the hub makes the off-canvas rope attachment unambiguous.
    knot = hard_ring(cx, cy - 4, 62, 12, 0.12)
    draw.polygon(knot, fill=(78, 58, 39, 255))
    draw_broken_ink_outline(
        draw,
        knot,
        rng,
        (12, 12, 11, 255),
        minimum_width=8,
        maximum_width=14,
        coverage=0.84,
    )
    draw.polygon(
        [(cx - 42, cy - 18), (cx - 8, cy - 45), (cx + 33, cy - 17), (cx + 11, cy + 8)],
        fill=(147, 105, 63, 235),
    )
    draw.polygon(
        [(cx - 31, cy + 7), (cx + 6, cy - 10), (cx + 40, cy + 20), (cx - 2, cy + 43)],
        fill=(104, 75, 47, 245),
    )
    draw.line(
        [(cx - 36, cy - 23), (cx + 34, cy + 24)],
        fill=(51, 38, 27, 220),
        width=8,
    )

    highlight = [
        polar_point(cx, cy, 279, angle)
        for angle in [3.42, 3.58, 3.75, 3.92, 4.10, 4.27, 4.44]
    ]
    draw_broken_ink_outline(
        draw,
        highlight,
        rng,
        (195, 186, 155, 112),
        minimum_width=8,
        maximum_width=14,
        coverage=0.79,
        closed=False,
    )
    canvas.alpha_composite(blade)

    # The low trigger cord remains the narrative cause of the swing.
    trigger = Image.new("RGBA", EVENT_SIZE, (0, 0, 0, 0))
    trigger_points = [(320, 1355), (598, 1310), (852, 1264), (1120, 1203), (1532, 1110)]
    draw_polyline_with_outline(
        trigger,
        trigger_points,
        outline=(14, 13, 11, 245),
        fill=(105, 78, 50, 240),
        outline_width=21,
        width=9,
    )
    trigger_draw = ImageDraw.Draw(trigger, "RGBA")
    draw_broken_ink_outline(
        trigger_draw,
        trigger_points,
        rng,
        (8, 9, 8, 225),
        minimum_width=4,
        maximum_width=8,
        coverage=0.68,
        closed=False,
    )
    knot_x, knot_y = 852, 1264
    trigger_draw.polygon(
        hard_ring(knot_x, knot_y, 27, 8, 0.1),
        fill=(126, 89, 52, 255),
        outline=(20, 17, 13, 255),
    )
    canvas.alpha_composite(trigger)


def darken_text_region(canvas: Image.Image) -> None:
    """Fade all scene detail to black before the event text region."""

    fade = Image.new("RGBA", EVENT_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(fade, "RGBA")
    # 1686 px is 49% of the final width, the beginning of the event-copy band.
    start_x, end_x = 1370, 1686
    for x in range(start_x, end_x + 1, 4):
        t = (x - start_x) / (end_x - start_x)
        alpha = round(255 * (t**1.45))
        draw.rectangle((x, 0, x + 4, EVENT_SIZE[1]), fill=(0, 0, 0, alpha))
    draw.rectangle((end_x, 0, EVENT_SIZE[0], EVENT_SIZE[1]), fill=(0, 0, 0, 255))
    canvas.alpha_composite(fade)


def add_vignette(canvas: Image.Image) -> None:
    light = Image.new("L", EVENT_SIZE, 0)
    draw = ImageDraw.Draw(light)
    draw.ellipse((-330, -365, 2100, 1985), fill=220)
    light = light.filter(ImageFilter.GaussianBlur(205))
    dark = ImageOps.invert(light).point(lambda value: round(value * 0.67))
    overlay = Image.new("RGBA", EVENT_SIZE, (0, 0, 0, 0))
    overlay.putalpha(dark)
    canvas.alpha_composite(overlay)


def build_event(source: Path, output: Path) -> None:
    environment = stylize_environment(source)
    environment.putalpha(event_art_mask())
    canvas = Image.new("RGBA", EVENT_SIZE, (0, 0, 0, 255))
    canvas.alpha_composite(environment, (0, 0))
    draw_oncoming_blade(canvas)
    darken_text_region(canvas)
    add_vignette(canvas)

    # Event textures are RGBA but intentionally contain no transparent pixels.
    alpha = Image.new("L", EVENT_SIZE, 255)
    canvas.putalpha(alpha)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)


def imagegen_frame_points(
    frame_width: int,
    frame_height: int,
) -> list[tuple[int, int]]:
    """Return the hard polygon used for the image-generated event plate."""

    return [
        (118, 82),
        (240, 55),
        (365, 86),
        (500, 52),
        (650, 88),
        (805, 58),
        (980, 91),
        (1160, 56),
        (1340, 84),
        (1530, 53),
        (1725, 87),
        (1930, 59),
        (frame_width, 86),
        (frame_width, frame_height - 52),
        (1938, frame_height - 84),
        (1760, frame_height - 53),
        (1580, frame_height - 91),
        (1390, frame_height - 60),
        (1205, frame_height - 86),
        (1015, frame_height - 55),
        (835, frame_height - 93),
        (650, frame_height - 61),
        (470, frame_height - 88),
        (300, frame_height - 57),
        (136, frame_height - 76),
        (95, frame_height - 190),
        (126, frame_height - 340),
        (87, frame_height - 500),
        (121, frame_height - 660),
        (91, frame_height - 815),
        (127, 250),
        (91, 145),
    ]


def validate_imagegen_geometry(content_size: tuple[int, int]) -> None:
    """Reject scale or placement changes that Pillow would silently crop."""

    content_width, content_height = content_size
    points = imagegen_frame_points(content_width, content_height)
    invalid_points = [
        point
        for point in points
        if not (
            0 <= point[0] <= content_width
            and 0 <= point[1] <= content_height
        )
    ]
    if invalid_points:
        raise ValueError(
            "Imagegen frame mask exceeds resized content: "
            f"{content_size=} {invalid_points[:4]=}"
        )

    content_right = IMAGEGEN_CONTENT_LEFT + content_width
    content_bottom = IMAGEGEN_CONTENT_TOP + content_height
    if (
        IMAGEGEN_CONTENT_LEFT < 0
        or IMAGEGEN_CONTENT_TOP < 0
        or content_right > EVENT_SIZE[0]
        or content_bottom > EVENT_SIZE[1]
    ):
        raise ValueError(
            "Imagegen content placement exceeds event canvas: "
            f"left={IMAGEGEN_CONTENT_LEFT} top={IMAGEGEN_CONTENT_TOP} "
            f"right={content_right} bottom={content_bottom}"
        )


def vanilla_visible_source_bounds() -> tuple[float, float, float, float, float]:
    """Map the vanilla 1920x1080 viewport back into this event texture."""

    texture_fit_scale = min(
        VANILLA_PORTRAIT_SIZE[0] / EVENT_SIZE[0],
        VANILLA_PORTRAIT_SIZE[1] / EVENT_SIZE[1],
    )
    source_to_screen_scale = texture_fit_scale * VANILLA_PORTRAIT_SCALE
    offset_left, offset_top, offset_right, offset_bottom = (
        VANILLA_PORTRAIT_OFFSETS
    )
    portrait_center = (
        VANILLA_VIEWPORT_SIZE[0] / 2
        + VANILLA_EVENT_ROOT_OFFSET[0]
        + (offset_left + offset_right) / 2,
        VANILLA_VIEWPORT_SIZE[1] / 2
        + VANILLA_EVENT_ROOT_OFFSET[1]
        + (offset_top + offset_bottom) / 2,
    )
    texture_center = (EVENT_SIZE[0] / 2, EVENT_SIZE[1] / 2)
    left = texture_center[0] - portrait_center[0] / source_to_screen_scale
    top = texture_center[1] - portrait_center[1] / source_to_screen_scale
    right = texture_center[0] + (
        VANILLA_VIEWPORT_SIZE[0] - portrait_center[0]
    ) / source_to_screen_scale
    bottom = texture_center[1] + (
        VANILLA_VIEWPORT_SIZE[1] - portrait_center[1]
    ) / source_to_screen_scale
    return left, top, right, bottom, source_to_screen_scale


def percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def build_imagegen_event(source: Path, output: Path) -> None:
    """Normalize and frame the selected imagegen plate for the vanilla layout."""

    if not source.is_file():
        raise FileNotFoundError(f"Missing imagegen event source: {source}")

    with Image.open(source) as opened:
        # The model output already contains the approved STS2-style event matte.
        # Fit rather than stretch so the razor-thin rolling silhouette stays thin.
        fitted = ImageOps.fit(
            opened.convert("RGB"),
            EVENT_SIZE,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        ).convert("RGBA")

    # default_event_layout.tscn displays the portrait in a 2560x1200 region at
    # scale 1.04, which trims a little more of every edge.  Inset the complete
    # approved plate before that crop so its hard polygonal top, bottom, and left
    # silhouette remains visible in game instead of reading as an oversized crop.
    content_size = tuple(
        round(dimension * IMAGEGEN_CONTENT_SCALE) for dimension in EVENT_SIZE
    )
    validate_imagegen_geometry(content_size)
    fitted = fitted.resize(content_size, Image.Resampling.LANCZOS)
    # Carve a second, deliberately irregular matte into the left/top/bottom
    # edges.  The source plate already has an organic right edge, but its other
    # three edges can disappear against the portrait node's overscan.  Keeping
    # this as a hard polygon matches the vanilla event-art cut-paper silhouette
    # and makes the boundary survive every supported display scale.
    frame_mask = Image.new("L", fitted.size, 0)
    frame_draw = ImageDraw.Draw(frame_mask)
    frame_width, frame_height = fitted.size
    frame_points = imagegen_frame_points(frame_width, frame_height)
    frame_draw.polygon(frame_points, fill=255)
    fitted.putalpha(frame_mask)
    content_top = IMAGEGEN_CONTENT_TOP
    canvas = Image.new("RGBA", EVENT_SIZE, (0, 0, 0, 255))
    canvas.alpha_composite(fitted, (IMAGEGEN_CONTENT_LEFT, content_top))
    ImageDraw.Draw(canvas).rectangle(
        (EVENT_TEXT_BLACK_START, 0, EVENT_SIZE[0] - 1, EVENT_SIZE[1] - 1),
        fill=(0, 0, 0, 255),
    )

    # The selected plate already contains the approved expanded path and its
    # organic, hard-edged right silhouette.  Do not re-mask it with a generated
    # fade or a mechanically repeating zigzag.
    canvas.putalpha(Image.new("L", EVENT_SIZE, 255))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)


def outlined_piece(piece: Image.Image, radius: int = 17) -> Image.Image:
    alpha = piece.getchannel("A")
    expanded = alpha.filter(ImageFilter.MaxFilter(radius * 2 + 1))
    outline = Image.new("RGBA", piece.size, (9, 18, 29, 0))
    outline.putalpha(expanded)
    return Image.alpha_composite(outline, piece)


def build_icon_chroma(output: Path) -> None:
    """Draw a clean two-piece card symbol on a removable green plate."""

    size = 512
    card = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card, "RGBA")
    draw.rounded_rectangle(
        (91, 62, 421, 449),
        radius=42,
        fill=(17, 41, 75, 255),
    )
    draw.rounded_rectangle(
        (108, 80, 404, 431),
        radius=30,
        fill=(20, 126, 224, 255),
        outline=(94, 213, 255, 255),
        width=16,
    )
    # One broad highlight, not fine text, stays legible at 64 px.
    draw.polygon(
        [(126, 104), (207, 89), (167, 405), (123, 414)],
        fill=(72, 173, 245, 128),
    )

    split = [
        (270, 61),
        (234, 120),
        (276, 173),
        (229, 231),
        (278, 292),
        (235, 354),
        (271, 450),
    ]
    left_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(left_mask).polygon(
        [(55, 34), split[0], *split[1:], (55, 480)],
        fill=255,
    )
    right_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(right_mask).polygon(
        [split[0], (458, 34), (458, 480), split[-1], *reversed(split[1:-1])],
        fill=255,
    )

    left = card.copy()
    left.putalpha(Image.composite(card.getchannel("A"), Image.new("L", card.size, 0), left_mask))
    right = card.copy()
    right.putalpha(Image.composite(card.getchannel("A"), Image.new("L", card.size, 0), right_mask))
    left = outlined_piece(left)
    right = outlined_piece(right)

    split_icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    split_icon.alpha_composite(left, (-17, 3))
    split_icon.alpha_composite(right, (17, -3))
    spark_draw = ImageDraw.Draw(split_icon, "RGBA")
    spark_draw.polygon([(258, 217), (279, 230), (259, 242)], fill=(238, 230, 183, 255))
    spark_draw.polygon([(255, 296), (276, 309), (254, 320)], fill=(238, 230, 183, 230))

    # A restrained counter-rotation makes the two pieces feel physically torn.
    split_icon = split_icon.rotate(
        -5,
        resample=Image.Resampling.BICUBIC,
        expand=False,
        center=(256, 256),
    )
    chroma = Image.new("RGB", (size, size), (0, 255, 0))
    chroma.paste(split_icon.convert("RGB"), mask=split_icon.getchannel("A"))
    output.parent.mkdir(parents=True, exist_ok=True)
    chroma.save(output, format="PNG", optimize=True)


def remove_icon_chroma(chroma: Path, output: Path) -> None:
    if not CHROMA_HELPER.is_file():
        raise FileNotFoundError(f"Missing chroma helper: {CHROMA_HELPER}")

    temporary = chroma.with_name("things_split_alpha_512.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(CHROMA_HELPER),
            "--input",
            str(chroma),
            "--out",
            str(temporary),
            "--auto-key",
            "border",
            "--soft-matte",
            "--transparent-threshold",
            "12",
            "--opaque-threshold",
            "220",
            "--edge-contract",
            "1",
            "--despill",
            "--force",
        ],
        check=True,
    )

    with Image.open(temporary) as opened:
        icon = opened.convert("RGBA")
        icon = icon.resize((64, 64), Image.Resampling.LANCZOS)
        alpha = icon.getchannel("A").point(lambda value: 0 if value < 4 else value)
        icon.putalpha(alpha)
        icon.save(output, format="PNG", optimize=True)
    temporary.unlink(missing_ok=True)


def validate(event_path: Path, icon_path: Path) -> None:
    content_size = tuple(
        round(dimension * IMAGEGEN_CONTENT_SCALE) for dimension in EVENT_SIZE
    )
    validate_imagegen_geometry(content_size)

    with Image.open(event_path) as event:
        if event.size != EVENT_SIZE or event.mode != "RGBA":
            raise ValueError(f"Unexpected event texture: {event.size=} {event.mode=}")
        alpha_min, alpha_max = event.getchannel("A").getextrema()
        if (alpha_min, alpha_max) != (255, 255):
            raise ValueError("Event texture must be fully opaque")

        # The expanded illustration ends before 56% of the canvas; the remaining
        # event-copy field must stay pure black and free of scene detail.
        band = event.crop(
            (EVENT_TEXT_BLACK_START, 0, EVENT_SIZE[0], EVENT_SIZE[1])
        ).convert("L")
        if band.getextrema() != (0, 0):
            raise ValueError("Event text band is not pure black")

        # The vanilla portrait node overscans the texture.  These matte strips
        # preserve the authored hard edge after that crop and prevent regressions
        # back to a full-frame, oversized illustration.
        for label, box in (
            ("top", (0, 0, EVENT_SIZE[0], 100)),
            ("bottom", (0, EVENT_SIZE[1] - 100, EVENT_SIZE[0], EVENT_SIZE[1])),
            ("left", (0, 0, 100, EVENT_SIZE[1])),
        ):
            if event.crop(box).convert("L").getextrema()[1] != 0:
                raise ValueError(f"Event {label} framing matte is not pure black")

        # Outer black strips alone do not prove that a substantial hard edge
        # reaches the screen.  Measure a robust silhouette whose rows/columns
        # contain at least 100 painted pixels, then map its clearance through
        # the exact vanilla viewport, root offset, Portrait rect, fit mode, and
        # 1.04 node scale.  Area, span, and profile checks prevent a lone bright
        # pixel or an excessively shrunken plate from passing this contract.
        visible = event.convert("L").point(lambda value: 255 if value > 10 else 0)
        visible_bbox = visible.getbbox()
        if visible_bbox is None:
            raise ValueError("Event illustration is fully black")
        width, height = visible.size
        raw_rows = visible.tobytes()
        raw_columns = visible.transpose(Image.Transpose.TRANSPOSE).tobytes()
        row_counts = [
            raw_rows[y * width : (y + 1) * width].count(255)
            for y in range(height)
        ]
        column_counts = [
            raw_columns[x * height : (x + 1) * height].count(255)
            for x in range(width)
        ]
        painted_pixels = sum(row_counts)
        if painted_pixels < MIN_VISIBLE_PAINT_PIXELS:
            raise ValueError(
                "Event illustration is too small to read in the vanilla layout: "
                f"{painted_pixels=}"
            )

        robust_rows = [
            y for y, count in enumerate(row_counts) if count >= MIN_ROBUST_EDGE_SPAN
        ]
        robust_columns = [
            x
            for x, count in enumerate(column_counts)
            if count >= MIN_ROBUST_EDGE_SPAN
        ]
        if not robust_rows or not robust_columns:
            raise ValueError("Event illustration lacks a substantial visible silhouette")

        robust_left = robust_columns[0]
        robust_right = robust_columns[-1] + 1
        robust_top = robust_rows[0]
        robust_bottom = robust_rows[-1] + 1
        if robust_right - robust_left < 1000 or robust_bottom - robust_top < 900:
            raise ValueError(
                "Event illustration silhouette is too narrow or short: "
                f"robust_bbox={(robust_left, robust_top, robust_right, robust_bottom)}"
            )

        visible_left, visible_top, _, visible_bottom, screen_scale = (
            vanilla_visible_source_bounds()
        )
        clearances = {
            "left": (robust_left - visible_left) * screen_scale,
            "top": (robust_top - visible_top) * screen_scale,
            "bottom": (visible_bottom - robust_bottom) * screen_scale,
        }
        for label, clearance in clearances.items():
            if not (
                MIN_EDGE_CLEARANCE_SCREEN
                <= clearance
                <= MAX_EDGE_CLEARANCE_SCREEN
            ):
                raise ValueError(
                    f"Event {label} hard-edge clearance is outside the vanilla "
                    f"screen contract: {clearance:.1f}px"
                )

        left_profile = []
        for y in robust_rows:
            row = raw_rows[y * width : (y + 1) * width]
            left_profile.append(row.find(b"\xff"))
        top_profile = []
        bottom_profile = []
        for x in robust_columns:
            column = raw_columns[x * height : (x + 1) * height]
            top_profile.append(column.find(b"\xff"))
            bottom_profile.append(column.rfind(b"\xff"))
        profiles = {
            "left": left_profile,
            "top": top_profile,
            "bottom": bottom_profile,
        }
        for label, profile in profiles.items():
            variation = percentile(profile, 0.95) - percentile(profile, 0.05)
            if variation < MIN_EDGE_PROFILE_VARIATION:
                raise ValueError(
                    f"Event {label} boundary is too mechanically flat: {variation=}"
                )

    with Image.open(icon_path) as icon:
        if icon.size != (64, 64) or icon.mode != "RGBA":
            raise ValueError(f"Unexpected icon texture: {icon.size=} {icon.mode=}")
        alpha_min, alpha_max = icon.getchannel("A").getextrema()
        if alpha_min != 0 or alpha_max != 255:
            raise ValueError("Icon must contain transparent and opaque pixels")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--imagegen-source",
        type=Path,
        default=DEFAULT_IMAGEGEN_EVENT_SOURCE,
    )
    parser.add_argument(
        "--procedural-event",
        action="store_true",
        help="Use the legacy procedural plate instead of the approved imagegen plate.",
    )
    parser.add_argument("--event-out", type=Path, default=DEFAULT_EVENT_OUT)
    parser.add_argument("--icon-chroma", type=Path, default=DEFAULT_ICON_CHROMA)
    parser.add_argument("--icon-out", type=Path, default=DEFAULT_ICON_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.procedural_event:
        build_event(args.source, args.event_out)
    else:
        build_imagegen_event(args.imagegen_source, args.event_out)
    build_icon_chroma(args.icon_chroma)
    remove_icon_chroma(args.icon_chroma, args.icon_out)
    validate(args.event_out, args.icon_out)
    print(f"Built event art: {args.event_out}")
    print(f"Built enchantment icon: {args.icon_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
