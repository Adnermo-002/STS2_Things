# STS2_Things Monster Cutout Rig V2 — segmentation and seam contract

Target: STS2 v0.108.0. This plan keeps every shipping RGB value from the current
`images/monsters/*.png`; diagnostic overlays are never packaged. It deliberately
uses native Godot `Skeleton2D/Bone2D/Sprite2D` rather than a Spine runtime so the
existing mod loader/PCK contract remains unchanged.

## Non-negotiable construction rules

1. **Stage owns translation.** Attack/Hit/Cast displacement belongs to
   `ThingsRigStage`. Structural shell/body bones never receive independent local
   translation.
2. **Only joints articulate.** Local bone animation is rotation plus at most
   0.5–1.5% scale on a complete anatomical cluster. A child never receives the
   same whole-body transform already inherited from its parent.
3. **Opaque socket overlap.** Every shoulder/hip/leg socket is a parent-owned
   underlay declared before its child. The child borrows 12–24 fully opaque
   source pixels over that socket. Semi-transparent pixels remain single-owner.
4. **No ghost underlay.** Never leave the intact full monster below moving
   pieces. Underlays are small joint caps only.
5. **Draw order and ownership are separate.** Ownership follows the table's
   declaration order; `z` follows visual depth. Dark ink contours belong to the
   foreground anatomical part.
6. **Translucent rigs are special.** `the_legacy` and all Soul Roe textures use
   no duplicated translucent padding. Their main pieces stay locked to one
   anchor unless a later art pass supplies hidden backfill.
7. **Bind-pose gate.** For rigs made from their own source PNG, reconstructed
   visible RGBA must have zero mismatching pixels. The Soul Roes cluster is an
   intentional external-composition rig and is checked against its authored
   twelve-orb composition instead.
8. **Runtime matching.** Exact-name whitelists must replace substring rules such
   as `Contains("Leg")`; otherwise a parent and its `*Shin/*Foot` descendants
   receive the same transform twice.

Coordinates below are absolute source-canvas pixels. `parent` is the Bone2D
parent. Multiple sprites may share one bone and therefore share its pivot.

## 1. Origin Fogmog — 21 sprite parts / 16 bones

Canvas 886×954. Preserve `Root/Body/Face/CapCenter/LeftArm/RightArm/LeftFoot/RightFoot`
for runtime compatibility.

| part(s) | bone (pivot) | parent | z | source/mask action |
|---|---|---:|---:|---|
| `base`, `body_core` | `Body` (443,620) | Root | 0,20 | Base becomes only unclaimed pixels; body mask follows trunk silhouette, not a rectangle. |
| `face` | `Face` (438,455) | Body | 42 | Existing `face` narrowed to the facial trunk between cap and shoulders. |
| `face_features` | Face (438,455) | Body | 48 | Eyes, mouth and green marks; same bone, alpha/emission events only. |
| `cap_underside` | `CapCenter` (443,300) | Face | 43 | Entire tan underside/rim; provides rigid cover behind cap sectors. |
| `cap_left` | `CapLeft` (260,286) | CapCenter | 45 | Existing `cap` split at x≈350, following red rim. |
| `cap_center` | CapCenter (443,300) | Face | 47 | Central crown x≈330–565. |
| `cap_right` | `CapRight` (650,280) | CapCenter | 44 | Right overhang x≈545–886. |
| `socket_left_shoulder` | Body (443,620) | Root | 24 | Opaque 22 px cap centered near (322,487). |
| `left_upper_arm` | `LeftArm` (322,487) | Body | 30 | Existing `left_arm` shoulder→elbow only. |
| `left_forearm` | `LeftForearm` (229,602) | LeftArm | 31 | Elbow→wrist. |
| `left_hand` | `LeftHand` (137,700) | LeftForearm | 34 | Palm and all three claws as one rigid hand. |
| `socket_right_shoulder` | Body (443,620) | Root | 24 | Opaque 22 px cap centered near (568,473). |
| `right_upper_arm` | `RightArm` (568,473) | Body | 30 | Existing `right_arm` shoulder→elbow only. |
| `right_forearm` | `RightForearm` (672,585) | RightArm | 31 | Elbow→wrist. |
| `right_hand` | `RightHand` (760,692) | RightForearm | 34 | Palm and claws. |
| `socket_left_hip` | Body (443,620) | Root | 18 | Opaque 20 px cap near (337,736). |
| `left_leg` | `LeftLeg` (337,736) | Body | 21 | Thigh/shin above ankle; split out of old `left_foot`. |
| `left_foot` | `LeftFoot` (318,844) | LeftLeg | 23 | Foot and toes. |
| `socket_right_hip` | Body (443,620) | Root | 18 | Opaque 20 px cap near (571,736). |
| `right_leg` | `RightLeg` (571,736) | Body | 21 | Thigh/shin above ankle. |
| `right_foot` | `RightFoot` (608,849) | RightLeg | 23 | Foot and toes. |

