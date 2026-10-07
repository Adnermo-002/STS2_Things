"""Prepare reference-only boards and requests for genuinely new floor paintings.

This script DOES NOT generate artwork. No stock floor is copied into a new
floor image. Generation awaits an available, user-authorized image service.
"""
from pathlib import Path
import importlib.util
import json
from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
MOD = HERE.parents[2]
BASE = HERE.parent / "hollow_grotto"
VANILLA = MOD.parent / "STS2-V111"
REFS = HERE / "references"
PROMPTS = HERE / "prompts"
for p in [REFS, PROMPTS, HERE / "generated"]:
    p.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location("cave_layout", BASE / "build_art.py")
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)

JOBS = [
    {"slug": "hollow_grotto", "name": "幽蓝溶洞", "palette": "muted blue-slate, deep indigo shadows, a faint cool teal atmospheric distance",
     "design": "An original naturally water-worn cave floor of broad continuous slate bedrock. Long irregular erosion furrows curve diagonally through the outer foreground. Shallow silt pockets and a few small rounded pebbles collect at the edges. The broad central combat area remains flat and quiet. Invent the bedrock silhouette, fissures, erosion pattern and pebble placement from scratch. No assembled paving stones."},
    {"slug": "hollow_grotto_moss", "name": "苔光岩窟", "palette": "deep muted moss green, cool charcoal stone, olive-brown damp earth",
     "design": "An original damp karst cave floor: continuous rounded limestone worn nearly smooth, irregular seams filled with dark earth, a few thin moss islands and shallow worn depressions toward the outer edges. Use a completely new organic layout. Keep moss sparse enough that the stone still reads as a cave floor; no grass field, copied fern shapes or forest flagstones."},
    {"slug": "hollow_grotto_ember", "name": "余烬石窟", "palette": "charcoal plum shadows, muted brown-ochre rock, restrained distant amber illumination",
     "design": "An original dry volcanic cave floor: broad overlapping flows of cooled rock with long asymmetrical wrinkles, broken thin crusts and a few charcoal chips at the side edges. The quiet flat central stage is continuous geological rock. Design fresh irregular forms without polygonal cell tessellation, hexagons, honeycomb, paving tiles or a copy of the game's Hive floor. No bright lava rivers or luminous cracks."},
    {"slug": "hollow_grotto_violet", "name": "紫雾深窟", "palette": "deep charcoal-violet, muted mauve slate, a faint lilac atmospheric distance",
     "design": "An original ancient cave floor formed from gently folded layers of schist. Broad low strata, thin irregular mineral veins and sparse chipped flakes lie mostly near the side foreground. The central walking surface remains flat and uninterrupted. Invent a new asymmetrical geological arrangement rather than individual laid stones. No masonry blocks, geometric paving, crystal clusters, neon veins or reused Glory floor pattern."},
]

# Use only the existing upper/foreground planes as a composition reference.
# The current stock-derived layer 00 is deliberately excluded.
for job in JOBS:
    canvas = Image.new("RGBA", (2048, 960), (13, 14, 19, 255))
    for suffix in ["01", "02", "03", "fg"]:
        img = Image.open(MOD / "images/rooms" / job["slug"] / (job["slug"] + "_" + suffix + ".png")).convert("RGBA")
        canvas.alpha_composite(img)
    layout.viewport(canvas).convert("RGB").save(REFS / (job["slug"] + "_walls_only.png"))

