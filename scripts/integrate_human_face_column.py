"""Wire the column's native scenes, two encounter pools and bilingual text."""
from pathlib import Path
import json
import shutil
from PIL import Image, ImageFilter

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'source_assets/monsters/human_face_column'
RES='res://STS2_Things/animations/monsters/human_face_column'
scene=f'''[gd_scene load_steps=5 format=3]
[ext_resource type="Script" path="res://STS2_Things/Visuals/NHumanFaceColumnVisuals.cs" id="1"]
[ext_resource type="SpineSkeletonDataResource" path="{RES}/human_face_column_skel_data.tres" id="2"]
[sub_resource type="Gradient" id="ShadowGradient"]
offsets = PackedFloat32Array(0, 0.5, 1)
colors = PackedColorArray(0.02,0.03,0.04,0.4, 0.02,0.03,0.04,0.15, 0.02,0.03,0.04,0)
[sub_resource type="GradientTexture2D" id="Shadow"]
gradient = SubResource("ShadowGradient")
width = 512
height = 64
fill = 1
fill_from = Vector2(0.5,0.5)
fill_to = Vector2(0.5,1)
[node name="human_face_column" type="Node2D"]
script = ExtResource("1")
[node name="ContactShadow" type="Sprite2D" parent="."]
position = Vector2(0, 2)
scale = Vector2(0.82,0.30)
texture = SubResource("Shadow")
[node name="Visuals" type="SpineSprite" parent="."]
unique_name_in_owner = true
skeleton_data_res = ExtResource("2")
preview_skin = "default"
preview_animation = "idle_loop"
preview_frame = false
scale = Vector2(0.41,1.04)
[node name="Bounds" type="Control" parent="."]
unique_name_in_owner = true
offset_left = -210.0
offset_top = -190.0
offset_right = 210.0
offset_bottom = 4.0
mouse_filter = 2
[node name="CenterPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(0,-95)
[node name="IntentPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(-334,-150)
'''
(ROOT/'scenes/creature_visuals/human_face_column.tscn').write_text(scene,'utf-8')
for name,x,with_companion in [('human_face_column_weak',1460,False),('human_face_column_encounter',1300,True)]:
    layout='''[gd_scene format=3]
[node name="Encounter" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
mouse_filter = 2
'''
    for level,key in [(2,'top'),(1,'middle'),(0,'bottom')]:
        layout+=f'[node name="column_{key}" type="Marker2D" parent="."]\nposition = Vector2({x},{830-level*190})\n'
    if with_companion:
        for companion,y in [('rock',842),('crystal',842),('leech',842),('fish',865),('moth',842),('sponge',842)]:
            layout+=f'[node name="{companion}" type="Marker2D" parent="."]\nposition = Vector2(1740,{y})\n'
    (ROOT/f'scenes/encounters/{name}.tscn').write_text(layout,'utf-8')
    background=ROOT/f'scenes/backgrounds/{name}'
    (background/'layers').mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'scenes/backgrounds/snail_trio_weak/snail_trio_weak_background.tscn',background/f'{name}_background.tscn')
    shutil.copy2(ROOT/'scenes/backgrounds/depths/layers/depths_bg_00_c_cave_quartz.tscn',background/f'layers/{name}_bg_00_a.tscn')
    icon=Image.open(ROOT/'images/powers/human_face_column_power.png').convert('RGBA')
    icon.save(ROOT/f'images/ui/run_history/{name}.png')
    outline=Image.new('RGBA',icon.size,'white')
    outline.putalpha(icon.getchannel('A').filter(ImageFilter.MaxFilter(7)))
    outline.save(ROOT/f'images/ui/run_history/{name}_outline.png')

