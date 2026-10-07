# 盛碗虫祖母 Bowlbug Progenitor — native Spine 4.2 rig source pipeline

Build-time only (`tools/` is `.gdignore`d and excluded from the PCK).
Shipping output: `STS2_Things/animations/monsters/bowlbug_progenitor/`
(`bowlbug_progenitor.png/.atlas/.spatlas/.spjson`, `bowlbug_progenitor_skel_data.tres`), used by
`scenes/creature_visuals/bowlbug_progenitor.tscn` (SpineSprite, position (21.58,-3.12), scale 0.52 —
pixel-aligned with the former static Sprite2D) and `BowlbugProgenitor : ThingsSpineMonster`.
Built the same way as `tools/TheLegacyRig`; the old cutout parts under `images/monsters/rig_parts`
/ `ai_rig_parts` and the old source rig `animations/monsters/sts2_things/bowlbug_progenitor` are NOT used.

## Pipeline (Python 3, numpy, opencv-python, scikit-image, scipy, Pillow)
Copy `source_assets/monsters/bowlbug_progenitor.png` here as `src.png` (1437x782), then:

1. Layer split (34 parts, occluded areas painted in, gem/eye glow overlays):
   `python seg.py && python parts.py && python recomp.py`
   -> `labels.npy`, `sac_mask.npy`, `parts_list.json`, `parts/*.png` + `parts/meta.json`, `order.json`
   (all committed, so step 1 can be skipped). `recomp.py` re-composites the layers over the source.
   Parts: membrane_rear/front, egg_sac, rear_shell, shell_mid, dome2/3, leaf_plate, crest_1..5,
   shell_front, head, mandible_upper/lower, eye, pupil, leg1..5 upper/shin/claw.
2. `leg_joints.json` — hip/knee/ankle/toe per leg (committed).
3. `python build_rig.py` -> packed 2048 atlas + weighted meshes (`out/rig_static.json`):
   47 bones / 40 slots / 3736 verts / 5786 tris. Membranes and egg sac are multi-bone gaussian
   skinned (egg_f/m/r/lo drive the peristaltic egg push), crests are 2-bone chains, the rest rigid.
   Rig definition (bone tree, pivots, skin rules) lives in `rigdef.py`; origin = pixel (760,776), y up.
4. `python export.py` -> `out/bowlbug_progenitor.json` (Spine 4.2). Poses from `anims.py` are sampled
   at 30 fps. Legs are planted with a bend-limited IK (leg1 exact 2-bone, <=45°; the near-straight
   legs 2-5 flex <=16° and slide/lift the foot for the rest, so there is no knee flipping). Crest
   spines ride a damped spring (2.1 Hz, zeta 0.28, clamp ±28°) driven by the carapace motion.
   Keys are then reduced within an error tolerance.
5. `python package.py` -> `pkg/` (copy into the shipping folder).
6. Preview without Godot: `python render.py attack 0,9,14,20 tag` (CPU mesh render -> `prev/*.jpg`).

## Animations (game timing contract in brackets)
| name | length | notes |
|---|---|---|
| idle_loop | 3.0 s loop | breathing carapace, egg sac pulse, gem/eye glow, mandible twitch, leg3 fidget step; seamless |
| attack | 1.25 s | rear up 0-0.36, lunge + mandible bite, contact 0.45-0.50 [attack hit ~0.45-0.5], rear legs step with the lunge |
| cast | 1.4 s | head sway + mandible chitter, release pulse at 0.50 [Disrupt: "Cast"] |
| power_up | 1.5 s | brace, crests flare, gem glow surge at 0.50 [Prepare / Rest / failed summon: "PowerUp"] |
| summon | 1.3 s | egg sac peristalsis front->rear, pop at 0.70, rear stomps [lay egg: "Summon", minion spawns 0.75] |
| hurt | 0.65 s | recoil, squash, crest whip |
| die | 2.6 s | stagger, legs buckle, collapse (sink 74 px), darkening tint |
| revive | 1.8 s | reverse of collapse, blends into idle |

## Verification
- `scripts/verify_bowlbug_progenitor_spine_scene.gd [PCK]` (headless) mounts an exported PCK, instantiates
  the shipping scene and plays all 8 animations to completion.
- `scripts/render_bowlbug_progenitor_visual_probe.gd OUTPUT_DIR [FPS]` renders every animation through the
  real spine-godot runtime.
- `scripts/verify_project.py` checks the scene/asset/export/model contract for the native rig.
- `review/` — per-animation contact sheets and GIFs.

## Legacy generator
`scripts/build_spine_monsters.py` retains the historical cutout assets in RIG_KEYS, but protects the
shipping scenes for Bowlbug Progenitor, The Legacy, Origin Fogmog and Scale Beetle. Use this directory's
pipeline to update the current Bowlbug rig; `--no-scenes` also protects all other scenes during a legacy rebuild.