# Original paint vocabulary references; no ground/floor layer is included.
samples = [
    ("images/rooms/underdocks/underdocks_03_b.png", "Vanilla rock brushwork / irregular outlines"),
    ("images/rooms/waterfall_giant_bg/waterfallgiant_bg_4_rocksb.png", "Vanilla rock planes / small hand-painted marks"),
    ("images/rooms/hive/hive_04_a.png", "Vanilla dark foreground values / faceted rock"),
]
board = Image.new("RGB", (1600, 1000), "#20222b")
draw = ImageDraw.Draw(board)
font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 23)
for i, (relative, label) in enumerate(samples):
    im = Image.open(VANILLA / relative).convert("RGBA")
    bounds = im.getchannel("A").getbbox()
    im = im.crop(bounds)
    thumb = ImageOps.contain(im, (1550, 275), Image.Resampling.LANCZOS)
    y = i * 330
    draw.text((22, y + 12), label, fill="#d5d9e3", font=font)
    board.paste(thumb, ((1600 - thumb.width) // 2, y + 48), thumb)
board.save(REFS / "vanilla_rock_style_only.jpg", quality=96, subsampling=0)

common = """Use case: stylized-concept
Asset type: brand-new opaque floor painting for a layered Slay the Spire 2 combat background.
Primary request: Create completely NEW original ground artwork for a NEW cave region. The supplied pictures are style/composition references only. Do not copy or trace any reference geometry or reuse image pixels.
Input images: Image 1 is the existing cave walls with the old floor REMOVED; use it only to match perspective and lighting. Image 2 shows original game rock brushwork; use it only for line weight, simple painted shading and restrained detail.
Output canvas: one full-bleed 2048 x 960 landscape PNG, opaque throughout, no text or labels.
Composition: Paint ONLY the floor and a quiet dark atmospheric fade above the far ground. The far floor should dissolve into atmosphere around canvas y=330-400. The bottom 60 percent contains the perspective ground plane, larger forms in front, smaller forms receding into the distance. Do not draw the surrounding walls, pillars, ceiling, stalactites, characters, UI or foreground rock frame; those are separate engine layers.
Gameplay space: Keep x=420..1680 and y=490..770 smooth, flat and readable for combatants. Put most geological accents near outer edges and lower foreground. No obstacles, stairs, deep holes or large upright stones in this area.
Style/medium: Match the references' hand-painted 2D game background style: irregular confident dark contours, broad simplified pigment planes, selective softly brushed variation, subtle hand-painted surface marks, restrained low-frequency detail. Low overall luminance so bright characters remain readable; retain dark shadow pockets without crushing all midtones. No photographic textures, PBR/3D render, plastic gloss, procedural Voronoi pattern, vector-flat placeholder, airbrushed cinematic concept art or dense high-frequency grunge.
Lighting: Broad subdued ambient light consistent with the wall reference. Native mist and light will be added by Godot; avoid strong baked bloom or isolated point lights.
Originality constraint: Every fissure, bedrock shape and material mark must be newly invented. Do not reproduce the existing Overgrowth flagstones, Hive hexagonal cells, Glory cobblestones or any previous floor. All four requested versions need their own new ground composition, not merely palette swaps of one floor.
"""

for job in JOBS:
    prompt = common + "\nGround design: " + job["design"] + "\nColor palette: " + job["palette"] + ".\n"
    prompt_file = PROMPTS / (job["slug"] + ".txt")
    prompt_file.write_text(prompt, encoding="utf-8")
    job["prompt_file"] = str(prompt_file)
    job["reference_images"] = [str(REFS / (job["slug"] + "_walls_only.png")), str(REFS / "vanilla_rock_style_only.jpg")]
    job["expected_generated_image"] = str(HERE / "generated" / (job["slug"] + "_floor.png"))
    job["runtime_destination"] = str(MOD / "images/rooms" / job["slug"] / (job["slug"] + "_00.png"))

(HERE / "generation_brief.json").write_text(json.dumps({
    "status": "awaiting_image_generation_service", "all_floors_must_be_new": True,
    "reference_policy": "style only; no stock floor images are supplied", "jobs": JOBS,
    "target_size": [2048, 960], "runtime_state": "unchanged until all four new paintings are generated and reviewed",
}, ensure_ascii=False, indent=2), encoding="utf-8")
print("BRIEFS_READY; no floor artwork has been generated or replaced.")
