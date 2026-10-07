"""Three cave variants with independent generated floors and layered walls.

Run from the preserved workspace layout. The original hollow_grotto assets are
read-only inputs. New resources use independent scene/image namespaces.
"""
from pathlib import Path
import importlib.util
import json
import shutil
import numpy as np
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "hollow_grotto"
MOD = HERE.parents[2]
PREVIEW = HERE / "preview_project"
REVIEW = HERE / "review"


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, BASE / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


art = module("approved_cave_art", "build_art.py")
native = module("approved_cave_scenes", "build_scene.py")
native.PREVIEW = PREVIEW

VARIANTS = {
    "moss": {
        "name": "苔光岩窟", "slug": "hollow_grotto_moss", "subtitle": "新绘石灰岩 · 苔土过渡 · 稀疏萤光",
        "air": [(8, 18, 15), (25, 40, 28), 85],
        "far": [(10, 22, 20), (30, 43, 31), 44],
        "back": [(8, 17, 18), (27, 37, 29), 42],
        "stone": [(5, 11, 12), (32, 42, 31), 38],
        "roof": [(3, 7, 6), (21, 28, 17), 26],
        "front": [(2, 4, 4), (13, 18, 12), 27],
        "light": "Color(0.09, 0.23, 0.07, 0.65)",
        "light_pos": "Vector2(-140, -180)",
        "fog_left": "Color(0.10, 0.18, 0.09, 0.20)",
        "fog_right": "Color(0.08, 0.16, 0.08, 0.20)",
        "motes": "Color(0.43, 0.65, 0.17, 0.60)", "amount": 22,
    },
    "ember": {
        "name": "余烬石窟", "slug": "hollow_grotto_ember", "subtitle": "新绘冷却岩流 · 碎薄壳 · 缓升余烬",
        "air": [(22, 12, 15), (48, 28, 20), 85],
        "far": [(21, 14, 20), (45, 30, 27), 44],
        "back": [(15, 10, 18), (37, 23, 29), 42],
        "stone": [(9, 6, 13), (43, 28, 31), 38],
        "roof": [(5, 4, 8), (26, 17, 19), 26],
        "front": [(2, 2, 5), (17, 10, 13), 27],
        "light": "Color(0.29, 0.11, 0.025, 0.66)",
        "light_pos": "Vector2(-90, -110)",
        "fog_left": "Color(0.18, 0.09, 0.035, 0.20)",
        "fog_right": "Color(0.15, 0.075, 0.03, 0.18)",
        "motes": "Color(0.95, 0.37, 0.08, 0.70)", "amount": 26,
    },
    "violet": {
        "name": "紫雾深窟", "slug": "hollow_grotto_violet", "subtitle": "新绘层状片岩 · 细矿脉 · 紫色薄雾",
        "air": [(18, 11, 27), (35, 25, 51), 85],
        "far": [(22, 16, 34), (43, 32, 57), 44],
        "back": [(16, 11, 26), (36, 27, 47), 42],
        "stone": [(8, 6, 18), (42, 31, 58), 38],
        "roof": [(4, 3, 11), (22, 15, 33), 26],
        "front": [(2, 2, 6), (15, 10, 24), 27],
        "light": "Color(0.16, 0.075, 0.26, 0.58)",
        "light_pos": "Vector2(370, -155)",
        "fog_left": "Color(0.15, 0.09, 0.23, 0.21)",
        "fog_right": "Color(0.13, 0.07, 0.21, 0.23)",
        "motes": "Color(0.43, 0.30, 0.62, 0.38)", "amount": 14,
    },
}


def graded(im, settings, key, retention=.07):
    dark, light, maximum = settings[key]
    return art.grade(im, dark, light, maximum, color_retention=retention)


