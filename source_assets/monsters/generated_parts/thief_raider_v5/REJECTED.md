# Thief Raider v5 — rejected

This candidate is retained only as failed-pipeline evidence. It is not a production source.

## Why it failed

- The master is too realistic and too densely rendered for the shipped Ruby Raider family.
- The ownership result produces visible paint fragments, not clean articulation pieces.
- The body and limb donor sheets were generated independently, so their perspective and contours are not a single coherent character.
- Forty bones and thirty-four slots are unjustified for this silhouette and amplify seam and layer failures.
- Numerical alpha reconstruction only proves that the bind image can be reassembled; it does not prove that the parts remain coherent when animated.

## Build rule

Do not copy this directory into `ai_cutout_parts`, do not add it to a mapping file, and do not package it in the PCK.

The replacement must pass, in order:

1. Ruby Raider style comparison at combat scale.
2. One approved coherent master pose.
3. Same-master articulation cut plan with no paint-island slots.
4. Hidden-joint repaint only where a rotation exposes previously occluded pixels.
5. Extreme-pose seam, silhouette, target-line, and card/UI overlap review.
