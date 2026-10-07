"""Build both native Spine rigs using the established project mesh/runtime toolkit."""
from pathlib import Path
import json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
for key in ['mycorrhizal_vanguard','mycorrhizal_bulwark']:
 folder=HERE/key
 for file in ['rigkit.py','rigutil.py']:shutil.copy2(ROOT/'tools/SilkMothRig'/file,folder/file)
 shutil.copy2(HERE/'rigdef_shared.py',folder/'rigdef.py');shutil.copy2(HERE/'anims_shared.py',folder/'anims.py')
 for command in ['build','export']:subprocess.run([sys.executable,'-m','rigkit',command],cwd=folder,check=True)
 sys.path.insert(0,str(folder));import importlib
 if 'anims' in sys.modules:del sys.modules['anims']
 anims=importlib.import_module('anims');events=anims.EVENTS
 data=json.loads((folder/'out'/f'{key}.json').read_text())
 data['events']={n:{} for ev in events.values() for n,_ in ev}
 for name,ev in events.items():data['animations'][name]['events']=[{'name':n,'time':t} for n,t in ev]
 # The form layer must key ONLY its own bone: it may not override track 0.
 for name in ['robust','withered']:
  data['animations'][name]={'bones':{'cap_posture':data['animations'][name]['bones']['cap_posture']}}
 dest=ROOT/'STS2_Things/animations/monsters'/key;dest.mkdir(parents=True,exist_ok=True)
 res=f'res://STS2_Things/animations/monsters/{key}'
 atlas=(folder/'out'/f'{key}.atlas').read_text()
 (dest/f'{key}.spjson').write_text(json.dumps(data,separators=(',',':')),'utf-8')
 (dest/f'{key}.atlas').write_text(atlas,'utf-8')
 (dest/f'{key}.spatlas').write_text(json.dumps(dict(source_path=f'{res}/{key}.atlas',atlas_data=atlas,normal_texture_prefix='n',specular_texture_prefix='s')),'utf-8')
 shutil.copy2(folder/'out'/f'{key}.png',dest/f'{key}.png')
 (dest/f'{key}_skel_data.tres').write_text(f'''[gd_resource type="SpineSkeletonDataResource" load_steps=3 format=3]
[ext_resource type="SpineAtlasResource" path="{res}/{key}.spatlas" id="1"]
[ext_resource type="SpineSkeletonFileResource" path="{res}/{key}.spjson" id="2"]
[resource]
atlas_res = ExtResource("1")
skeleton_file_res = ExtResource("2")
default_mix = 0.14
''','utf-8')
 print('Deployed',key)
