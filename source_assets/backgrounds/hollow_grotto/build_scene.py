"""Write native layer resources and stage a self-contained Godot preview.

The runtime root uses the game's actual NCombatBackground. Preview assembly
loads the same layer scenes directly, so the editor needs no game C# services.
Reference copies omit only C# hooks and editor UIDs; native VFX remain intact.
"""
from pathlib import Path
import json
import re
import shutil
import hashlib

HERE = Path(__file__).resolve().parent
MOD = HERE.parents[2]
VANILLA = MOD.parent / "STS2-V111"
PREVIEW = HERE / "preview_project"
SCENES = MOD / "scenes/backgrounds/hollow_grotto"
STAGED = set()


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def image_import(path):
    # Exact vanilla BPTC/straight-alpha settings, with a fresh resource UID
    # and the canonical Godot import-cache key for this new resource path.
    template = (VANILLA / "images/rooms/overgrowth/overgrowth_00.png.import").read_text()
    source_path = "res://" + path.relative_to(MOD).as_posix()
    cache_key = hashlib.md5(source_path.encode()).hexdigest()
    cache_path = f"res://.godot/imported/{path.name}-{cache_key}.bptc.ctex"
    template = re.sub(r'^uid=.*\n', '', template, flags=re.M)
    template = re.sub(r'res://\.godot/imported/[^"\n]+', cache_path, template)
    template = re.sub(r'^source_file=.*$', f'source_file="{source_path}"', template, flags=re.M)
    write(path.with_suffix(path.suffix + ".import"), template)


def stage(path, origin):
    if path in STAGED or path.endswith(".cs"):
        return
    STAGED.add(path)
    src = origin / path
    if not src.exists():
        src = VANILLA / path
    dst = PREVIEW / path
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix in [".tscn", ".tres", ".gd", ".gdshader"]:
        content = src.read_text(encoding="utf-8-sig")
        if src.suffix in [".tscn", ".tres"]:
            script_ids = re.findall(r'\[ext_resource[^\n]+path="[^"\n]+\.cs"[^\n]+id="([^"]+)"[^\n]*\]', content)
            content = re.sub(r'^\[ext_resource[^\n]+\.cs"[^\n]*\]\r?\n', '', content, flags=re.M)
            for sid in script_ids:
                content = re.sub(r'^script = ExtResource\("' + re.escape(sid) + r'"\)\r?\n', '', content, flags=re.M)
            content = re.sub(r' uid="[^"]+"', '', content)
            content = re.sub(r'^VisibleLayer = .+\n', '', content, flags=re.M)
            # Debug C# normally hides the accessibility alternative.
            content = re.sub(r'(\[node name="PhobiaModeVisual"[^\n]*\]\n)', r'\1visible = false\n', content)
        write(dst, content)
        for dep in set(re.findall(r'res://([^"\s]+)', content)):
            if (origin / dep).is_file() or (VANILLA / dep).is_file():
                stage(dep, origin)
    else:
        shutil.copy2(src, dst)
        if src.suffix == ".png" and src.with_suffix(".png.import").exists():
            shutil.copy2(src.with_suffix(".png.import"), dst.with_suffix(".png.import"))


FOG_RESOURCES = '''
[ext_resource type="Texture2D" path="res://images/vfx/fog_sheet_1.png" id="2_fog"]
[ext_resource type="Texture2D" path="res://images/vfx/light.png" id="3_light"]
[ext_resource type="Texture2D" path="res://images/vfx/dot.png" id="4_dot"]

[sub_resource type="CanvasItemMaterial" id="FogAdditive"]
blend_mode = 1
particles_animation = true
particles_anim_h_frames = 1
particles_anim_v_frames = 3
particles_anim_loop = false

[sub_resource type="CanvasItemMaterial" id="Additive"]
blend_mode = 1

[sub_resource type="Gradient" id="FogFade"]
offsets = PackedFloat32Array(0, 0.23, 0.81, 1)
colors = PackedColorArray(0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0)

[sub_resource type="Gradient" id="MoteFade"]
offsets = PackedFloat32Array(0, 0.3, 0.75, 1)
colors = PackedColorArray(1, 1, 1, 0, 1, 1, 1, 0.6, 1, 1, 1, 0.6, 1, 1, 1, 0)
'''

