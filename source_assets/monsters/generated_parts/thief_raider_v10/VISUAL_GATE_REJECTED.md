# Thief Raider v10 visual gate — REJECTED

Date: 2026-07-16

## Verdict

The current near-arm weighted-mesh prototype is rejected as production art.
Pixel reconstruction and alpha coverage checks only prove that the bind image can be rebuilt; they do not prove that the separated art deforms believably.

## Visible failures in `near_arm_weighted_mesh_v05/contact.jpg`

1. The prototype is a detached arm test rather than a complete Raider animation, so body silhouette, center of gravity, draw order, and combat framing remain untested.
2. The shoulder terminates in a torn diagonal cut. Rotation exposes the crop edge and makes the shoulder plate float over a missing torso connection.
3. The upper sleeve reads as a swollen tube. Its volume changes across poses and produces a rubber-hose silhouette rather than a cloth-covered arm.
4. At elbow +75 and +110 degrees, the inner elbow collapses into a dark triangular cavity. The bracer, wrist, and hand form a cramped mechanical hinge.
5. The generated elbow-fold asset is an oversized pillow-shaped cloth patch, not a semantic elbow component. Scaling and masking it does not repair the topology.
6. The dagger/hand chain rotates as one rigid prop and loses the guarded stabbing gesture of the locked character pose.
7. The test angles are arbitrary stress rotations, not keyed Raider motion. Passing them would not establish a good idle, attack, hurt, or death animation.
8. No complete-character contact sheet demonstrates that the scarf, sack, cape, limbs, intent, health bar, cards, and neighboring monsters remain correctly layered.

## Disposition

- Reject `near_arm_weighted_mesh_v01` through `near_arm_weighted_mesh_v05`.
- Reject `near_elbow_fold_candidate_01_alpha.png` as a production attachment.
- Keep the locked identity source unchanged.
- Keep the current Steam package unchanged.
- Restart from a complete-character semantic-part board produced from the locked three-quarter-left character, then review the assembled bind pose before any animation keys are authored.

## Next visual gate

A candidate advances only when one review board shows all of the following together:

- exact three-quarter-left Raider identity and compact proportions;
- complete semantic parts with natural hidden joint underlaps;
- assembled bind pose matching the locked master at combat scale;
- explicit global draw order;
- no square crops, tubular limbs, plug joints, floating plates, or exposed cut edges;
- four full-character silhouette poses: idle, attack contact, short hurt, collapsed death.
