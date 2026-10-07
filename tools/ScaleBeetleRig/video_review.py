"""Encode a true-colour review of all ten actions from the Godot PNG captures."""
from pathlib import Path
import argparse
import json
import subprocess
import os

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('frames', type=Path)
parser.add_argument('silhouettes', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
report = json.loads((args.frames / 'report.json').read_text())
fps = report['fps']
names = [('idle_loop','待机'),('attack','撕咬'),('whip','触角鞭打'),('cast','重构化'),
         ('molt','蜕壳'),('power_up','强化'),('hurt','受击'),('die','死亡'),('revive','复起'),('summon','登场')]
bounds=[]
for file in args.silhouettes.glob('*.png'):
    mask=cv2.imread(str(file),cv2.IMREAD_GRAYSCALE)>127
    ys,xs=np.nonzero(mask)
    bounds.append([xs.min(),ys.min(),xs.max(),ys.max()])
bounds=np.array(bounds)
lo,hi=bounds[:,:2].min(0),bounds[:,2:].max(0)
box=(max(0,int(lo[0])-35),max(0,int(lo[1])-35),min(1550,int(hi[0])+36),min(920,int(hi[1])+36))
font_path=Path('C:/Windows/Fonts/msyh.ttc')
font=ImageFont.truetype(str(font_path),24) if font_path.exists() else ImageFont.load_default()
small=ImageFont.truetype(str(font_path),18) if font_path.exists() else ImageFont.load_default()
size=(1000,680)
args.output.parent.mkdir(parents=True,exist_ok=True)
command=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24',
         '-s',f'{size[0]}x{size[1]}','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','medium',
         '-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(args.output)]
process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
count=0
for name,label in names:
    files=sorted(args.frames.glob(f'{name}_*.png'))
    duration=float(report['durations'][name])
    files=files[:int(np.ceil(duration*fps-0.0001))+1]
    if name=='idle_loop': files=files[:24]
    for i,file in enumerate(files):
        canvas=Image.new('RGB',size,'#20242a')
        picture=ImageOps.contain(Image.open(file).convert('RGB').crop(box),(976,610),Image.Resampling.LANCZOS)
        canvas.paste(picture,((1000-picture.width)//2,58+(610-picture.height)//2))
        draw=ImageDraw.Draw(canvas)
        draw.text((22,15),f'放缩巨甲虫 · {label}',font=font,fill='#e9eef0')
        draw.text((900,20),f'{min(i/fps,duration):.2f}s',font=small,fill='#9ca9ae')
        process.stdin.write(canvas.tobytes())
        count+=1
process.stdin.close()
errors=process.stderr.read().decode('utf-8',errors='replace')
assert process.wait()==0, errors
capture=cv2.VideoCapture(str(args.output))
assert int(capture.get(cv2.CAP_PROP_FRAME_COUNT))==count
capture.release()
print(f'Created {args.output}: {count} frames, {count/fps:.2f}s, {args.output.stat().st_size} bytes')
