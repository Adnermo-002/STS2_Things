#!/usr/bin/env python3
"""Extract draw-order-safe torso and pelvis attachments from the context edit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
MASTER = HERE / "00_reference" / "locked_master.png"
BASELINE = HERE / "00_reference" / "visible_baseline"
MANIFEST = BASELINE / "visible_baseline.manifest.json"
DONOR_ROOT = HERE / "02_semantic_parts" / "context_reveals" / "torso_v01"
DONOR = DONOR_ROOT / "context_reveal_master_space.png"
ALIGN_AUDIT = DONOR_ROOT / "alignment.audit.json"


SPECS = {
    "torso_core": {
        "z": 11,
        "distance": 22.0,
        "roi": [(175, 165), (350, 150), (385, 220), (360, 295), (205, 305), (155, 250)],
        "front_file": "torso_core_attachment.png",
        "back_file": "torso_core_underpaint_back.png",
    },
    "pelvis_tunic": {
        "z": 12,
        "distance": 22.0,
        "roi": [(175, 230), (385, 220), (390, 325), (310, 350), (190, 330)],
        "front_file": "pelvis_tunic_attachment.png",
        "back_file": "pelvis_tunic_underpaint_back.png",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def alpha_over(bottom: np.ndarray, top: np.ndarray) -> np.ndarray:
    image = Image.fromarray(bottom, "RGBA")
    image.alpha_composite(Image.fromarray(top, "RGBA"))
    return np.asarray(image, dtype=np.uint8)


def load_baseline() -> tuple[dict, dict[str, np.ndarray], np.ndarray, np.ndarray]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    parts: dict[str, np.ndarray] = {}
    owner_z = np.full((420, 534), -999, dtype=np.int16)
    owner_alpha = np.zeros((420, 534), dtype=np.uint8)
    for record in manifest["parts"]:
        crop = np.asarray(Image.open(BASELINE / record["file"]).convert("RGBA"), dtype=np.uint8)
        x, y, width, height = map(int, record["source_bbox"])
        canvas = np.zeros((420, 534, 4), dtype=np.uint8)
        canvas[y : y + height, x : x + width] = crop
        parts[record["semantic"]] = canvas
        mask = crop[:, :, 3] > 0
        owner_z[y : y + height, x : x + width][mask] = int(record["z"])
        owner_alpha[y : y + height, x : x + width][mask] = crop[:, :, 3][mask]
    return manifest, parts, owner_z, owner_alpha


def semantic_hidden(
    donor: np.ndarray,
    master: np.ndarray,
    visible: np.ndarray,
    roi_points: list[tuple[int, int]],
    distance_limit: float,
) -> np.ndarray:
    hsv = cv2.cvtColor(donor[:, :, :3], cv2.COLOR_RGB2HSV)
    cloth = (
        (donor[:, :, 3] >= 80)
        & (hsv[:, :, 1] <= 105)
        & (hsv[:, :, 2] >= 18)
        & (hsv[:, :, 2] <= 160)
    )
    roi = np.zeros(visible.shape, dtype=np.uint8)
    cv2.fillPoly(roi, [np.asarray(roi_points, dtype=np.int32)], 255)
    distance = cv2.distanceTransform((~visible).astype(np.uint8), cv2.DIST_L2, 5)
    hidden = cloth & (roi > 0) & ~visible & (master[:, :, 3] == 255) & (distance <= distance_limit)

    # Keep every generated component that connects to at least one exact
    # visible island; discard unrelated arm/leg/cape material inside the ROI.
    union = visible | hidden
    count, labels, _, _ = cv2.connectedComponentsWithStats(union.astype(np.uint8), 8)
    visible_labels = np.unique(labels[visible])
    connected = np.isin(labels, visible_labels[visible_labels > 0])
    hidden &= connected
    return hidden


def make_contact(master: np.ndarray, donor: np.ndarray, outputs: dict[str, np.ndarray], output: Path) -> None:
    sheet = Image.new("RGBA", (1600, 1040), (27, 31, 39, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    merged = np.zeros_like(master)
    merged = alpha_over(merged, outputs["torso_core_underpaint_back"])
    merged = alpha_over(merged, outputs["pelvis_tunic_underpaint_back"])
    merged = alpha_over(merged, outputs["torso_core_attachment"])
    merged = alpha_over(merged, outputs["pelvis_tunic_attachment"])
    panels = [
        ("LOCKED MASTER", master),
        ("ALIGNED CONTEXT DONOR", donor),
        ("TORSO + PELVIS SEMANTIC ATTACHMENTS", merged),
        ("BIND RECONSTRUCTION", np.asarray(Image.open(DONOR_ROOT / "full_bind_preview.png").convert("RGBA"))),
    ]
    for index, (label, rgba) in enumerate(panels):
        x = 25 + (index % 2) * 790
        y = 50 + (index // 2) * 500
        draw.text((x, y - 25), label, fill=(242, 244, 248, 255), font=font)
        shown = Image.fromarray(rgba, "RGBA").resize((720, 566), Image.Resampling.LANCZOS)
        sheet.alpha_composite(shown, (x, y))
    sheet.crop((0, 0, 1600, 1040)).convert("RGB").save(output, quality=95)


def main() -> None:
    manifest, parts, owner_z, owner_alpha = load_baseline()
    master = np.asarray(Image.open(MASTER).convert("RGBA"), dtype=np.uint8)
    donor = np.asarray(Image.open(DONOR).convert("RGBA"), dtype=np.uint8)
    outputs: dict[str, np.ndarray] = {}
    records = {}

    for semantic, spec in SPECS.items():
        visible_rgba = parts[semantic]
        visible = visible_rgba[:, :, 3] > 0
        hidden = semantic_hidden(donor, master, visible, spec["roi"], spec["distance"])
        opaque_cover = owner_alpha == 255
        front_hidden = hidden & (owner_z >= int(spec["z"])) & opaque_cover
        back_hidden = hidden & (owner_z >= 0) & (owner_z < int(spec["z"])) & opaque_cover

        front = np.zeros_like(master)
        front[front_hidden] = donor[front_hidden]
        front[:, :, 3][front_hidden] = 255
        front[visible] = visible_rgba[visible]
        back = np.zeros_like(master)
        back[back_hidden] = donor[back_hidden]
        back[:, :, 3][back_hidden] = 255

        Image.fromarray(front, "RGBA").save(DONOR_ROOT / spec["front_file"])
        Image.fromarray(back, "RGBA").save(DONOR_ROOT / spec["back_file"])
        outputs[Path(spec["front_file"]).stem] = front
        outputs[Path(spec["back_file"]).stem] = back
        records[semantic] = {
            "visible_pixels": int(visible.sum()),
            "generated_hidden_pixels": int(hidden.sum()),
            "front_hidden_pixels": int(front_hidden.sum()),
            "back_hidden_pixels": int(back_hidden.sum()),
            "discarded_partial_or_unowned_pixels": int(hidden.sum() - front_hidden.sum() - back_hidden.sum()),
            "distance_limit": spec["distance"],
            "roi_xy": spec["roi"],
            "front_file": spec["front_file"],
            "back_file": spec["back_file"],
        }

    # Reconstruct through the actual slot order: back underpaints first, then
    # replace exact torso/pelvis slots with their front attachments.
    result = np.zeros_like(master)
    result = alpha_over(result, outputs["torso_core_underpaint_back"])
    result = alpha_over(result, outputs["pelvis_tunic_underpaint_back"])
    for record in sorted(manifest["parts"], key=lambda item: (int(item["z"]), int(item["index"]))):
        semantic = record["semantic"]
        if semantic == "torso_core":
            layer = outputs["torso_core_attachment"]
        elif semantic == "pelvis_tunic":
            layer = outputs["pelvis_tunic_attachment"]
        else:
            layer = parts[semantic]
        result = alpha_over(result, layer)
    bind_path = DONOR_ROOT / "full_bind_preview.png"
    Image.fromarray(result, "RGBA").save(bind_path)
    mismatch = int(np.any(result != master, axis=2).sum())

    make_contact(master, donor, outputs, DONOR_ROOT / "extraction_contact.jpg")
    alignment = json.loads(ALIGN_AUDIT.read_text(encoding="utf-8"))["alignment"]
    report = {
        "schema_version": 1,
        "status": "semantic_attachments_pass_body_bend_gate_pending",
        "identity_sha256": sha256(MASTER),
        "donor_sha256": sha256(DONOR),
        "alignment": alignment,
        "parts": records,
        "bind_mismatch_pixels": mismatch,
        "full_bind_rgba_exact": mismatch == 0,
        "shipping_allowed": False,
        "steam_install_allowed": False,
        "next_gate": "full_character_torso_pelvis_hierarchy_bend_review",
    }
    if mismatch:
        raise RuntimeError(report)
    (DONOR_ROOT / "extraction.audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
