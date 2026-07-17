# Thief Raider v10 — Semantic Image-to-Image Production Brief

## Identity lock

- Sole identity master: `00_reference/current_master.png`.
- Preserve its compact crouched proportions, left-facing 3/4 orientation, silhouette, face/hood identity, colors, matte low-frequency paint, and asymmetry.
- Preserve current-master visible pixels wherever practical. Generated pixels exist to create complete semantic pieces and hidden overlap; they are not a redesign source.

## Generation unit

Generate a small coherent family per image-to-image pass, never a generic full-sheet batch:

1. head + hood + front/back scarf
2. torso + pelvis tunic + near/far upper-arm underlap
3. near arm: upper arm, forearm/bracer, open dagger hand
4. far arm: upper arm, forearm/bracer, strap hand
5. near leg: thigh, shin, boot
6. far leg: thigh, shin, boot
7. cape + sack + knot + rear/front strap
8. belt + pouch + shoulder plates + dagger

Every part must be a filled painted sprite with a natural concealed overlap flap at both joints. No socket holes, open cuffs, rounded plugs, tube/sausage anatomy, square crops, generic inventory icons, or front-facing neutral anatomy.

## Mandatory visual gates

Each family is rejected before extraction if any item fails:

- Same compact Raider anatomy and exact palette as the master.
- Same left-facing camera and light direction.
- Smooth matte hand-painted masses; no glossy 3D render, polygon facets, or excessive micro-shading.
- Joint ends continue the local cloth/leather material and taper naturally under the neighbor.
- At final scale the generated visible region is fully covered by master-owned pixels.
- No part contains another semantic part baked into it.

## Assembly gates

Before Spine data:

- 1:1 bind composite beside the original at 100%, 200%, and combat scale.
- Difference view marks only hidden-overlap pixels in bind pose.
- Shoulder ±45°, elbow 25–145°, hip ±35°, knee 55–155°, ankle ±25°.
- No holes, caps, texture seams, detached hands, floating straps, rectangular edges, or draw-order swaps.
- The whole silhouette stays inside the creature visual envelope and away from combat UI.

## Animation gate

Build only `idle`, `attack`, `hurt`, and `die` first. Approve those in Godot 4.5.1 + spine-godot 4.2 before adding the remaining clips or touching the formal PCK/Steam install.