text={
 'zhs':{
  'monsters':{'HUMAN_FACE_COLUMN.name':'人面柱',
   'HUMAN_FACE_COLUMN.moves.KNOCK_MOVE.title':'磕碰',
   'HUMAN_FACE_COLUMN.moves.REBUKE_MOVE.title':'呵斥',
   'HUMAN_FACE_COLUMN.moves.SEAL_MOVE.title':'合缝',
   'HUMAN_FACE_COLUMN.moves.RATTLE_MOVE.title':'震击'},
  'powers':{'HUMAN_FACE_COLUMN_POWER.title':'叠柱',
   'HUMAN_FACE_COLUMN_POWER.description':'共[blue]6[/blue]层，同时显露[blue]3[/blue]层。\n上层免疫伤害，中层受到的伤害降低[blue]50%[/blue]。\n击碎底层后，原中层[gold]眩晕[/gold]一回合。',
   'HUMAN_FACE_COLUMN_POWER.topDescription':'剩余[blue]{Amount}[/blue]层。\n免疫伤害。\n击碎底层后，原中层[gold]眩晕[/gold]一回合。',
   'HUMAN_FACE_COLUMN_POWER.middleDescription':'剩余[blue]{Amount}[/blue]层。\n受到的伤害降低[blue]50%[/blue]。\n击碎底层后，原中层[gold]眩晕[/gold]一回合。',
   'HUMAN_FACE_COLUMN_POWER.bottomDescription':'剩余[blue]{Amount}[/blue]层。\n击碎底层后，原中层[gold]眩晕[/gold]一回合。'},
  'encounters':{'HUMAN_FACE_COLUMN_WEAK.title':'人面柱',
   'HUMAN_FACE_COLUMN_WEAK.loss':'{character}被[gold]{encounter}[/gold]压垮了。',
   'HUMAN_FACE_COLUMN_ENCOUNTER.title':'柱下住客',
   'HUMAN_FACE_COLUMN_ENCOUNTER.loss':'{character}没能躲过[gold]{encounter}[/gold]。'}},
 'eng':{
  'monsters':{'HUMAN_FACE_COLUMN.name':'Human-Faced Column',
   'HUMAN_FACE_COLUMN.moves.KNOCK_MOVE.title':'Knock',
   'HUMAN_FACE_COLUMN.moves.REBUKE_MOVE.title':'Rebuke',
   'HUMAN_FACE_COLUMN.moves.SEAL_MOVE.title':'Seal',
   'HUMAN_FACE_COLUMN.moves.RATTLE_MOVE.title':'Rattle'},
  'powers':{'HUMAN_FACE_COLUMN_POWER.title':'Stacked',
   'HUMAN_FACE_COLUMN_POWER.description':'[blue]6[/blue] layers; [blue]3[/blue] exposed at a time.\nThe top takes no damage. The middle takes [blue]50%[/blue] less damage.\nBreaking the bottom layer [gold]Stuns[/gold] the former middle layer for a turn.',
   'HUMAN_FACE_COLUMN_POWER.topDescription':'[blue]{Amount}[/blue] layers remain.\nTakes no damage.\nBreaking the bottom layer [gold]Stuns[/gold] the former middle layer for a turn.',
   'HUMAN_FACE_COLUMN_POWER.middleDescription':'[blue]{Amount}[/blue] layers remain.\nTakes [blue]50%[/blue] less damage.\nBreaking the bottom layer [gold]Stuns[/gold] the former middle layer for a turn.',
   'HUMAN_FACE_COLUMN_POWER.bottomDescription':'[blue]{Amount}[/blue] layers remain.\nBreaking the bottom layer [gold]Stuns[/gold] the former middle layer for a turn.'},
  'encounters':{'HUMAN_FACE_COLUMN_WEAK.title':'Human-Faced Column',
   'HUMAN_FACE_COLUMN_WEAK.loss':'{character} was crushed beneath the [gold]{encounter}[/gold].',
   'HUMAN_FACE_COLUMN_ENCOUNTER.title':'Column Dwellers',
   'HUMAN_FACE_COLUMN_ENCOUNTER.loss':'{character} could not get past the [gold]{encounter}[/gold].'}}}
(SOURCE/'localization.json').write_text(json.dumps(text,ensure_ascii=False,indent=2)+'\n','utf-8')
for lang,tables in text.items():
    for table,entries in tables.items():
        path=ROOT/f'STS2_Things/localization/{lang}/{table}.json'
        current=json.loads(path.read_text('utf-8-sig'));current.update(entries)
        path.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n','utf-8')
path=ROOT/'export_presets.cfg';data=path.read_text('utf-8')
if '/human_face_column/*.spjson' not in data:
    i=data.index('"',data.index('include_filter="')+len('include_filter="'))
    extra=','.join(f'STS2_Things/animations/monsters/human_face_column/*.{extension}' for extension in ('atlas','spatlas','spjson','png'))
    data=data[:i]+','+extra+data[i:]
    path.write_text(data,'utf-8')
print('Integrated column scenes, native power icon, two encounters and both languages.')
