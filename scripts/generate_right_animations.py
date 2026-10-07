import json
import copy
import os
from pathlib import Path
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[1]

@lru_cache(maxsize=1)
def right_grab_rotations():
    # Captured by the real Spine solver at 60 Hz. Left/right forearms have
    # different setup lengths, so negating FK angles is not a valid mirror.
    path = ROOT / 'source_assets/monsters/cave_god_motion/right_grab_bake.json'
    return json.loads(path.read_text(encoding='utf-8'))

def normalize_angle(a):
    return (a + 180.0) % 360.0 - 180.0

def mirror_animation(data, source_anim_name):
    bones_def = {b['name']: b for b in data['bones']}
    src_anim = data['animations'][source_anim_name]
    target_anim = copy.deepcopy(src_anim)
    
    # 1. Bone mapping
    pair_map = {
        'arm1_IK': 'arm2_IK', 'arm2_IK': 'arm1_IK',
        'shoulder1': 'shoulder2', 'shoulder2': 'shoulder1',
        'arm1_1': 'arm2_1', 'arm2_1': 'arm1_1',
        'arm1_2': 'arm2_2', 'arm2_2': 'arm1_2',
        'arm1_2_side': 'arm2_2_side', 'arm2_2_side': 'arm1_2_side',
        'arm1_3': 'arm2_3', 'arm2_3': 'arm1_3',
        'fist1': 'fist2', 'fist2': 'fist1',
        'horn1': 'horn2', 'horn2': 'horn1',
    }
    
    new_bones = {}
    src_bones = src_anim.get('bones', {})
    
    for bone_name, channels in src_bones.items():
        dst_bone_name = pair_map.get(bone_name, bone_name)
        new_channels = copy.deepcopy(channels)
        
        # Mirror rotate
        if 'rotate' in new_channels:
            if bone_name in pair_map:
                rot_src = bones_def[bone_name].get('rotation', 0.0)
                rot_dst = bones_def[dst_bone_name].get('rotation', 0.0)
                for k in new_channels['rotate']:
                    abs_angle = rot_src + k['value']
                    k['value'] = normalize_angle(-abs_angle - rot_dst)
            else:
                for k in new_channels['rotate']:
                    k['value'] = normalize_angle(-k['value'])
                    
        # Mirror translate
        if 'translate' in new_channels:
            if bone_name in ('arm1_IK', 'arm2_IK'):
                # Global IK translation
                for k in new_channels['translate']:
                    old_setup = bones_def[bone_name]
                    new_setup = bones_def[dst_bone_name]
                    wx = old_setup['x'] + k.get('x', 0.0)
                    wy = old_setup['y'] + k.get('y', 0.0)
                    m_wx = -wx
                    m_wy = wy
                    k['x'] = m_wx - new_setup['x']
                    k['y'] = m_wy - new_setup['y']
            elif bone_name in ('shoulder1', 'shoulder2'):
                # Shoulder translation: lateral axis Y is negated
                for k in new_channels['translate']:
                    if 'y' in k:
                        k['y'] = -k['y']
            elif bone_name in ('arm1_1', 'arm2_1', 'arm1_2', 'arm2_2', 'arm1_3', 'arm2_3'):
                # FK arm bones: local translate x=0, y=0
                pass
            elif bone_name in ('root', 'tail_IK', 'impact_center', 'player_grab'):
                # Root coordinates: x is negated, y is preserved
                for k in new_channels['translate']:
                    if 'x' in k:
                        k['x'] = -k['x']
            else:
                # Vertical torso bones (body1, body2, body3, head, beard):
                # Bone axis is UP (X), lateral axis is LEFT (Y).
                # Lateral displacement Y is negated, X is preserved.
                for k in new_channels['translate']:
                    if 'y' in k:
                        k['y'] = -k['y']
                        
        # Mirror shear
        if 'shear' in new_channels:
            for k in new_channels['shear']:
                if 'x' in k: k['x'] = -k['x']
                if 'y' in k: k['y'] = -k['y']
                
        new_bones[dst_bone_name] = new_channels
        
    target_anim['bones'] = new_bones
    
    # 2. IK mapping
    # In cave_god rig:
    # IK constraint arm1_IK controls arm2 (right arm)
    # IK constraint arm2_IK controls arm1 (left arm)
    if 'ik' in src_anim:
        new_ik = {}
        for ik_name, keys in src_anim['ik'].items():
            dst_ik = 'arm2_IK' if ik_name == 'arm1_IK' else ('arm1_IK' if ik_name == 'arm2_IK' else ik_name)
            new_keys = copy.deepcopy(keys)
            for k in new_keys:
                if 'bendPositive' in k:
                    k['bendPositive'] = not k['bendPositive']
            new_ik[dst_ik] = new_keys
        target_anim['ik'] = new_ik
        
    # 3. Slot mapping
    slot_pair_map = {
        'arm1_1': 'arm2_1', 'arm2_1': 'arm1_1',
        'arm1_2': 'arm2_2', 'arm2_2': 'arm1_2',
        'arm1_2_red': 'arm2_2_red', 'arm2_2_red': 'arm1_2_red',
        'arm1_3': 'arm2_3', 'arm2_3': 'arm1_3',
        'horn1': 'horn2', 'horn2': 'horn1',
        'horn1_red': 'horn2_red', 'horn2_red': 'horn1_red',
    }
    att_remap = {
        'arm1_1': 'arm2_1', 'arm2_1': 'arm1_1',
        'arm1_2': 'arm2_2', 'arm2_2': 'arm1_2',
        'arm1_2_red': 'arm2_2_red', 'arm2_2_red': 'arm1_2_red',
        'arm1_3': 'arm2_3', 'arm2_3': 'arm1_3',
        'arm1_3_2': 'arm2_3_2', 'arm2_3_2': 'arm1_3_2',
        'horn1': 'horn2', 'horn2': 'horn1',
        'horn1_red': 'horn2_red', 'horn2_red': 'horn1_red',
    }
    if 'slots' in src_anim:
        new_slots = {}
        for s_name, s_data in src_anim['slots'].items():
            dst_s_name = slot_pair_map.get(s_name, s_name)
            new_s_data = copy.deepcopy(s_data)
            if 'attachment' in new_s_data:
                for k in new_s_data['attachment']:
                    if k.get('name') in att_remap:
                        k['name'] = att_remap[k['name']]
            new_slots[dst_s_name] = new_s_data
        target_anim['slots'] = new_slots
        
    if source_anim_name.startswith(('grab_player', 'grab_slam')):
        destination = (source_anim_name[:-6] + '_right_angry'
                       if source_anim_name.endswith('_angry') else source_anim_name + '_right')
        for name, keys in target_anim['ik'].items():
            for key in keys:
                key['mix'] = 1
                # An omitted bendPositive defaults to true in an IK timeline,
                # even when the setup constraint bends the other way.
                key['bendPositive'] = name == 'arm2_IK'
        for bone, rotations in right_grab_rotations()[destination].items():
            target_anim['bones'][bone]['rotate'] = copy.deepcopy(rotations)
    return target_anim

def main():
    spjson_path = os.path.abspath('animations/monsters/cave_god/cave_god.spjson')
    print(f"Reading {spjson_path}...")
    with open(spjson_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    pairs = [
        ('front_sweep', 'front_sweep_right'),
        ('front_sweep_angry', 'front_sweep_right_angry'),
        ('grab_player', 'grab_player_right'),
        ('grab_player_angry', 'grab_player_right_angry'),
        ('grab_slam', 'grab_slam_right'),
        ('grab_slam_angry', 'grab_slam_right_angry'),
    ]
    
    for src, dst in pairs:
        print(f"Mirroring {src} -> {dst}...")
        data['animations'][dst] = mirror_animation(data, src)
        
    print(f"Total animations now: {len(data['animations'])}")
    print("Writing back to spjson...")
    with open(spjson_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Done!")

if __name__ == '__main__':
    main()
