# Thief Raider v13 visual audit

## Why v12 was discarded

The v12 result was a different broad, realistic underbody with the locked character's gear pasted over it. It failed identity, silhouette, contact, draw order, joint continuity, attack readability, and grounded death. It is archived and barred from packaging.

## v13 construction policy

- Locked master remains the only source of visible bind-pose pixels.
- Image-to-image output is used as semantic hidden underpaint, never as a replacement full character.
- Arms and legs are continuous meshes; there are no upper/lower rectangular tiles.
- Dagger remains below the gripping fingers.
- Generated rope-with-hand donor is rejected because it duplicates the far hand.
- Generated skin/leather is stripped from hidden seam donors; only dark cloth may heal cloth joints.
- Bind reconstruction must remain byte-exact before any motion review.

## Current audit

- Locked master SHA256: `643a86c7d8b9bb885161ac6abad39f8c3b8af09fcb8ad8e016b90feee73b06fb`
- Exact bind mismatch: `0` pixels.
- Body board connected components: `6` real alpha silhouettes.
- Accessory board connected components: `13` real alpha silhouettes.
- Rejected donor: `rope_front_with_hand_rejected`.
- Generated torso/arm/leg assets are hidden-underpaint sources only; they are not approved visible replacements.
- Spine export, PCK promotion, and Steam installation remain gated.

## Next visual gate

Render padded checkerboard frames for idle inhale/exhale, attack anticipation/contact/hit-stop/recoil, short hurt, and a multi-stage grounded death. Inspect shoulder, elbow, wrist, waist, hip, knee, weapon grip, rope path, cape/sack lag, combat bounds, intent, and health-bar clearance at every key frame.
