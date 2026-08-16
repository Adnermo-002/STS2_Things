# Gravetide Slug Asset Style Audit (STS2 v0.109.0)

This is the generation brief for every Gravetide image deliverable. It was
written from the shipped v0.109.0 data before selecting or generating the
asset sources.

## Inventory

| Asset family | Shipped coverage reviewed | Contract used by Gravetide |
| --- | ---: | --- |
| Monster atlas textures | 102 families / 120 textures | Native Corpse Slug Spine region contract |
| Boss and Underdocks backgrounds | 12 families / 275 textures | Five native background layers at 2048x960 |
| Boss map icons | 18 textures / 9 icon-and-outline pairs | 352x300 Alpha silhouette pair |
| Boss run-history images | 26 textures / 13 image-and-outline pairs | 88x88 Alpha thumbnail pair |
| Power icons | 271 textures | 256x256 primary and 64x64 packed Alpha icon |
| Underdocks Boss music | 11 decoded stems/states | 150-second dedicated stereo loop |
| Corpse Slug SFX | 14 decoded round-robin/state samples | 15 custom action variants |

Audit data and contact sheets live in `build/style_audit/`:

- `monsters.json` and `monsters_contact.png`
- `backgrounds.json`, `backgrounds_contact.png`, and
  `backgrounds_representative_contact.png`
- `icons.json` and `icons_contact.png`
- `gravetide_audio_metrics.json` and `gravetide_audio_output_metrics.json`

## Visual Language

### Boss creature

The native Corpse Slug establishes the shared animation vocabulary: a low,
side-facing wet body, a readably segmented mouth, a distinct head/top layer,
and a compact set of appendage regions. Across the 102 monster families, the
largest forms reserve their complexity for the silhouette and a small number
of unmistakable material breaks. They do not distribute equal detail across
the whole body.

Gravetide should therefore retain the Corpse Slug's Spine region count and
action poses while changing the first-read silhouette: a taller brackish
carapace, a grave-marker ridge, and a single pale bone seam. The boss reads as
one massive tidal carrion eater rather than an enlarged regular slug. Dark
teal-blue is the body family; bone-white is the only high-value accent. Avoid
neon, evenly spaced markings, symmetrical ornament, or a second competing
motif.

### Underdocks boss background

The twelve reviewed boss/Underdocks families use a deep opaque architectural
base with isolated transparent atmosphere and foreground layers. Most scene
families use 2048x960 art planes and reserve bright values for a small focal
area. Waterfall Giant and Soul Fysh show the relevant Act 1B rule: cold water,
weathered masonry, and low fog create depth before the boss is drawn.

Gravetide's five-layer scene follows that contract:

1. far wall and vaults stay dark and quiet;
2. middle dock shapes establish perspective without competing with enemies;
3. water carries the only moving reflection signal;
4. atmosphere is sparse mist, not a full-screen wash;
5. foreground framing remains below creature readability.

### Power icon

Of the 271 reviewed Power icons, 270 are 256x256 RGBA and their median filled
area is 59.2%. Their common visual rule is semantic compression: one central
object, one dominant hue family, one small contrast accent, and a black or
transparent negative-space field. The icon is a status symbol, not a portrait
or a mini encounter scene.

The Digestion icon uses only one read: **a deep-blue stomach vortex consuming
one bone-white bone**. It excludes the previous shield, rainbow arc, purple
bubbles, tooth crown, gold gem, skull, and multi-bone cues. The packed 64x64
version must preserve the bone as the only bright focal point.

The simplified revision is limited to one centered stomach silhouette and one
bone. It uses three flat subject colors plus a near-black outline, one broad
highlight plane at most, and no creature portrait, teeth ring, bubbles,
surface texture, gradients, particles, or secondary ornament. The 64x64 read
must be "stomach consuming bone" before any decorative detail is visible.

### Map and run-history UI

All nine shipped Boss map icon pairs use a white Alpha silhouette and a larger
white Alpha outline. They carry no local creature palette. All thirteen
run-history pairs are 88x88 RGBA thumbnails plus a matching outline and need
their silhouette to read at one glance.

Map and history assets therefore need separate ImageGen outputs, not crops of
the runtime Spine atlas and not programmatically whitened derivatives.