CapLeft/CapRight rotate no more than ±0.8°; the visible life comes from hands,
forearms and whole-stage timing, not independent cap translation.

## 2. Bowlbug Progenitor — 38 sprite parts / 24 bones

Canvas 1437×782. The four large armor/abdomen regions remain rigid siblings of
Root. Every visible leg becomes a three-bone chain.

### Structural and accent pieces

| part | bone (pivot) | parent | z | replaces/subdivides |
|---|---|---|---:|---|
| `base` | Root (745,520) | — | 0 | Only purple membrane/unclaimed pixels. |
| `head` | Head (420,510) | FrontShell | 30 | Old head, contour-tight. |
| `crest` | Crest (420,350) | Head | 26 | Old crest; no independent spike translation. |
| `mandible_upper` | Mandible (115,590) | Head | 46 | Upper orange jaw from old `mandible`. |
| `mandible_lower` | MandibleLower (105,646) | Head | 47 | Lower orange jaw from old `mandible`. |
| `front_shell` | FrontShell (600,465) | Root | 21 | Old mask follows green plate outline. |
| `mid_shell` | MidShell (865,470) | Root | 22 | Old mask follows next green plate. |
| `egg_sac` | EggSac (1060,475) | Root | 20 | Orange egg field only. |
| `rear_shell` | RearShell (1260,500) | Root | 23 | Rear green crescent/tail armor. |
| `gem_head_crown`, `gem_head_brow` | Crest (420,350) | Head | 50 | Teal gems around (255,205), (198,350). |
| `gem_crest_front`, `gem_crest_mid` | Crest (420,350) | Head | 50 | Teal gems around (335,310), (625,180). |
| `gem_front_shell_top`, `gem_front_shell_low` | FrontShell (600,465) | Root | 50 | Gems around (710,84), (635,180). |
| `gem_mid_shell` | MidShell (865,470) | Root | 50 | Gem around (860,215). |
| `gem_rear_shell`, `gem_tail` | RearShell (1260,500) | Root | 50 | Gems around (1198,72), (1415,375). |

Gem sprites share their plate bone: they may flash/modulate but never drift away.

### Leg chains and opaque socket caps

| chain | upper bone/pivot | lower bone/pivot | foot bone/pivot | parent | z |
|---|---|---|---|---|---:|
| `front_leg`, `front_leg_lower`, `front_foot` | FrontLeg (575,592) | FrontLegLower (480,660) | FrontFoot (426,747) | FrontShell | 34–36 |
| `mid_leg_a`, `mid_leg_a_lower`, `mid_foot_a` | MidLegA (690,595) | MidLegALower (720,671) | MidFootA (748,747) | MidShell | 33–35 |
| `mid_leg_b`, `mid_leg_b_lower`, `mid_foot_b` | MidLegB (945,595) | MidLegBLower (984,681) | MidFootB (1020,744) | EggSac | 33–35 |
| `rear_leg_a`, `rear_leg_a_lower`, `rear_foot_a` | RearLegA (1128,595) | RearLegALower (1182,676) | RearFootA (1254,742) | RearShell | 33–35 |
| `rear_leg_b`, `rear_leg_b_lower`, `rear_foot_b` | RearLegB (1320,595) | RearLegBLower (1364,666) | RearFootB (1411,720) | RearShell | 33–35 |

Add `socket_front_leg`, `socket_mid_leg_a`, `socket_mid_leg_b`,
`socket_rear_leg_a`, `socket_rear_leg_b` to their plate's bone at z=31. Each owns
an 18–24 px opaque ring at the hip and is declared before its corresponding
upper leg. The child pad re-covers the ring in bind pose.

## 3. Scale Beetle — 38 sprite parts / 32 bones

Canvas 1127×883. Keep both seven-piece antenna chains exactly. Existing broad
leg rectangles are the most visible source of bad layer separation and are
replaced by contour-following joint chains.

