# The Legacy (心脏残躯) native Spine 4.2 rig — source pipeline

Build-time only (`tools/` is `.gdignore`d and excluded from the PCK).
Shipping output: `STS2_Things/animations/monsters/the_legacy/`
(`the_legacy.png/.atlas/.spatlas/.spjson`, `the_legacy_skel_data.tres`), used by
`scenes/creature_visuals/things_the_legacy.tscn` (SpineSprite) and
`ThingsTheLegacy : ThingsSpineMonster`.

## Pipeline (Python 3, numpy, opencv-python, scikit-image, scipy, Pillow)
Copy `source_assets/monsters/the_legacy.png` here as `src.png`, then:

1. Split into layered parts (29 parts, painted-in occluded areas):
   `python seg.py && python build_parts.py && python build_tex.py && python recomp.py && python sheet.py body && python sheet.py front`
   -> `parts/*.png` + `parts/meta.json` (already committed, so steps 1 can be skipped).
   `recomp.py` re-composites the layers over the source (mean abs diff 0.13/255).
2. `python weed_axes.py` (seaweed/coral base->tip axes -> `weed_axes.json`)
3. `python build_rig.py` -> packed atlas + weighted meshes (`out/rig_static.json`), 67 bones,
   26 body bones + 2-3 bone chains per seaweed/coral, 3346 verts / 5208 tris.
4. `python export.py` -> `out/the_legacy.json` (Spine 4.2). Procedural poses (`anims.py`)
   are sampled at 30 fps; seaweed/coral chains are driven by a damped spring simulation
   reacting to the body's acceleration, then keys are reduced within an error tolerance.
5. `python package.py` -> `pkg/` (copy into the shipping folder).
6. Optional preview without Godot: `python render.py attack 0,9,13,20 2` (writes `prev/*.jpg`).

## Animations
| name | length | notes |
|---|---|---|
| idle_loop | 3.0 s loop | two lub-dub beats (1.5 s period, matches the heartbeat SFX), breathing, tube sway, vein glow pulse |
| attack | 1.25 s | anticipation 0-0.30, lunge left 0.30-0.42 (contact ~0.4), settle |
| cast | 1.4 s | three accelerating beats, release burst at 0.40-0.55, vein glow |
| power_up | 1.5 s | stronger cast + quiver |
| summon | 1.3 s | peristaltic wave through tubes |
| hurt | 0.65 s | recoil right, squash, glow flash |
| die | 2.6 s | arrhythmia, collapse, seaweed droop, darkening tint |
| revive | 1.8 s | reverse of collapse, blends into idle |

## Verification
- `scripts/render_the_legacy_visual_probe.gd OUTPUT_DIR [FPS]` renders every animation through the real
  spine-godot runtime (Godot GUI executable); `review/` holds contact sheets / GIFs from that probe.
- `scripts/verify_the_legacy_spine_scene.gd [PCK]` (headless) mounts an exported PCK, instantiates the
  shipping scene and plays all 8 animations to completion.
- `scripts/verify_project.py` checks the scene/asset/export contract for the native rig.
