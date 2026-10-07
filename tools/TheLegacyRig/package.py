import json, shutil, os
P='pkg'; os.makedirs(P,exist_ok=True)
RES='res://STS2_Things/animations/monsters/the_legacy'
shutil.copy('out/the_legacy.png',f'{P}/the_legacy.png')
atlas=open('out/the_legacy.atlas').read()
open(f'{P}/the_legacy.atlas','w',newline='\n').write(atlas)
json.dump({"source_path":f"{RES}/the_legacy.atlas","atlas_data":atlas,"normal_texture_prefix":"n","specular_texture_prefix":"s"},open(f'{P}/the_legacy.spatlas','w',newline='\n'),separators=(',',':'))
shutil.copy('out/the_legacy.json',f'{P}/the_legacy.spjson')
open(f'{P}/the_legacy_skel_data.tres','w',newline='\n').write(f'''[gd_resource type="SpineSkeletonDataResource" load_steps=3 format=3]

[ext_resource type="SpineAtlasResource" path="{RES}/the_legacy.spatlas" id="1_atlas"]
[ext_resource type="SpineSkeletonFileResource" path="{RES}/the_legacy.spjson" id="2_json"]

[resource]
atlas_res = ExtResource("1_atlas")
skeleton_file_res = ExtResource("2_json")
default_mix = 0.15
''')
