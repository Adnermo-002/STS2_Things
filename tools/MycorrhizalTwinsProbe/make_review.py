"""Encode the final native Godot captures; this is a visual probe, not a game recording."""
from pathlib import Path
import argparse,json,os,subprocess
import imageio_ffmpeg
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--build-dir',default='build/mycorrhizal_twins');args=parser.parse_args()
SOURCE=ROOT/args.build_dir/'final/visuals'
OUT=ROOT/args.build_dir/'review';OUT.mkdir(parents=True,exist_ok=True)
report=json.loads((SOURCE/'motion/report.json').read_text('utf-8'));fps=report['fps']
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',24);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
names={'idle_loop':'待机 · 呼吸、菌帽滞后与眨眼','attack':'根鞭与菌帽顶撞','double_attack':'双抽 · 两次接触',
 'cast':'战孢强化','guard':'撑帽防护','exchange':'菌根交换','enrage':'断根狂暴','hurt':'受击回弹',
 'power_up':'强化','die':'枯萎倒地','revive':'复起','summon':'登场'}
video=OUT/'mycorrhizal-twins.mp4'
proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','1280x780',
 '-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],
 stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
written=0
def frame(path,label):
 c=Image.new('RGB',(1280,780),'#202b2a');c.paste(Image.open(path).convert('RGB').resize((1280,720),Image.Resampling.LANCZOS),(0,60))
 d=ImageDraw.Draw(c);d.text((20,16),label,font=font,fill='#ede7cd');d.text((1060,21),'原生渲染预览',font=small,fill='#bfccbd');return c
for name,label in [('01_elite_robust_elder','菌根双生子 · 攻击专精／防御专精'),('02_exchanged_robust_younger','交换生命与体态 · 丰盛更强，萎蔫更弱'),('03_root_transfer','根部养分输送')]:
 c=frame(SOURCE/f'{name}.png',label)
 for _ in range(fps*2):proc.stdin.write(c.tobytes());written+=1
for clip in report['clips']:
 for i in range(clip['frames']):
  c=frame(SOURCE/'motion'/f"{clip['slug']}_{i:04d}.jpg",'菌根双生子 · '+names[clip['name']]);proc.stdin.write(c.tobytes());written+=1
for _ in range(fps*2):proc.stdin.write(frame(SOURCE/'04_surviving_elder_fury.png','击杀一只 · 存活者断根狂暴').tobytes());written+=1
proc.stdin.close();err=proc.stderr.read().decode('utf-8','replace');assert proc.wait()==0,err
metadata=dict(source='native Godot + Spine pose captures and native creature UI; not live gameplay recording',fps=fps,source_frames=report['frames'],video_frames=written,seconds=written/fps,video=str(video))
(OUT/'review.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),'utf-8')
sheet=Image.new('RGB',(1280,720),'#202b2a')
for i,(name,title) in enumerate([('01_elite_robust_elder','丰盛长兄 / 萎蔫幼弟'),('02_exchanged_robust_younger','萎蔫长兄 / 丰盛幼弟')]):
 im=Image.open(SOURCE/f'{name}.png').crop((960,370,1880,865));im.thumbnail((630,580));sheet.paste(im,(i*640,110))
 ImageDraw.Draw(sheet).text((i*640+40,50),title,font=font,fill='#eee3c9')
sheet.save(OUT/'forms-comparison.jpg',quality=96)
print(json.dumps(metadata,ensure_ascii=False))
