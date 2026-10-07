# Origin Fogmog — native Spine 4.2 mesh rig (v2, 2026-09-30)

Source painting: `src.png` (= images/monsters/origin_fogmog.png; signature mark masked out in parts.py).

Rebuild (Python 3 + numpy, opencv-python, pillow):

    python parts.py                                   # split + occlusion fill -> parts/
    set PYTHONPATH=kit;.
    python -m rigkit build && python -m rigkit export # -> out/origin_fogmog.{png,atlas,json}
    python -m rigkit render attack auto x             # CPU review sheet -> prev/
    python kit/package.py origin_fogmog               # -> pkg/ (copy to STS2_Things/animations/monsters/origin_fogmog)

v2 vs v1: 26 slots / 39 bones instead of 6 / 22. Parts follow the vanilla fogmog structure:
cap (dome+gills), trunk, separate eyes (blink/squint/widen) and mouth, arms with 3+4 individually
animated claws, IK-planted legs, additive glow on the cap spots and face drips, 8 additive spore sprites
(cast / summon / power_up / die / revive / idle puffs). Trunk painted in underneath cap, face and right arm
(push-pull fill + wood-grain noise, no Telea streaks); arms/legs extend under the trunk instead of the
trunk covering them, so poses no longer tear wedges. Same animation names, durations and hit timings
(attack 0.50 s, power_up 0.55 s, summon 0.75 s) and the same skeleton origin as v1, so the scene transform is unchanged.
