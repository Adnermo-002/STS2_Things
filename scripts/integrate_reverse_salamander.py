"""Create native encounter, creature, localization and export references."""
from pathlib import Path
import json,shutil
ROOT=Path(__file__).resolve().parents[1];key='reverse_salamander'
(ROOT/f'scenes/creature_visuals/{key}.tscn').write_text('''[gd_scene load_steps=5 format=3]
[ext_resource type="Script" path="res://STS2_Things/Visuals/NReverseSalamanderVisuals.cs" id="1"]
[ext_resource type="SpineSkeletonDataResource" path="res://STS2_Things/animations/monsters/reverse_salamander/reverse_salamander_skel_data.tres" id="2"]
[sub_resource type="Gradient" id="Gradient"]
offsets = PackedFloat32Array(0,0.55,1)
colors = PackedColorArray(0.025,0.055,0.06,0.32,0.025,0.055,0.06,0.13,0.025,0.055,0.06,0)
[sub_resource type="GradientTexture2D" id="Shadow"]
gradient = SubResource("Gradient")
width = 512
height = 64
fill = 1
fill_from = Vector2(0.5,0.5)
fill_to = Vector2(0.5,1)
[node name="ReverseSalamander" type="Node2D"]
script = ExtResource("1")
[node name="ContactShadow" type="Sprite2D" parent="."]
position = Vector2(-45,-6)
scale = Vector2(0.76,0.45)
texture = SubResource("Shadow")
[node name="Visuals" type="SpineSprite" parent="."]
unique_name_in_owner = true
skeleton_data_res = ExtResource("2")
preview_skin = "default"
preview_animation = "idle_loop"
preview_frame = false
scale = Vector2(0.36,0.36)
[node name="Bounds" type="Control" parent="."]
unique_name_in_owner = true
offset_left = -265.0
offset_top = -360.0
offset_right = 290.0
offset_bottom = 5.0
mouse_filter = 2
[node name="CenterPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(-54,-126)
[node name="IntentPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(-50,-414)
''','utf-8')
enc='reverse_salamander_elite';folder=ROOT/f'scenes/backgrounds/{enc}';(folder/'layers').mkdir(parents=True,exist_ok=True)
shutil.copy2(ROOT/'scenes/backgrounds/lantern_fish_encounter/lantern_fish_encounter_background.tscn',folder/f'{enc}_background.tscn')
shutil.copy2(ROOT/'scenes/backgrounds/depths/layers/depths_bg_00_b_cave_riverbend.tscn',folder/'layers'/f'{enc}_bg_00_a.tscn')
(ROOT/f'scenes/encounters/{enc}.tscn').write_text('''[gd_scene format=3]
[node name="Encounter" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
mouse_filter = 2
[node name="salamander" type="Marker2D" parent="."]
position = Vector2(1365,800)
''','utf-8')
desc_zhs="玩家回合开始抽牌后，返还其上回合最后一张可[gold]回流[/gold]的牌，本回合耗能少[blue]1[/blue]。\n每当玩家打出[gold]回流[/gold]牌时，获得[blue]{Amount}[/blue]点[gold]力量[/gold]。"
desc_eng="After players' opening draw, return their last eligible card from the previous turn with [gold]Reflux[/gold]. It costs [blue]1[/blue] less this turn.\nWhenever a player plays it, gain [blue]{Amount}[/blue] [gold]Strength[/gold]."
texts={
 'zhs':{'monsters':{'REVERSE_SALAMANDER.name':'逆流蝾螈','REVERSE_SALAMANDER.moves.UPSTREAM_MOVE.title':'逆潮','REVERSE_SALAMANDER.moves.TAIL_WAVE_MOVE.title':'尾浪','REVERSE_SALAMANDER.moves.BACKWASH_MOVE.title':'倒卷','REVERSE_SALAMANDER.moves.GATHER_MOVE.title':'蓄流'},
 'powers':{'REVERSE_CURRENT_POWER.title':'逆流','REVERSE_CURRENT_POWER.description':desc_zhs.replace('{Amount}','2'),'REVERSE_CURRENT_POWER.smartDescription':desc_zhs,"REVERSE_CURRENT_POWER.refluxTitle":"回流","REVERSE_CURRENT_POWER.refluxDescription":"可打出的非X费攻击或技能牌。带有[gold]消耗[/gold]、已消耗或已有卡牌附着的牌不会回流。"},
 'afflictions':{'UPSTREAM_RECALL.title':'回流','UPSTREAM_RECALL.extraCardText':'[gold]回流[/gold]','UPSTREAM_RECALL.description':'本回合耗能少[blue]1[/blue]。\n打出时，存活的逆流蝾螈获得[blue]{Amount}[/blue]点[gold]力量[/gold]。'},
 'encounters':{'REVERSE_SALAMANDER_ELITE.title':'逆流蝾螈','REVERSE_SALAMANDER_ELITE.loss':'{character}被[gold]{encounter}[/gold]卷回了深处……'}},
 'eng':{'monsters':{'REVERSE_SALAMANDER.name':'Reverse-Current Salamander','REVERSE_SALAMANDER.moves.UPSTREAM_MOVE.title':'Upstream','REVERSE_SALAMANDER.moves.TAIL_WAVE_MOVE.title':'Tail Wave','REVERSE_SALAMANDER.moves.BACKWASH_MOVE.title':'Backwash','REVERSE_SALAMANDER.moves.GATHER_MOVE.title':'Gathering Flow'},
 'powers':{'REVERSE_CURRENT_POWER.title':'Reverse Current','REVERSE_CURRENT_POWER.description':desc_eng.replace('{Amount}','2'),'REVERSE_CURRENT_POWER.smartDescription':desc_eng,"REVERSE_CURRENT_POWER.refluxTitle":"Reflux","REVERSE_CURRENT_POWER.refluxDescription":"Playable, non-X Attacks and Skills. Cards with [gold]Exhaust[/gold], cards in the Exhaust Pile, and already afflicted cards cannot return."},
 'afflictions':{'UPSTREAM_RECALL.title':'Reflux','UPSTREAM_RECALL.extraCardText':'[gold]Reflux[/gold]','UPSTREAM_RECALL.description':'Costs [blue]1[/blue] less this turn.\nWhen played, living Reverse-Current Salamanders gain [blue]{Amount}[/blue] [gold]Strength[/gold].'},
 'encounters':{'REVERSE_SALAMANDER_ELITE.title':'Reverse-Current Salamander','REVERSE_SALAMANDER_ELITE.loss':'{character} was swept back into the Depths by the [gold]{encounter}[/gold].'}}}
for lang,tables in texts.items():
 for table,entries in tables.items():
  path=ROOT/f'STS2_Things/localization/{lang}/{table}.json';s=path.read_text('utf-8-sig');current=json.loads(s);missing={k:v for k,v in entries.items() if k not in current}
  if missing:
   prefix=s[:s.rfind('}')].rstrip();prefix+=',' if not prefix.endswith('{') else ''
   path.write_text(prefix+'\n'+json.dumps(missing,ensure_ascii=False,indent=2)[2:-2]+'\n}\n','utf-8')
path=ROOT/'export_presets.cfg';s=path.read_text('utf-8')
if '/reverse_salamander/*.atlas' not in s:
 marker='include_filter="';i=s.index('"',s.index(marker)+len(marker));s=s[:i]+''.join(f',STS2_Things/animations/monsters/{key}/{p}' for p in ['*.atlas','*.spatlas','*.spjson',f'{key}.png'])+s[i:];path.write_text(s,'utf-8')
print('Integrated salamander native resources and bilingual descriptions.')
