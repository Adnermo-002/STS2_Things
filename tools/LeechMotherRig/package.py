"""Package and deploy the native Spine matriarch assets."""
from pathlib import Path
import json,shutil
from anims import EVENTS
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
KEY='leech_mother'
DEST=HERE/'pkg';DEST.mkdir(exist_ok=True)
RES=f'res://STS2_Things/animations/monsters/{KEY}'
atlas=(HERE/'out'/f'{KEY}.atlas').read_text()
shutil.copyfile(HERE/'out'/f'{KEY}.png',DEST/f'{KEY}.png')
skeleton=json.loads((HERE/'out'/f'{KEY}.json').read_text())
skeleton['events']={name:{} for events in EVENTS.values() for name,_ in events}
for clip,events in EVENTS.items():skeleton['animations'][clip]['events']=[{'time':t,'name':name} for name,t in events]
(DEST/f'{KEY}.spjson').write_text(json.dumps(skeleton,separators=(',',':')),encoding='utf-8')
(DEST/f'{KEY}.atlas').write_text(atlas,encoding='utf-8')
(DEST/f'{KEY}.spatlas').write_text(json.dumps({'source_path':f'{RES}/{KEY}.atlas','atlas_data':atlas,
    'normal_texture_prefix':'n','specular_texture_prefix':'s'},separators=(',',':')),encoding='utf-8')
(DEST/f'{KEY}_skel_data.tres').write_text(f'''[gd_resource type="SpineSkeletonDataResource" load_steps=3 format=3]
[ext_resource type="SpineAtlasResource" path="{RES}/{KEY}.spatlas" id="1_atlas"]
[ext_resource type="SpineSkeletonFileResource" path="{RES}/{KEY}.spjson" id="2_skeleton"]
[resource]
atlas_res = ExtResource("1_atlas")
skeleton_file_res = ExtResource("2_skeleton")
default_mix = 0.10
''',encoding='utf-8')
target=ROOT/'STS2_Things/animations/monsters'/KEY;target.mkdir(parents=True,exist_ok=True)
for source in DEST.iterdir():shutil.copyfile(source,target/source.name)
scene=ROOT/'scenes/creature_visuals/leech_mother.tscn'
scene.write_text(f'''[gd_scene load_steps=5 format=3]
[ext_resource type="Script" path="res://STS2_Things/Visuals/NThingsStaticCreatureVisuals.cs" id="1"]
[ext_resource type="SpineSkeletonDataResource" path="{RES}/{KEY}_skel_data.tres" id="2"]
[sub_resource type="Gradient" id="ContactGradient"]
offsets = PackedFloat32Array(0, 0.58, 1)
colors = PackedColorArray(0.04, 0.025, 0.02, 0.32, 0.04, 0.025, 0.02, 0.18, 0.04, 0.025, 0.02, 0)
[sub_resource type="GradientTexture2D" id="ContactShadow"]
gradient = SubResource("ContactGradient")
width = 256
height = 64
fill = 1
fill_from = Vector2(0.5, 0.5)
fill_to = Vector2(0.5, 1)
[node name="LeechMother" type="Node2D"]
script = ExtResource("1")
[node name="ContactShadow" type="Sprite2D" parent="."]
position = Vector2(-3, -1)
scale = Vector2(1.9, 0.5)
texture = SubResource("ContactShadow")
[node name="Visuals" type="SpineSprite" parent="."]
unique_name_in_owner = true
skeleton_data_res = ExtResource("2")
preview_skin = "default"
preview_animation = "sleep_loop"
preview_frame = false
scale = Vector2(0.34, 0.34)
[node name="Bounds" type="Control" parent="."]
unique_name_in_owner = true
offset_left = -345.0
offset_top = -297.0
offset_right = 177.0
offset_bottom = 0.0
mouse_filter = 2
[node name="CenterPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(-77, -156)
[node name="IntentPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(-75, -341)
[node name="SleepVfxPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(-223, -227)
''',encoding='utf-8')
print('Native Leech Mother skeleton and creature scene deployed.')
