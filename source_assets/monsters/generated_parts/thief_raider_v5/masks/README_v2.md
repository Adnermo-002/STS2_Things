# Thief Raider v5 ownership v2 — skeleton-aligned draft

`ownership_v2.png` is the current review draft aligned one-for-one with
`../skeleton_spec.json`. It remains deliberately disconnected from the formal
monster mapping and build pipeline.

## Contract proof

- Master: `../approved_master.png` only.
- Canvas: 768×896.
- Master visible pixels: **195,732**.
- Visible pixels with one and only one owner: **195,732**.
- Missing / overlap / foreign: **0 / 0 / 0**.
- Labels on transparent master pixels: **0**.
- Extracted visible RGBA mismatch: **0**.
- Source parts: **34**, exactly equal to
  `skeleton_spec.json/slot_order_back_to_front[*].source_part`.
- Contract z values: exactly **0 through 33**, with no gap or duplicate.
- Every required source part has visible pixels.
- No visible pixels were generated, repainted, recolored, or copied from an
  independent part image.

Strict linked-cutout QA:

`D:/Things/Things-Workspace/STS2_Things/build/thief_v5_masks/linked_cutouts_v2/linked_cutouts.qa.json`

Result: `PASS` for all 34 parts.

## V2 structural changes

- `rear_cloak` → `cloak_tail_far`, `cloak_tail_near`, `upper_back_cloak`.
- Added `far_knee_cover`, `near_knee_cover` from the painted boot cuffs.
- Added `far_elbow_cover`, `near_elbow_cover` from the painted armor/cuff
  overlays.
- Split the two-anchor strap into `sack_strap_back`, `sack_strap_front`, and
  `strap_grip`; rebuilt `far_strap_hand` above the grip.
- Split hanging gray panels to `waist_cloth_front`, retaining the upper hip wrap
  in `pelvis_skirt`.
- Recovered 2,361 gray lower-body pixels that V1's default cloak carrier had
  captured.
- Recovered the complete visible fist from V1's front-scarf polygon.
- Recovered plum scarf/cape boundary pixels from sack, limb, torso, belt and
  hood polygons using connected source-color regions constrained to the V1
  cloak boundary.
- Moved the visible brown belt tongue from cloth ownership to
  `belt_and_pouch`.
- Rebuilt ankle cuts along the painted boot direction instead of a translation
  seam.

## Files

- `ownership_v2.png` — indexed ownership map.
- `ownership_contract_v2.json` — exact 34-slot/z contract.
- `ownership_preview_v2.png` — source-colored semantic overlay with white seams.
- `ownership_legend_v2.png` — opaque semantic map and z/name legend.
- `ownership_uncertainty_v2.png` — yellow exact seam and red two-pixel review
  bands.
- `ownership_qa_v2.json` — coverage, slot alignment, per-part area/bbox, hashes,
  construction metrics and seam audit.
- `build_ownership_v2.py` — reproducible builder.

The seam-review bands cover **14,078 unique visible pixels (7.192%)**. This is
the inspection envelope for all intentional articulated seams and cover edges,
not a count of known wrong pixels. Every recorded seam pair has a non-zero
visible shared boundary.

## Reproduce

```powershell
python source_assets/monsters/generated_parts/thief_raider_v5/masks/build_ownership_v2.py
python scripts/build_master_linked_cutouts.py `
  --master source_assets/monsters/generated_parts/thief_raider_v5/approved_master.png `
  --labels source_assets/monsters/generated_parts/thief_raider_v5/masks/ownership_v2.png `
  --contract source_assets/monsters/generated_parts/thief_raider_v5/masks/ownership_contract_v2.json `
  --output-dir build/thief_v5_masks/linked_cutouts_v2 `
  --strict
```
