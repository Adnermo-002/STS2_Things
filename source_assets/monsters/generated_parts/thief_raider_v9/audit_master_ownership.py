#!/usr/bin/env python3
"""Strict visual-boundary audit for v9 master-owned semantic layers."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
OWNERSHIP = ROOT / "03_master_ownership"
MANIFEST_PATH = OWNERSHIP / "master_ownership.manifest.json"
MASTER_PATH = ROOT / "00_reference/current_master.png"
REPORT_JSON = OWNERSHIP / "master_ownership.audit.json"
REPORT_MD = OWNERSHIP / "master_ownership.audit.md"


PROFILE = {
    "cloak_tail_far": ("magenta", 0.75, {"brown": 0.03, "metal": 0.02}),
    "cloak_tail_near": ("magenta", 0.72, {"brown": 0.04, "metal": 0.02}),
    "scarf": ("magenta", 0.75, {"brown": 0.03, "metal": 0.04}),
    "loot_sack": ("brown", 0.82, {"magenta": 0.02, "metal": 0.02}),
    "sack_strap": ("brown", 0.75, {"magenta": 0.03, "metal": 0.06}),
    "far_lower_leg": ("brown", 0.75, {"magenta": 0.02, "metal": 0.02}),
    "near_lower_leg": ("brown", 0.75, {"magenta": 0.02, "metal": 0.02}),
    "far_thigh": ("dark", 0.86, {"magenta": 0.02, "brown": 0.04, "metal": 0.02}),
    "near_thigh": ("dark", 0.86, {"magenta": 0.02, "brown": 0.04}),
    "pelvis_skirt": ("dark", 0.82, {"magenta": 0.03, "brown": 0.04}),
    "torso_core": ("dark", 0.78, {"magenta": 0.03, "brown": 0.08, "metal": 0.03}),
    "near_upper_arm": ("dark", 0.90, {"magenta": 0.02, "brown": 0.03, "metal": 0.03}),
    "far_shoulder_plate": ("metal", 0.76, {"magenta": 0.01, "brown": 0.04}),
    "near_shoulder_plate": ("metal", 0.82, {"magenta": 0.01, "brown": 0.03}),
    "hooded_head": ("head", 0.95, {"magenta": 0.01, "brown": 0.02}),
    "dagger": ("metal", 0.75, {"magenta": 0.01, "brown": 0.04}),
    "eye_glow": ("yellow", 0.90, {}),
}


def _materials(rgba: np.ndarray) -> dict[str, np.ndarray]:
    foreground = rgba[:, :, 3] > 0
    hsv = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2HSV)
    hue, saturation, value = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    yellow = (
        foreground
        & (hue >= 18)
        & (hue <= 42)
        & (saturation >= 120)
        & (value >= 130)
    )
    magenta = foreground & (hue >= 150) & (saturation >= 48) & (value >= 25)
    brown = foreground & (hue <= 28) & (saturation >= 42) & (value >= 22) & ~yellow
    metal = foreground & (saturation <= 48) & (value >= 82)
    dark = foreground & ~(yellow | magenta | brown | metal)
    return {
        "foreground": foreground,
        "yellow": yellow,
        "magenta": magenta,
        "brown": brown,
        "metal": metal,
        "dark": dark,
        "head": dark | metal | yellow,
    }


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    master = np.asarray(Image.open(MASTER_PATH).convert("RGBA"), dtype=np.uint8)
    height, width = master.shape[:2]
    owner = np.full((height, width), -1, dtype=np.int16)
    overlap = np.zeros((height, width), dtype=np.uint8)
    parts: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    notices: list[dict[str, object]] = []

    for record in manifest["parts"]:
        index = int(record["index"])
        x, y, part_width, part_height = map(int, record["source_bbox"])
        rgba = np.asarray(Image.open(OWNERSHIP / record["file"]).convert("RGBA"), dtype=np.uint8)
        if rgba.shape[:2] != (part_height, part_width):
            raise RuntimeError(f"bbox/texture mismatch for {record['semantic']}")
        mask = rgba[:, :, 3] > 0
        canvas_mask = np.zeros((height, width), dtype=bool)
        canvas_mask[y:y + part_height, x:x + part_width] = mask
        overlap[canvas_mask] += 1
        owner[canvas_mask] = index

        component_count, _, component_stats, _ = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8), 8
        )
        component_areas = sorted(
            [int(component_stats[i, cv2.CC_STAT_AREA]) for i in range(1, component_count)],
            reverse=True,
        )
        allowed_components = 2 if record["semantic"] == "eye_glow" else 1
        detached_area = sum(component_areas[allowed_components:])
        if detached_area:
            notices.append(
                {
                    "semantic": record["semantic"],
                    "notice": "visible_islands_require_hidden_underlap",
                    "actual_pixels": detached_area,
                }
            )

        material_masks = _materials(rgba)
        visible = int(mask.sum())
        ratios = {
            key: round(float(material_masks[key].sum()) / max(1, visible), 6)
            for key in ("magenta", "brown", "metal", "dark", "yellow", "head")
        }
        profile = PROFILE.get(str(record["semantic"]))
        if profile is not None:
            primary, minimum, maxima = profile
            if ratios[primary] < minimum:
                failures.append(
                    {
                        "semantic": record["semantic"],
                        "gate": f"{primary}_minimum",
                        "actual": ratios[primary],
                        "limit": minimum,
                    }
                )
            for material_name, maximum in maxima.items():
                if ratios[material_name] > maximum:
                    failures.append(
                        {
                            "semantic": record["semantic"],
                            "gate": f"foreign_{material_name}_maximum",
                            "actual": ratios[material_name],
                            "limit": maximum,
                        }
                    )
        parts.append(
            {
                "semantic": record["semantic"],
                "visible_pixels": visible,
                "component_areas": component_areas,
                "material_ratios": ratios,
            }
        )

    master_foreground = master[:, :, 3] > 0
    uncovered = int((master_foreground & (owner < 0)).sum())
    outside = int(((owner >= 0) & ~master_foreground).sum())
    overlapping = int((overlap > 1).sum())
    for gate, actual in (
        ("uncovered_master_pixels", uncovered),
        ("owned_outside_master_pixels", outside),
        ("overlapping_visible_ownership_pixels", overlapping),
    ):
        if actual:
            failures.append({"semantic": "__global__", "gate": gate, "actual_pixels": actual})

    report = {
        "schema_version": 1,
        "status": "pass" if not failures else "fail",
        "exact_bind_rgba": bool(manifest["bind_reconstruction"]["exact_rgba"]),
        "global": {
            "master_foreground_pixels": int(master_foreground.sum()),
            "uncovered_pixels": uncovered,
            "outside_pixels": outside,
            "overlapping_pixels": overlapping,
        },
        "failure_count": len(failures),
        "failures": failures,
        "notice_count": len(notices),
        "notices": notices,
        "parts": parts,
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Thief Raider v9 visible-ownership audit",
        "",
        f"**Verdict:** {report['status'].upper()}",
        "",
        "Bind reconstruction is exact RGBA, but exact reconstruction alone does not approve moving boundaries.",
        "",
        f"- master pixels: {report['global']['master_foreground_pixels']}",
        f"- uncovered / outside / overlap: {uncovered} / {outside} / {overlapping}",
        f"- boundary/material failures: {len(failures)}",
        f"- underlap notices: {len(notices)}",
        "",
        "## Failures",
        "",
    ]
    if failures:
        for failure in failures:
            lines.append(f"- `{failure['semantic']}` — `{failure['gate']}`: {failure}")
    else:
        lines.append("- none")
    lines.extend(["", "## Underlap notices", ""])
    if notices:
        for notice in notices:
            lines.append(f"- `{notice['semantic']}` — {notice}")
    else:
        lines.append("- none")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        "THIEF_V9_MASTER_OWNERSHIP_AUDIT "
        f"status={report['status']} failures={len(failures)}"
    )


if __name__ == "__main__":
    main()
