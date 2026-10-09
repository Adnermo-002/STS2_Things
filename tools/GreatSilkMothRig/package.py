from pathlib import Path
import json
import shutil
from anims import EVENTS
HERE=Path(__file__).resolve().parent
KEY='great_silk_moth'
RES=f'res://STS2_Things/animations/monsters/{KEY}'
TARGET=HERE.parents[1]/f'STS2_Things/animations/monsters/{KEY}'
TARGET.mkdir(parents=True,exist_ok=True)
atlas=(HERE/'out'/f'{KEY}.atlas').read_text()
data=json.loads((HERE/'out'/f'{KEY}.json').read_text())
data['events']={name:{} for values in EVENTS.values() for name,_ in values}
for name,events in EVENTS.items():data['animations'][name]['events']=[{'time':t,'name':e} for e,t in events]
(TARGET/f'{KEY}.spjson').write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
(TARGET/f'{KEY}.atlas').write_text(atlas,encoding='utf-8')
(TARGET/f'{KEY}.spatlas').write_text(json.dumps(dict(source_path=f'{RES}/{KEY}.atlas',atlas_data=atlas,normal_texture_prefix='n',specular_texture_prefix='s')),encoding='utf-8')
shutil.copyfile(HERE/'out'/f'{KEY}.png',TARGET/f'{KEY}.png')
mixes=[('idle_loop','attack',.055),('idle_loop','cast',.10),
       ('idle_loop','flutter',.06),('idle_loop','hurt',.025),
       ('attack','idle_loop',.14),('cast','idle_loop',.14),
       ('flutter','idle_loop',.14),('hurt','idle_loop',.11),
       ('hurt','hurt',.02),('hurt','die',.035)]
mix_resources='\n'.join(f'''[sub_resource type="SpineAnimationMix" id="Mix_{i}"]
from = "{source}"
to = "{target}"
mix = {duration}
''' for i,(source,target,duration) in enumerate(mixes))
mix_refs=', '.join(f'SubResource("Mix_{i}")' for i in range(len(mixes)))
(TARGET/f'{KEY}_skel_data.tres').write_text(f'''[gd_resource type="SpineSkeletonDataResource" load_steps={3+len(mixes)} format=3]
[ext_resource type="SpineAtlasResource" path="{RES}/{KEY}.spatlas" id="1_atlas"]
[ext_resource type="SpineSkeletonFileResource" path="{RES}/{KEY}.spjson" id="2_skeleton"]

{mix_resources}
[resource]
atlas_res = ExtResource("1_atlas")
skeleton_file_res = ExtResource("2_skeleton")
default_mix = 0.08
animation_mixes = [{mix_refs}]
''',encoding='utf-8')
print('Deployed great moth skeleton, atlas and animations.')