FOG_NODES = '''
[node name="CavernAmbientLight" type="Sprite2D" parent="."]
material = SubResource("Additive")
modulate = Color(0.09, 0.18, 0.19, 0.7)
position = Vector2(210, -180)
scale = Vector2(5.7, 3.8)
texture = ExtResource("3_light")

[node name="FloorMistLeft" type="CPUParticles2D" parent="."]
material = SubResource("FogAdditive")
position = Vector2(-1500, 100)
amount = 4
lifetime = 95.0
preprocess = 78.0
local_coords = true
texture = ExtResource("2_fog")
emission_shape = 3
emission_rect_extents = Vector2(10, 100)
direction = Vector2(1, 0)
spread = 2.0
gravity = Vector2(0.2, 0)
initial_velocity_min = 10.0
initial_velocity_max = 14.0
scale_amount_min = 0.38
scale_amount_max = 0.5
color = Color(0.12, 0.18, 0.22, 0.24)
color_ramp = SubResource("FogFade")
anim_offset_max = 1.0

[node name="FloorMistRight" type="CPUParticles2D" parent="."]
material = SubResource("FogAdditive")
position = Vector2(1500, 125)
amount = 3
lifetime = 105.0
preprocess = 80.0
local_coords = true
texture = ExtResource("2_fog")
emission_shape = 3
emission_rect_extents = Vector2(10, 80)
direction = Vector2(-1, 0)
spread = 2.0
gravity = Vector2(-0.17, 0)
initial_velocity_min = 8.0
initial_velocity_max = 12.0
scale_amount_min = 0.35
scale_amount_max = 0.55
color = Color(0.10, 0.16, 0.19, 0.22)
color_ramp = SubResource("FogFade")
anim_offset_max = 1.0

[node name="CaveMotes" type="CPUParticles2D" parent="."]
material = SubResource("Additive")
position = Vector2(0, -80)
amount = 16
lifetime = 22.0
preprocess = 15.0
local_coords = true
texture = ExtResource("4_dot")
emission_shape = 3
emission_rect_extents = Vector2(1080, 300)
direction = Vector2(0, -1)
spread = 60.0
gravity = Vector2(0, -0.35)
initial_velocity_min = 0.5
initial_velocity_max = 1.5
scale_amount_min = 0.009
scale_amount_max = 0.017
color = Color(0.3, 0.46, 0.5, 0.35)
color_ramp = SubResource("MoteFade")
'''


def build():
    SCENES.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, suffix in enumerate(["00", "01", "02", "03", "fg"]):
        key = "fg" if suffix == "fg" else "bg_" + suffix
        filename = f"hollow_grotto_{key}_a.tscn"
        texture = f"res://images/rooms/hollow_grotto/hollow_grotto_{suffix}.png"
        is_vfx = suffix == "01"
        resources = f'[ext_resource type="Texture2D" path="{texture}" id="1_art"]\n'
        if is_vfx:
            resources += FOG_RESOURCES
        content = f'[gd_scene load_steps={9 if is_vfx else 2} format=3]\n\n{resources}\n'
        content += f'''[node name="HollowGrotto{suffix.upper()}" type="Control"]
mouse_filter = 2

[node name="PaintedLayer" type="TextureRect" parent="."]
offset_left = -1382.4
offset_top = -648.0
offset_right = 1382.4
offset_bottom = 648.0
mouse_filter = 2
texture = ExtResource("1_art")
expand_mode = 1
metadata/plane = "{key}"
'''
        if is_vfx:
            content += FOG_NODES
        p = SCENES / "layers" / filename
        write(p, content)
        paths.append(str(p.relative_to(MOD)).replace("\\", "/"))
        image_import(MOD / texture.replace("res://", ""))

    root_text = '''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://src/Core/Nodes/Rooms/NCombatBackground.cs" id="1_native"]

[node name="HollowGrottoBackground" type="Control"]
layout_mode = 3
anchors_preset = 0
mouse_filter = 2
script = ExtResource("1_native")
'''
    for name in ["Layer_00", "Layer_01", "Layer_02", "Layer_03", "Foreground"]:
        root_text += f'''\n[node name="{name}" type="Control" parent="."]
unique_name_in_owner = true
anchors_preset = 0
mouse_filter = 2
'''
    write(SCENES / "hollow_grotto_background.tscn", root_text)
    stage("scenes/backgrounds/hollow_grotto/hollow_grotto_background.tscn", MOD)
    for path in paths:
        stage(path, MOD)

    specs = {"hollow_grotto": {"root": "scenes/backgrounds/hollow_grotto/hollow_grotto_background.tscn", "layers": paths}}
    for title, variants in {"underdocks": ["a", "a", "a", "b", "b", "b"], "overgrowth": ["a", "a", "a", "a", "a", "a"], "glory": ["a", "b", "a", "a", "a"]}.items():
        root = f"scenes/backgrounds/{title}/{title}_background.tscn"
        stage(root, VANILLA)
        layers = []
        for i, variant in enumerate(variants):
            suffix = "fg" if i == len(variants) - 1 else f"bg_{i:02}"
            path = f"scenes/backgrounds/{title}/layers/{title}_{suffix}_{variant}.tscn"
            stage(path, VANILLA)
            layers.append(path)
        specs[title] = {"root": root, "layers": layers}
    write(PREVIEW / "scene_specs.json", json.dumps(specs, indent=2))
    write(PREVIEW / "project.godot", '''
config_version=5

[application]
config/name="Hollow Grotto - STS2 Native Background Preview"
run/main_scene="res://preview.tscn"
config/features=PackedStringArray("4.5", "Mobile")

[display]
window/size/viewport_width=1920
window/size/viewport_height=1080
window/size/window_width_override=1280
window/size/window_height_override=720
window/stretch/mode="canvas_items"
window/stretch/aspect="expand"

[rendering]
renderer/rendering_method="mobile"
rendering_device/driver.windows="d3d12"
environment/defaults/default_clear_color=Color(0.0923724, 0.122398, 0.116929, 1)
''')
    write(PREVIEW / "preview.tscn", '''
[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://preview.gd" id="1"]

[node name="HollowGrottoPreview" type="Node"]
script = ExtResource("1")
''')
    shutil.copy2(HERE / "preview.gd", PREVIEW / "preview.gd")
    print("Native scenes:", SCENES)
    print("Preview project:", PREVIEW)


if __name__ == "__main__":
    build()
