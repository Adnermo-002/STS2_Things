"""Native scenes, localizations, and export entries for the authored elite."""
from pathlib import Path
import json,shutil
ROOT=Path(__file__).resolve().parents[1]
for key,scale,top,center in [('mycorrhizal_vanguard',.38,-435,-185),('mycorrhizal_bulwark',.46,-345,-140)]:
 text=f'''[gd_scene load_steps=6 format=3]
[ext_resource type="Script" path="res://STS2_Things/Visuals/NMycorrhizalVisuals.cs" id="1"]
[ext_resource type="SpineSkeletonDataResource" path="res://STS2_Things/animations/monsters/{key}/{key}_skel_data.tres" id="2"]
[ext_resource type="Script" path="res://STS2_Things/Visuals/NMycorrhizalLink.cs" id="3"]
[sub_resource type="Gradient" id="Gradient"]
offsets = PackedFloat32Array(0, 0.55, 1)
colors = PackedColorArray(0.025, 0.04, 0.035, 0.30, 0.025, 0.04, 0.035, 0.13, 0.025, 0.04, 0.035, 0)
[sub_resource type="GradientTexture2D" id="Shadow"]
gradient = SubResource("Gradient")
width = 256
height = 64
fill = 1
fill_from = Vector2(0.5, 0.5)
fill_to = Vector2(0.5, 1)
[node name="MycorrhizalTwin" type="Node2D"]
script = ExtResource("1")
[node name="ContactShadow" type="Sprite2D" parent="."]
scale = Vector2(0.8, 0.32)
texture = SubResource("Shadow")
[node name="RootLink" type="Node2D" parent="."]
script = ExtResource("3")
[node name="Visuals" type="SpineSprite" parent="."]
unique_name_in_owner = true
skeleton_data_res = ExtResource("2")
preview_skin = "default"
preview_animation = "idle_loop"
preview_frame = false
scale = Vector2({scale},{scale})
[node name="RootSocket" type="SpineBoneNode" parent="Visuals"]
bone_name = "root_socket"
[node name="Bounds" type="Control" parent="."]
unique_name_in_owner = true
offset_left = -245.0
offset_top = {top+30}.0
offset_right = 195.0
offset_bottom = 3.0
mouse_filter = 2
[node name="CenterPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(-20,{center})
[node name="IntentPos" type="Marker2D" parent="."]
unique_name_in_owner = true
position = Vector2(-12,{top})
'''
 (ROOT/f'scenes/creature_visuals/{key}.tscn').write_text(text,'utf-8')
key='mycorrhizal_twins_elite';folder=ROOT/f'scenes/backgrounds/{key}';(folder/'layers').mkdir(parents=True,exist_ok=True)
shutil.copy2(ROOT/'scenes/backgrounds/sponge_leech_encounter/sponge_leech_encounter_background.tscn',folder/f'{key}_background.tscn')
shutil.copy2(ROOT/'scenes/backgrounds/depths/layers/depths_bg_00_f_hollow_grotto_moss.tscn',folder/'layers'/f'{key}_bg_00_a.tscn')
(ROOT/f'scenes/encounters/{key}.tscn').write_text('''[gd_scene format=3]
[node name="Encounter" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
mouse_filter = 2
[node name="vanguard" type="Marker2D" parent="."]
position = Vector2(1210,775)
[node name="bulwark" type="Marker2D" parent="."]
position = Vector2(1610,740)
''','utf-8')
data={
 'zhs':{
 'monsters':{'MYCORRHIZAL_VANGUARD.name':'菌根长兄','MYCORRHIZAL_BULWARK.name':'菌根幼弟'},
 'encounters':{'MYCORRHIZAL_TWINS_ELITE.title':'菌根双生子','MYCORRHIZAL_TWINS_ELITE.loss':'{character}成了[gold]{encounter}[/gold]的养料……'},
 'powers':{'MYCORRHIZAL_BOND_POWER.title':'同根',
 'MYCORRHIZAL_BOND_POWER.description':'每轮结束时，与同伴交换当前生命值。交换后，生命较高的一方变为[gold]丰盛[/gold]，另一方变为[gold]萎蔫[/gold]。生命相等时互换体态。\n同伴死亡时，获得[blue]4[/blue]点[gold]力量[/gold]并进入[gold]狂暴[/gold]。',
 'MYCORRHIZAL_FURY_POWER.title':'断根狂暴',
 'MYCORRHIZAL_FURY_POWER.description':'已因同伴死亡获得[blue]4[/blue]点[gold]力量[/gold]。保持[gold]丰盛[/gold]，造成的攻击伤害提高[blue]25%[/blue]，并使用狂暴招式。'},
 },
 'eng':{
 'monsters':{'MYCORRHIZAL_VANGUARD.name':'Rootbound Elder','MYCORRHIZAL_BULWARK.name':'Rootbound Younger'},
 'encounters':{'MYCORRHIZAL_TWINS_ELITE.title':'Mycorrhizal Twins','MYCORRHIZAL_TWINS_ELITE.loss':'{character} became nourishment for the [gold]{encounter}[/gold].'},
 'powers':{'MYCORRHIZAL_BOND_POWER.title':'Shared Roots',
 'MYCORRHIZAL_BOND_POWER.description':'At the end of each round, swap current HP with its twin. The twin with more HP becomes [gold]Robust[/gold] and the other becomes [gold]Withered[/gold]. Equal HP swaps their forms.\nWhen its twin dies, gain [blue]4[/blue] [gold]Strength[/gold] and become [gold]Enraged[/gold].',
 'MYCORRHIZAL_FURY_POWER.title':'Severed Fury',
 'MYCORRHIZAL_FURY_POWER.description':'Gained [blue]4[/blue] [gold]Strength[/gold] when its twin died. Remains [gold]Robust[/gold], dealing [blue]25%[/blue] more attack damage, and uses enraged moves.'},
 }}
