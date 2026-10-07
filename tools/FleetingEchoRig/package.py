from pathlib import Path
import json,shutil
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];key='fleeting_echo'
dest=ROOT/'STS2_Things/animations/monsters'/key;dest.mkdir(parents=True,exist_ok=True)
data=json.loads((HERE/'out'/f'{key}.json').read_text('utf-8'))
contacts={'attack':.52,'sweep':.58,'grasp':.62,'pulse':.64,'scatter':.70}
data['events']={'contact':{},'dissolve':{}}
for clip,t in contacts.items():data['animations'][clip]['events']=[{'time':t,'name':'contact'}]
data['animations']['die']['events']=[{'time':1.1,'name':'dissolve'}]
(dest/f'{key}.spjson').write_text(json.dumps(data,separators=(',',':')),'utf-8')
atlas=(HERE/'out'/f'{key}.atlas').read_text('utf-8');(dest/f'{key}.atlas').write_text(atlas,'utf-8')
shutil.copy2(HERE/'out'/f'{key}.png',dest/f'{key}.png')
res=f'res://STS2_Things/animations/monsters/{key}'
(dest/f'{key}.spatlas').write_text(json.dumps({'source_path':f'{res}/{key}.atlas','atlas_data':atlas,'normal_texture_prefix':'n','specular_texture_prefix':'s'}),'utf-8')
(dest/f'{key}_skel_data.tres').write_text(f'''[gd_resource type="SpineSkeletonDataResource" load_steps=3 format=3]
[ext_resource type="SpineAtlasResource" path="{res}/{key}.spatlas" id="1"]
[ext_resource type="SpineSkeletonFileResource" path="{res}/{key}.spjson" id="2"]
[resource]
atlas_res = ExtResource("1")
skeleton_file_res = ExtResource("2")
default_mix = 0.14
''','utf-8')
print('Packaged',len(data['bones']),'bones',len(data['slots']),'weighted layers',len(data['animations']),'animations')
