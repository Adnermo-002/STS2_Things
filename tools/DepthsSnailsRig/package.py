"""Export native Spine 4.2 bodies and a shell that follows a SpineBoneNode."""
import json,shutil,sys,os
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
name=sys.argv[1];os.chdir(HERE/name);sys.path.insert(0,str(HERE/name))
from snail_rig import C,META
from snail_anims import EVENTS
dest=ROOT/'STS2_Things/animations/monsters'/name;dest.mkdir(parents=True,exist_ok=True)
res=f'res://STS2_Things/animations/monsters/{name}'
data=json.loads(Path(f'out/{name}.json').read_text('utf-8'))
data['events']={n:{} for entries in EVENTS.values() for n,_ in entries}
for clip,entries in EVENTS.items():data['animations'][clip]['events']=[dict(name=n,time=t) for n,t in entries]
if 'shell' in META:
    data['slots']=[slot for slot in data['slots'] if slot['name']!='shell']
    for skin in data['skins']:skin['attachments'].pop('shell',None)
    for anim in data['animations'].values():anim.get('slots',{}).pop('shell',None)
    shutil.copy2('parts/shell.png',dest/'shell.png')
    m=META['shell'];center=(m['x']+m['w']/2,m['y']+m['h']/2)
    (dest/'shell-offset.json').write_text(json.dumps(dict(x=center[0]-C['shell'][0],y=center[1]-C['shell'][1])),'utf-8')
(dest/f'{name}.spjson').write_text(json.dumps(data,separators=(',',':')),'utf-8')
atlas=Path(f'out/{name}.atlas').read_text('utf-8')
(dest/f'{name}.atlas').write_text(atlas,'utf-8')
shutil.copy2(f'out/{name}.png',dest/f'{name}.png')
(dest/f'{name}.spatlas').write_text(json.dumps(dict(source_path=f'{res}/{name}.atlas',atlas_data=atlas,normal_texture_prefix='n',specular_texture_prefix='s')),'utf-8')
(dest/f'{name}_skel_data.tres').write_text(f'''[gd_resource type="SpineSkeletonDataResource" load_steps=3 format=3]
[ext_resource type="SpineAtlasResource" path="{res}/{name}.spatlas" id="1"]
[ext_resource type="SpineSkeletonFileResource" path="{res}/{name}.spjson" id="2"]
[resource]
atlas_res = ExtResource("1")
skeleton_file_res = ExtResource("2")
default_mix = 0.14
''','utf-8')
print('Packaged',name,len(data['bones']),'bones',len(data['animations']),'clips',flush=True)