def make_art(key, v):
    rocks = art.source("images/rooms/underdocks/underdocks_03_b.png")
    ridge = art.source("images/rooms/hive/hive_04_a.png")
    loose = art.source("images/rooms/waterfall_giant_bg/waterfallgiant_bg_4_rocksb.png")
    base = art.load_generated_floor(v["slug"])
    far, mid, roof, front = [art.blank() for _ in range(4)]
    distant, back, stone = [graded(rocks, v, k, .08) for k in ["far", "back", "stone"]]
    cap = graded(ridge, v, "roof", .04)
    fg = graded(ridge, v, "front", .03)
    # Every capped spike crop has transparent padding around its silhouette.
    twin = (1605, 210, 1825, 515)
    pillar = (1170, 0, 1550, 552)

    if key == "moss":
        art.put(far, distant.crop((0, 0, 1165, 552)), (140, -30), (750, 565))
        art.put(far, distant.crop(pillar), (1330, -50), (320, 585), flip_x=True)
        art.put(far, distant.crop(twin), (950, 393), (120, 161))
        art.put(far, distant.crop(twin), (1185, 398), (105, 141), flip_x=True)
        art.put(far, back.crop(pillar), (225, -65), (380, 670), flip_x=True)
        art.put(far, back.crop(pillar), (1530, -105), (440, 715))
        art.put(mid, stone.crop((0, 0, 274, 520)), (-70, -80), (610, 740))
        art.put(mid, stone.crop(pillar), (1570, -90), (545, 775), flip_x=True)
        art.put(mid, stone.crop(twin), (500, 447), (200, 219))
        art.put(mid, stone.crop(twin), (1510, 480), (157, 180), flip_x=True)
        art.put(roof, cap, (0, 23), flip_y=True, flip_x=True)
        art.put(roof, stone.crop(twin), (745, -45), (230, 307), flip_y=True)
        art.put(roof, stone.crop(twin), (1220, -70), (155, 210), flip_x=True, flip_y=True)
        foliage = art.source("images/rooms/overgrowth/overgrowth_04_a_1.png")
        art.put(roof, foliage, (525, 532), (112, 119))
        art.put(roof, foliage, (1500, 574), (93, 99), flip_x=True)
        root_ridge = art.source("images/rooms/hive/hive_04_b.png")
        art.put(front, graded(root_ridge, v, "front", .05), (0, 58))
    elif key == "ember":
        art.put(far, distant.crop(pillar), (620, -140), (280, 650), flip_x=True)
        # Whole connected cluster, excluding the half-pillar at the source
        # left border. Interior pieces must never expose a sheet crop edge.
        art.put(far, distant.crop((292, 0, 1168, 552)), (1020, -90), (795, 650))
        art.put(far, distant.crop(twin), (1040, 379), (139, 170))
        art.put(far, back.crop((292, 0, 1168, 552)), (-180, -110), (855, 732), flip_x=True)
        art.put(mid, stone.crop((0, 0, 274, 520)), (-105, -45), (595, 735))
        art.put(mid, stone.crop(pillar), (1495, -100), (595, 770))
        art.put(mid, stone.crop(twin), (401, 435), (193, 238), flip_x=True)
        art.put(mid, stone.crop(twin), (1580, 430), (187, 247))
        art.put(roof, cap, (0, -38), flip_y=True)
        art.put(roof, stone.crop(twin), (552, -32), (167, 283), flip_y=True)
        art.put(roof, stone.crop(twin), (872, -44), (210, 297), flip_y=True, flip_x=True)
        art.put(roof, stone.crop(twin), (1320, -66), (211, 346), flip_y=True)
        art.put(front, fg, (0, 74), flip_x=True)
    else:
        art.put(far, distant, (265, -60), (1450, 540))
        art.put(far, back.crop((292, 0, 1168, 552)), (-20, -155), (840, 742))
        art.put(far, back.crop(pillar), (1490, -90), (390, 635), flip_x=True)
        art.put(far, distant.crop(twin), (1115, 389), (133, 183))
        art.put(mid, stone.crop(pillar), (182, -168), (465, 827), flip_x=True)
        art.put(mid, stone.crop((0, 0, 274, 520)), (1505, -168), (623, 840), flip_x=True)
        art.put(mid, stone.crop(twin), (590, 422), (164, 232))
        art.put(roof, cap, (0, -70), flip_y=True, flip_x=True)
        art.put(roof, stone.crop(twin), (647, -65), (165, 395), flip_y=True)
        art.put(roof, stone.crop(twin), (1304, -47), (175, 275), flip_x=True, flip_y=True)
        art.put(front, fg, (0, 105))

    pebble = graded(loose, v, "stone", .08).crop((111, 34, 243, 84))
    art.put(roof, pebble, (615 if key == "ember" else 730, 652), (97, 37))
    art.put(roof, pebble, (1415, 652), (80, 30), flip_x=True)
    layers = [base, far, mid, roof, front]
    out = MOD / "images/rooms" / v["slug"]
    out.mkdir(parents=True, exist_ok=True)
    for suffix, im in zip(["00", "01", "02", "03", "fg"], layers):
        p = out / (v["slug"] + "_" + suffix + ".png")
        im.save(p, optimize=True)
        native.image_import(p)
    combined = art.blank()
    for im in layers:
        combined.alpha_composite(im)
    REVIEW.mkdir(exist_ok=True)
    art.viewport(combined).convert("RGB").save(REVIEW / (v["slug"] + "_paint_r03_new_floor.png"))


