# Card Portrait Rebuild V109 - 2026-07-25

## Source Audit

- Target game: STS2 V109.
- Complete card-portrait inventory: 615 vanilla sprites across 12 groups.
- Silent inventory: all 91 `images/packed/card_portraits/silent/*.png` reviewed through `research/v109-card-art-style/contact-sheets/silent.jpg`.
- Closest functional subset for Recall: the 12 Silent rare Skills: Adrenaline, Blade of Ink, Bullet Time, Burst, Corrosive Wave, Flanking, Knife Trap, Malaise, Nightmare, Shadow Step, Shadowmeld, and Storm of Steel.
- Silent identity sources reviewed: the complete Silent Spine-parts board and character-select portrait.

## Style Synthesis

- Landscape card art is read as one action at thumbnail scale: a dominant diagonal, arc, spiral, or collision axis with one brightest focal point.
- Backgrounds use two to five broad flowing masses. Dark navy, deep green, muted violet, and a controlled lime/teal accent keep Silent images readable without dense scenery.
- Subjects use three to six large value groups, selective near-black contour, curved cloth shadows, and a small number of hard force planes.
- Card effects express the action through a continuous force path. Recall therefore uses a returning S-curve of translucent teal/lime memory flow and blank card backs, not a static portrait or UI pile.
- Silent locks: paired segmented horns, elongated pale beak-like skull mask, lime-green eye glow, layered dark-green hood/cloak, bandaged five-digit hands when visible, and narrow pale-blue daggers only when the action calls for one.

## Asset Mapping

The approved ImageGen source images are normalized only for the game's 1000x760 portrait contract. This is a non-creative center-fit conversion; no pixels are painted procedurally.

| Card | Approved source | Runtime destination |
|---|---|---|
| Pack Up | `source_assets/card_portraits_v109_rebuild_20260725/pack_up-v4-source.png` | `images/packed/card_portraits/silent/pack_up.png` |
| Reuse | `source_assets/card_portraits_v109_rebuild_20260725/reuse-v3-source.png` | `images/packed/card_portraits/defect/reuse.png` |
| Soulfysh Disease | `source_assets/card_portraits_v109_rebuild_20260725/soulfysh_disease-v3-source.png` | `images/packed/card_portraits/silent/soulfysh_disease.png` |
| Collision | `source_assets/card_portraits_v109_rebuild_20260725/things_collision-v3-source.png` | `images/packed/card_portraits/ironclad/things_collision.png` |
| Recall | Generated through the system `imagegen` workflow documented below | `images/packed/card_portraits/silent/recall.png` |

`Surrender` has no matching rendered source in this rebuild directory and remains unchanged.

## Recall Brief

- Card contract: Silent rare Skill, self-targeted; draws prioritize the discard pile for the turn.
- Action: discarded blank card backs arc backward from the right into a luminous brain-shaped memory core at Silent's skull crown.
- Composition: a three-quarter Silent head is the primary form, with one curved card-return path entering the memory core. The concept is head/mind first, cards second; no static head-on portrait.
- Background: three or four broad navy, deep-green, and muted-violet flowing bands with a restrained teal/lime memory glow.
- Style references: Silent `Memento Mori`, `Nightmare`, `Reflex`, and `Master Planner`; Colorless `Mind Blast`; and the `Liquid Memories` potion. The shared rule is thick selective dark outline, a small number of opaque color fields, and one high-contrast conceptual focal shape.
- Exclusions: text, card frame, UI, logos, watermarks, generic human face, single horn, generic gloves, extra digits, photorealism, 3D render, collage, dense scenery, medical realism, and gore.

## Recall Iteration Note

`recall-v5-source.png` achieved the card-return action and Silent anatomy, but its surface treatment was too painterly and its focal point was the hand. It is retained as a rejected source only. The final iteration moves the focal point to a stylized symbolic brain/memory core connected to Silent's skull and uses the V109 card-art shape language above.
