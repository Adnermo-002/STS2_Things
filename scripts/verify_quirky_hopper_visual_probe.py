#!/usr/bin/env python3
"""Validate rendered Quirky Hopper animation frames and build a contact sheet."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    return parser.parse_args()


def load_rgba(path: Path) -> np.ndarray:
    with Image.open(path) as source:
        return np.asarray(source.convert("RGBA"), dtype=np.int16)


def foreground_mask(frame: np.ndarray, background: np.ndarray) -> np.ndarray:
    rgb_delta = np.max(np.abs(frame[:, :, :3] - background), axis=2)
    return (frame[:, :, 3] > 0) & (rgb_delta > 12)


def pink_mask(frame: np.ndarray) -> np.ndarray:
    red = frame[:, :, 0]
    green = frame[:, :, 1]
    blue = frame[:, :, 2]
    return (
        (red >= 120)
        & (blue >= 80)
        & (red >= green + 35)
        & (blue >= green - 5)
    )


def centroid(mask: np.ndarray) -> tuple[float, float] | None:
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return None
    return float(xs.mean()), float(ys.mean())


def make_montage(frame_entries: list[dict], output_dir: Path) -> Path:
    thumb_size = (400, 300)
    columns = 3
    rows = math.ceil(len(frame_entries) / columns)
    canvas = Image.new("RGB", (columns * 400, rows * 332), "#101317")
    draw = ImageDraw.Draw(canvas)
    for index, entry in enumerate(frame_entries):
        with Image.open(output_dir / entry["file"]) as source:
            image = source.convert("RGB")
            image.thumbnail(thumb_size, Image.Resampling.LANCZOS)
            x = (index % columns) * 400 + (400 - image.width) // 2
            y = (index // columns) * 332
            canvas.paste(image, (x, y))
        label = f'{entry["animation"]} {entry["fraction"]:.2f}'
        draw.text(((index % columns) * 400 + 10, y + 306), label, fill="white")
    montage_path = output_dir / "animation_montage.png"
    canvas.save(montage_path)
    return montage_path


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    report_path = output_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    frames = report["frames"]
    background = np.asarray(report["background_rgb"], dtype=np.int16)

    failures: list[str] = []
    metrics: dict[str, object] = {
        "frame_count": len(frames),
        "foreground_pixels": {},
        "pink_pixels": {},
        "die_changed_pixels": [],
        "die_mean_absolute_difference": [],
    }
    rendered: dict[str, np.ndarray] = {}
    pink_centroids: list[tuple[float, float]] = []

    for entry in frames:
        path = output_dir / entry["file"]
        if not path.is_file():
            failures.append(f"missing rendered frame: {path.name}")
            continue
        frame = load_rgba(path)
        rendered[entry["file"]] = frame
        foreground = foreground_mask(frame, background)
        foreground_pixels = int(foreground.sum())
        metrics["foreground_pixels"][entry["file"]] = foreground_pixels
        if foreground_pixels < 2_000:
            failures.append(f"rendered frame is blank or too sparse: {entry['file']}")

        pink = pink_mask(frame)
        pink_pixels = int(pink.sum())
        metrics["pink_pixels"][entry["file"]] = pink_pixels
        pink_center = centroid(pink)
        if pink_pixels >= 80 and pink_center is not None:
            pink_centroids.append(pink_center)

    die_entries = [entry for entry in frames if entry["animation"] == "die"]
    if len(die_entries) < 5:
        failures.append("death animation probe rendered fewer than five samples")
    else:
        for left_entry, right_entry in zip(die_entries, die_entries[1:]):
            left = rendered.get(left_entry["file"])
            right = rendered.get(right_entry["file"])
            if left is None or right is None:
                continue
            difference = np.abs(left[:, :, :3] - right[:, :, :3])
            union = foreground_mask(left, background) | foreground_mask(right, background)
            changed = int(((difference.max(axis=2) > 10) & union).sum())
            mean_difference = float(difference[union].mean()) if union.any() else 0.0
            metrics["die_changed_pixels"].append(changed)
            metrics["die_mean_absolute_difference"].append(mean_difference)
        if max(metrics["die_changed_pixels"], default=0) < 1_000:
            failures.append("death animation frames do not contain meaningful pixel motion")
        if sum(metrics["die_changed_pixels"]) < 4_000:
            failures.append("death animation motion is too small across the full sequence")

    if report.get("bow_bone") != "head" or not report.get("bow_behind_parent"):
        failures.append("bow is not bound behind the head bone")
    if len(pink_centroids) < 2:
        failures.append("pink bow is not visibly rendered in enough animation frames")
    else:
        max_bow_motion = max(
            math.dist(left, right)
            for left in pink_centroids
            for right in pink_centroids
        )
        metrics["pink_bow_max_centroid_motion"] = max_bow_motion
        if max_bow_motion < 3.0:
            failures.append("pink bow does not visibly follow the animated head")

    montage_path = make_montage(frames, output_dir)
    metrics["montage"] = str(montage_path)
    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    if failures:
        for failure in failures:
            print(f"QUIRKY_HOPPER_VISUAL_FAIL: {failure}")
        return 1

    print(
        "QUIRKY_HOPPER_VISUAL_PASS "
        f"frames={len(frames)} "
        f"die_changed={metrics['die_changed_pixels']} "
        f"bow_motion={metrics.get('pink_bow_max_centroid_motion', 0.0):.2f}"
    )
    print(f"montage={montage_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

