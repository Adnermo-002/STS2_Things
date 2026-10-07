"""CPU authoring preview, not an in-game capture or runtime validation."""
from pathlib import Path
import pickle
import sys
from PIL import Image, ImageDraw
from rigkit import Renderer

DEST = Path(__file__).resolve().parents[2] / 'build/reverse_salamander_polish/authoring'
DEST.mkdir(parents=True, exist_ok=True)
frames = pickle.load(open('out/frames.pkl', 'rb'))
renderer = Renderer()
view = dict(scale=.34, W=640, H=420, ox=310, oy=390)


def render(name, index):
    frame = frames[name][index]
    result = Image.fromarray(renderer.render(frame, **view, bg=(43, 54, 59)))
    draw = ImageDraw.Draw(result)
    draw.text((12, 10), f'{name} | {frame["t"]:.2f}s | CPU authoring preview', fill=(235, 239, 225))
    return result


for name, times in {
    'attack': [0, .24, .39, .50, .72, 1.05],
    'roll': [0, .25, .46, .74, 1.02, 1.45],
    'gather': [0, .28, .56, .85, 1.20, 1.55],
    'recall': [0, .22, .54, .80, 1.10, 1.4],
    'die': [0, .40, .80, 1.2, 1.55, 2.0],
}.items():
    sheet = Image.new('RGB', (view['W']*3, view['H']*2))
    for i, t in enumerate(times):
        index = min(len(frames[name])-1, round(t*60))
        sheet.paste(render(name, index), ((i%3)*view['W'], (i//3)*view['H']))
    sheet.save(DEST/f'{name}.jpg', quality=90)
    print(f'Authored poses: {name}', flush=True)

if '--poses-only' in sys.argv:
    raise SystemExit(0)

sequence = []
for name in ('idle_loop', 'attack', 'roll', 'gather', 'recall'):
    # 15 fps preview at real clip speed; the shipped Spine curves are 60 Hz.
    clip_end = min(180, len(frames[name])-1) if name == 'idle_loop' else len(frames[name])-1
    for index in range(0, clip_end, 4):
        sequence.append(render(name, index).quantize(128))
    print(f'Authored motion: {name}', flush=True)
durations = [70 if i%3 == 0 else 60 if i%3 == 1 else 70 for i in range(len(sequence))]
sequence[0].save(DEST/'motion.gif', save_all=True, append_images=sequence[1:],
                 duration=durations, loop=0, disposal=2)
print(DEST/'motion.gif', flush=True)
