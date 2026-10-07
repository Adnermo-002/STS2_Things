"""Create faithful-aspect contact sheets and GIFs from real Godot captures."""
from pathlib import Path
import argparse
import json

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('frames', type=Path)
parser.add_argument('silhouettes', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
report = json.loads((args.frames / 'report.json').read_text())
fps = report['fps']
names = [('idle_loop','待机'),('attack','撕咬'),('whip','触角鞭打'),('cast','重构化'),
         ('molt','蜕壳'),('power_up','强化'),('hurt','受击'),('die','死亡'),('revive','复起'),('summon','登场')]
font_path = Path('C:/Windows/Fonts/msyh.ttc')
font = ImageFont.truetype(str(font_path), 20) if font_path.exists() else ImageFont.load_default()
small = ImageFont.truetype(str(font_path), 16) if font_path.exists() else ImageFont.load_default()
boxes = {}
for name, _ in names:
    bounds = []
    for file in sorted(args.silhouettes.glob(f'{name}_*.png')):
        image = cv2.imread(str(file), cv2.IMREAD_GRAYSCALE)
        ys, xs = np.nonzero(image > 127)
        bounds.append((int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))
    values = np.array(bounds)
    lo, hi = values[:, :2].min(axis=0), values[:, 2:].max(axis=0)
    boxes[name] = (max(0,int(lo[0])-35), max(0,int(lo[1])-35),
                   min(1550,int(hi[0])+36), min(920,int(hi[1])+36))

global_values = np.array(list(boxes.values()))
global_box = (*global_values[:, :2].min(axis=0), *global_values[:, 2:].max(axis=0))

def panel(file, box, label, time, size=(780,570)):
    canvas = Image.new('RGB', size, '#20242a')
    picture = Image.open(file).convert('RGB').crop(box)
    picture = ImageOps.contain(picture, (size[0]-24, size[1]-54), Image.Resampling.LANCZOS)
    canvas.paste(picture, ((size[0]-picture.width)//2, 48+(size[1]-54-picture.height)//2))
    draw = ImageDraw.Draw(canvas)
    draw.text((18,10), f'放缩巨甲虫 · {label}', fill='#e9eef0', font=font)
    draw.text((size[0]-92,15),f'{time:.2f}s',fill='#9ca9ae',font=small)
    return canvas

overview = Image.new('RGB',(1800,1840),'#20242a')
overview_draw=ImageDraw.Draw(overview)
all_frames=[]
key_times={'idle_loop':1.25,'attack':.68,'whip':.60,'cast':.76,'molt':.80,
           'power_up':.75,'hurt':.11,'die':2.8,'revive':1.05,'summon':.88}
for index,(name,label) in enumerate(names):
    files=sorted(args.frames.glob(f'{name}_*.png'))
    duration=float(report['durations'][name])
    # Drop duplicate capture-end frames introduced by runtime float precision.
    files=files[:int(np.ceil(duration*fps-0.0001))+1]
    frames=[panel(file,boxes[name],label,min(i/fps,duration)) for i,file in enumerate(files)]
    durations=[round(1000/fps)]*len(frames)
    if name!='idle_loop': durations[-1]=350
    else: frames=frames[:-1]; durations=durations[:-1]
    paletted=[frame.quantize(colors=192) for frame in frames]
    paletted[0].save(args.output/f'{name}.gif',save_all=True,append_images=paletted[1:],
        duration=durations,loop=0,optimize=True,disposal=2)
    selected=min(round(key_times[name]*fps),len(files)-1)
    tile=panel(files[selected],boxes[name],label,min(selected/fps,duration),(600,460))
    overview.paste(tile,((index%3)*600,(index//3)*460))
    selected_files=files
    if name=='idle_loop': selected_files=files[:24]
    # Constant camera across the combined reel; movement/size is never faked by zoom.
    if name in ('idle_loop','attack','whip','cast','molt','die','revive'):
        for i,file in enumerate(selected_files):
            all_frames.append(panel(file,global_box,label,min(i/fps,duration),(780,540)).quantize(colors=176))
overview.save(args.output/'overview.png')
all_frames[0].save(args.output/'preview.gif',save_all=True,append_images=all_frames[1:],
    duration=round(1000/fps),loop=0,optimize=True,disposal=2)
(args.output/'README.md').write_text('# 放缩巨甲虫动画预览\n\n来自 Godot 原生 Spine 渲染，保留画面比例。\n\n'+
    '\n'.join(f'- [{label}]({name}.gif)' for name,label in names)+'\n',encoding='utf-8')
print(f'Created {len(names)} action GIFs, overview.png, and preview.gif ({len(all_frames)} frames)')
