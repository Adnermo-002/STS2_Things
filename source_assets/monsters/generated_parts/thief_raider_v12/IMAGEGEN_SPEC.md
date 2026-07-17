# Thief Raider v12 — Production Parts Image Generation Spec

## Identity and style lock

- Preserve the locked master's exact hood, two yellow eyes, scarf, armor, sack, dagger, clothing, boots, colors, and left-facing three-quarter crouched Raider identity.
- Preserve the original palette; no global recolor.
- Smooth matte, low-frequency painted forms matching the shipped Ruby Raiders.
- Compact stylized proportions; avoid realistic anatomy, faceted polygon shading, and plastic highlights.

## Required semantic parts

Every part must be a complete solid painted object with hidden overlap extending beneath adjacent parts:

1. hooded head and black face cavity
2. eye glow
3. scarf front and scarf back
4. torso cloth without armor, belt, strap, or pouch
5. pelvis tunic
6. near/far upper arms
7. near/far forearms
8. near dagger hand and far gripping hand
9. near/far thighs
10. near/far lower legs
11. near/far boots
12. both shoulder plates and both forearm plates
13. belt, buckle, pouch
14. sack, knot, rear strap, front strap
15. near/far cape tails
16. dagger

## Joint engineering gate

- Organic tapered underlap of at least 15–25% of the neighboring segment length.
- Closed painted ends under armor/cloth, not visible hollow tubes.
- No circular sockets, ball joints, plugs, sausage limbs, square crops, or torn transparent edges.
- Parts separated with generous empty space and no overlap with each other.
- Maintain the character's side/three-quarter orientation; do not turn parts into a front-facing model sheet.

## Acceptance gate before rigging

- Reassemble a static bind character from generated parts without using pixels cut from the full-character master.
- Inspect shoulder, elbow, wrist, waist, hip, knee, ankle, strap, and cape seams on checkerboard at 3× scale.
- Reject any sheet with hollow ports, ambiguous composites, missing hidden volume, or style drift before writing Spine data.
