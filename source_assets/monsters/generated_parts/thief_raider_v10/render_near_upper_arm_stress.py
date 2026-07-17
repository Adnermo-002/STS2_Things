#!/usr/bin/env python3
"""Render local shoulder/elbow stress poses for the corrected near arm chain."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OWNERSHIP_ROOT = ROOT / "00_reference/near_arm_ownership_v2"
OWNERSHIP_MANIFEST = OWNERSHIP_ROOT / "near_arm_ownership_v2.manifest.json"
UPPER_ATTACHMENT = ROOT / "02_semantic_parts/near_upper_arm_context_01/near_upper_arm_attachment.png"
OUT = ROOT / "04_pose_stress/near_upper_arm_context_01"
CANVAS = (534, 420)
SHOULDER = (169.0, 232.0)
ELBOW = (139.0, 283.0)


def _font(size: int) -> ImageFont.ImageFont:
    for path in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _full_canvas(part: np.ndarray, bbox: list[int]) -> np.ndarray:
    left, top, right, bottom = map(int, bbox)
    expected = (bottom - top, right - left)
    if part.shape[:2] != expected:
        raise RuntimeError(f"part shape {part.shape[:2]} != bbox {expected}")
    canvas = np.zeros((CANVAS[1], CANVAS[0], 4), dtype=np.uint8)
    canvas[top:bottom, left:right] = part
    return canvas


def _rotate(rgba: np.ndarray, pivot: tuple[float, float], angle: float) -> np.ndarray:
    matrix = cv2.getRotationMatrix2D(pivot, angle, 1.0)
    return cv2.warpAffine(
        rgba,
        matrix,
        CANVAS,
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )


def _alpha_over(bottom: np.ndarray, top: np.ndarray) -> np.ndarray:
    result = Image.fromarray(bottom, "RGBA")
    result.alpha_composite(Image.fromarray(top, "RGBA"))
    return np.asarray(result, dtype=np.uint8)


def _checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
    width, height = size
    yy, xx = np.indices((height, width))
    value = np.where(((xx // cell + yy // cell) & 1) == 0, 38, 51).astype(np.uint8)
    return Image.fromarray(np.dstack((value, value + 3, value + 8, np.full_like(value, 255))), "RGBA")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(OWNERSHIP_MANIFEST.read_text(encoding="utf-8-sig"))
    corrected = manifest["corrected_parts"]
    parts: dict[str, np.ndarray] = {
        "near_upper_arm": np.asarray(Image.open(UPPER_ATTACHMENT).convert("RGBA"), dtype=np.uint8),
    }
    for name in ("near_forearm", "near_shoulder_plate", "dagger", "near_dagger_hand"):
        record = corrected[name]
        crop = np.asarray(Image.open(OWNERSHIP_ROOT / record["file"]).convert("RGBA"), dtype=np.uint8)
        parts[name] = _full_canvas(crop, record["source_bbox_xyxy"])

    cases = [
        ("bind", 0.0, 0.0),
        ("shoulder_back_45", -45.0, 0.0),
        ("shoulder_forward_45", 45.0, 0.0),
        ("elbow_open_55", 0.0, -55.0),
        ("elbow_close_75", 0.0, 75.0),
        ("elbow_close_110", 0.0, 110.0),
    ]
    cards: list[tuple[str, Image.Image]] = []
    metrics: list[dict[str, object]] = []
    for name, shoulder_angle, elbow_angle in cases:
        upper = _rotate(parts["near_upper_arm"], SHOULDER, shoulder_angle)
        plate = parts["near_shoulder_plate"]
        # The whole distal chain follows shoulder rotation.  The isolated
        # elbow cases keep shoulder at setup, so local rotation can be applied
        # directly at the setup elbow pivot without introducing retarget math.
        forearm = _rotate(parts["near_forearm"], SHOULDER, shoulder_angle)
        hand = _rotate(parts["near_dagger_hand"], SHOULDER, shoulder_angle)
        dagger = _rotate(parts["dagger"], SHOULDER, shoulder_angle)
        if elbow_angle:
            forearm = _rotate(forearm, ELBOW, elbow_angle)
            hand = _rotate(hand, ELBOW, elbow_angle)
            dagger = _rotate(dagger, ELBOW, elbow_angle)

        composite = np.zeros((CANVAS[1], CANVAS[0], 4), dtype=np.uint8)
        for layer in (upper, forearm, plate, dagger, hand):
            composite = _alpha_over(composite, layer)
        alpha = composite[:, :, 3]
        ys, xs = np.where(alpha >= 24)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]
        crop = Image.fromarray(composite, "RGBA").crop(tuple(bbox))
        frame = _checker((460, 420))
        scale = min(420 / crop.width, 365 / crop.height)
        shown = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.Resampling.LANCZOS)
        frame.alpha_composite(shown, ((frame.width - shown.width) // 2, 38 + (365 - shown.height) // 2))
        draw = ImageDraw.Draw(frame)
        draw.text((14, 10), name, font=_font(21), fill=(239, 242, 247, 255))
        draw.text((14, 388), f"shoulder {shoulder_angle:+.0f}  elbow {elbow_angle:+.0f}", font=_font(15), fill=(192, 201, 214, 255))
        frame.save(OUT / f"{name}.png")
        cards.append((name, frame))
        metrics.append({"name": name, "shoulder_deg": shoulder_angle, "elbow_deg": elbow_angle, "alpha_bbox": bbox})

    contact = Image.new("RGBA", (460 * 3, 420 * 2), (25, 28, 34, 255))
    for index, (_, card) in enumerate(cards):
        contact.alpha_composite(card, ((index % 3) * 460, (index // 3) * 420))
    contact.convert("RGB").save(OUT / "contact.jpg", quality=95)
    report = {
        "schema_version": 1,
        "status": "visual_review_required",
        "upper_attachment": UPPER_ATTACHMENT.relative_to(ROOT).as_posix(),
        "ownership_manifest": OWNERSHIP_MANIFEST.relative_to(ROOT).as_posix(),
        "cases": metrics,
        "contact": "contact.jpg",
        "policy": "local joint stress only; torso underpaint and production Spine constraints remain pending",
        "shipping_allowed": False,
        "steam_install_allowed": False,
    }
    (OUT / "audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"THIEF_V10_NEAR_UPPER_ARM_STRESS cases={len(cases)} status=visual_review_required")


if __name__ == "__main__":
    main()
