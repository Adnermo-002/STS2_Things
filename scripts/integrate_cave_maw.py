"""Author scenes and bilingual entries for the solo/mixed Cave Maw encounters."""
from pathlib import Path
import json,shutil

ROOT=Path(__file__).resolve().parents[1]
(ROOT/'scenes/creature_visuals/cave_maw.tscn').write_text('''[gd_scene load_steps=3 format=3]
[ext_resource type="Script" path="res://STS2_Things/Visuals/NCaveMawVisuals.cs" id="1"]
[ext_resource type="SpineSkeletonDataResource" path="res://STS2_Things/animations/monsters/cave_maw/cave_maw_skel_data.tres" id="2"]
[node name="CaveMaw" type="Node2D"]
script = ExtResource("1")
[node name="Visuals" type="SpineSprite" parent="."]
unique_name_in_owner = true
skeleton_data_res = ExtResource("2")
preview_skin = "default"
preview_animation = "idle_loop"
preview_frame = false
scale = Vector2(0.245, 0.245)
[node name="MouthSocket" type="SpineBoneNode" parent="Visuals"]
bone_name = "mouth_vfx"
[node name="Bounds" type="Control" parent="."]
unique_name_in_owner = true
offset_left = -230.0
offset_top = -158.0
offset_right = 230.0
offset_bottom = 8.0
mouse_filter = 2
[node name="CenterPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(-8,-57)
[node name="IntentPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(0,-198)
''','utf-8')

for key,slots,variant in [
    ('cave_maw_weak',[('maw',(1435,824))],'d_cave_rootfungus'),
    ('cave_maw_encounter',[('maw',(1188,824)),('moth',(1495,744)),('leech',(1780,809))],'f_hollow_grotto_moss'),
]:
    scene='''[gd_scene format=3]
[node name="Encounter" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
mouse_filter = 2
'''
    for name,(x,y) in slots:
        scene+=f'[node name="{name}" type="Marker2D" parent="."]\nposition = Vector2({x},{y})\n'
    (ROOT/f'scenes/encounters/{key}.tscn').write_text(scene,'utf-8')
    folder=ROOT/f'scenes/backgrounds/{key}';(folder/'layers').mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'scenes/backgrounds/sponge_leech_weak/sponge_leech_weak_background.tscn',folder/f'{key}_background.tscn')
    shutil.copy2(ROOT/f'scenes/backgrounds/depths/layers/depths_bg_00_{variant}.tscn',folder/f'layers/{key}_bg_00_a.tscn')

zhs='投食后的回合，[gold]消耗[/gold]手牌和弃牌堆中的所有状态牌。每张获得[blue]{BlockPerCard}[/blue]点[gold]格挡[/gold]和[blue]1[/blue]点[gold]力量[/gold]（每次至多[blue]{StrengthCap}[/blue]点力量）。'
eng='On the turn after offering Debris, [gold]Exhaust[/gold] ALL Status cards in players\' Hands and Discard Piles. Gain [blue]{BlockPerCard}[/blue] [gold]Block[/gold] and [blue]1[/blue] [gold]Strength[/gold] per card (up to [blue]{StrengthCap}[/blue] Strength per meal).'
entries={
 'zhs':{
  'monsters':{'CAVE_MAW.name':'馋嘴洞胃','CAVE_MAW.moves.OFFER_MOVE.title':'投食','CAVE_MAW.moves.DEVOUR_MOVE.title':'吞食','CAVE_MAW.moves.BITE_MOVE.title':'啃咬','CAVE_MAW.moves.PRESS_MOVE.title':'挤压'},
  'powers':{'CAVE_MAW_APPETITE_POWER.title':'饕口','CAVE_MAW_APPETITE_POWER.description':zhs.replace('{BlockPerCard}','3').replace('{StrengthCap}','3'),'CAVE_MAW_APPETITE_POWER.smartDescription':zhs},
  'encounters':{'CAVE_MAW_WEAK.title':'馋嘴洞胃','CAVE_MAW_WEAK.loss':'{character}成了[gold]{encounter}[/gold]的盘中餐。','CAVE_MAW_ENCOUNTER.title':'洞胃与虫群','CAVE_MAW_ENCOUNTER.loss':'{character}没能逃出[gold]{encounter}[/gold]的围困。'}},
 'eng':{
  'monsters':{'CAVE_MAW.name':'Gluttonous Cave Maw','CAVE_MAW.moves.OFFER_MOVE.title':'Offering','CAVE_MAW.moves.DEVOUR_MOVE.title':'Devour','CAVE_MAW.moves.BITE_MOVE.title':'Nibble','CAVE_MAW.moves.PRESS_MOVE.title':'Squeeze'},
  'powers':{'CAVE_MAW_APPETITE_POWER.title':'Gluttony','CAVE_MAW_APPETITE_POWER.description':eng.replace('{BlockPerCard}','3').replace('{StrengthCap}','3'),'CAVE_MAW_APPETITE_POWER.smartDescription':eng},
  'encounters':{'CAVE_MAW_WEAK.title':'Gluttonous Cave Maw','CAVE_MAW_WEAK.loss':'{character} became a meal for the [gold]{encounter}[/gold].','CAVE_MAW_ENCOUNTER.title':'Maw and Brood','CAVE_MAW_ENCOUNTER.loss':'{character} was surrounded by the [gold]{encounter}[/gold].'}}}
for lang,tables in entries.items():
    for table,values in tables.items():
        path=ROOT/f'STS2_Things/localization/{lang}/{table}.json'
        data=json.loads(path.read_text('utf-8-sig'));data.update(values)
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
path=ROOT/'export_presets.cfg';text=path.read_text('utf-8')
if '/cave_maw/*.atlas' not in text:
    marker='include_filter="';i=text.index('"',text.index(marker)+len(marker))
    text=text[:i]+',STS2_Things/animations/monsters/cave_maw/*.atlas,STS2_Things/animations/monsters/cave_maw/*.spatlas,STS2_Things/animations/monsters/cave_maw/*.spjson,STS2_Things/animations/monsters/cave_maw/cave_maw.png'+text[i:]
    path.write_text(text,'utf-8')
print('Integrated Cave Maw: solo weak, maw/moth/leech strong, native card and power UI.')
