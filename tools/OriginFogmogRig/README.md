# Origin Fogmog — current Spine rig

The shipping rig uses the vanilla Fogmog skeleton, IK and transform constraints,
with a repaired skin and an authored boss-motion layer in `v3/`.
The old 39-bone generator is retained in `legacy_v2/` for historical editing only.
Do not deploy its output over the current rig.

## Rebuild

Requirements: Python 3 with `numpy`, `opencv-python`, `pillow`; Node.js with npm.
The rebuild script installs the locked Spine 4.2.43 runtime locally if necessary.
From the project root:

```powershell
.\tools\OriginFogmogRig\rebuild.ps1          # build and verify only
.\tools\OriginFogmogRig\rebuild.ps1 -Deploy  # update the four project assets
.\scripts\build.ps1                        # Godot import, validation and PCK export
```

`-Deploy` updates project files only. Installing the package into the game remains
the separate `scripts/build.ps1 -Install` operation.

## Inputs and outputs

- `v3/source/`: recovered v3 JSON/atlas/texture, kept as immutable rebuild inputs.
  The original v3 generator was lost; these three files are required source assets.
- `source_assets/monsters/origin_fogmog.png`: canonical painting, read by the builder
  to protect exposed original pixels while trimming occluded underpainting.
- `v3/build.py`: matched shoulder/hip/ankle weights, weighted claw roots, seven
  painted-root curl bones, and face cutouts that follow the trunk surface.
- `v3/motion.mjs`: weight-shifting breathing, stepping claw rake, advancing
  cap-led headbutt, sweep/rising rake/downward chop combo, spore hop with landing
  compression, broad exhale, and damped hurt response. Death
  and revival retain their original dried-fungus poses. Writes `out/origin_fogmog_boss.spjson`.
- `v3/runtime.mjs`, `snapshot.mjs`: actual Spine 4.2 bind-pose evaluation, including
  constraints. Bind at `idle_loop` time 0; the setup pose is **not** the painting pose.
- `v3/verify.mjs`: verifies the original repair, then checks all ten shipping
  motions at 120 Hz with `--authored-motion`. Both sides of nine painted joints
  must stay within 1.5 units; original geometry, constraints and repaired skin
  weights remain protected. Only the motion layer may change timelines.
- `v3/verify_motion.mjs`: checks foot reach, planted-contact drift, lift and return
  steps, claw clearance, grounded shadow/dust, stable arm scale, displacement and
  velocity continuity, and exact return-to-idle alignment. Minimum travel and
  body-arc checks protect the action amplitude; combo hits have distinct heights.
- `v3/out/`: generated files; ignored by Git and safe to regenerate.
- `STS2_Things/animations/monsters/origin_fogmog/`: shipping assets and VFX textures.

The repair preserves the 50 original bones and 27 slots, adds seven small curl
bones, and retains the seated death and revival. The boss's summon loads into a
crouch, opens its arms during a heavy hop, then compresses after landing. The
seven former rigid claws use the hand's weight field at their roots. The two
textures at each ankle share one continuous field. Triangular scraps of old
occlusion fill and detached claw-edge pixels are removed from the atlas.

## Visual verification

Use the Spine-enabled Godot 4.5.1 Mono executable already used by `scripts/build.ps1`:

```powershell
godot --path . --rendering-method gl_compatibility --script res://scripts/render_origin_fogmog_visual_probe.gd -- build/fogmog-review origin_fogmog 10
python scripts/verify_fogmog_render.py build/fogmog-review
godot --headless --path . --script res://scripts/verify_origin_fogmog_spine_scenes.gd -- build/v111/STS2_Things.pck
```

Run Godot import after changing the PNG. Rendering without import can silently
use the previous cached texture. The render probe manually updates the skeleton,
so frame times do not drift with rendering speed. The image check detects detached
painted pieces; review the contact sheet as well for texture and silhouette quality.