## ImageGen Delivery Specs

### Boss regions

Generate each existing Spine region as a separate opaque painted element on a
flat removable chroma background. Preserve its assigned region's pose and
negative space. The body, body-top, eat, and small-parts outputs are source
art only; the atlas build may crop, fit, and apply the shipped region alpha.

### Digestion Power

Use case: stylized-concept

Asset type: 256x256 combat Power icon source

Primary request: a compact deep-sea blue stomach vortex, seen front-on, with
one short bone-white bone being drawn inward; hand-painted game icon; one
clear symbol at thumbnail size.

Constraints: transparent or flat removable chroma background; deep navy and
muted teal with bone-white only; thick near-black outline; exactly one broad
highlight plane; no frame; no creature portrait; no teeth ring; no shield; no
crown; no gem; no skull; no bubbles; no gold; no texture; no gradient; no
particles; no text; no watermark.

### Boss map icon and outline

Use case: stylized-concept

Asset type: 352x300 Boss-map Alpha pair

Primary request: a single solid white silhouette of a towering tide-bloated
slug with a grave-marker dorsal ridge, side-facing, simple readable outer
contour; separate output for its slightly larger solid white outline.

Constraints: black or removable chroma background; white subject only; no
interior color, texture, text, shadow, or watermark.

### Run-history thumbnail and outline

Use case: stylized-concept

Asset type: 88x88 run-history Alpha pair

Primary request: compact portrait of the tide-bloated slug's open dark-blue
mouth with one bone-white bone, using the same dorsal ridge silhouette;
separate matching outline image.

Constraints: sparse two-color composition; no text, frame, background scene,
or watermark; silhouette remains readable at 88 pixels.

## Acceptance Gates

- Every game-facing image begins as an ImageGen source retained under
  `source_assets/` with `imagegen` in its filename.
- Python use is limited to chroma removal, crop, resize, PNG conversion, and
  alpha/size validation. It does not draw, recolor, or create silhouettes.
- `scripts/build_gravetide_ui_assets.py --require-direct-ui-sources` must pass
  before Release packaging.
- Visual probe output is reviewed at both runtime scale and 64x64 icon scale.

## Audio Language

The shipped `act1_b1.fsb` contains 35 music samples. Eleven belong to the two
Underdocks bosses: eight synchronized Waterfall Giant layers at about 150.2
seconds and three Soul Fysh states at 175.2-183.9 seconds. The complete shipped
SFX bank contains 1,929 samples; all 14 Corpse Slug samples were decoded and
measured (three light attacks, three attacks, three deaths, three ravenous
starts, and two ravenous releases).

The reference medians establish the useful envelope:

| Measure | Waterfall Giant | Soul Fysh | Corpse Slug SFX | Gravetide final |
| --- | ---: | ---: | ---: | ---: |
| Duration | 150.2 s | 182.9 s | 1.97 s | 150.0 s / 1.82 s median |
| RMS | -26.2 dBFS | -21.5 dBFS | -36.6 dBFS | -23.5 dBFS / -31.0 dBFS |
| Crest | 19.6 dB | 20.1 dB | 20.6 dB | 18.8 dB / 17.4 dB |
| Dynamic range | 10.0 dB | 12.2 dB | 44.8 dB | 9.3 dB / 25.0 dB |
| Spectral centroid | 665 Hz | 454 Hz | 902 Hz | 829 Hz / 1,056 Hz |
| 20-120 Hz share | 1.8% | 40.5% | 1.3% | 4.3% / 0.5% |
| 500-2000 Hz share | 41.7% | 29.5% | 60.8% | 50.3% / 46.6% |
| Stereo correlation | 0.23 | 0.30 | 0.78 | 0.53 / 0.80 |

The Gravetide theme combines an independent stereo tide bed, upper-register
choir intervals, sparse bone bells, and restrained low drums. It avoids the
rejected 64-second near-mono sub drone. SFX retain the Corpse Slug family's wet
midrange, long tails, and round-robin variation while adding the boss's heavier
body and bone resonance. No shipped sample is copied into the generated WAVs.

`scripts/audit_gravetide_audio_style.py --outputs-only` is part of the normal
build and rejects duration, loudness, dynamics, spectrum, or stereo regressions.
