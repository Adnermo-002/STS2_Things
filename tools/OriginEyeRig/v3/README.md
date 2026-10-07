# Origin Eye With Teeth — v3 (2026-09-30): vanilla rig, grey V1 re-skin, NORMAL blend

**Skeleton & animations — faithful vanilla conversion.** `skel2json.mjs` converts the vanilla
`eye_with_teeth.skel` (Spine 4.2.43) to Spine 4.2 JSON *without baking*: 191 bones, the
`tentacle_rot_const` transform constraint, the 5 path constraints that drive the thorny tentacles,
weighted meshes / path attachments and the exact Bezier control points of every key (recorded by
hooking `setBezier` while the binary is read). Result vs the vanilla binary, sampled at 120 Hz:
idle_loop / attack / die max world-vertex error 0.01 units, slot colours and attachment switches
identical. (v2 baked world keys at 30 fps: 5.4 MB, up to ~200 units of mid-frame drift in the
attack tentacles, and its 4.0-style `deform` block was silently ignored by 4.2 readers.)
spjson is now 471 KB, atlas 1024x1024.

**Look (user decisions Q3=c, Q5, Q6, Q8).** The grey V1 design (`../design_mono_v1n2.png`) painted
onto the vanilla regions (same shapes / UVs, 2x): translucent dark-grey petals with light outlines,
midribs and pale spots; jaws with a pale shell, white teeth and a black maw; toothed pale lid; pale
eyeball, light iris with a dark ring, black vertical slit pupil; pale thorny tentacles drifting like
vanilla. NORMAL blending on every slot. Slot colours are grey: vanilla glow brightness -> grey,
breathing alpha 0.75..1, the eye kept mostly opaque, the additive `death_still` afterimage -> an
alpha ghost (peak 0.55). Tentacles are drawn behind the flower. No stalk.

**Mod-only animations** (`Monsters/OriginEyeWithTeeth.cs`: Hit -> `hurt`, IllusionPower wake-up -> `revive`):
- `hurt` 0.5 s = idle_loop 0..0.5 s (curves split exactly at 0.5 s) + recoil on `cog`
  (unkeyed in idle: -14 deg, +22 x, 0.92 x 1.06 squash) + a light red flash at 0.033 s.
- `revive` 1.2 s = `die` reversed (Bezier handles mirrored, stepped / attachment keys shifted), time-scaled.

## Rebuild

Vanilla inputs are not shipped. Point `EYE_REF` at the unpacked game's
`animations/monsters/eye_with_teeth` (eye_with_teeth.skel / .atlas / .png).

    npm i                                   # @esotericsoftware/spine-core 4.2
    pip install numpy opencv-python pillow rectpack
    node skel2json.mjs $EYE_REF/eye_with_teeth.skel $EYE_REF/eye_with_teeth.atlas out/eye_raw.json
    python eye_json.py                      # -> out/origin_eye_with_teeth.spjson
    python eye_tex.py                       # -> out/origin_eye_with_teeth.{png,atlas,spatlas}, out/tex_preview.jpg
    node verify_eye.mjs $EYE_REF/eye_with_teeth out/origin_eye_with_teeth.spjson out/origin_eye_with_teeth.atlas

Copy `out/origin_eye_with_teeth.{spjson,atlas,spatlas,png}` to
`STS2_Things/animations/monsters/origin_eye_with_teeth/` (the `_skel_data.tres`, `.uid` and
`.png.import` files stay). Output of this revision (sha256 prefixes): spjson `d227a86e6fa5e169`,
png `cf0966a46cf9dedd`, atlas `3de9ff29cb645316`, spatlas `a2b53d6d293aef0c`.
`../v2` is kept for history only.