moves={'MYCORRHIZAL_VANGUARD':{'LASH_MOVE':('根鞭','Root Lash'),'DOUBLE_MOVE':('双抽','Twin Lash'),'WAR_SPORES_MOVE':('战孢','War Spores'),'FURY_LASH_MOVE':('狂鞭','Furious Lash'),'RAGE_SPORES_MOVE':('怒孢','Rage Spores')},
 'MYCORRHIZAL_BULWARK':{'SHELTER_MOVE':('护根','Root Shelter'),'ARMOR_MOVE':('菌甲','Fungal Plating'),'BASH_MOVE':('菌帽顶撞','Cap Bash'),'RAMPART_MOVE':('壁垒冲撞','Rampart Bash'),'FORTIFY_MOVE':('固守','Fortify')}}
for lang,tables in data.items():
 for monster,entries in moves.items():
  for move,titles in entries.items():tables['monsters'][f'{monster}.moves.{move}.title']=titles[0 if lang=='zhs' else 1]
 base=tables['powers']['MYCORRHIZAL_BOND_POWER.description']
 if lang=='zhs':
  states={'robust':'[gold]丰盛[/gold]：攻击伤害提高[blue]25%[/blue]，提供的格挡提高[blue]25%[/blue]。战孢给予[blue]3[/blue]点力量，菌甲给予[blue]4[/blue]层覆甲。',
  'withered':'[gold]萎蔫[/gold]：攻击伤害降低[blue]25%[/blue]，提供的格挡降低[blue]25%[/blue]。战孢给予[blue]1[/blue]点力量，菌甲给予[blue]2[/blue]层覆甲。'}
 else:
  states={'robust':'[gold]Robust[/gold]: Deal [blue]25%[/blue] more attack damage and grant [blue]25%[/blue] more Block. War Spores grants [blue]3[/blue] Strength; Fungal Plating grants [blue]4[/blue] Plating.',
  'withered':'[gold]Withered[/gold]: Deal [blue]25%[/blue] less attack damage and grant [blue]25%[/blue] less Block. War Spores grants [blue]1[/blue] Strength; Fungal Plating grants [blue]2[/blue] Plating.'}
 for state,desc in states.items():tables['powers'][f'MYCORRHIZAL_BOND_POWER.{state}Description']=desc+'\n'+base
 for table,entries in tables.items():
  path=ROOT/f'STS2_Things/localization/{lang}/{table}.json';s=path.read_text('utf-8-sig');current=json.loads(s)
  missing={k:v for k,v in entries.items() if k not in current}
  if missing:
   prefix=s[:s.rfind('}')].rstrip();prefix+=',' if not prefix.endswith('{') else ''
   path.write_text(prefix+'\n'+json.dumps(missing,ensure_ascii=False,indent=2)[2:-2]+'\n}\n','utf-8')
path=ROOT/'export_presets.cfg';s=path.read_text('utf-8')
for key in ['mycorrhizal_vanguard','mycorrhizal_bulwark']:
 if f'/{key}/*.atlas' not in s:
  marker='include_filter="';i=s.index('"',s.index(marker)+len(marker))
  s=s[:i]+''.join(f',STS2_Things/animations/monsters/{key}/{pattern}' for pattern in ['*.atlas','*.spatlas','*.spjson',f'{key}.png'])+s[i:]
path.write_text(s,'utf-8')
print('Integrated native scenes, bilingual text and PCK exports.')
