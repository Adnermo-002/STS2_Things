#!/usr/bin/env python3
"""Audit a generated near-dagger-arm sprite sheet before any rig use.

This is deliberately a rejection-oriented supplement to direct visual review.
It extracts the four expected quadrants, reports connectivity/material problems,
and creates a contact sheet.  A numerical result never grants production
approval; ``candidate.status.json`` and a human bind/extreme-pose review remain
authoritative.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "01_image_to_image_families/near_dagger_arm_candidate_01_alpha.png"
DEFAULT_OUT = ROOT / "01_image_to_image_families/near_dagger_arm_candidate_01_audit"

QUADRANTS = {
    "near_upper_arm": (0, 0, 768, 512),
    "near_forearm": (768, 0, 1536, 512),
    "near_dagger_hand": (0, 512, 768, 1024),
    "dagger": (768, 512, 1536, 1024),
}


def _font(size: int) -> ImageFont.ImageFont:
    for path in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _material_counts(rgba: np.ndarray, mask: np.ndarray) -> dict[str, int]:
    rgb = rgba[:, :, :3]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    metal = mask & (sat <= 52) & (val >= 82)
    skin = mask & (hue <= 18) & (sat >= 70) & (val >= 115)
    brown = mask & (hue <= 26) & (sat >= 42) & ~skin
    dark = mask & ~(metal | skin | brown)
    return {
        "metal": int(metal.sum()),
        "skin": int(skin.sum()),
        "brown": int(brown.sum()),
        "dark": int(dark.sum()),
    }


def _holes(mask_u8: np.ndarray) -> tuple[int, int]:
    contours, hierarchy = cv2.findContours(mask_u8, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return 0, 0
    count = 0
    area = 0
    for index, contour in enumerate(contours):
        if hierarchy[0][index][3] >= 0:
            candidate_area = int(round(abs(cv2.contourArea(contour))))
            if candidate_area >= 8:
                count += 1
                area += candidate_area
    return count, area


def _crop_to_alpha(image: Image.Image, padding: int = 12) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return Image.new("RGBA", (1, 1))
    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(image.width, right + padding)
    bottom = min(image.height, bottom + padding)
    return image.crop((left, top, right, bottom))


def _checker(size: tuple[int, int], cell: int = 16) -> Image.Image:
    width, height = size
    yy, xx = np.indices((height, width))
    values = np.where(((xx // cell + yy // cell) & 1) == 0, 42, 54).astype(np.uint8)
    rgba = np.dstack((values, values + 3, values + 8, np.full_like(values, 255)))
    return Image.fromarray(rgba, "RGBA")


def audit(input_path: Path, out_dir: Path) -> dict[str, object]:
    sheet = Image.open(input_path).convert("RGBA")
    if sheet.size != (1536, 1024):
        raise ValueError(f"expected 1536x1024 sheet, got {sheet.size}")
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, object]] = []
    extracted: dict[str, Image.Image] = {}
    for semantic, box in QUADRANTS.items():
        quadrant = sheet.crop(box)
        rgba = np.asarray(quadrant, dtype=np.uint8)
        mask = rgba[:, :, 3] >= 24
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
        components = sorted(
            (int(stats[index, cv2.CC_STAT_AREA]) for index in range(1, count)),
            reverse=True,
        )
        hole_count, hole_area = _holes(mask.astype(np.uint8))
        materials = _material_counts(rgba, mask)
        visible = int(mask.sum())
        material_ratios = {
            key: round(value / max(1, visible), 6) for key, value in materials.items()
        }
        cropped = _crop_to_alpha(quadrant)
        crop_path = out_dir / f"{semantic}.png"
        cropped.save(crop_path)
        extracted[semantic] = cropped

        failures: list[str] = []
        substantial = [area for area in components if area >= 24]
        if len(substantial) != 1:
            failures.append(f"expected one connected semantic piece, found {len(substantial)}")
        if hole_count:
            failures.append(f"contains {hole_count} enclosed alpha hole(s), area={hole_area}")
        if semantic == "near_upper_arm" and material_ratios["metal"] > 0.03:
            failures.append("metal baked into cloth upper arm (likely pauldron contamination)")
        if semantic == "near_forearm" and len(substantial) > 1:
            failures.append("detached pommel/crescent remains in forearm quadrant")
        if semantic == "near_dagger_hand" and material_ratios["metal"] > 0.025:
            failures.append("weapon metal baked into hand attachment")

        records.append(
            {
                "semantic": semantic,
                "crop": crop_path.relative_to(ROOT).as_posix(),
                "bbox_in_quadrant": list(cropped.getbbox() or (0, 0, 0, 0)),
                "visible_pixels": visible,
                "components_over_24px": substantial,
                "holes": {"count": hole_count, "area": hole_area},
                "materials": materials,
                "material_ratios": material_ratios,
                "automatic_failures": failures,
                "automatic_status": "fail" if failures else "needs_visual_review",
            }
        )

    card_width, card_height = 720, 460
    contact = Image.new("RGBA", (card_width * 2, card_height * 2), (27, 30, 36, 255))
    draw = ImageDraw.Draw(contact)
    for index, record in enumerate(records):
        semantic = str(record["semantic"])
        x0 = (index % 2) * card_width
        y0 = (index // 2) * card_height
        draw.rectangle((x0, y0, x0 + card_width - 1, y0 + card_height - 1), outline=(83, 91, 105, 255), width=2)
        draw.text((x0 + 18, y0 + 14), semantic, font=_font(25), fill=(238, 241, 246, 255))
        status = str(record["automatic_status"])
        draw.text(
            (x0 + 18, y0 + 49),
            status,
            font=_font(17),
            fill=(255, 92, 92, 255) if status == "fail" else (255, 193, 77, 255),
        )
        sprite = extracted[semantic]
        max_w, max_h = 400, 330
        scale = min(max_w / sprite.width, max_h / sprite.height, 1.0)
        shown = sprite.resize((max(1, int(sprite.width * scale)), max(1, int(sprite.height * scale))), Image.Resampling.LANCZOS)
        checker = _checker((max_w, max_h))
        px = (max_w - shown.width) // 2
        py = (max_h - shown.height) // 2
        checker.alpha_composite(shown, (px, py))
        contact.alpha_composite(checker, (x0 + 18, y0 + 92))
        failures = record["automatic_failures"]
        if failures:
            text = " | ".join(str(item) for item in failures)
            draw.text((x0 + 430, y0 + 96), text, font=_font(15), fill=(255, 155, 155, 255))
        ratios = record["material_ratios"]
        ratio_text = "\n".join(f"{key}: {float(value):.1%}" for key, value in ratios.items())
        draw.multiline_text((x0 + 430, y0 + 190), ratio_text, font=_font(16), fill=(188, 197, 210, 255), spacing=5)

    contact_path = out_dir / "contact.png"
    contact.convert("RGB").save(contact_path, quality=94)
    report = {
        "schema_version": 1,
        "input": input_path.relative_to(ROOT).as_posix(),
        "policy": "automatic checks supplement, never replace, direct visual bind and pose review",
        "status": "fail" if any(record["automatic_status"] == "fail" for record in records) else "visual_review_required",
        "parts": records,
        "contact": contact_path.relative_to(ROOT).as_posix(),
    }
    (out_dir / "audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    report = audit(args.input.resolve(), args.out.resolve())
    print(
        "THIEF_V10_NEAR_DAGGER_ARM_AUDIT "
        f"status={report['status']} parts={len(report['parts'])}"
    )


if __name__ == "__main__":
    main()
