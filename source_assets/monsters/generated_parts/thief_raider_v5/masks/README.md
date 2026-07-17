# Thief Raider v5 visible-pixel ownership (draft v1)

This folder is a reviewable first-pass semantic segmentation of
`../approved_master.png`. It is **not wired into the production mapping or build
pipeline**.

## Invariants already proved

- Approved-master visible pixels: **195,732**.
- Visible pixels with exactly one semantic owner: **195,732**.
- Missing / overlapping / foreign visible pixels: **0 / 0 / 0**.
- Labels on transparent master pixels: **0**.
- Byte-exact visible recomposition mismatch: **0**.
- No visible character artwork was generated, repainted, color-corrected, or
  borrowed from another source. Part RGBA comes only from the approved master.

The generic linked-cutout contract audit is at
`../../../../../build/thief_v5_masks/linked_cutouts_v1/linked_cutouts.qa.json`
when run from the project tree. Its strict result is `PASS` for all 26 parts.

## Files

- `ownership_v1.png` — 768×896 `L`-mode semantic index map.
- `ownership_contract_v1.json` — IDs, part names, filenames and back-to-front
  draw order accepted by `scripts/build_master_linked_cutouts.py`.
- `ownership_preview_v1.png` — source art blended with semantic colors and
  one-pixel white ownership seams.
- `ownership_legend_v1.png` — opaque index visualization plus ID legend.
- `ownership_uncertainty_v1.png` — yellow exact seam / red two-pixel review
  band for the boundaries that still need hand approval.
- `ownership_qa_v1.json` — coverage, per-part bounds, hashes and quantified
  review bands.
- `build_ownership_v1.py` — reproducible polygon/index builder; it reads only
  the approved master for visible RGBA.

## Remaining boundary review

The uncertainty overlay covers **8,230 unique visible pixels (4.205%)** in wide
review bands; this is the inspection envelope, not a claim that every pixel in
the band is wrong. The unresolved choices are:

1. scarf-back emergence between hood and the rear shoulder stack;
2. back-strap contact with scarf, shoulder plate and bag knot;
3. finger-over/under islands at `far_hand` / `strap_front_grip`;
4. left belt return against the tunic;
5. cloth-only hip-root seams for near/far thigh;
6. the two chosen articulation cuts inside continuous painted boots.

## Reproduce and audit

```powershell
python source_assets/monsters/generated_parts/thief_raider_v5/masks/build_ownership_v1.py
python scripts/build_master_linked_cutouts.py `
  --master source_assets/monsters/generated_parts/thief_raider_v5/approved_master.png `
  --labels source_assets/monsters/generated_parts/thief_raider_v5/masks/ownership_v1.png `
  --contract source_assets/monsters/generated_parts/thief_raider_v5/masks/ownership_contract_v1.json `
  --output-dir build/thief_v5_masks/linked_cutouts_v1 `
  --strict
```
