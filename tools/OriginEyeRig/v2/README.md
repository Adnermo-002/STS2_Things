# Origin Eye With Teeth — v2 (2026-09-30): vanilla rig, Origin re-skin

The illusion eye now uses the **vanilla EyeWithTeeth skeleton and animations** exactly
(191 bones, 5 thorny tentacles, path-constraint motion), baked to a constraint-free Spine 4.2 JSON
(world-space bone keys @30 fps; verified against the runtime: idle max vertex error < 1 unit).
Origin traits, derived from Origin Fogmog: petals/leaves/tentacles re-tinted from the vanilla green to the
fogmog cap's brick red (slot colours hue-mapped, animated flashes preserved), glowing lime cap-style spots on
every petal and toothed leaf (additive overlay slots that follow the same meshes/deforms), eyeball kept vanilla green.
Extra animations the mod needs: hurt (0.5 s recoil on `cog` + red flash over idle), revive (die reversed, 1.2 s).

Inputs (vanilla, not shipped here): STS2-V109/animations/monsters/eye_with_teeth/eye_with_teeth.{skel,atlas,png} in ../ref/

    npm i @esotericsoftware/spine-core@4.2
    python tex.py                               # -> origin_eye_with_teeth.{png,atlas} (unrotated, x2, spots)
    node bake.mjs ../ref/eye_with_teeth.skel ../ref/eye_with_teeth.atlas origin_eye_with_teeth.json extra.json
    node dump.mjs origin_eye_with_teeth.json origin_eye_with_teeth.atlas attack 6 d.json && python render.py d.json sheet.jpg origin_eye_with_teeth.png=origin_eye_with_teeth.png