| part/chain | bones and absolute pivots | parent | z | existing mask action |
|---|---|---|---:|---|
| `base` | Root (610,650) | — | 0 | Only small unclaimed thorax pixels. |
| `front_shell` | FrontShell (505,555) | Root | 20 | Rigid; contour-tight. |
| `core_shell` | Core (690,545) | Root | 21 | Rigid; contour-tight. |
| `rear_shell` | RearShell (900,565) | Root | 19 | Rigid; contour-tight. |
| `head` | Head (350,600) | FrontShell | 30 | Excludes eye and jaw masks. |
| `eye` | Head (350,600) | FrontShell | 48 | Same Head bone; blink/flash only. |
| `jaw_upper` | JawUpper (165,660) | Head | 44 | Contour-tight upper beak. |
| `jaw_lower` | JawLower (180,690) | Head | 45 | Contour-tight lower tusk/jaw. |
| `fore_claw`, `fore_claw_lower`, `fore_claw_tip` | ForeClaw (430,680); ForeClawLower (333,755); ForeClawTip (176,835) | FrontShell chain | 38–42 | Split old foreground `fore_claw` into shoulder, spiked forearm, terminal claw. |
| `front_leg`, `front_leg_lower`, `front_foot` | FrontLeg (530,680); FrontLegLower (560,744); FrontFoot (529,804) | FrontShell chain | 28–31 | Split small rear-plane front leg. |
| `mid_leg`, `mid_leg_lower`, `mid_foot` | MidLeg (620,650); MidLegLower (656,744); MidFoot (690,846) | Core chain | 33–36 | Split at both visible dark rings. |
| `rear_leg`, `rear_leg_lower`, `rear_foot` | RearLeg (866,625); RearLegLower (911,735); RearFoot (958,842) | RearShell chain | 34–37 | Split at hip and ankle rings. |
| `socket_fore_claw`, `socket_front_leg` | FrontShell | Root | 26 | 16–22 px opaque shoulder caps. |
| `socket_mid_leg` | Core | Root | 26 | 18 px hip cap. |
| `socket_rear_leg` | RearShell | Root | 26 | 18 px hip cap. |

Antenna bones/parts stay named exactly:

```text
AntennaFrontBase -> AntennaFront1 -> AntennaFront2 -> AntennaFront3
 -> AntennaFront4 -> AntennaFront5 -> AntennaFrontTip
AntennaBackBase -> AntennaBack1 -> AntennaBack2 -> AntennaBack3
 -> AntennaBack4 -> AntennaBack5 -> AntennaBackTip
```

Their existing pivots remain unchanged. Each segment keeps 3 px opaque-only
borrow and rotates 0.5–1.3° relative to its parent; accumulated tip travel is
visible while the socket stays closed.

## 4–6. Soul Roe 1/2/3 — 3 sprite parts / 3 bones each

Canvas 104×104. The source is 98–99% translucent, so padding is zero.

| part | bone/pivot | parent | z | rule |
|---|---|---|---:|---|
| `membrane` (generated base) | Root (52,52) | — | 0 | Entire outer membrane and transparent fringe. |
| `inner_halo` | Core (52,56) | Root | 2 | Annulus around the yolk; no pad. |
| `nucleus` | Nucleus (52,56) | Core | 3 | Central yolk, no pad. |

The three variants use identical geometry and retain their individual RGBA.
Core/Nucleus motion is limited to sub-pixel rotation and scale; no quadrant
splitting is used because it creates four visible translucent seams at this
resolution.

## 7. Soul Roes cluster — 12 sprite parts / 16 bones

The twelve existing external orb sprites are already the correct fine-grained
units. Do not split them again. Add three virtual grouping bones while keeping
all current orb names and pivots:

```text
Root (178,140)
├─ ClusterTop (178,65): RoeTopLeft, RoeTop, RoeTopRight
├─ ClusterMiddle (178,145): RoeMiddleFarLeft, RoeMiddleLeft, RoeCore,
│                          RoeMiddleRight, RoeFarRight
└─ ClusterBottom (180,220): RoeBottomLeft, RoeBottom, RoeBottomRight,
                           RoeBottomFarRight
```

Cluster bones supply a slow 1–2 px breathing arc; each orb adds only a small
phase-delayed scale/rotation. No orb becomes the parent of another orb.

## 8. The Legacy — 14 sprite parts / 14 bones

Canvas 1358×689. About 98% of visible pixels are translucent. Every region has
zero duplicate pad and all anatomical masses inherit `HeartAnchor`; realistic
heartbeat is driven once at `HeartAnchor`, never once per lobe.

