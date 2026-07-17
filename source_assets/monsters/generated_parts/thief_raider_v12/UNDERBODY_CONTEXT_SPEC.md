# Full Character Underbody Context v03

Isolated garment generation repeatedly creates hollow sleeve/collar ports. v03 instead generates one intact character underbody in the locked pose.

## Keep

- exact canvas placement, scale, crouch, left-facing three-quarter orientation, proportions, lighting and palette
- hood and eyes as alignment anchors
- continuous charcoal tunic, trousers and filled shoulder/elbow/wrist/hip/knee/ankle volumes
- empty gripping hands and boots

## Remove from the context plate

- scarf and cape
- shoulder/forearm armor
- sack, rope, knot and straps
- belt and pouch
- dagger

## Extraction strategy

After alignment, semantic masks will cut one-bone segments from the continuous painted body. Adjacent masks deliberately overlap along the generated continuous volume, so no isolated clothing opening becomes visible during motion.
