# Origin Eye (OriginEyeWithTeeth) — native Spine 4.2 mesh rig

Origin-exclusive redesign of the illusion Eye: monochrome grey + alpha like the vanilla eye_with_teeth atlas,
AI-generated painting `flower.png` (design `design_mono_v1n2.png`) plus three long thin tentacles
(`tentacle_src.png`, bent along the Bezier curves in parts.py -> `tentacles.json`).

Rebuild: `python parts.py`, then `PYTHONPATH=kit python -m rigkit build|export`, `python kit/package.py origin_eye_with_teeth`.
parts.py compensates semi-transparent layering so the rest pose recomposites the painting (alpha err ~0.06).

Parts (back->front): tent_c, tent_b, tent_a, petals, stalk, jaw, eyeball, iris, lid_low, lid_top.
Bones 42: 12 radial petal bones, eye/iris/lids/jaw, 2-bone stalk, 3 x 7-bone spring tentacles.
Animations: idle_loop, attack (heal 0.45s / distract 0.70s), hurt, die (held while the illusion is down), revive.
The skeleton faces right; the scene mirrors it (scale.x = -0.36).
