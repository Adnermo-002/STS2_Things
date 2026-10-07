"""Package the exported rig for Godot (spine-godot 4.2): atlas, png, spatlas, spjson, skel_data.tres."""
import json, shutil, os
K = 'bowlbug_progenitor'
P = 'pkg'; os.makedirs(P, exist_ok=True)
RES = f'res://STS2_Things/animations/monsters/{K}'
shutil.copy(f'out/{K}.png', f'{P}/{K}.png')
atlas = open(f'out/{K}.atlas').read()
open(f'{P}/{K}.atlas', 'w', newline='\n').write(atlas)
json.dump({"source_path": f"{RES}/{K}.atlas", "atlas_data": atlas,
           "normal_texture_prefix": "n", "specular_texture_prefix": "s"},
          open(f'{P}/{K}.spatlas', 'w', newline='\n'), separators=(',', ':'))
shutil.copy(f'out/{K}.json', f'{P}/{K}.spjson')
open(f'{P}/{K}_skel_data.tres', 'w', newline='\n').write(f'''[gd_resource type="SpineSkeletonDataResource" load_steps=3 format=3]

[ext_resource type="SpineAtlasResource" path="{RES}/{K}.spatlas" id="1_atlas"]
[ext_resource type="SpineSkeletonFileResource" path="{RES}/{K}.spjson" id="2_json"]

[resource]
atlas_res = ExtResource("1_atlas")
skeleton_file_res = ExtResource("2_json")
default_mix = 0.15
''')
print('packaged', sorted(os.listdir(P)))
