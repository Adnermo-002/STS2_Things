#!/usr/bin/env python3
"""Extract the corrected closed-joint Sheet B2 using Sheet B's fixed layout."""

from __future__ import annotations

import extract_sheet_b as sheet


sheet.SOURCE = sheet.ROOT / "01_generated_sheets/sheet_b2_closed_corrections_alpha.png"
sheet.OUT = sheet.ROOT / "02_extracted_donors/sheet_b2"
sheet.MANIFEST = sheet.ROOT / "02_extracted_donors/sheet_b2.manifest.json"
sheet.CONTACT = sheet.ROOT / "02_extracted_donors/sheet_b2.contact.png"

sheet.CLASSIFICATION = {
    "near_upper_arm": (
        "donor_only_closed_joint_review",
        ["B2 removed the hollow end; registration and extreme rotation remain gated"],
    ),
    "near_forearm": (
        "donor_only_closed_joint_review",
        ["B2 removed the hollow cuff; current-master pixels remain the visible surface"],
    ),
    "near_dagger_hand": (
        "donor_only_grip_registration_review",
        ["open handle channel must be fitted to the exact master dagger grip"],
    ),
    "far_upper_arm": (
        "donor_only_closed_joint_review",
        ["B2 removed the hollow end; registration and extreme rotation remain gated"],
    ),
    "far_forearm": (
        "donor_only_closed_joint_review",
        ["B2 removed the hollow cuff; current-master pixels remain the visible surface"],
    ),
    "far_strap_hand": (
        "donor_only_grip_registration_review",
        ["open strap channel must stay locked to strap_front under IK"],
    ),
    "near_shin": (
        "donor_only_joint_review",
        ["hidden knee/ankle fill only"],
    ),
    "near_thigh": (
        "donor_only_joint_review",
        ["hidden hip/knee volume only"],
    ),
    "far_thigh": (
        "donor_only_joint_review",
        ["hidden hip/knee volume only"],
    ),
    "far_shin": (
        "donor_only_joint_review",
        ["hidden knee/ankle fill only"],
    ),
    "near_boot": (
        "donor_only_closed_boot_review",
        ["B2 closed the shaft; ankle nesting and silhouette remain gated"],
    ),
    "dagger": (
        "donor_only_identity_review",
        ["current-master blade remains the visible source"],
    ),
    "far_boot": (
        "donor_only_closed_boot_review",
        ["B2 closed the shaft; ankle nesting and silhouette remain gated"],
    ),
}


if __name__ == "__main__":
    sheet.main()
