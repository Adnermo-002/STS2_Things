# Thief Raider v9 — current-master semantic-parts rebuild

## Immutable identity source

`00_reference/current_master.png` is copied from the actual project sprite
`images/monsters/thief_raider.png`.  It is the identity, proportions, palette,
left-facing pose language, material treatment, and combat silhouette source.

The v8 generated full-body candidate and donor-bind composite are rejected as
identity sources.

## Asset-generation rule

Generate semantic body parts from the current master before rigging.  Every
part must keep the same character, camera/view, light direction, smooth matte
paint, and compact Raider anatomy.

- closed, solid joint ends with hidden overlap extensions;
- no hollow sleeves, boot openings, sockets, or rectangular crop faces;
- no full-body redesign and no front-facing neutral mannequin;
- no realistic long limbs, faceting, plastic highlights, or palette shift;
- no floating belt, duplicate hand, detached armor, or accessory ambiguity;
- cape/scarf/sack are isolated soft pieces; metal armor is isolated rigid art;
- dagger hand, grip, and dagger are distinct but reconstruct the master exactly.

The generated sheets are donors only.  A bind-pose reconstruction must match
the immutable master at alpha IoU >= 0.995 and must pass visual inspection at
combat scale before Spine work begins.