| part | bone/pivot | parent | z | replaces/subdivides |
|---|---|---|---:|---|
| `base` | Root (680,560) | — | 0 | Ground vegetation/unclaimed pixels. |
| `top_purple` | TopPurple (790,170) | HeartAnchor | 10 | Purple dorsal aorta/back mass. |
| `top_tubes` | TopTubes (690,115) | TopPurple | 18 | Two upper open tubes only. |
| `left_tubes` | LeftTubes (350,275) | HeartAnchor | 20 | Upper-left cyan vessel. |
| `left_lobe` | LeftLobe (340,430) | HeartAnchor | 21 | Left/lower cyan lobe. |
| `bottom_lobe` | BottomLobe (420,565) | HeartAnchor | 22 | Bottom foreground cyan lobe. |
| `heart_core` | HeartCore (690,430) | HeartAnchor | 25 | Central ventricle. |
| `right_lobe` | RightLobe (930,440) | HeartAnchor | 23 | Cyan right mass behind tubes. |
| `right_tubes` | RightTubes (1120,410) | HeartAnchor | 26 | Blue right arterial cluster. |
| `right_purple_tubes` | RightPurpleTubes (1230,520) | HeartAnchor | 17 | Purple lower-right tubes. |
| `coral_left` | CoralLeft (300,430) | HeartAnchor | 40 | Pink coral foreground; locked until backfill exists. |
| `coral_right` | CoralRight (805,560) | HeartAnchor | 41 | Purple coral foreground; locked until backfill exists. |
| `seaweed_left` | SeaweedLeft (260,350) | Root | 8 | Left/background vegetation. |
| `seaweed_right` | SeaweedRight (1050,420) | Root | 8 | Right/background vegetation. |

`HeartAnchor` is at (690,430), parent Root. Main organ bones keep identity local
transforms for Idle/Hit/Cast/Attack; HeartAnchor performs the 1.50 s systole
(0.5–0.8% scale). Coral/seaweed sway starts only after hidden organ/backdrop
pixels have been painted beneath their roots.

## 9. Thief Raider — 26 sprite parts / 22 bones

Canvas 353×534. At this resolution, cuts follow the existing dark outlines and
use 8–14 px opaque socket overlap.

| part/chain | bone pivots | parent | z | existing mask action |
|---|---|---|---:|---|
| `base`, `torso` | Torso (190,235) | Pelvis | 0,25 | Torso becomes contour-tight; base holds tiny unclaimed pixels. |
| `pelvis` | Pelvis (190,285) | Root | 24 | Belt/hip block only. |
| `head` | Head (190,125) | Torso | 38 | Hood and face void. |
| `scarf` | Scarf (207,145) | Torso | 40 | Front scarf panel, same torso motion plus ≤1° settle. |
| `bag` | Bag (126,145) | Torso | 5 | Bag body; strap stays Torso. |
| `cloak`, `cloak_left_tail`, `cloak_right_tail` | Cloak (145,190); CloakLeftTail (69,300); CloakRightTail (150,315) | Torso chain | 6–10 | Split old cloak along the two visible tail valleys. |
| `guard_arm`, `guard_forearm`, `guard_hand` | GuardArm (120,135); GuardForearm (105,185); GuardHand (163,172) | Torso chain | 42–46 | Split shoulder plate, bracer/forearm and gripping hand. |
| `dagger_upper_arm`, `dagger_forearm`, `dagger_hand`, `dagger` | DaggerUpperArm (260,170); DaggerForearm (282,235); DaggerHand (297,290); Dagger (310,300) | Torso chain | 43–50 | Existing upper/forearm tightened; hand separated; dagger parent becomes DaggerHand. |
| `left_leg`, `left_shin`, `left_foot` | LeftLeg (145,320); LeftShin (135,410); LeftFoot (118,495) | Pelvis chain | 17–21 | Split old left leg at knee armor and ankle wrap. |
| `right_leg`, `right_shin`, `right_foot` | RightLeg (220,320); RightShin (225,405); RightFoot (252,485) | Pelvis chain | 18–22 | Split old right leg at knee armor and ankle wrap. |
| `socket_guard_shoulder`, `socket_dagger_shoulder` | Torso | Pelvis | 39 | Parent-owned 10–14 px caps. |
| `socket_left_hip`, `socket_right_hip` | Pelvis | Root | 15 | Parent-owned 10–12 px caps. |

## Target totals and migration order

| rig | current parts | V2 parts | current bones | V2 bones |
|---|---:|---:|---:|---:|
| Origin Fogmog | 7 | 21 | 8 | 16 |
| Bowlbug Progenitor | 13 | 38 | 13 | 24 |
| Scale Beetle | 25 | 38 | 25 | 32 |
| Soul Roe 1 | 2 | 3 | 2 | 3 |
| Soul Roe 2 | 2 | 3 | 2 | 3 |
| Soul Roe 3 | 2 | 3 | 2 | 3 |
| Soul Roes | 12 | 12 | 13 | 16 |
| The Legacy | 8 | 14 | 9 | 14 |
| Thief Raider | 11 | 26 | 12 | 22 |
| **Total** | **82** | **158** | **86** | **133** |

Migration order: Scale Beetle → Origin Fogmog → Thief Raider → Bowlbug → Legacy
→ Soul Roe variants/cluster. Each rig must pass bind-pose RGBA reconstruction,
then sampled extreme Attack/Hit/Cast poses, before the next rig replaces its
old masks.
