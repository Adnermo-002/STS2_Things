"""Prepare original, diverse cave paintings using reference brushwork only."""
from pathlib import Path
import json
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
MOD = HERE.parents[2]
SOURCE = HERE.parent / "new_cave_floors"
for name in ["prompts", "references", "generated", "review", "delivery"]:
    (HERE / name).mkdir(parents=True, exist_ok=True)

# Reference-only readability adjustment. It is not a generated scene asset.
im = Image.open(SOURCE / "references/vanilla_rock_style_only.jpg").convert("RGB")
rgb = np.asarray(im, dtype=np.float32) / 255.0
Image.fromarray(np.clip(np.power(rgb, .80) * 255, 0, 255).astype(np.uint8)).save(HERE / "references/paint_style_readable.jpg", quality=96)
floor = Image.open(SOURCE / "generated/hollow_grotto_floor.png").convert("RGB")
rgb = np.asarray(floor, dtype=np.float32) / 255.0
Image.fromarray(np.clip(np.power(rgb, .80) * 255, 0, 255).astype(np.uint8)).save(HERE / "references/floor_brushwork_only.jpg", quality=96)

SCENES = {
    "cave_skylight": {
        "name": "天隙岩厅", "subtitle": "破顶天光 · 石灰岩拱 · 开阔岩台",
        "design": "A spacious limestone hall with an asymmetrical natural rock arch. A broken opening high in the left-middle roof admits soft warm daylight onto large cream-grey limestone surfaces. There is a smaller cool recess deep on the right. Broad angular slabs and weathered smooth chalk form the walls; absolutely no repeated vertical ribbed coral-like columns. The combat floor is an original broad uninterrupted pale shale and limestone shelf. A few low angular rocks frame the bottom corners, while the entire central arena stays flat and empty. The main ceiling opening must remain inside the central 65 percent of the canvas so it survives the game's center crop.",
        "palette": "muted warm ivory and grey-green limestone, cool desaturated blue recesses, restrained ochre daylight; readable medium-value paint planes",
        "fog": [0.16,0.19,0.19,0.14], "motes": [0.56,0.50,0.34,0.28],
        "light": [0.11,0.09,0.06,0.24], "light_position": [-280,-230],
    },
    "cave_riverbend": {
        "name": "回水石湾", "subtitle": "地下河湾 · 低岩檐 · 干燥战斗平台",
        "design": "A broad subterranean river bend beneath a low, horizontally layered rock overhang. An underground turquoise pool occupies only the rear half of the room, curving toward the far right, with a thin cascade far behind the arena. Water-worn banded shale and rounded boulders create a distinctly horizontal chamber. The lower 50 percent is a wide DRY continuous natural rock terrace where both sides of a combat can stand at the same height. No bridge, central hole or water channel crossing the combat lane. A shallow fringe of water may sit far behind it. Keep low foreground boulders at the bottom outer corners. No ribbed pillar forest.",
        "palette": "muted turquoise water, grey-blue shale, soft sage and cream highlights; bright enough to read rock faces, never neon",
        "fog": [0.10,0.22,0.23,0.14], "motes": [0.25,0.47,0.52,0.20],
        "light": [0.06,0.13,0.14,0.24], "light_position": [200,-120],
    },
    "cave_quartz": {
        "name": "白晶裂窟", "subtitle": "乳白晶簇 · 断层岩壁 · 细砂地表",
        "design": "An original fractured chalk-and-quartz cavern. A few large milky mineral clusters emerge diagonally from the left and right walls, forming broad simple faceted silhouettes. Broken layered limestone gives the roof its shape, with a narrow softly illuminated fissure in the upper rear. The quartz is opaque to translucent milky stone, rendered as a few hand-painted color planes, never glossy gems. The central combat floor is completely new continuous chalky bedrock with shallow silt pockets, subtle irregular cracks and very sparse flakes near the outer edges. Keep the middle flat and empty. Do not fill the arena with crystals; do not reuse a purple stalagmite forest.",
        "palette": "chalk white and muted lavender-grey mineral planes, soft powder blue shadows, restrained pale warm light; no magenta neon, no intense bloom",
        "fog": [0.18,0.16,0.23,0.12], "motes": [0.46,0.48,0.59,0.20],
        "light": [0.11,0.11,0.15,0.20], "light_position": [130,-235],
    },
    "cave_rootfungus": {
        "name": "根垂菌洞", "subtitle": "垂落根须 · 巨型菌伞 · 土岩地面",
        "design": "A broad earthy cave shaped by tangled hanging roots and ancient fungi. Thick roots descend from a low ochre stone ceiling; a few large shelf mushrooms and umbrella-shaped mushrooms occupy the side walls and rear corners, with visible simplified cream gills. A small opening far behind the right side suggests deeper connected burrows. Keep the center open rather than filling it with plants. The original ground is a continuous dark-earth and weathered rock surface with a few root impressions at the very outer edges. Both combatants stand on the same clear level stage. No copied fern props, tiled floor, characters or giant central mushroom obstructing combat.",
        "palette": "muted warm ochre, mushroom cream, russet-brown roots and soft sage-grey stone; gentle warm biological fill light, not saturated fluorescent green",
        "fog": [0.17,0.17,0.10,0.14], "motes": [0.54,0.47,0.23,0.30],
        "light": [0.12,0.10,0.045,0.20], "light_position": [250,-150],
    },
}

