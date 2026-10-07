"""Package generated Spine data; deployment into the project is explicit."""
from pathlib import Path
import json
import shutil
import sys
from anims import EVENTS

HERE = Path(__file__).resolve().parent
KEY = 'lantern_fish'
DEST = HERE / 'pkg'
DEST.mkdir(exist_ok=True)
RES = f'res://STS2_Things/animations/monsters/{KEY}'
atlas = (HERE / 'out' / f'{KEY}.atlas').read_text()
shutil.copyfile(HERE / 'out' / f'{KEY}.png', DEST / f'{KEY}.png')
skeleton = json.loads((HERE / 'out' / f'{KEY}.json').read_text())
skeleton['events'] = {name: {} for events in EVENTS.values() for name, _ in events}
for animation, events in EVENTS.items():
    skeleton['animations'][animation]['events'] = [{'time': time, 'name': event} for event, time in events]
(DEST / f'{KEY}.spjson').write_text(json.dumps(skeleton, separators=(',', ':')), newline='\n')
(DEST / f'{KEY}.atlas').write_text(atlas, newline='\n')
(DEST / f'{KEY}.spatlas').write_text(json.dumps(dict(source_path=f'{RES}/{KEY}.atlas',
    atlas_data=atlas, normal_texture_prefix='n', specular_texture_prefix='s'), separators=(',', ':')), newline='\n')
(DEST / f'{KEY}_skel_data.tres').write_text(f'''[gd_resource type="SpineSkeletonDataResource" load_steps=3 format=3]

[ext_resource type="SpineAtlasResource" path="{RES}/{KEY}.spatlas" id="1_atlas"]
[ext_resource type="SpineSkeletonFileResource" path="{RES}/{KEY}.spjson" id="2_skeleton"]

[resource]
atlas_res = ExtResource("1_atlas")
skeleton_file_res = ExtResource("2_skeleton")
default_mix = 0.10
''', newline='\n')
if '--deploy' in sys.argv:
    target = HERE.parents[1] / 'STS2_Things/animations/monsters/lantern_fish'
    target.mkdir(parents=True, exist_ok=True)
    for file in DEST.iterdir():
        shutil.copyfile(file, target / file.name)
    print('Deployed', target)
else:
    print('Packaged', DEST)

