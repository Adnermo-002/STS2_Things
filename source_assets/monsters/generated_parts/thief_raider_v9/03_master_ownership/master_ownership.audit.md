# Thief Raider v9 visible-ownership audit

**Verdict:** PASS

Bind reconstruction is exact RGBA, but exact reconstruction alone does not approve moving boundaries.

- master pixels: 93228
- uncovered / outside / overlap: 0 / 0 / 0
- boundary/material failures: 0
- underlap notices: 12

## Failures

- none

## Underlap notices

- `cloak_tail_far` — {'semantic': 'cloak_tail_far', 'notice': 'visible_islands_require_hidden_underlap', 'actual_pixels': 6}
- `cloak_tail_near` — {'semantic': 'cloak_tail_near', 'notice': 'visible_islands_require_hidden_underlap', 'actual_pixels': 17}
- `far_lower_leg` — {'semantic': 'far_lower_leg', 'notice': 'visible_islands_require_hidden_underlap', 'actual_pixels': 1}
- `sack_strap` — {'semantic': 'sack_strap', 'notice': 'visible_islands_require_hidden_underlap', 'actual_pixels': 30}
- `near_lower_leg` — {'semantic': 'near_lower_leg', 'notice': 'visible_islands_require_hidden_underlap', 'actual_pixels': 1}
- `pelvis_skirt` — {'semantic': 'pelvis_skirt', 'notice': 'visible_islands_require_hidden_underlap', 'actual_pixels': 38}
- `torso_core` — {'semantic': 'torso_core', 'notice': 'visible_islands_require_hidden_underlap', 'actual_pixels': 820}
- `belt_and_pouch` — {'semantic': 'belt_and_pouch', 'notice': 'visible_islands_require_hidden_underlap', 'actual_pixels': 3}
- `far_shoulder_plate` — {'semantic': 'far_shoulder_plate', 'notice': 'visible_islands_require_hidden_underlap', 'actual_pixels': 1}
- `scarf` — {'semantic': 'scarf', 'notice': 'visible_islands_require_hidden_underlap', 'actual_pixels': 156}
- `hooded_head` — {'semantic': 'hooded_head', 'notice': 'visible_islands_require_hidden_underlap', 'actual_pixels': 6}
- `dagger` — {'semantic': 'dagger', 'notice': 'visible_islands_require_hidden_underlap', 'actual_pixels': 2}