common = """Use case: stylized-concept
Asset type: final original hand-painted 2D combat background for a new Slay the Spire 2 cave region.
Primary request: Paint ONE completely new cave scene, with its own rock silhouettes, walls, ceiling, floor and composition. This must be a new location, not a recolor or rearrangement of an existing room.
Input images: Image 1 is brushwork/style reference only, with brighter display values for readability; ignore its collage layout and do not copy its rock shapes. Image 2 is an independently painted floor reference for simplified brushwork and camera angle only; invent a DIFFERENT ground layout. Do not trace, collage or reuse reference pixels.
Canvas: a single 2048 x 960 full-bleed opaque PNG. No panel layout, labels, characters, items, UI, lettering, border or watermark.
Camera: fixed side-view combat background, showing an oblique ground plane. The scene displays at 1.35x, centered in a 1920x1080 viewport, so the visible central crop is approximately x=295..1717, y=80..880 in the source canvas. Put the location's important forms inside this crop and extend artwork across the whole canvas for ultrawide displays.
Arena: keep x=420..1680, y=540..780 a broad, quiet, flat, unobstructed combat area. Both sides of the arena must share one ground level. Keep most foreground accents below y=825 or along the extreme sides. No deep fissure, step cliff, tall object or bright highlight directly under combatants.
Style: closely match the references' stylized hand-painted 2D game art. Bold irregular dark contours, broad simplified pigment planes, rounded yet angular rock masses, a few selected brush marks and small local imperfections. Clear readable silhouettes and painted shading. Do not turn this into photorealistic terrain, PBR, a glossy 3D render, intricate cinematic matte painting, anime scenery or uniform flat vector art.
Readability: noticeably easier to see than a near-black cave, while still subdued behind game characters. Use readable middle values on rock walls and the ground, soft ambient fill, and darker foreground framing. Preserve colored shadows and depth; do not wash the entire image with fog. No large clipped white area, dramatic spotlight beam, excessive bloom or lens effects.
Original ground: all ground shapes, cracks and material marks must be newly invented natural geology. No game stock floor, regular cobblestone paving, artificial flagstones, hexagonal cells, honeycomb or repeating Voronoi tiling.
"""
for slug, scene in SCENES.items():
    text = common + "\nDistinct scene: " + scene["design"] + "\nColor and light: " + scene["palette"] + ".\n"
    (HERE / "prompts" / (slug + ".txt")).write_text(text,encoding="utf-8")
    scene["prompt_file"] = "prompts/" + slug + ".txt"
    scene["raw_output"] = "output/imagegen/cave_diversity/raw/" + slug + "_r01.png"
(HERE / "scenes.json").write_text(json.dumps(SCENES,ensure_ascii=False,indent=2),encoding="utf-8")
print("FOUR_DIVERSE_SCENE_BRIEFS_READY")
