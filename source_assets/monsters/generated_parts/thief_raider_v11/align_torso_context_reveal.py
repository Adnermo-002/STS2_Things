#!/usr/bin/env python3
"""Align the generated torso/pelvis context plate to the locked master."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from align_far_arm_context_reveal import canvas_to_master, make_contact, sha256, sift_align


HERE = Path(__file__).resolve().parent
MASTER = HERE / "00_reference" / "locked_master.png"
TARGET = HERE / "00_reference" / "torso_context" / "torso_context_edit_target_alpha.png"
EDIT_MASK = HERE / "00_reference" / "torso_context" / "torso_context_edit_mask.png"
CANDIDATE = HERE / "01_imagegen_boards" / "torso_context_reveal_candidate_v01_alpha.png"
OUT = HERE / "02_semantic_parts" / "context_reveals" / "torso_v01"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master = np.asarray(Image.open(MASTER).convert("RGBA"), dtype=np.uint8)
    target = np.asarray(Image.open(TARGET).convert("RGBA"), dtype=np.uint8)
    candidate = np.asarray(Image.open(CANDIDATE).convert("RGBA"), dtype=np.uint8)
    edit_mask = np.asarray(Image.open(EDIT_MASK).convert("L"), dtype=np.uint8)
    aligned, metrics = sift_align(target, candidate, edit_mask)
    donor = canvas_to_master(aligned)
    Image.fromarray(aligned, "RGBA").save(OUT / "context_reveal_aligned.png")
    Image.fromarray(donor, "RGBA").save(OUT / "context_reveal_master_space.png")
    make_contact(master, donor, OUT / "alignment_contact.jpg")
    report = {
        "schema_version": 1,
        "status": "alignment_pass_semantic_extraction_pending",
        "identity_sha256": sha256(MASTER),
        "candidate_sha256": sha256(CANDIDATE),
        "alignment": metrics,
        "outputs": {
            "aligned": "context_reveal_aligned.png",
            "master_space": "context_reveal_master_space.png",
            "contact": "alignment_contact.jpg",
        },
        "shipping_allowed": False,
        "steam_install_allowed": False,
    }
    (OUT / "alignment.audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
