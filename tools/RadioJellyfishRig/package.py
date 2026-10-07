"""Package native Spine 4.2 files without launching the game."""
from pathlib import Path
import json,shutil
from anims import EVENTS

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
KEY='radio_jellyfish';RES=f'res://STS2_Things/animations/monsters/{KEY}'
dest=ROOT/'STS2_Things/animations/monsters'/KEY;dest.mkdir(parents=True,exist_ok=True)
data=json.loads((HERE/'out'/f'{KEY}.json').read_text('utf-8'))
data['events']={n:{} for events in EVENTS.values() for n,_ in events}
for key,events in EVENTS.items():data['animations'][key]['events']=[dict(name=n,time=t) for n,t in events]
(dest/f'{KEY}.spjson').write_text(json.dumps(data,separators=(',',':')),'utf-8')
atlas=(HERE/'out'/f'{KEY}.atlas').read_text('utf-8')
(dest/f'{KEY}.atlas').write_text(atlas,'utf-8');shutil.copy2(HERE/'out'/f'{KEY}.png',dest/f'{KEY}.png')
(dest/f'{KEY}.spatlas').write_text(json.dumps(dict(source_path=f'{RES}/{KEY}.atlas',atlas_data=atlas,normal_texture_prefix='n',specular_texture_prefix='s')),'utf-8')
(dest/f'{KEY}_skel_data.tres').write_text(f'''[gd_resource type="SpineSkeletonDataResource" load_steps=3 format=3]
[ext_resource type="SpineAtlasResource" path="{RES}/{KEY}.spatlas" id="1"]
[ext_resource type="SpineSkeletonFileResource" path="{RES}/{KEY}.spjson" id="2"]
[resource]
atlas_res = ExtResource("1")
skeleton_file_res = ExtResource("2")
default_mix = 0.14
''','utf-8')
print('Packaged',KEY,'bones',len(data['bones']),'layers',len(data['slots']),'animations',len(data['animations']))
