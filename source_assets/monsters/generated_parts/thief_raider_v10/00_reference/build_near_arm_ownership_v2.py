#!/usr/bin/env python3
"""Correct Thief Raider near-dagger-arm ownership and build the upper-arm-only I2I guide.

The script is deliberately coordinate-locked to the v10 identity master.  It only
reassigns existing master pixels; it never repaints them and never touches formal
game resources.  Candidate 01 remains rejected evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Iterable, Sequence

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
V10_ROOT = HERE.parent
V9_ROOT = V10_ROOT.parent / "thief_raider_v9"
V9_VISIBLE_ROOT = V9_ROOT / "04_production_attachments"

MASTER_PATH = HERE / "current_master.png"
COORD_GRID_PATH = HERE / "near_arm_master_coord_grid.png"
V9_MANIFEST_PATH = V9_VISIBLE_ROOT / "production_visible.manifest.json"

OUTPUT_ROOT = HERE / "near_arm_ownership_v2"
AUDIT_PATH = OUTPUT_ROOT / "near_arm_ownership_v2_visual_audit_1536x1024.png"
RECONSTRUCTION_PATH = OUTPUT_ROOT / "full_bind_reconstruction.png"
MANIFEST_PATH = OUTPUT_ROOT / "near_arm_ownership_v2.manifest.json"

GUIDE_PATH = V10_ROOT / "01_image_to_image_families" / "near_upper_arm_i2i_guide_v02_1536x1024.png"
PROMPT_PATH = V10_ROOT / "01_image_to_image_families" / "near_upper_arm_imagegen_prompt_v02.txt"

TARGET_SEMANTICS = (
    "near_upper_arm",
    "near_forearm",
    "near_shoulder_plate",
    "near_dagger_hand",
    "dagger",
)

OWNERSHIP_COLORS = {
    "near_upper_arm": (73, 176, 255),
    "near_forearm": (255, 162, 69),
    "near_shoulder_plate": (255, 232, 96),
    "near_dagger_hand": (76, 234, 151),
    "dagger": (218, 82, 245),
}

BG = (18, 21, 27, 255)
PANEL = (27, 31, 39, 255)
PANEL_EDGE = (72, 80, 95, 255)
TEXT = (238, 241, 245, 255)
MUTED = (158, 168, 183, 255)
CYAN = (61, 229, 224, 255)
AMBER = (255, 185, 76, 255)
GREEN = (98, 230, 157, 255)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


F_TITLE = get_font(28, True)
F_H2 = get_font(20, True)
F_SLOT = get_font(17, True)
F_BODY = get_font(15)
F_SMALL = get_font(12)
F_TINY = get_font(10)


def rounded_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 16) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=PANEL, outline=PANEL_EDGE, width=2)


def checker(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], cell: int = 14) -> None:
    x0, y0, x1, y1 = box
    colors = ((39, 44, 53, 255), (49, 55, 65, 255))
    for y in range(y0, y1, cell):
        for x in range(x0, x1, cell):
            color = colors[((x - x0) // cell + (y - y0) // cell) & 1]
            draw.rectangle((x, y, min(x + cell - 1, x1 - 1), min(y + cell - 1, y1 - 1)), fill=color)


def contain(image: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    scale = min(max_size[0] / image.width, max_size[1] / image.height)
    return image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)


def paste_center(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    x = x0 + (x1 - x0 - image.width) // 2
    y = y0 + (y1 - y0 - image.height) // 2
    canvas.alpha_composite(image, (x, y))
    return (x, y, x + image.width, y + image.height)


def cubic_points(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    steps: int = 26,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for index in range(steps + 1):
        t = index / steps
        u = 1.0 - t
        points.append((
            u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
            u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
        ))
    return points


def dashed_polyline(
    draw: ImageDraw.ImageDraw,
    points: Sequence[tuple[float, float]],
    fill: tuple[int, int, int, int] = CYAN,
    width: int = 3,
    dash: float = 9.0,
    gap: float = 7.0,
) -> None:
    drawing = True
    remaining = dash
    for start, end in zip(points, points[1:]):
        x0, y0 = start
        x1, y1 = end
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length <= 0:
            continue
        position = 0.0
        while position < length:
            run = min(remaining, length - position)
            if drawing:
                a = position / length
                b = (position + run) / length
                draw.line((x0 + dx * a, y0 + dy * a, x0 + dx * b, y0 + dy * b), fill=fill, width=width)
            position += run
            remaining -= run
            if remaining <= 1e-6:
                drawing = not drawing
                remaining = dash if drawing else gap


def bbox_of(mask: np.ndarray) -> tuple[int, int, int, int]:
    y, x = np.where(mask)
    if len(x) == 0:
        return (0, 0, 1, 1)
    return (int(x.min()), int(y.min()), int(x.max()) + 1, int(y.max()) + 1)


def connected_component_areas(mask: np.ndarray) -> list[int]:
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    return sorted((int(stats[index, cv2.CC_STAT_AREA]) for index in range(1, count)), reverse=True)


def rgba_for_mask(master: np.ndarray, mask: np.ndarray) -> tuple[Image.Image, tuple[int, int, int, int]]:
    bbox = bbox_of(mask)
    x0, y0, x1, y1 = bbox
    crop = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
    local = mask[y0:y1, x0:x1]
    crop[local] = master[y0:y1, x0:x1][local]
    return Image.fromarray(crop, "RGBA"), bbox


def load_v9_layers(master_size: tuple[int, int]) -> tuple[dict, dict[str, np.ndarray], dict[str, np.ndarray], dict[str, Path]]:
    manifest = json.loads(V9_MANIFEST_PATH.read_text(encoding="utf-8"))
    width, height = master_size
    masks: dict[str, np.ndarray] = {}
    alphas: dict[str, np.ndarray] = {}
    files: dict[str, Path] = {}
    for record in manifest["parts"]:
        semantic = str(record["semantic"])
        path = V9_VISIBLE_ROOT / str(record["file"])
        if sha256(path) != str(record["sha256"]):
            raise RuntimeError(f"Source hash drift: {path}")
        image = np.array(Image.open(path).convert("RGBA"))
        x, y, w, h = [int(value) for value in record["source_bbox"]]
        if image.shape[1] != w or image.shape[0] != h:
            raise RuntimeError(f"Source bbox mismatch: {semantic}")
        mask = np.zeros((height, width), dtype=bool)
        alpha = np.zeros((height, width), dtype=np.uint8)
        mask[y:y+h, x:x+w] = image[:, :, 3] > 0
        alpha[y:y+h, x:x+w] = image[:, :, 3]
        masks[semantic] = mask
        alphas[semantic] = alpha
        files[semantic] = path
    return manifest, masks, alphas, files


def assert_global_coverage(master: np.ndarray, masks: dict[str, np.ndarray]) -> dict[str, int | bool]:
    foreground = master[:, :, 3] > 0
    coverage = np.zeros(foreground.shape, dtype=np.uint16)
    for mask in masks.values():
        coverage += mask.astype(np.uint16)
    uncovered = int((foreground & (coverage == 0)).sum())
    overlap = int((coverage > 1).sum())
    outside = int(((~foreground) & (coverage > 0)).sum())
    return {
        "foreground_pixels": int(foreground.sum()),
        "uncovered_pixels": uncovered,
        "overlap_pixels": overlap,
        "outside_pixels": outside,
        "pass": uncovered == 0 and overlap == 0 and outside == 0,
    }


def build_transfer_masks(
    master: np.ndarray,
    masks: dict[str, np.ndarray],
    alphas: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    height, width = master.shape[:2]
    yy, xx = np.indices((height, width))

    # 1. Exact bottom-rim sliver of the pauldron, including its bright core,
    # dark outline and antialiased diagonal edge.  Taking only high-value pixels
    # leaves a grey metal notch in the sleeve guide, so ownership follows the
    # complete coordinate-defined plate contour instead of a color threshold.
    sliver_polygon = np.array([(164, 229), (182, 224), (185, 229), (176, 233), (166, 233)], np.int32)
    polygon_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(polygon_mask, [sliver_polygon], 1)
    shoulder_sliver = masks["near_upper_arm"] & (polygon_mask > 0)
    if int(shoulder_sliver.sum()) != 68 or bbox_of(shoulder_sliver) != (165, 226, 186, 234):
        raise RuntimeError("Shoulder-sliver coordinate contract drifted")

    # 2. Pommel core is the 17x18 high-alpha island.  Grow only enough to take
    # its antialiased fringe; the main bracer component remains untouched.
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (alphas["near_forearm"] > 8).astype(np.uint8), connectivity=8
    )
    pommel_component = None
    for index in range(1, component_count):
        x, y, w, h = [int(value) for value in stats[index, :4]]
        if (x, y, w, h) == (142, 316, 17, 18):
            pommel_component = index
            break
    if pommel_component is None:
        raise RuntimeError("Pommel 17x18 component not found")
    pommel_core = labels == pommel_component
    pommel_fringe = cv2.dilate(pommel_core.astype(np.uint8), np.ones((5, 5), np.uint8), iterations=1) > 0
    pommel = masks["near_forearm"] & pommel_fringe & (xx >= 138) & (yy >= 312)
    if int(pommel.sum()) != 226 or bbox_of(pommel) != (140, 314, 161, 335):
        raise RuntimeError("Pommel ownership contract drifted")

    # 3. Visible handle is the narrow diagonal band above the fingers plus the
    # exposed right segment.  The piecewise lower boundary follows the actual
    # finger crests visible on the coordinate grid.  x=118..122 is deliberately
    # retained by the hand: those warm pixels are the thumb/finger edge, not wood.
    upper = 328.0 - 0.35 * (xx - 118)
    lower = upper + 18.0
    finger_crest = np.interp(xx, [118, 125, 132, 139, 146], [333, 331, 327, 324, 322])
    handle = (
        masks["near_dagger_hand"]
        & (xx >= 123)
        & (xx <= 158)
        & (yy >= upper)
        & (yy <= lower)
        & ((xx >= 146) | (yy <= finger_crest))
    )

    # Removing the visible band leaves eleven near-transparent pixels at the
    # exposed handle tip.  They follow the dagger too, leaving the hand as one
    # coherent wrist/palm/finger island.
    provisional_hand = masks["near_dagger_hand"] & ~handle
    count, component_labels, component_stats, _ = cv2.connectedComponentsWithStats(
        provisional_hand.astype(np.uint8), connectivity=8
    )
    ranked = sorted(range(1, count), key=lambda index: int(component_stats[index, cv2.CC_STAT_AREA]), reverse=True)
    handle_fringe = np.zeros_like(handle)
    for index in ranked[1:]:
        handle_fringe |= component_labels == index
    handle |= handle_fringe
    if int(handle.sum()) != 144 or bbox_of(handle) != (123, 321, 157, 337):
        raise RuntimeError("Handle ownership contract drifted")

    return {
        "shoulder_sliver": shoulder_sliver,
        "pommel": pommel,
        "handle": handle,
    }


def apply_transfers(masks: dict[str, np.ndarray], transfers: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    corrected = {semantic: mask.copy() for semantic, mask in masks.items()}
    corrected["near_upper_arm"] &= ~transfers["shoulder_sliver"]
    corrected["near_shoulder_plate"] |= transfers["shoulder_sliver"]
    corrected["near_forearm"] &= ~transfers["pommel"]
    corrected["dagger"] |= transfers["pommel"]
    corrected["near_dagger_hand"] &= ~transfers["handle"]
    corrected["dagger"] |= transfers["handle"]
    return corrected


def overlay_crop(
    master: np.ndarray,
    masks: dict[str, np.ndarray],
    crop: tuple[int, int, int, int],
    size: tuple[int, int],
    transfer_masks: dict[str, np.ndarray] | None = None,
) -> Image.Image:
    x0, y0, x1, y1 = crop
    base = master[y0:y1, x0:x1, :3].copy()
    for semantic in TARGET_SEMANTICS:
        mask = masks[semantic][y0:y1, x0:x1]
        color = np.array(OWNERSHIP_COLORS[semantic], dtype=np.float32)
        base[mask] = (base[mask].astype(np.float32) * 0.31 + color * 0.69).astype(np.uint8)
    if transfer_masks:
        transfer_colors = {
            "shoulder_sliver": (50, 240, 235),
            "pommel": (255, 190, 65),
            "handle": (255, 88, 190),
        }
        for semantic, mask_world in transfer_masks.items():
            mask = mask_world[y0:y1, x0:x1]
            base[mask] = np.array(transfer_colors[semantic], dtype=np.uint8)
    return Image.fromarray(base, "RGB").resize(size, Image.Resampling.NEAREST).convert("RGBA")


def coordinate_crop(
    master: np.ndarray,
    crop: tuple[int, int, int, int],
    size: tuple[int, int],
    transfers: dict[str, np.ndarray] | None = None,
    step: int = 10,
) -> Image.Image:
    x0, y0, x1, y1 = crop
    source = Image.fromarray(master[y0:y1, x0:x1], "RGBA")
    image = contain(source, (size[0] - 8, size[1] - 8))
    canvas = Image.new("RGBA", size, (14, 17, 22, 255))
    ox = (size[0] - image.width) // 2
    oy = (size[1] - image.height) // 2
    canvas.alpha_composite(image, (ox, oy))
    draw = ImageDraw.Draw(canvas)
    sx = image.width / (x1 - x0)
    sy = image.height / (y1 - y0)
    for gx in range(math.ceil(x0 / step) * step, x1 + 1, step):
        px = round(ox + (gx - x0) * sx)
        draw.line((px, oy, px, oy + image.height), fill=(0, 225, 225, 120), width=1)
        draw.text((px + 2, oy + 2), str(gx), font=F_TINY, fill=(0, 255, 255, 255))
    for gy in range(math.ceil(y0 / step) * step, y1 + 1, step):
        py = round(oy + (gy - y0) * sy)
        draw.line((ox, py, ox + image.width, py), fill=(255, 218, 0, 120), width=1)
        draw.text((ox + 2, py + 1), str(gy), font=F_TINY, fill=(255, 230, 0, 255))
    if transfers:
        colors = {
            "shoulder_sliver": (45, 242, 236, 255),
            "pommel": (255, 180, 55, 255),
            "handle": (255, 80, 185, 255),
        }
        for name, world_mask in transfers.items():
            local = world_mask[y0:y1, x0:x1].astype(np.uint8) * 255
            if local.max() == 0:
                continue
            resized = Image.fromarray(local, "L").resize((image.width, image.height), Image.Resampling.NEAREST)
            color_layer = Image.new("RGBA", (image.width, image.height), colors[name])
            color_layer.putalpha(resized.point(lambda value: 220 if value else 0))
            canvas.alpha_composite(color_layer, (ox, oy))
    return canvas


def build_visual_audit(
    master: np.ndarray,
    original: dict[str, np.ndarray],
    corrected: dict[str, np.ndarray],
    transfers: dict[str, np.ndarray],
    part_images: dict[str, Image.Image],
    part_records: dict[str, dict],
    global_audit: dict,
) -> None:
    canvas = Image.new("RGBA", (1536, 1024), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((32, 22), "THIEF RAIDER v10  /  CORRECTED NEAR-ARM OWNERSHIP", font=F_TITLE, fill=TEXT)
    draw.text((32, 57), "all visible pixels copied unchanged from current_master.png", font=F_BODY, fill=MUTED)

    panel_boxes = ((26, 88, 512, 606), (525, 88, 1011, 606), (1024, 88, 1510, 606))
    titles = ("COORDINATE TRANSFERS", "V9 OWNERSHIP — WRONG", "V10 OWNERSHIP — CORRECTED")
    for box, title in zip(panel_boxes, titles):
        rounded_panel(draw, box)
        draw.text((box[0] + 18, box[1] + 16), title, font=F_H2, fill=TEXT)

    crop = (70, 190, 220, 390)
    canvas.alpha_composite(coordinate_crop(master, crop, (450, 452), transfers, step=10), (44, 138))
    canvas.alpha_composite(overlay_crop(master, original, crop, (450, 452)), (543, 138))
    canvas.alpha_composite(overlay_crop(master, corrected, crop, (450, 452)), (1042, 138))

    draw.text((45, 574), "cyan shoulder sliver · amber pommel · magenta handle", font=F_SMALL, fill=MUTED)
    draw.text((543, 574), "plate sliver in arm · pommel in forearm · handle in hand", font=F_SMALL, fill=AMBER)
    draw.text((1042, 574), "plate owns metal · dagger owns handle/pommel · hand overlays", font=F_SMALL, fill=GREEN)

    cell_y0, cell_y1 = 626, 918
    gap = 12
    cell_w = (1484 - gap * 4) // 5
    for index, semantic in enumerate(TARGET_SEMANTICS):
        x0 = 26 + index * (cell_w + gap)
        box = (x0, cell_y0, x0 + cell_w, cell_y1)
        rounded_panel(draw, box, radius=14)
        draw.text((x0 + 14, cell_y0 + 13), semantic, font=F_SLOT, fill=TEXT)
        record = part_records[semantic]
        draw.text(
            (x0 + 14, cell_y0 + 39),
            f"pixels {record['visible_pixel_count']}  bbox {record['source_bbox_xyxy']}",
            font=F_TINY,
            fill=MUTED,
        )
        art_box = (x0 + 14, cell_y0 + 64, x0 + cell_w - 14, cell_y1 - 18)
        checker(draw, art_box, cell=12)
        enlarged = contain(part_images[semantic], (art_box[2] - art_box[0] - 18, art_box[3] - art_box[1] - 18))
        paste_center(canvas, enlarged, art_box)
        draw.rounded_rectangle(art_box, radius=10, outline=(61, 69, 82, 255), width=2)

    metrics = (
        f"GLOBAL RGBA RECONSTRUCTION: {'PASS' if global_audit['exact_rgba'] else 'FAIL'}    "
        f"uncovered {global_audit['uncovered_pixels']}    overlap {global_audit['overlap_pixels']}    "
        f"outside {global_audit['outside_pixels']}    transfers 68 / 226 / 144 px"
    )
    draw.rounded_rectangle((26, 938, 1510, 994), radius=14, fill=(24, 55, 47, 255), outline=(65, 145, 114, 255), width=2)
    draw.text((46, 953), metrics, font=F_H2, fill=GREEN)
    canvas.convert("RGB").save(AUDIT_PATH, format="PNG", optimize=True)


def draw_upper_underlap_hints(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    # Open contour pairs: they communicate direction and taper without drawing
    # a closed circular cap for the generator to imitate.
    dashed_polyline(draw, cubic_points(
        (x0 + .24*w, y0 + .08*h), (x0 + .27*w, y0 - 8),
        (x0 + .34*w, y0 - 19), (x0 + .40*w, y0 - 22)))
    dashed_polyline(draw, cubic_points(
        (x0 + .65*w, y0 + .08*h), (x0 + .61*w, y0 - 5),
        (x0 + .53*w, y0 - 17), (x0 + .47*w, y0 - 21)))
    dashed_polyline(draw, cubic_points(
        (x0 + .05*w, y0 + .57*h), (x0 - 8, y0 + .65*h),
        (x0 - 15, y0 + .72*h), (x0 - 18, y0 + .78*h)))
    dashed_polyline(draw, cubic_points(
        (x0 + .23*w, y0 + .89*h), (x0 + .11*w, y0 + .91*h),
        (x0 - 6, y0 + .86*h), (x0 - 13, y0 + .81*h)))


def build_upper_arm_guide(master: np.ndarray, upper_image: Image.Image, upper_record: dict) -> None:
    canvas = Image.new("RGBA", (1536, 1024), BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((34, 22), "THIEF RAIDER v10  /  NEAR UPPER ARM ONLY", font=F_TITLE, fill=TEXT)
    draw.text((34, 57), "corrected ownership v2 — generate one dark-cloth sleeve, not an arm family", font=F_BODY, fill=MUTED)

    full_panel = (28, 90, 602, 500)
    bind_panel = (28, 516, 602, 992)
    coord_panel = (620, 90, 988, 626)
    contract_panel = (620, 644, 988, 992)
    target_panel = (1006, 90, 1510, 992)
    for box in (full_panel, bind_panel, coord_panel, contract_panel, target_panel):
        rounded_panel(draw, box)

    draw.text((48, 108), "LOCKED IDENTITY MASTER", font=F_H2, fill=TEXT)
    draw.text((48, 137), "compact crouch · left-facing 3/4 · original palette", font=F_SMALL, fill=MUTED)
    master_image = Image.fromarray(master, "RGBA")
    full = contain(master_image, (522, 328))
    full_box = paste_center(canvas, full, (48, 158, 582, 484))
    sx = (full_box[2] - full_box[0]) / master.shape[1]
    sy = (full_box[3] - full_box[1]) / master.shape[0]
    focus = (132, 194, 218, 302)
    focus_full = (
        round(full_box[0] + focus[0] * sx), round(full_box[1] + focus[1] * sy),
        round(full_box[0] + focus[2] * sx), round(full_box[1] + focus[3] * sy),
    )
    draw.rounded_rectangle(focus_full, radius=7, outline=AMBER, width=3)

    draw.text((48, 534), "BIND-POSE CONTEXT", font=F_H2, fill=TEXT)
    draw.text((48, 563), "pauldron above · bracer below · sleeve axis stays diagonal", font=F_SMALL, fill=MUTED)
    bind_crop = master_image.crop((120, 184, 225, 320))
    bind_zoom = contain(bind_crop, (510, 382))
    bind_art = (48, 590, 582, 970)
    checker(draw, bind_art)
    paste_center(canvas, bind_zoom, bind_art)
    draw.rounded_rectangle(bind_art, radius=10, outline=(61, 69, 82, 255), width=2)

    draw.text((640, 108), "SOURCE COORDINATES", font=F_H2, fill=TEXT)
    draw.text((640, 137), "ownership corrected at native 534×420 pixels", font=F_SMALL, fill=MUTED)
    coord = coordinate_crop(master, (132, 194, 218, 302), (328, 458), None, step=10)
    canvas.alpha_composite(coord, (640, 157))

    draw.text((640, 662), "ONE-PIECE CONTRACT", font=F_H2, fill=TEXT)
    contract_lines = (
        (GREEN, "dark charcoal cloth only"),
        (GREEN, "same 77×64 visible envelope"),
        (CYAN, "short shoulder overlap"),
        (CYAN, "short elbow overlap"),
        (AMBER, "zero pauldron metal"),
        (AMBER, "zero bracer / hand / weapon"),
        (AMBER, "zero caps / tubes / sockets"),
    )
    for index, (color, label) in enumerate(contract_lines):
        y = 706 + index * 37
        draw.ellipse((642, y + 5, 653, y + 16), fill=color)
        draw.text((663, y), label, font=F_BODY, fill=TEXT)
    draw.text((642, 966), "cyan dashes are unfilled hidden-contour hints", font=F_SMALL, fill=MUTED)

    draw.text((1026, 108), "TARGET  /  EXACTLY ONE PIECE", font=F_H2, fill=TEXT)
    draw.text((1026, 137), "near_upper_arm · corrected master-visible pixels", font=F_SMALL, fill=MUTED)
    draw.rounded_rectangle((1026, 168, 1213, 197), radius=9, fill=(31, 78, 65, 255))
    draw.ellipse((1037, 177, 1048, 188), fill=GREEN)
    draw.text((1058, 173), "MASTER PIXELS · NO METAL", font=F_SMALL, fill=GREEN)
    target_art = (1030, 220, 1486, 760)
    checker(draw, target_art, cell=16)
    enlarged = contain(upper_image, (352, 292))
    placed = paste_center(canvas, enlarged, target_art)
    draw_upper_underlap_hints(draw, placed)
    draw.rounded_rectangle(target_art, radius=12, outline=(61, 69, 82, 255), width=2)
    dashed_polyline(draw, [(1040, 793), (1095, 793)], CYAN, width=3)
    draw.text((1107, 783), "concealed continuation only — do not paint the cyan", font=F_SMALL, fill=MUTED)

    draw.rounded_rectangle((1030, 834, 1486, 962), radius=13, fill=(45, 34, 31, 255), outline=(123, 86, 60, 255), width=2)
    draw.text((1050, 851), "DO NOT GENERATE", font=F_SLOT, fill=AMBER)
    draw.text((1050, 881), "pauldron · metal sliver · forearm · bracer", font=F_BODY, fill=TEXT)
    draw.text((1050, 909), "hand · handle · pommel · dagger · full character", font=F_BODY, fill=TEXT)
    draw.text((1050, 937), "round caps · flat cuffs · hollow ends · sausage volume", font=F_BODY, fill=TEXT)
    canvas.convert("RGB").save(GUIDE_PATH, format="PNG", optimize=True)


def main() -> None:
    for path in (MASTER_PATH, COORD_GRID_PATH, V9_MANIFEST_PATH, PROMPT_PATH):
        if not path.exists():
            raise FileNotFoundError(path)

    master = np.array(Image.open(MASTER_PATH).convert("RGBA"))
    height, width = master.shape[:2]
    if (width, height) != (534, 420):
        raise RuntimeError(f"Unexpected identity canvas: {(width, height)}")
    if sha256(MASTER_PATH) != "643a86c7d8b9bb885161ac6abad39f8c3b8af09fcb8ad8e016b90feee73b06fb":
        raise RuntimeError("Identity master hash drifted")

    source_manifest, original_masks, source_alphas, source_files = load_v9_layers((width, height))
    original_audit = assert_global_coverage(master, original_masks)
    if not original_audit["pass"]:
        raise RuntimeError(f"V9 ownership source is not exact: {original_audit}")

    transfers = build_transfer_masks(master, original_masks, source_alphas)
    corrected_masks = apply_transfers(original_masks, transfers)
    corrected_audit = assert_global_coverage(master, corrected_masks)
    if not corrected_audit["pass"]:
        raise RuntimeError(f"Corrected coverage failed: {corrected_audit}")

    # The five-part arm union itself must be invariant across reassignment.
    original_union = np.logical_or.reduce([original_masks[name] for name in TARGET_SEMANTICS])
    corrected_union = np.logical_or.reduce([corrected_masks[name] for name in TARGET_SEMANTICS])
    if not np.array_equal(original_union, corrected_union):
        raise RuntimeError("Corrected arm union differs from v9 arm union")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    GUIDE_PATH.parent.mkdir(parents=True, exist_ok=True)

    part_images: dict[str, Image.Image] = {}
    part_records: dict[str, dict] = {}
    for semantic in TARGET_SEMANTICS:
        image, bbox = rgba_for_mask(master, corrected_masks[semantic])
        path = OUTPUT_ROOT / f"{semantic}.png"
        image.save(path, format="PNG", optimize=True)
        part_images[semantic] = image
        part_records[semantic] = {
            "file": path.name,
            "sha256": sha256(path),
            "source_bbox_xyxy": list(bbox),
            "size": list(image.size),
            "visible_pixel_count": int(corrected_masks[semantic].sum()),
            "connected_component_areas": connected_component_areas(corrected_masks[semantic]),
        }

    # Full 28-layer reconstruction proves the correction is a pure reassignment.
    reconstruction = np.zeros_like(master)
    coverage = np.zeros((height, width), dtype=np.uint16)
    for mask in corrected_masks.values():
        coverage += mask.astype(np.uint16)
        reconstruction[mask] = master[mask]
    exact_rgba = bool(np.array_equal(reconstruction, master))
    Image.fromarray(reconstruction, "RGBA").save(RECONSTRUCTION_PATH, format="PNG", optimize=True)
    if not exact_rgba:
        raise RuntimeError("Full RGBA reconstruction differs from current master")

    global_audit = {
        **corrected_audit,
        "exact_rgba": exact_rgba,
        "reconstruction_sha256": sha256(RECONSTRUCTION_PATH),
        "arm_union_exact": bool(np.array_equal(original_union, corrected_union)),
    }

    build_visual_audit(
        master,
        original_masks,
        corrected_masks,
        transfers,
        part_images,
        part_records,
        global_audit,
    )
    build_upper_arm_guide(master, part_images["near_upper_arm"], part_records["near_upper_arm"])

    transfer_records = {
        "shoulder_sliver": {
            "from": "near_upper_arm",
            "to": "near_shoulder_plate",
            "pixel_count": int(transfers["shoulder_sliver"].sum()),
            "bbox_xyxy": list(bbox_of(transfers["shoulder_sliver"])),
            "semantic_reason": "complete pauldron bottom-rim sliver including metal core, dark outline and antialiasing",
        },
        "pommel": {
            "from": "near_forearm",
            "to": "dagger",
            "pixel_count": int(transfers["pommel"].sum()),
            "bbox_xyxy": list(bbox_of(transfers["pommel"])),
            "semantic_reason": "17x18 pommel-cap island plus antialiased fringe",
        },
        "handle": {
            "from": "near_dagger_hand",
            "to": "dagger",
            "pixel_count": int(transfers["handle"].sum()),
            "bbox_xyxy": list(bbox_of(transfers["handle"])),
            "semantic_reason": "visible diagonal handle band behind gripping fingers",
        },
    }

    manifest = {
        "schema_version": 2,
        "status": "corrected_ownership_pass_upper_arm_i2i_ready",
        "formal_resources_modified": False,
        "identity": {
            "file": str(MASTER_PATH.relative_to(V10_ROOT)).replace("\\", "/"),
            "sha256": sha256(MASTER_PATH),
            "canvas": [width, height],
        },
        "coordinate_reference": {
            "file": str(COORD_GRID_PATH.relative_to(V10_ROOT)).replace("\\", "/"),
            "sha256": sha256(COORD_GRID_PATH),
        },
        "source_ownership": {
            "manifest": str(V9_MANIFEST_PATH.relative_to(V10_ROOT.parent)).replace("\\", "/"),
            "manifest_sha256": sha256(V9_MANIFEST_PATH),
            "audit": original_audit,
            "source_files": {
                semantic: {
                    "file": str(source_files[semantic].relative_to(V10_ROOT.parent)).replace("\\", "/"),
                    "sha256": sha256(source_files[semantic]),
                }
                for semantic in TARGET_SEMANTICS
            },
        },
        "transfers": transfer_records,
        "corrected_parts": part_records,
        "draw_order_contract_bottom_to_top": [
            "near_upper_arm",
            "near_forearm",
            "near_shoulder_plate",
            "dagger",
            "near_dagger_hand",
        ],
        "draw_order_invariant": "near_dagger_hand overlays dagger handle and pommel",
        "global_reconstruction_audit": global_audit,
        "artifacts": {
            "visual_audit": {
                "file": str(AUDIT_PATH.relative_to(V10_ROOT)).replace("\\", "/"),
                "sha256": sha256(AUDIT_PATH),
                "size": [1536, 1024],
            },
            "upper_arm_guide": {
                "file": str(GUIDE_PATH.relative_to(V10_ROOT)).replace("\\", "/"),
                "sha256": sha256(GUIDE_PATH),
                "size": [1536, 1024],
                "target_piece_count": 1,
            },
            "upper_arm_prompt": {
                "file": str(PROMPT_PATH.relative_to(V10_ROOT)).replace("\\", "/"),
                "sha256": sha256(PROMPT_PATH),
            },
            "full_bind_reconstruction": {
                "file": str(RECONSTRUCTION_PATH.relative_to(V10_ROOT)).replace("\\", "/"),
                "sha256": sha256(RECONSTRUCTION_PATH),
            },
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print("THIEF_V10_NEAR_ARM_OWNERSHIP_V2_PASS")
    print(f"manifest={MANIFEST_PATH}")
    print(f"audit={AUDIT_PATH}")
    print(f"guide={GUIDE_PATH}")
    print(f"prompt={PROMPT_PATH}")
    print(f"global_exact_rgba={exact_rgba}")
    print("transfers=68/226/144")


if __name__ == "__main__":
    main()