def effects(v, key):
    nodes = native.FOG_NODES
    replacements = {
        "Color(0.09, 0.18, 0.19, 0.7)": v["light"],
        "Vector2(210, -180)": v["light_pos"],
        "Color(0.12, 0.18, 0.22, 0.24)": v["fog_left"],
        "Color(0.10, 0.16, 0.19, 0.22)": v["fog_right"],
        "Color(0.3, 0.46, 0.5, 0.35)": v["motes"],
        "amount = 16": "amount = " + str(v["amount"]),
    }
    if key == "ember":
        replacements.update({"gravity = Vector2(0, -0.35)": "gravity = Vector2(0, -1.6)",
                             "scale_amount_min = 0.009": "scale_amount_min = 0.010",
                             "scale_amount_max = 0.017": "scale_amount_max = 0.023"})
    for a, b in replacements.items():
        assert a in nodes, a
        nodes = nodes.replace(a, b)
    return nodes


def make_scene(key, v):
    slug = v["slug"]
    scene_dir = MOD / "scenes/backgrounds" / slug
    scene_dir.mkdir(parents=True, exist_ok=True)
    root_file = scene_dir / (slug + "_background.tscn")
    native.write(root_file, (MOD / "scenes/backgrounds/hollow_grotto/hollow_grotto_background.tscn")
                 .read_text().replace("HollowGrottoBackground", "HollowGrotto" + key.title() + "Background"))
    layers = []
    for suffix in ["00", "01", "02", "03", "fg"]:
        layer_name = "fg" if suffix == "fg" else "bg_" + suffix
        template = MOD / f"scenes/backgrounds/hollow_grotto/layers/hollow_grotto_{layer_name}_a.tscn"
        content = template.read_text().replace("/images/rooms/hollow_grotto/hollow_grotto_", "/images/rooms/" + slug + "/" + slug + "_")
        if suffix == "01":
            index = content.index('[node name="CavernAmbientLight"')
            content = content[:index] + effects(v, key)
        target = scene_dir / "layers" / (slug + "_" + layer_name + "_a.tscn")
        native.write(target, content)
        layers.append(target.relative_to(MOD).as_posix())
    paths = {"root": root_file.relative_to(MOD).as_posix(), "layers": layers, "name": v["name"]}
    for path in [paths["root"]] + paths["layers"]:
        native.stage(path, MOD)
    return paths


def build():
    specs = {}
    for key, v in VARIANTS.items():
        make_art(key, v)
        specs[v["slug"]] = make_scene(key, v)
        print("BUILT", v["name"], v["slug"])
    original = json.loads((BASE / "preview_project/scene_specs.json").read_text())["hollow_grotto"]
    original["name"] = "幽蓝溶洞 · 新绘水蚀岩床"
    for path in [original["root"]] + original["layers"]:
        native.stage(path, MOD)
    specs["hollow_grotto"] = original
    native.write(PREVIEW / "scene_specs.json", json.dumps(specs, ensure_ascii=False, indent=2))
    native.write(PREVIEW / "project.godot", (BASE / "preview_project/project.godot").read_text()
                 .replace("Hollow Grotto - STS2 Native Background Preview", "STS2 Cave Variants"))
    shutil.copy2(BASE / "preview_project/preview.tscn", PREVIEW / "preview.tscn")
    shutil.copy2(HERE / "preview.gd", PREVIEW / "preview.gd")
    native.write(HERE / "variants_manifest.json", json.dumps({
        "revision": "r03_new_floor", "source_version": "STS2-V111", "variants": VARIANTS,
        "method": "Four independent generated floor paintings; existing cave walls remain separate layers.",
        "source_sha256": art.SOURCES, "layer_size": [2048, 960],
        "generated_floors": art.GENERATED_FLOORS,
        "native_root_script": "res://src/Core/Nodes/Rooms/NCombatBackground.cs",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build()
