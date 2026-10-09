from pathlib import Path
import json,shutil
import numpy as np
from PIL import Image,ImageOps,ImageFilter

ROOT=Path(__file__).resolve().parents[1]
icons=Image.open(ROOT/'output/imagegen/fleeting_echo/powers-white-v1.png').convert('RGBA')
for i,key in enumerate(['borrowed_shadow_power','fleeting_fade_power']):
    cut=icons.crop((i*icons.width//2,0,(i+1)*icons.width//2,icons.height))
    arr=np.array(cut);arr[...,3]=np.uint8(np.clip((arr[...,3].astype(float)-140)/100,0,1)*255)
    cut=Image.fromarray(arr);cut=cut.crop(cut.getbbox())
    cut=ImageOps.contain(cut,(230,230),Image.Resampling.LANCZOS)
    tile=Image.new('RGBA',(256,256));tile.alpha_composite(cut,((256-cut.width)//2,(256-cut.height)//2))
    tile.save(ROOT/f'images/powers/{key}.png')
    tile.resize((64,64),Image.Resampling.LANCZOS).save(ROOT/f'images/powers/{key}_packed.png')
    (ROOT/f'images/atlases/power_atlas.sprites/{key}.tres').write_text(f'''[gd_resource type="AtlasTexture" load_steps=2 format=3]
[ext_resource type="Texture2D" path="res://images/powers/{key}_packed.png" id="1"]
[resource]
atlas = ExtResource("1")
region = Rect2(0, 0, 64, 64)
''','utf-8')

(ROOT/'scenes/creature_visuals/fleeting_echo.tscn').write_text('''[gd_scene load_steps=5 format=3]
[ext_resource type="Script" path="res://STS2_Things/Visuals/NFleetingEchoVisuals.cs" id="1"]
[ext_resource type="SpineSkeletonDataResource" path="res://STS2_Things/animations/monsters/fleeting_echo/fleeting_echo_skel_data.tres" id="2"]
[ext_resource type="Shader" path="res://shaders/monsters/fleeting_echo.gdshader" id="3"]
[sub_resource type="ShaderMaterial" id="Fade"]
shader = ExtResource("3")
shader_parameter/erosion = 0.0
[node name="FleetingEcho" type="Node2D"]
script = ExtResource("1")
[node name="Visuals" type="SpineSprite" parent="."]
unique_name_in_owner = true
skeleton_data_res = ExtResource("2")
preview_skin = "default"
preview_animation = "idle_loop"
preview_frame = false
scale = Vector2(0.34, 0.34)
position = Vector2(0, -10)
material = SubResource("Fade")
[node name="Bounds" type="Control" parent="."]
unique_name_in_owner = true
offset_left = -232.0
offset_top = -340.0
offset_right = 232.0
offset_bottom = 8.0
mouse_filter = 2
[node name="CenterPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(-14,-165)
[node name="IntentPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(0,-368)
''','utf-8')
(ROOT/'scenes/encounters/fleeting_echo_weak.tscn').write_text('''[gd_scene format=3]
[node name="Encounter" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
mouse_filter = 2
[node name="echo" type="Marker2D" parent="."]
position = Vector2(1320,800)
''','utf-8')
dest=ROOT/'scenes/backgrounds/fleeting_echo_weak';(dest/'layers').mkdir(parents=True,exist_ok=True)
shutil.copy2(ROOT/'scenes/backgrounds/sponge_leech_weak/sponge_leech_weak_background.tscn',dest/'fleeting_echo_weak_background.tscn')
shutil.copy2(ROOT/'scenes/backgrounds/depths/layers/depths_bg_00_h_hollow_grotto_violet.tscn',dest/'layers/fleeting_echo_weak_bg_00_a.tscn')

entries={
'zhs':{
 'monsters':{'FLEETING_ECHO.name':'余影魔','FLEETING_ECHO.moves.REACH_MOVE.title':'探身','FLEETING_ECHO.moves.SWEEP_MOVE.title':'横扫','FLEETING_ECHO.moves.GRASP_MOVE.title':'攫取','FLEETING_ECHO.moves.PULSE_MOVE.title':'震荡','FLEETING_ECHO.moves.SCATTER_MOVE.title':'散形'},
 'powers':{'BORROWED_SHADOW_POWER.title':'借影','BORROWED_SHADOW_POWER.description':'受到攻击伤害时，攻击者获得等量[gold]格挡[/gold]。','FLEETING_FADE_POWER.title':'消逝','FLEETING_FADE_POWER.description':'[blue]{Amount}[/blue]回合后消失。','FLEETING_FADE_POWER.smartDescription':'[blue]{Amount}[/blue]回合后消失。'},
 'encounters':{'FLEETING_ECHO_WEAK.title':'余影魔','FLEETING_ECHO_WEAK.loss':'{character}消失在[gold]{encounter}[/gold]的影子里。'}},
'eng':{
 'monsters':{'FLEETING_ECHO.name':'Fleeting Echo','FLEETING_ECHO.moves.REACH_MOVE.title':'Reach','FLEETING_ECHO.moves.SWEEP_MOVE.title':'Sweep','FLEETING_ECHO.moves.GRASP_MOVE.title':'Grasp','FLEETING_ECHO.moves.PULSE_MOVE.title':'Pulse','FLEETING_ECHO.moves.SCATTER_MOVE.title':'Scatter'},
 'powers':{'BORROWED_SHADOW_POWER.title':'Borrowed Shadow','BORROWED_SHADOW_POWER.description':'When damaged by an attack, the attacker gains that much [gold]Block[/gold].','FLEETING_FADE_POWER.title':'Fading','FLEETING_FADE_POWER.description':'Disappears in [blue]{Amount}[/blue] turns.','FLEETING_FADE_POWER.smartDescription':'Disappears in [blue]{Amount}[/blue] turns.'},
 'encounters':{'FLEETING_ECHO_WEAK.title':'Fleeting Echo','FLEETING_ECHO_WEAK.loss':'{character} vanished into the shadow of the [gold]{encounter}[/gold].'}}}
for lang,tables in entries.items():
    for table,values in tables.items():
        path=ROOT/f'STS2_Things/localization/{lang}/{table}.json'
        data=json.loads(path.read_text('utf-8-sig'));data.update(values)
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
portrait=Image.open(ROOT/'source_assets/monsters/fleeting_echo/assembled.png').convert('RGBA')
portrait=ImageOps.contain(portrait.crop(portrait.getbbox()),(112,112),Image.Resampling.LANCZOS)
tile=Image.new('RGBA',(128,128));tile.alpha_composite(portrait,((128-portrait.width)//2,(128-portrait.height)//2))
tile.save(ROOT/'images/ui/run_history/fleeting_echo_weak.png')
outline=Image.new('RGBA',tile.size,(230,222,194,0));outline.putalpha(tile.getchannel('A').filter(ImageFilter.MaxFilter(5)))
outline.save(ROOT/'images/ui/run_history/fleeting_echo_weak_outline.png')
path=ROOT/'export_presets.cfg';text=path.read_text('utf-8')
if '/fleeting_echo/*.atlas' not in text:
    marker='include_filter="';i=text.index('"',text.index(marker)+len(marker))
    text=text[:i]+',STS2_Things/animations/monsters/fleeting_echo/*.atlas,STS2_Things/animations/monsters/fleeting_echo/*.spatlas,STS2_Things/animations/monsters/fleeting_echo/*.spjson,STS2_Things/animations/monsters/fleeting_echo/fleeting_echo.png'+text[i:]
    path.write_text(text,'utf-8')
print('Integrated Fleeting Echo: single weak encounter, two native powers, violet cave and run-history assets.')
