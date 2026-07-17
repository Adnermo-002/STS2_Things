#!/usr/bin/env python3
"""Build continuous v13 mesh sources while preserving exact locked-master pixels.

Generated v13 parts are used only as hidden, style-matched underpaint.  Every
visible bind-pose pixel is still owned by the locked master partition from v11.
The resulting arm and leg sources are continuous semantic silhouettes rather
than rectangular cutouts or disconnected upper/lower limb stickers.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
MASTER = HERE / "00_reference" / "thief_raider_locked_master.png"
V11_BASE = HERE.parent / "thief_raider_v11" / "00_reference" / "visible_baseline"
DONORS = HERE / "02_semantic_parts" / "body"
OUT = HERE / "02_semantic_parts" / "master_mesh_sources_v01"
EXACT_OUT = OUT / "exact_master_visible"
UNDER_OUT = OUT / "generated_hidden_underpaint"
MESH_OUT = OUT / "continuous_mesh_sources"


AFFINE_SPECS = {
    "torso": {
        "file": "torso_pelvis_donor.png",
        "src": [(55, 105), (305, 105), (180, 350)],
        "dst": [(166, 215), (340, 175), (290, 330)],
        "parts": ["torso_core", "pelvis_tunic"],
        "bones": [((185, 210), (290, 295), 72)],
        "dilate": 26,
        "transform": "affine",
    },
    "near_arm": {
        "file": "near_full_arm_donor.png",
        "src": [(350, 95), (230, 190), (105, 285)],
        "dst": [(169, 230), (139, 281), (116, 329)],
        "parts": ["near_upper_arm", "near_forearm", "near_dagger_hand"],
        "bones": [((169, 230), (139, 281), 42), ((139, 281), (116, 329), 38)],
        "dilate": 15,
        "transform": "similarity",
    },
    "far_arm": {
        "file": "far_full_arm_donor.png",
        "src": [(260, 100), (165, 205), (90, 105)],
        "dst": [(332, 155), (367, 198), (301, 192)],
        "parts": ["far_forearm", "far_strap_hand"],
        "bones": [((332, 155), (367, 198), 46), ((367, 198), (301, 192), 42)],
        "dilate": 18,
        "transform": "similarity",
    },
    "near_leg": {
        "file": "near_full_leg_donor.png",
        "src": [(225, 75), (130, 175), (125, 275)],
        "dst": [(221, 278), (214, 330), (220, 369)],
        "parts": ["near_thigh", "near_shin", "near_boot"],
        "bones": [((221, 278), (214, 330), 55), ((214, 330), (220, 369), 44)],
        "dilate": 14,
        "transform": "similarity",
    },
    "far_leg": {
        "file": "far_full_leg_donor.png",
        "src": [(255, 75), (150, 170), (235, 265)],
        "dst": [(354, 282), (382, 335), (398, 370)],
        "parts": ["far_thigh", "far_shin", "far_boot"],
        "bones": [((354, 282), (382, 335), 52), ((382, 335), (398, 370), 42)],
        "dilate": 14,
        "transform": "similarity",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def alpha_over(bottom: np.ndarray, top: np.ndarray) -> np.ndarray:
    out = Image.fromarray(bottom, "RGBA")
    out.alpha_composite(Image.fromarray(top, "RGBA"))
    return np.asarray(out, dtype=np.uint8)


def premultiply(image: np.ndarray) -> np.ndarray:
    data = image.astype(np.float32) / 255.0
    data[:, :, :3] *= data[:, :, 3:4]
    return data


def unpremultiply(image: np.ndarray) -> np.ndarray:
    alpha = image[:, :, 3:4]
    rgb = np.divide(image[:, :, :3], np.maximum(alpha, 1e-6), where=alpha > 1e-6)
    rgba = np.concatenate([rgb, alpha], axis=2)
    rgba[alpha[:, :, 0] <= 1e-6] = 0
    return np.clip(np.round(rgba * 255.0), 0, 255).astype(np.uint8)


def warp_donor(
    donor: np.ndarray,
    src: list[tuple[int, int]],
    dst: list[tuple[int, int]],
    size: tuple[int, int],
    transform: str,
) -> np.ndarray:
    source_points = np.asarray(src, np.float32)
    target_points = np.asarray(dst, np.float32)
    if transform == "affine":
        matrix = cv2.getAffineTransform(source_points, target_points)
    elif transform == "similarity":
        matrix, _ = cv2.estimateAffinePartial2D(
            source_points,
            target_points,
            method=cv2.LMEDS,
        )
        if matrix is None:
            raise RuntimeError(f"failed to estimate similarity transform: {src} -> {dst}")
    else:
        raise ValueError(transform)
    warped = cv2.warpAffine(
        premultiply(donor),
        matrix,
        size,
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )
    return unpremultiply(warped)


def load_exact_parts() -> tuple[list[dict], dict[str, np.ndarray]]:
    manifest = json.loads((V11_BASE / "visible_baseline.manifest.json").read_text(encoding="utf-8"))
    parts: dict[str, np.ndarray] = {}
    width, height = manifest["canvas"]
    for record in manifest["parts"]:
        canvas = np.zeros((height, width, 4), dtype=np.uint8)
        crop = np.asarray(Image.open(V11_BASE / record["file"]).convert("RGBA"), dtype=np.uint8)
        x, y, w, h = map(int, record["source_bbox"])
        canvas[y : y + h, x : x + w] = crop
        parts[record["semantic"]] = canvas
    return manifest["parts"], parts


def build_target_mask(
    part_names: list[str],
    parts: dict[str, np.ndarray],
    bones: list[tuple[tuple[int, int], tuple[int, int], int]],
    dilate: int,
    master_alpha: np.ndarray,
) -> np.ndarray:
    mask = np.zeros(master_alpha.shape, dtype=np.uint8)
    for name in part_names:
        mask = np.maximum(mask, (parts[name][:, :, 3] > 4).astype(np.uint8) * 255)
    for start, end, thickness in bones:
        cv2.line(mask, start, end, 255, thickness, cv2.LINE_AA)
    if dilate:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate * 2 + 1, dilate * 2 + 1))
        mask = cv2.dilate(mask, kernel, iterations=1)
    return cv2.bitwise_and(mask, master_alpha)


def clip_alpha(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    result = image.copy()
    alpha = result[:, :, 3].astype(np.float32) * (mask.astype(np.float32) / 255.0)
    result[:, :, 3] = np.clip(np.round(alpha), 0, 255).astype(np.uint8)
    result[result[:, :, 3] == 0, :3] = 0
    return result


def keep_dark_cloth_only(image: np.ndarray) -> np.ndarray:
    """Remove generated skin/leather so donor pixels can only heal cloth seams."""
    result = image.copy()
    rgb = result[:, :, :3].astype(np.float32)
    red, green, blue = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    brightness = rgb.max(axis=2)
    cloth = (
        (brightness < 165.0)
        & (blue >= red * 0.82)
        & (blue >= green * 0.88)
    )
    result[~cloth] = 0
    return result


def exact_composite(records: list[dict], parts: dict[str, np.ndarray], underlays: dict[str, np.ndarray]) -> np.ndarray:
    height, width = next(iter(parts.values())).shape[:2]
    result = np.zeros((height, width, 4), dtype=np.uint8)
    for underlay in underlays.values():
        result = alpha_over(result, underlay)
    for record in sorted(records, key=lambda item: (int(item["z"]), int(item["index"]))):
        result = alpha_over(result, parts[record["semantic"]])
    return result


def save_trimmed(image: np.ndarray, path: Path, pad: int = 16) -> list[int]:
    ys, xs = np.where(image[:, :, 3] > 3)
    if not len(xs):
        Image.new("RGBA", (1, 1)).save(path)
        return [0, 0, 1, 1]
    left = max(0, int(xs.min()) - pad)
    top = max(0, int(ys.min()) - pad)
    right = min(image.shape[1], int(xs.max()) + 1 + pad)
    bottom = min(image.shape[0], int(ys.max()) + 1 + pad)
    Image.fromarray(image[top:bottom, left:right], "RGBA").save(path)
    return [left, top, right - left, bottom - top]


def make_debug_contact(master: np.ndarray, bind: np.ndarray, underlays: dict[str, np.ndarray], output: Path) -> None:
    tiles: list[tuple[str, np.ndarray]] = [("LOCKED MASTER", master), ("EXACT BIND + HIDDEN UNDERPAINT", bind)]
    tiles += [(name, image) for name, image in underlays.items()]
    cols, cell_w, cell_h = 3, 620, 500
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (27, 31, 39, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (name, array) in enumerate(tiles):
        x0, y0 = (index % cols) * cell_w, (index // cols) * cell_h
        draw.text((x0 + 10, y0 + 9), name, fill=(244, 246, 249, 255), font=font)
        shown = Image.fromarray(array, "RGBA")
        bbox = shown.getchannel("A").getbbox()
        if bbox:
            shown = shown.crop(bbox)
        scale = min(560 / max(1, shown.width), 420 / max(1, shown.height), 1.15)
        shown = shown.resize((max(1, round(shown.width * scale)), max(1, round(shown.height * scale))), Image.Resampling.LANCZOS)
        sheet.alpha_composite(shown, (x0 + (cell_w - shown.width) // 2, y0 + 48 + (420 - shown.height) // 2))
    sheet.convert("RGB").save(output, quality=95)


def main() -> None:
    for directory in (OUT, EXACT_OUT, UNDER_OUT, MESH_OUT):
        directory.mkdir(parents=True, exist_ok=True)
    if EXACT_OUT.exists():
        shutil.rmtree(EXACT_OUT)
    shutil.copytree(V11_BASE / "parts", EXACT_OUT)

    records, parts = load_exact_parts()
    master = np.asarray(Image.open(MASTER).convert("RGBA"), dtype=np.uint8)
    height, width = master.shape[:2]
    # Hidden underpaint may sit only beneath a pixel that one exact ownership
    # layer covers at alpha 255.  Looking at the final master alpha is not
    # sufficient because a fully opaque final pixel can still be assembled
    # from feathered source ownership; a donor behind that feather changes RGB.
    guaranteed_cover = np.zeros((height, width), dtype=np.uint8)
    for exact in parts.values():
        guaranteed_cover = np.maximum(
            guaranteed_cover, np.where(exact[:, :, 3] == 255, 255, 0).astype(np.uint8)
        )
    master_alpha = guaranteed_cover

    underlays: dict[str, np.ndarray] = {}
    underlay_records = []
    mesh_records = []
    for name, spec in AFFINE_SPECS.items():
        donor = np.asarray(Image.open(DONORS / spec["file"]).convert("RGBA"), dtype=np.uint8)
        warped = warp_donor(
            donor,
            spec["src"],
            spec["dst"],
            (width, height),
            str(spec["transform"]),
        )
        Image.fromarray(warped, "RGBA").save(UNDER_OUT / f"{name}_warped_full_debug.png")
        warped = keep_dark_cloth_only(warped)
        target_mask = build_target_mask(
            spec["parts"], parts, spec["bones"], int(spec["dilate"]), master_alpha
        )
        warped = clip_alpha(warped, target_mask)
        underlays[name] = warped
        under_path = UNDER_OUT / f"{name}_underpaint.png"
        Image.fromarray(warped, "RGBA").save(under_path)
        underlay_records.append(
            {
                "semantic": name,
                "file": str(under_path.relative_to(OUT)).replace("\\", "/"),
                "donor": spec["file"],
                "src_landmarks": spec["src"],
                "dst_landmarks": spec["dst"],
                "alpha_pixels": int((warped[:, :, 3] > 4).sum()),
            }
        )

        mesh = warped.copy()
        for part_name in spec["parts"]:
            mesh = alpha_over(mesh, parts[part_name])
        mesh_path = MESH_OUT / f"{name}_continuous_mesh.png"
        bbox = save_trimmed(mesh, mesh_path)
        mesh_records.append(
            {
                "semantic": name,
                "file": str(mesh_path.relative_to(OUT)).replace("\\", "/"),
                "source_bbox_xywh": bbox,
                "exact_visible_parts": spec["parts"],
                "construction": "generated hidden underpaint + exact master visible pixels",
            }
        )

    # The exact visible partition is composited last, so hidden donor pixels can
    # never alter the locked bind pose.
    bind = exact_composite(records, parts, underlays)
    bind_path = OUT / "exact_bind_reconstruction.png"
    Image.fromarray(bind, "RGBA").save(bind_path)
    mismatch = int(np.any(bind != master, axis=2).sum())
    if mismatch:
        raise RuntimeError(f"locked bind drifted by {mismatch} pixels")

    make_debug_contact(master, bind, underlays, OUT / "master_mesh_sources_contact.jpg")
    report = {
        "schema_version": 1,
        "status": "mesh_source_visual_review_required",
        "locked_master": str(MASTER.relative_to(HERE)).replace("\\", "/"),
        "locked_master_sha256": sha256(MASTER),
        "exact_bind_file": bind_path.name,
        "exact_bind_sha256": sha256(bind_path),
        "bind_mismatch_pixels": mismatch,
        "rectangular_tile_parts": False,
        "generated_pixels_visible_in_bind": False,
        "underlays": underlay_records,
        "continuous_meshes": mesh_records,
        "shipping_allowed": False,
        "steam_install_allowed": False,
        "next_gate": "continuous weighted-motion checkerboard review",
    }
    (OUT / "master_mesh_sources.manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
