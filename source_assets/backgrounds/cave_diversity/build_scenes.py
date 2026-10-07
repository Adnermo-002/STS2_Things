"""Build four original cave paintings plus an eight-scene readable preview.

New scenes use a full painted environment, native atmosphere and a static
foreground occlusion matte. The matte is not an independently movable prop.
"""
from pathlib import Path
import importlib.util
import hashlib
import json
import shutil
from PIL import Image, ImageDraw, ImageFilter
from brighten_existing import apply as brighten_existing

HERE = Path(__file__).resolve().parent
MOD = HERE.parents[2]
BASE = HERE.parent / "hollow_grotto"
PREVIEW = HERE / "preview_project"
RAW = MOD.parent / "output/imagegen/cave_diversity/raw"
if not RAW.exists():
    RAW = HERE / "raw"
spec = importlib.util.spec_from_file_location("native_scene_helpers", BASE / "build_scene.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
native.PREVIEW = PREVIEW
SCENES = json.loads((HERE / "scenes.json").read_text(encoding="utf-8"))
OLD = {
    "hollow_grotto": "幽蓝溶洞 · 提亮版",
    "hollow_grotto_moss": "苔光岩窟 · 提亮版",
    "hollow_grotto_ember": "余烬石窟 · 提亮版",
    "hollow_grotto_violet": "紫雾深窟 · 提亮版",
}


def color(values):
    return "Color(" + ", ".join(str(v) for v in values) + ")"


def matte(paint, slug):
    """Near-edge holdout: original pixels keep native fog behind the frame."""
    mask = Image.new("L", paint.size, 0)
    d = ImageDraw.Draw(mask)
    if slug == "cave_rootfungus":
        left = [(0,.65),(.07,.70),(.12,.77),(.18,.82),(.23,.89),(.31,.95),(.43,1),(0,1)]
        right = [(1,.66),(.94,.73),(.88,.78),(.80,.87),(.73,.92),(.65,.97),(.55,1),(1,1)]
    elif slug == "cave_quartz":
        left = [(0,.62),(.06,.74),(.10,.69),(.15,.83),(.21,.84),(.28,.94),(.39,1),(0,1)]
        right = [(1,.67),(.95,.77),(.90,.75),(.83,.87),(.76,.92),(.68,.98),(.59,1),(1,1)]
    else:
        left = [(0,.75),(.04,.77),(.08,.83),(.14,.82),(.19,.88),(.25,.88),(.34,.96),(.46,1),(0,1)]
        right = [(1,.74),(.95,.81),(.92,.79),(.88,.87),(.82,.88),(.76,.94),(.68,.97),(.59,1),(1,1)]
    for points in [left,right]:
        d.polygon([(round(x*paint.width),round(y*paint.height)) for x,y in points],fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(.7))
    result = paint.copy()
    result.putalpha(mask)
    return result


def paint_layer(slug, suffix, image_suffix):
    return f'''[gd_scene load_steps=3 format=3]

[ext_resource type="Texture2D" path="res://images/rooms/{slug}/{slug}_{image_suffix}.png" id="1_art"]
[ext_resource type="Material" path="res://materials/backgrounds/cave_readable_new.tres" id="readability"]

[node name="Cave{suffix}" type="Control"]
mouse_filter = 2

[node name="PaintedLayer" type="TextureRect" parent="."]
material = ExtResource("readability")
offset_left = -1382.4
offset_top = -648.0
offset_right = 1382.4
offset_bottom = 648.0
mouse_filter = 2
texture = ExtResource("1_art")
expand_mode = 1
'''


def effects(scene):
    text = native.FOG_NODES
    replacements = {
        "Color(0.09, 0.18, 0.19, 0.7)": color(scene["light"]),
        "Vector2(210, -180)": "Vector2("+", ".join(map(str,scene["light_position"]))+")",
        "Color(0.12, 0.18, 0.22, 0.24)": color(scene["fog"]),
        "Color(0.10, 0.16, 0.19, 0.22)": color(scene["fog"]),
        "Color(0.3, 0.46, 0.5, 0.35)": color(scene["motes"]),
        "amount = 16": "amount = 12",
    }
    for before,after in replacements.items():
        assert before in text
        text = text.replace(before,after)
    return text


def build():
    brighten_existing()
    specs, provenance = {}, {}
    for slug, scene in SCENES.items():
        raw_name = slug + ("_r01.png" if slug == "cave_riverbend" else "_r02.png")
        raw_path = RAW / raw_name
        source = Image.open(raw_path)
        assert abs(source.width/source.height - 2048/960) < .02
        paint = source.convert("RGBA").resize((2048,960),Image.Resampling.LANCZOS)
        assert paint.getchannel("A").getextrema() == (255,255)
        generated = HERE / "generated" / (slug + ".png")
        paint.save(generated,optimize=True)
        image_dir = MOD / "images/rooms" / slug
        image_dir.mkdir(parents=True,exist_ok=True)
        paint.save(image_dir/(slug+"_00.png"),optimize=True)
        matte(paint,slug).save(image_dir/(slug+"_occlusion.png"),optimize=True)
        for png in image_dir.glob("*.png"):
            native.image_import(png)
        scene_dir = MOD / "scenes/backgrounds" / slug
        root = '''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://src/Core/Nodes/Rooms/NCombatBackground.cs" id="1_native"]

[node name="NewCaveBackground" type="Control"]
layout_mode = 3
anchors_preset = 0
mouse_filter = 2
script = ExtResource("1_native")
'''
        for slot in ["Layer_00","Layer_01","Foreground"]:
            root += f'''\n[node name="{slot}" type="Control" parent="."]
unique_name_in_owner = true
anchors_preset = 0
mouse_filter = 2
'''
        root_path = scene_dir/(slug+"_background.tscn")
        native.write(root_path,root)
        paths = [scene_dir/"layers"/(slug+"_bg_00_a.tscn"),scene_dir/"layers"/(slug+"_bg_01_a.tscn"),scene_dir/"layers"/(slug+"_fg_a.tscn")]
        native.write(paths[0],paint_layer(slug,"Environment","00"))
        native.write(paths[1],'[gd_scene load_steps=8 format=3]\n'+native.FOG_RESOURCES+'\n[node name="CaveAtmosphere" type="Control"]\nmouse_filter = 2\n'+effects(scene))
        native.write(paths[2],paint_layer(slug,"ForegroundOcclusion","occlusion"))
        specs[slug] = {"name":scene["name"],"subtitle":scene["subtitle"],"root":root_path.relative_to(MOD).as_posix(),"layers":[p.relative_to(MOD).as_posix() for p in paths],"kind":"new"}
        provenance[slug] = {
            "requested_model":"gpt-image-2","requested_quality":"high","generation_mode":"bundled imagegen CLI; user-approved OpenAI-compatible API",
            "raw_file":str(raw_path),"raw_size":list(source.size),"raw_sha256":hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            "source_painting":str(generated),"normalized_size":[2048,960],"normalized_sha256":hashlib.sha256(generated.read_bytes()).hexdigest(),
            "prompt":scene["prompt_file"],"revision_prompt":"prompts/"+slug+"_r02.txt" if slug!="cave_riverbend" else None,
            "postprocess":"RGBA/size normalization and foreground fog-occlusion alpha only; painted content is generated",
            "layer_contract":"full painting + native atmosphere + static foreground holdout; holdout is not independently repositionable",
        }
        print("NEW_SCENE_BUILT",slug)
    for slug,name in OLD.items():
        root = f"scenes/backgrounds/{slug}/{slug}_background.tscn"
        layers = [f"scenes/backgrounds/{slug}/layers/{slug}_bg_{i:02}_a.tscn" for i in range(4)]
        layers.append(f"scenes/backgrounds/{slug}/layers/{slug}_fg_a.tscn")
        specs[slug] = {"name":name,"subtitle":"已生成的新地面 · 暗部与中间调提亮","root":root,"layers":layers,"kind":"brightened_existing"}
    for scene in specs.values():
        for path in [scene["root"]]+scene["layers"]:
            native.stage(path,MOD)
    native.write(PREVIEW/"scene_specs.json",json.dumps(specs,ensure_ascii=False,indent=2))
    config = (BASE/"preview_project/project.godot").read_text(encoding="utf-8").replace("Hollow Grotto - STS2 Native Background Preview","Eight Readable Cave Scenes")
    native.write(PREVIEW/"project.godot",config)
    shutil.copy2(BASE/"preview_project/preview.tscn",PREVIEW/"preview.tscn")
    shutil.copy2(HERE/"preview.gd",PREVIEW/"preview.gd")
    (HERE/"generation_provenance.json").write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding="utf-8")
    print("EIGHT_CAVE_PREVIEW_READY",PREVIEW)


if __name__ == "__main__":
    build()
