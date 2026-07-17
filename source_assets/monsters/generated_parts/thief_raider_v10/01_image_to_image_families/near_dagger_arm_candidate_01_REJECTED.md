# Near dagger arm candidate 01 visual gate

Status: **REJECTED**.

Candidate: `01_image_to_image_families/near_dagger_arm_candidate_01_alpha.png`

## Root input error discovered

The v9 ownership guide itself has two semantic layer mistakes:

1. The white sliver shown on `near_upper_arm` belongs to `near_shoulder_plate`, so image generation baked an entire pauldron into the upper-arm piece.
2. The detached 17x18 metal crescent shown on `near_forearm` is the dagger pommel cap, not a cuff bridge. The brown handle/pommel visible behind the fingers must belong to the dagger attachment. The hand must overlay the dagger handle.

## Candidate failures

- `near_upper_arm`: shoulder plate baked in; both joint ends are broad flat cuffs; silhouette is elongated and more inflated than the compact master.
- `near_forearm`: pommel remains a detached crescent; wrist end is visibly hollow; proximal end is a rounded plug.
- `near_dagger_hand`: contains dagger blade/guard/handle pixels and therefore is still a composite, not an isolated hand.
- `dagger`: cleaner than the other three, but blade/guard proportions and values drift from the locked master and it does not prove a full hidden handle under the hand.
- All four use smoother/glossier volume rendering than the master and require identity overlay before any donor use.

No piece from candidate 01 enters bind, Spine, PCK, or Steam.

## Correct layer contract for the next guide

- `near_shoulder_plate`: all white shoulder metal.
- `near_upper_arm`: dark cloth sleeve only, hidden under shoulder plate and forearm bracer.
- `near_forearm`: dark/brown sleeve plus its actual bracer only; no pommel cap.
- `near_dagger_hand`: skin/glove/fingers/wrist only; no weapon pixels.
- `dagger`: blade, guard, a complete handle passing beneath the gripping fingers, and pommel cap; hand draws above dagger.
