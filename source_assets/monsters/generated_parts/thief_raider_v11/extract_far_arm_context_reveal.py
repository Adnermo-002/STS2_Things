#!/usr/bin/env python3
"""Extract a continuous hidden far-arm cloth base from the aligned context edit.

Only pixels fully occluded by the locked master are retained.  The attachment
therefore reconstructs the bind pose exactly while supplying a real, solid
shoulder-to-elbow-to-wrist surface for skeletal deformation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
MASTER = HERE / "00_reference" / "locked_master.png"
DONOR = HERE / "02_semantic_parts" / "context_reveals" / "far_arm_v01" / "context_reveal_master_space.png"
ALIGN_AUDIT = HERE / "02_semantic_parts" / "context_reveals" / "far_arm_v01" / "alignment.audit.json"
OUT = HERE / "02_semantic_parts" / "context_reveals" / "far_arm_v01"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def largest_component(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if count <= 1:
        raise RuntimeError("far-arm material mask is empty")
    index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return labels == index


def build_mask(donor: np.ndarray, master: np.ndarray) -> tuple[np.ndarray, dict]:
    hsv = cv2.cvtColor(donor[:, :, :3], cv2.COLOR_RGB2HSV)
    roi = np.zeros(donor.shape[:2], dtype=np.uint8)
    cv2.fillPoly(
        roi,
        [
            np.asarray(
                [(300, 115), (355, 112), (388, 138), (398, 182), (392, 218), (365, 242), (315, 242), (288, 216), (286, 172)],
                dtype=np.int32,
            )
        ],
        255,
    )
    raw = (
        (roi > 0)
        & (donor[:, :, 3] >= 80)
        & (hsv[:, :, 1] <= 82)
        & (hsv[:, :, 2] >= 22)
        & (hsv[:, :, 2] <= 130)
    )
    semantic = largest_component(raw)
    semantic = cv2.morphologyEx(semantic.astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)) > 0
    semantic &= donor[:, :, 3] >= 40
    semantic &= roi > 0
    # Opaque cover is a hard bind-pose invariant.  No generated pixel may leak
    # into the exact visible silhouette.
    hidden = semantic & (master[:, :, 3] == 255)
    hidden = largest_component(hidden)
    count, _, stats, _ = cv2.connectedComponentsWithStats(hidden.astype(np.uint8), 8)
    components = sorted((int(stats[i, cv2.CC_STAT_AREA]) for i in range(1, count)), reverse=True)
    return hidden, {
        "roi_xy": [[300, 115], [355, 112], [388, 138], [398, 182], [392, 218], [365, 242], [315, 242], [288, 216], [286, 172]],
        "raw_pixels": int(raw.sum()),
        "hidden_pixels": int(hidden.sum()),
        "components": components,
        "hsv_contract": {"s_max": 82, "v_min": 22, "v_max": 130},
    }


def distribution(rgba: np.ndarray, mask: np.ndarray) -> dict:
    pixels = rgba[:, :, :3][mask]
    return {
        "count": int(len(pixels)),
        "mean_rgb": [round(float(v), 4) for v in pixels.mean(axis=0)],
        "median_rgb": [round(float(v), 4) for v in np.median(pixels, axis=0)],
        "p10_rgb": [round(float(v), 4) for v in np.percentile(pixels, 10, axis=0)],
        "p90_rgb": [round(float(v), 4) for v in np.percentile(pixels, 90, axis=0)],
    }


def make_contact(master: np.ndarray, donor: np.ndarray, base: np.ndarray, hidden: np.ndarray, output: Path) -> None:
    sheet = Image.new("RGBA", (1600, 1040), (27, 31, 39, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    overlay = master.copy()
    overlay[hidden, :3] = (overlay[hidden, :3].astype(np.float32) * 0.28 + np.asarray([0, 235, 235]) * 0.72).astype(np.uint8)
    panels = [
        ("LOCKED MASTER", master),
        ("ALIGNED CONTEXT DONOR", donor),
        ("HIDDEN FAR-ARM CLOTH BASE", base),
        ("CYAN = EXACTLY OCCLUDED BASE", overlay),
    ]
    for i, (label, rgba) in enumerate(panels):
        x = 25 + (i % 2) * 790
        y = 55 + (i // 2) * 500
        draw.text((x, y - 28), label, fill=(242, 244, 248, 255), font=font)
        image = Image.fromarray(rgba, "RGBA")
        shown = image.resize((720, 566), Image.Resampling.LANCZOS)
        sheet.alpha_composite(shown, (x, y))
    sheet.crop((0, 0, 1600, 1040)).convert("RGB").save(output, quality=95)


def main() -> None:
    master = np.asarray(Image.open(MASTER).convert("RGBA"), dtype=np.uint8)
    donor = np.asarray(Image.open(DONOR).convert("RGBA"), dtype=np.uint8)
    hidden, mask_audit = build_mask(donor, master)

    base = np.zeros_like(master)
    base[hidden] = donor[hidden]
    # The hidden component is fully opaque in both donor and cover; retain the
    # generated RGB while normalising alpha to a stable mesh texture.
    base[:, :, 3][hidden] = 255
    base_path = OUT / "far_arm_cloth_base.png"
    Image.fromarray(base, "RGBA").save(base_path)

    bind = Image.fromarray(base, "RGBA")
    bind.alpha_composite(Image.fromarray(master, "RGBA"))
    bind_path = OUT / "full_bind_preview.png"
    bind.save(bind_path)
    bind_exact = bool(np.array_equal(np.asarray(bind, dtype=np.uint8), master))

    make_contact(master, donor, base, hidden, OUT / "extraction_contact.jpg")

    near_visible = np.asarray(
        Image.open(HERE / "00_reference" / "visible_baseline" / "parts" / "18_near_upper_arm.png").convert("RGBA"),
        dtype=np.uint8,
    )
    near_mask = near_visible[:, :, 3] >= 128
    alignment = json.loads(ALIGN_AUDIT.read_text(encoding="utf-8"))["alignment"]
    report = {
        "schema_version": 1,
        "status": "static_hidden_base_pass_mesh_pose_gate_pending",
        "identity_sha256": sha256(MASTER),
        "donor_sha256": sha256(DONOR),
        "policy": "donor supplies one continuous far-arm cloth base only where the locked bind pose is fully opaque",
        "alignment": alignment,
        "mask": mask_audit,
        "palette_comparison": {
            "far_arm_donor": distribution(base, hidden),
            "exact_near_arm_master": distribution(near_visible, near_mask),
        },
        "full_bind_rgba_exact": bind_exact,
        "outputs": {
            "base": "far_arm_cloth_base.png",
            "bind": "full_bind_preview.png",
            "contact": "extraction_contact.jpg",
        },
        "shipping_allowed": False,
        "steam_install_allowed": False,
        "next_gate": "two_dimensional_weighted_mesh_at_raider_motion_angles",
    }
    if not bind_exact or mask_audit["components"] != [mask_audit["hidden_pixels"]]:
        raise RuntimeError(f"far-arm extraction audit failed: {report}")
    (OUT / "extraction.audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
