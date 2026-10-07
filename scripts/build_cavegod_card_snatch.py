"""Author Cave God's separate open-palm card theft in the existing Spine rig.

Only card_snatch[ _right ][ _angry ] is generated. Wrist rotations are solved by
the native Spine runtime, because the two forearms have different bind poses.
"""
import argparse
import copy
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source_assets/monsters/cave_god_motion'
RIG = ROOT / 'animations/monsters/cave_god/cave_god.spjson'
MOTION = json.loads((SOURCE / 'card_snatch_motion.json').read_text(encoding='utf-8'))
LENGTH = MOTION['duration']
TOUCH = MOTION['touch']
CLOSE = MOTION['close']


@lru_cache(maxsize=None)
def tangents(keys):
    """Shape-preserving Hermite tangents; pass through keys without stop/start.

    Only endpoints, flat holds and actual direction changes have zero velocity.
    Harmonic slopes prevent overshoot at the contact point and high windup.
    """
    result = [[0.0] * (len(keys[0]) - 1) for _ in keys]
    for i in range(1, len(keys) - 1):
        if keys[i][0] in (MOTION['launch'], MOTION['touch']):
            continue
        before = keys[i][0] - keys[i - 1][0]
        after = keys[i + 1][0] - keys[i][0]
        for c in range(1, len(keys[0])):
            a = (keys[i][c] - keys[i - 1][c]) / before
            b = (keys[i + 1][c] - keys[i][c]) / after
            if a * b > 0:
                w1, w2 = 2 * after + before, after + 2 * before
                result[i][c - 1] = (w1 + w2) / (w1 / a + w2 / b)
    return result


def sample(keys, t):
    if t <= keys[0][0]:
        return keys[0][1:]
    slopes = tangents(tuple(tuple(k) for k in keys))
    for i, (a, b) in enumerate(zip(keys, keys[1:])):
        if t <= b[0]:
            dt = b[0] - a[0]
            u = (t - a[0]) / dt
            if a[0] == MOTION['launch'] and b[0] == MOTION['touch']:
                # One minimum-jerk dash: no intermediate braking keys, and
                # acceleration eases in and out instead of snapping at contact.
                s = u*u*u*(u*(6*u-15)+10)
                return [x+(y-x)*s for x,y in zip(a[1:],b[1:])]
            h00, h10 = 2*u**3-3*u*u+1, u**3-2*u*u+u
            h01, h11 = -2*u**3+3*u*u, u**3-u*u
            return [h00*x + h10*dt*slopes[i][c] + h01*y + h11*dt*slopes[i+1][c]
                    for c, (x, y) in enumerate(zip(a[1:], b[1:]))]
    return keys[-1][1:]


def timeline(keys, fields):
    hz = MOTION['sample_hz']
    times = sorted({round(i / hz, 7) for i in range(round(LENGTH * hz) + 1)} | {k[0] for k in keys})
    return [dict(time=t, **dict(zip(fields, [round(v, 6) for v in sample(keys, t)]))) for t in times]


def build(data, right, angry):
    idle = data['animations']['idle_front' + ('_angry' if angry else '')]
    clip = copy.deepcopy(idle)
    for channels in clip.get('bones', {}).values():
        for channel, frames in channels.items():
            first = {k: v for k, v in frames[0].items() if k not in ('time', 'curve')}
            channels[channel] = [dict(time=0, **first), dict(time=LENGTH, **first)]
    clip.pop('events', None)
    clip.pop('drawOrder', None)
    # Keep the non-reaching arm planted, with its FK pose from idle.
    for constraint, keys in clip['ik'].items():
        for key in keys:
            key['bendPositive'] = constraint == 'arm2_IK'
            key['mix'] = int(constraint == ('arm1_IK' if right else 'arm2_IK'))
    arm = 'arm2' if right else 'arm1'
    sign = -1 if right else 1
    setup = {b['name']: b for b in data['bones']}
    start = idle['bones'][arm + '_IK']['translate'][0]
    sx = setup[arm + '_IK']['x'] + start['x']
    sy = setup[arm + '_IK']['y'] + start['y']
    # High windup, one accelerating lunge, a short grip, then one return arc.
    wrist = [[t, x * sign, y] for t, x, y in MOTION['wrist']]
    for key in wrist:
        if key[0] == 0 or key[0] >= MOTION['settled']:
            key[1:] = [sx, sy]
    clip['bones'][arm + '_IK']['translate'] = timeline(
        [[t, x - setup[arm + '_IK']['x'], y - setup[arm + '_IK']['y']] for t, x, y in wrist], ('x', 'y'))
    # Retain idle FK angles under the active IK. They must agree when the queued
    # idle blends IK weight back to zero, or the last few frames take a detour.
    # Shoulder anticipation and torso follow-through, without moving the resting hand.
    for bone in ('body1', 'body2', 'head'):
        keys = MOTION[bone + '_rotation']
        base = idle['bones'][bone].get('rotate', [{}])[0].get('value', 0)
        clip['bones'][bone]['rotate'] = timeline([[t, base + v * sign] for t, v in keys], ('value',))
    base = idle['bones']['body1'].get('translate', [{}])[0]
    clip['bones']['body1']['translate'] = timeline([
        [t, base.get('x', 0) + x, base.get('y', 0) + y*sign]
        for t, x, y in MOTION['body_translation']], ('x','y'))
    clip['bones'][arm + '_3']['scale'] = timeline(MOTION['wrist_scale'], ('x','y'))
    clip['slots'][arm + '_3']['attachment'] = [{'name': arm + '_3_2'}, {'time': CLOSE, 'name': arm + '_3'}]
    clip['events'] = [{'time': TOUCH, 'name':'central_hit'}, {'time': CLOSE,'name':'card_snatch'},
                      {'time':MOTION['settled'],'name':'attack_recover'}]
    return clip


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare-bake', action='store_true', help='Write authored paths before native wrist solving.')
    args = parser.parse_args()
    data = json.loads(RIG.read_text(encoding='utf-8'))
    baked = {} if args.prepare_bake else json.loads((SOURCE / 'card_snatch_bake.json').read_text(encoding='utf-8'))
    data.setdefault('events', {})['card_snatch'] = {}
    for right in (False, True):
        for angry in (False, True):
            name = 'card_snatch' + ('_right' if right else '') + ('_angry' if angry else '')
            clip = build(data, right, angry)
            if not args.prepare_bake:
                for bone, rotations in baked[name].items():
                    clip['bones'][bone]['rotate'] = rotations
            data['animations'][name] = clip
            print(name, 'prepared' if args.prepare_bake else 'native wrist bake applied')
    RIG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
