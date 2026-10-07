"""Encode native moth frames and real card UI captures without changing the art."""
from pathlib import Path
import json
import os
import subprocess
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'build/silk_moth/visuals'
OUT=ROOT/'build/silk_moth/review'
OUT.mkdir(parents=True,exist_ok=True)
report=json.loads((SOURCE/'motion/report.json').read_text('utf-8'))
fps=report['fps']
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',24)
small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
names={'idle_loop':'悬浮与摆丝','attack':'掠翅','cast':'牵丝','flutter':'连振','hurt':'受击',
       'power_up':'振翅','die':'坠落','revive':'复起','summon':'登场'}
video=OUT/'silk-moth-motion.mp4'
process=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-f','rawvideo',
    '-pix_fmt','rgb24','-s','1280x780','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast',
    '-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],stdin=subprocess.PIPE,
    stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
written=0
def frame(path,label):
    canvas=Image.new('RGB',(1280,780),'#202a30')
    canvas.paste(Image.open(path).convert('RGB').resize((1280,720),Image.Resampling.LANCZOS),(0,60))
    draw=ImageDraw.Draw(canvas);draw.text((22,16),label,font=font,fill='#eee5ce')
    draw.text((1040,20),'原生渲染预览',font=small,fill='#bfccd0')
    return canvas
for clip in report['clips']:
    for index in range(clip['frames']):
        canvas=frame(SOURCE/'motion'/f"{clip['slug']}_{index:04d}.jpg",'垂丝蛾 · '+names[clip['name']])
        process.stdin.write(canvas.tobytes());written+=1
    for _ in range(4):process.stdin.write(canvas.tobytes());written+=1
for name,label in [('player_pending_buff','先获得牵丝 buff'),('cards_bound','下回合抽牌完成后：先打出 1，才能使用 2'),('cards_released','解开后可正常出牌，费用不变')]:
    canvas=frame(SOURCE/f'{name}.png',label)
    for _ in range(fps*2):process.stdin.write(canvas.tobytes());written+=1
process.stdin.close();error=process.stderr.read().decode('utf-8','replace')
assert process.wait()==0,error
review={'source':'native Godot + Spine pose capture and native card UI fixture; not gameplay recording',
        'fps':fps,'clips':len(report['clips']),'source_frames':report['frames'],
        'video_frames':written,'video_seconds':written/fps,'video':str(video)}
(OUT/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n','utf-8')
Image.open(SOURCE/'cards_bound.png').convert('RGB').resize((1280,720),Image.Resampling.LANCZOS).save(OUT/'silk-moth-preview.jpg',quality=94)
print(json.dumps(review,ensure_ascii=False))
