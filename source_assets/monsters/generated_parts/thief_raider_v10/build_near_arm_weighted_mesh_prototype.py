#!/usr/bin/env python3
"""Build and render a weighted near-arm cloth prototype.

The context-reveal image supplies a continuous shoulder-to-wrist cloth base.
Exact master-owned upper-arm and forearm pixels remain separate overlays, but
all three are deformed by the same two-bone mesh.  This tests the production
solution for the round-cap/gap failure seen with rigid cutout pieces.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
MASTER_PATH = ROOT / "00_reference/current_master.png"
DONOR_PATH = ROOT / "02_semantic_parts/near_upper_arm_context_01/context_reveal_master_space.png"
GENERATED_ELBOW_PATCH = ROOT / "01_image_to_image_families/near_elbow_fold_candidate_01_alpha.png"
OWNERSHIP_ROOT = ROOT / "00_reference/near_arm_ownership_v2"
OWNERSHIP_MANIFEST = OWNERSHIP_ROOT / "near_arm_ownership_v2.manifest.json"
OUT = ROOT / "05_spine_prototype/near_arm_weighted_mesh_v05"

WIDTH, HEIGHT = 534, 420
SHOULDER = np.array([171.0, 224.0], dtype=np.float32)
ELBOW = np.array([139.0, 283.0], dtype=np.float32)
WRIST = np.array([110.0, 321.0], dtype=np.float32)
MESH_BOUNDS = (88, 184, 216, 346)
GRID_STEP = 8


def _font(size: int) -> ImageFont.ImageFont:
    for path in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _load_corrected_parts() -> tuple[dict[str, np.ndarray], dict[str, object]]:
    manifest = json.loads(OWNERSHIP_MANIFEST.read_text(encoding="utf-8-sig"))
    parts: dict[str, np.ndarray] = {}
    for name, record in manifest["corrected_parts"].items():
        crop = np.asarray(Image.open(OWNERSHIP_ROOT / record["file"]).convert("RGBA"), dtype=np.uint8)
        left, top, right, bottom = map(int, record["source_bbox_xyxy"])
        canvas = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
        canvas[top:bottom, left:right] = crop
        parts[name] = canvas
    return parts, manifest


def _context_cloth_mask(donor: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(donor[:, :, :3], cv2.COLOR_RGB2HSV)
    roi = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    cv2.line(roi, tuple(SHOULDER.astype(int)), tuple(ELBOW.astype(int)), 255, 58, cv2.LINE_AA)
    cv2.line(roi, tuple(ELBOW.astype(int)), tuple(WRIST.astype(int)), 255, 46, cv2.LINE_AA)
    cv2.circle(roi, tuple(SHOULDER.astype(int)), 29, 255, -1, cv2.LINE_AA)
    cv2.circle(roi, tuple(ELBOW.astype(int)), 27, 255, -1, cv2.LINE_AA)
    cv2.circle(roi, tuple(WRIST.astype(int)), 22, 255, -1, cv2.LINE_AA)
    cloth = (
        (donor[:, :, 3] >= 80)
        & (roi > 0)
        & (hsv[:, :, 1] <= 95)
        & (hsv[:, :, 2] >= 18)
        & (hsv[:, :, 2] <= 150)
    )
    count, labels, stats, _ = cv2.connectedComponentsWithStats(cloth.astype(np.uint8), 8)
    seed_label = int(labels[260, 150])
    if seed_label <= 0:
        raise RuntimeError("context cloth seed is not foreground")
    mask = labels == seed_label
    if int(stats[seed_label, cv2.CC_STAT_AREA]) < 3000:
        raise RuntimeError("context cloth component unexpectedly small")
    return mask


def _fit_donor_color(master: np.ndarray, donor: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
    valid = (reference[:, :, 3] >= 192) & (donor[:, :, 3] >= 192)
    corrected = donor.copy()
    report: dict[str, object] = {}
    for channel, name in enumerate(("r", "g", "b")):
        source = donor[:, :, channel][valid].astype(np.float32)
        target = master[:, :, channel][valid].astype(np.float32)
        design = np.column_stack((source, np.ones_like(source)))
        slope, intercept = np.linalg.lstsq(design, target, rcond=None)[0]
        slope = float(np.clip(slope, 0.80, 1.20))
        intercept = float(np.clip(intercept, -24.0, 24.0))
        corrected[:, :, channel] = np.clip(donor[:, :, channel].astype(np.float32) * slope + intercept, 0, 255).astype(np.uint8)
        report[name] = {"slope": round(slope, 7), "intercept": round(intercept, 7)}
    return corrected, report


def _partition_forearm(part: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, int]]:
    """Split exact forearm pixels into deforming cloth and rigid materials."""
    alpha = part[:, :, 3] > 0
    hsv = cv2.cvtColor(part[:, :, :3], cv2.COLOR_RGB2HSV)
    hue, saturation, value = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    metal_seed = alpha & (saturation <= 58) & (value >= 72)
    leather_seed = alpha & (hue <= 30) & (saturation >= 38) & (value >= 18) & ~metal_seed
    # Include antialiased outlines with the hard material they border.  Metal
    # gets priority, then leather; the remaining dark sleeve deforms with the
    # continuous cloth mesh.
    metal_mask = cv2.dilate(metal_seed.astype(np.uint8), np.ones((5, 5), np.uint8), 1).astype(bool) & alpha
    leather_mask = cv2.dilate(leather_seed.astype(np.uint8), np.ones((3, 3), np.uint8), 1).astype(bool) & alpha & ~metal_mask
    cloth_mask = alpha & ~metal_mask & ~leather_mask
    layers = []
    for mask in (cloth_mask, leather_mask, metal_mask):
        layer = np.zeros_like(part)
        layer[mask] = part[mask]
        layers.append(layer)
    counts = {"cloth": int(cloth_mask.sum()), "leather": int(leather_mask.sum()), "metal": int(metal_mask.sum())}
    if sum(counts.values()) != int(alpha.sum()):
        raise RuntimeError("forearm material partition does not cover exact alpha")
    return layers[0], layers[1], layers[2], counts


def _chain_coordinate(point: np.ndarray) -> float:
    upper = ELBOW - SHOULDER
    fore = WRIST - ELBOW
    upper_len = float(np.linalg.norm(upper))
    fore_len = float(np.linalg.norm(fore))
    upper_t = float(np.clip(np.dot(point - SHOULDER, upper) / np.dot(upper, upper), 0.0, 1.0))
    fore_t = float(np.clip(np.dot(point - ELBOW, fore) / np.dot(fore, fore), 0.0, 1.0))
    upper_near = SHOULDER + upper * upper_t
    fore_near = ELBOW + fore * fore_t
    if np.linalg.norm(point - upper_near) <= np.linalg.norm(point - fore_near):
        return upper_t * upper_len
    return upper_len + fore_t * fore_len


def _smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def _rotate_point(point: np.ndarray, pivot: np.ndarray, angle_deg: float) -> np.ndarray:
    angle = math.radians(angle_deg)
    cosine, sine = math.cos(angle), math.sin(angle)
    rotation = np.array([[cosine, -sine], [sine, cosine]], dtype=np.float32)
    return pivot + rotation @ (point - pivot)


def _deform_point(point: np.ndarray, shoulder_deg: float, elbow_deg: float) -> np.ndarray:
    elbow_after = _rotate_point(ELBOW, SHOULDER, shoulder_deg)
    upper_result = _rotate_point(point, SHOULDER, shoulder_deg)
    shoulder_then = _rotate_point(point, SHOULDER, shoulder_deg)
    fore_result = _rotate_point(shoulder_then, elbow_after, elbow_deg)
    upper_len = float(np.linalg.norm(ELBOW - SHOULDER))
    chain = _chain_coordinate(point)
    fore_weight = _smoothstep((chain - (upper_len - 12.0)) / 24.0)
    return upper_result * (1.0 - fore_weight) + fore_result * fore_weight


def _alpha_over(bottom: np.ndarray, top: np.ndarray) -> np.ndarray:
    result = Image.fromarray(bottom, "RGBA")
    result.alpha_composite(Image.fromarray(top, "RGBA"))
    return np.asarray(result, dtype=np.uint8)


def _warp_triangle(source: np.ndarray, destination: np.ndarray, source_tri: np.ndarray, destination_tri: np.ndarray) -> None:
    source_rect = cv2.boundingRect(source_tri.astype(np.float32))
    dest_rect = cv2.boundingRect(destination_tri.astype(np.float32))
    sx, sy, sw, sh = source_rect
    dx, dy, dw, dh = dest_rect
    if sw <= 0 or sh <= 0 or dw <= 0 or dh <= 0:
        return
    source_local = source_tri - np.array([sx, sy], dtype=np.float32)
    dest_local = destination_tri - np.array([dx, dy], dtype=np.float32)
    source_crop = source[sy : sy + sh, sx : sx + sw]
    matrix = cv2.getAffineTransform(source_local.astype(np.float32), dest_local.astype(np.float32))
    warped = cv2.warpAffine(
        source_crop,
        matrix,
        (dw, dh),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    triangle_mask = np.zeros((dh, dw), dtype=np.uint8)
    cv2.fillConvexPoly(triangle_mask, np.round(dest_local).astype(np.int32), 255, cv2.LINE_AA)
    warped[:, :, 3] = (warped[:, :, 3].astype(np.uint16) * triangle_mask.astype(np.uint16) // 255).astype(np.uint8)
    left, top = max(0, dx), max(0, dy)
    right, bottom = min(WIDTH, dx + dw), min(HEIGHT, dy + dh)
    if left >= right or top >= bottom:
        return
    crop = warped[top - dy : bottom - dy, left - dx : right - dx]
    region = destination[top:bottom, left:right]
    # Triangles tile one mesh; alpha-over on every shared edge creates a dark
    # crosshatch that the actual Spine mesh renderer does not have.  Directly
    # assign covered pixels so shared edges are sampled once.
    covered = triangle_mask[top - dy : bottom - dy, left - dx : right - dx] >= 128
    region[covered] = crop[covered]
    destination[top:bottom, left:right] = region


def _mesh_warp(source: np.ndarray, shoulder_deg: float, elbow_deg: float) -> np.ndarray:
    left, top, right, bottom = MESH_BOUNDS
    xs = list(range(left, right, GRID_STEP)) + [right]
    ys = list(range(top, bottom, GRID_STEP)) + [bottom]
    map_x = np.full((HEIGHT, WIDTH), -1.0, dtype=np.float32)
    map_y = np.full((HEIGHT, WIDTH), -1.0, dtype=np.float32)
    for yi in range(len(ys) - 1):
        for xi in range(len(xs) - 1):
            corners = np.array(
                [
                    [xs[xi], ys[yi]],
                    [xs[xi + 1], ys[yi]],
                    [xs[xi + 1], ys[yi + 1]],
                    [xs[xi], ys[yi + 1]],
                ],
                dtype=np.float32,
            )
            deformed = np.array([_deform_point(point, shoulder_deg, elbow_deg) for point in corners], dtype=np.float32)
            for indices in ((0, 1, 2), (0, 2, 3)):
                source_tri = corners[list(indices)]
                dest_tri = deformed[list(indices)]
                dx, dy, dw, dh = cv2.boundingRect(dest_tri.astype(np.float32))
                left_clip, top_clip = max(0, dx), max(0, dy)
                right_clip, bottom_clip = min(WIDTH, dx + dw), min(HEIGHT, dy + dh)
                if left_clip >= right_clip or top_clip >= bottom_clip:
                    continue
                local = dest_tri - np.array([dx, dy], dtype=np.float32)
                mask = np.zeros((dh, dw), dtype=np.uint8)
                cv2.fillConvexPoly(mask, np.round(local).astype(np.int32), 255, cv2.LINE_8)
                inverse = cv2.getAffineTransform(dest_tri.astype(np.float32), source_tri.astype(np.float32))
                yy, xx = np.indices((bottom_clip - top_clip, right_clip - left_clip), dtype=np.float32)
                world_x = xx + left_clip
                world_y = yy + top_clip
                source_x = inverse[0, 0] * world_x + inverse[0, 1] * world_y + inverse[0, 2]
                source_y = inverse[1, 0] * world_x + inverse[1, 1] * world_y + inverse[1, 2]
                local_mask = mask[top_clip - dy : bottom_clip - dy, left_clip - dx : right_clip - dx] > 0
                region_x = map_x[top_clip:bottom_clip, left_clip:right_clip]
                region_y = map_y[top_clip:bottom_clip, left_clip:right_clip]
                region_x[local_mask] = source_x[local_mask]
                region_y[local_mask] = source_y[local_mask]
                map_x[top_clip:bottom_clip, left_clip:right_clip] = region_x
                map_y[top_clip:bottom_clip, left_clip:right_clip] = region_y
    return cv2.remap(
        source,
        map_x,
        map_y,
        interpolation=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )


def _rigid_forearm(source: np.ndarray, shoulder_deg: float, elbow_deg: float) -> np.ndarray:
    elbow_after = _rotate_point(ELBOW, SHOULDER, shoulder_deg)
    # Derive a three-point affine transform for the exact two-rotation chain.
    basis = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    world = basis + ELBOW
    transformed = []
    for point in world:
        after_shoulder = _rotate_point(point, SHOULDER, shoulder_deg)
        transformed.append(_rotate_point(after_shoulder, elbow_after, elbow_deg))
    matrix = cv2.getAffineTransform(world, np.asarray(transformed, dtype=np.float32))
    return cv2.warpAffine(source, matrix, (WIDTH, HEIGHT), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))


def _rigid_shoulder(source: np.ndarray, angle: float) -> np.ndarray:
    matrix = cv2.getRotationMatrix2D(tuple(SHOULDER), angle, 1.0)
    return cv2.warpAffine(source, matrix, (WIDTH, HEIGHT), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))


def _build_elbow_patch(donor_corrected: np.ndarray, cloth_mask: np.ndarray) -> np.ndarray:
    shape = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
    # A slanted, asymmetric cloth fold sampled from the in-context reveal.
    polygon = np.array([(114, 276), (127, 261), (151, 258), (163, 277), (155, 299), (132, 308), (113, 294)], dtype=np.int32)
    cv2.fillConvexPoly(shape, polygon, 255, cv2.LINE_AA)
    shape = cv2.GaussianBlur(shape, (0, 0), 1.0)
    patch = np.zeros_like(donor_corrected)
    alpha = donor_corrected[:, :, 3].astype(np.float32) * (shape.astype(np.float32) / 255.0)
    mask = cloth_mask & (alpha >= 1.0)
    patch[mask] = donor_corrected[mask]
    patch[:, :, 3] = np.where(mask, np.clip(alpha, 0, 255), 0).astype(np.uint8)
    return patch


def _prepare_generated_elbow_patch(candidate: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
    alpha = candidate[:, :, 3]
    ys, xs = np.where(alpha >= 24)
    if not len(xs):
        raise RuntimeError("generated elbow patch is empty")
    crop = candidate[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1].copy()
    source_valid = crop[:, :, 3] >= 192
    target_valid = reference[:, :, 3] >= 192
    report: dict[str, object] = {}
    for channel, name in enumerate(("r", "g", "b")):
        source = crop[:, :, channel][source_valid].astype(np.float32)
        target = reference[:, :, channel][target_valid].astype(np.float32)
        source_mean, source_std = float(source.mean()), float(source.std())
        target_mean, target_std = float(target.mean()), float(target.std())
        # Preserve the generated broad fold while bringing its purple/blue
        # cast back to the locked Raider sleeve.  Reduced variance prevents the
        # high-resolution donor from looking noisier than the game sprite.
        scale = float(np.clip((target_std / max(1.0, source_std)) * 0.78, 0.58, 1.18))
        mapped = (crop[:, :, channel].astype(np.float32) - source_mean) * scale + target_mean + 3.0
        crop[:, :, channel] = np.clip(mapped, 0, 255).astype(np.uint8)
        report[name] = {
            "source_mean": round(source_mean, 5),
            "target_mean": round(target_mean, 5),
            "source_std": round(source_std, 5),
            "target_std": round(target_std, 5),
            "scale": round(scale, 7),
        }
    patch_image = Image.fromarray(crop, "RGBA").resize((58, 42), Image.Resampling.LANCZOS)
    patch_image = patch_image.rotate(30.0, resample=Image.Resampling.BICUBIC, expand=True)
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    left = int(round(ELBOW[0] - patch_image.width / 2))
    top = int(round(ELBOW[1] - patch_image.height / 2))
    canvas.alpha_composite(patch_image, (left, top))
    prepared = np.asarray(canvas, dtype=np.uint8)
    report["source_bbox"] = [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]
    report["prepared_size"] = [patch_image.width, patch_image.height]
    report["prepared_pixels"] = int((prepared[:, :, 3] >= 24).sum())
    report["setup_rotation_deg"] = 30.0
    return prepared, report


def _elbow_patch_pose(source: np.ndarray, shoulder_deg: float, elbow_deg: float) -> np.ndarray:
    elbow_after = _rotate_point(ELBOW, SHOULDER, shoulder_deg)
    angle = shoulder_deg + elbow_deg * 0.5
    magnitude = abs(elbow_deg)
    scale_x = 1.0 + min(0.34, magnitude * 0.0031)
    scale_y = 1.0 + min(0.16, magnitude * 0.00145)
    radians = math.radians(angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    rotation = np.array([[cosine, -sine], [sine, cosine]], dtype=np.float32)
    scaling = np.diag([scale_x, scale_y]).astype(np.float32)
    linear = rotation @ scaling
    translation = elbow_after - linear @ ELBOW
    matrix = np.column_stack((linear, translation)).astype(np.float32)
    posed = cv2.warpAffine(source, matrix, (WIDTH, HEIGHT), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    # Hidden in setup; fades in only when a real bend would expose the joint.
    fade = _smoothstep((magnitude - 20.0) / 35.0)
    posed[:, :, 3] = np.clip(posed[:, :, 3].astype(np.float32) * fade, 0, 255).astype(np.uint8)
    return posed


def _checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
    width, height = size
    yy, xx = np.indices((height, width))
    value = np.where(((xx // cell + yy // cell) & 1) == 0, 38, 51).astype(np.uint8)
    return Image.fromarray(np.dstack((value, value + 3, value + 8, np.full_like(value, 255))), "RGBA")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master = np.asarray(Image.open(MASTER_PATH).convert("RGBA"), dtype=np.uint8)
    donor = np.asarray(Image.open(DONOR_PATH).convert("RGBA"), dtype=np.uint8)
    parts, ownership = _load_corrected_parts()
    forearm_cloth, forearm_leather, forearm_metal, forearm_partition = _partition_forearm(parts["near_forearm"])
    cloth_mask = _context_cloth_mask(donor)
    donor_corrected, color_fit = _fit_donor_color(master, donor, parts["near_upper_arm"])
    cloth_base = np.zeros_like(donor)
    cloth_base[cloth_mask] = donor_corrected[cloth_mask]
    Image.fromarray(cloth_base, "RGBA").save(OUT / "near_arm_cloth_base.png")
    generated_patch = np.asarray(Image.open(GENERATED_ELBOW_PATCH).convert("RGBA"), dtype=np.uint8)
    elbow_patch, elbow_patch_report = _prepare_generated_elbow_patch(generated_patch, parts["near_upper_arm"])
    Image.fromarray(elbow_patch, "RGBA").save(OUT / "near_elbow_fold_patch.png")

    cases = [
        ("bind", 0.0, 0.0),
        ("shoulder_back_45", -45.0, 0.0),
        ("shoulder_forward_45", 45.0, 0.0),
        ("elbow_open_55", 0.0, -55.0),
        ("elbow_close_75", 0.0, 75.0),
        ("elbow_close_110", 0.0, 110.0),
    ]
    cards: list[Image.Image] = []
    case_metrics: list[dict[str, object]] = []
    for name, shoulder_deg, elbow_deg in cases:
        base = _mesh_warp(cloth_base, shoulder_deg, elbow_deg)
        Image.fromarray(base, "RGBA").save(OUT / f"debug_base_{name}.png")
        fold = _elbow_patch_pose(elbow_patch, shoulder_deg, elbow_deg)
        Image.fromarray(fold, "RGBA").save(OUT / f"debug_fold_{name}.png")
        upper = _mesh_warp(parts["near_upper_arm"], shoulder_deg, elbow_deg)
        # Keep the complete exact forearm mesh underneath so material-boundary
        # pixels never tear.  A rigid metal duplicate on top prevents the hard
        # bracer plate from visibly rubber-bending; the underlying duplicate is
        # covered in ordinary poses and acts as one-pixel seam insurance.
        forearm = _mesh_warp(parts["near_forearm"], shoulder_deg, elbow_deg)
        metal = _rigid_forearm(forearm_metal, shoulder_deg, elbow_deg)
        plate = _rigid_shoulder(parts["near_shoulder_plate"], shoulder_deg * 0.42)
        dagger = _rigid_forearm(parts["dagger"], shoulder_deg, elbow_deg)
        hand = _rigid_forearm(parts["near_dagger_hand"], shoulder_deg, elbow_deg)
        composite = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
        for layer in (base, fold, upper, forearm, metal, plate, dagger, hand):
            composite = _alpha_over(composite, layer)
        Image.fromarray(composite, "RGBA").save(OUT / f"{name}.png")
        alpha = composite[:, :, 3]
        ys, xs = np.where(alpha >= 24)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]
        crop = Image.fromarray(composite, "RGBA").crop(tuple(bbox))
        card = _checker((460, 420))
        scale = min(420 / crop.width, 355 / crop.height)
        shown = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.Resampling.LANCZOS)
        card.alpha_composite(shown, ((card.width - shown.width) // 2, 40 + (355 - shown.height) // 2))
        draw = ImageDraw.Draw(card)
        draw.text((14, 10), name, font=_font(21), fill=(239, 242, 247, 255))
        draw.text((14, 390), f"mesh shoulder {shoulder_deg:+.0f} / elbow {elbow_deg:+.0f}", font=_font(14), fill=(192, 201, 214, 255))
        cards.append(card)
        case_metrics.append({"name": name, "shoulder_deg": shoulder_deg, "elbow_deg": elbow_deg, "alpha_bbox": bbox})

    contact = Image.new("RGBA", (1380, 840), (25, 28, 34, 255))
    for index, card in enumerate(cards):
        contact.alpha_composite(card, ((index % 3) * 460, (index // 3) * 420))
    contact.convert("RGB").save(OUT / "contact.jpg", quality=95)
    report = {
        "schema_version": 1,
        "status": "weighted_mesh_visual_review_required",
        "technique": "context-reveal continuous cloth base + inverse-mapped two-bone mesh + bend-only elbow fold + rigid metal cover",
        "cloth_pixels": int(cloth_mask.sum()),
        "cloth_connected_components": 1,
        "color_fit": color_fit,
        "forearm_partition_pixels": forearm_partition,
        "elbow_patch_pixels": int((elbow_patch[:, :, 3] > 0).sum()),
        "generated_elbow_patch": {
            "source": GENERATED_ELBOW_PATCH.relative_to(ROOT).as_posix(),
            "color_and_layout": elbow_patch_report,
        },
        "mesh": {
            "bounds_xyxy": list(MESH_BOUNDS),
            "grid_step": GRID_STEP,
            "shoulder_xy": SHOULDER.tolist(),
            "elbow_xy": ELBOW.tolist(),
            "wrist_xy": WRIST.tolist(),
            "elbow_blend_width_px": 24,
        },
        "cases": case_metrics,
        "contact": "contact.jpg",
        "shipping_allowed": False,
        "steam_install_allowed": False,
        "next_gate": "direct visual comparison against rigid stress and Spine 4.2 mesh implementation",
    }
    (OUT / "audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"THIEF_V10_NEAR_ARM_WEIGHTED_MESH cases={len(cases)} cloth={int(cloth_mask.sum())} status=visual_review_required")


if __name__ == "__main__":
    main()
