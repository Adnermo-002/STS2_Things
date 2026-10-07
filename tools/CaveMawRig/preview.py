"""CPU authoring sheets and motion, including a version-to-version comparison."""
from pathlib import Path
import argparse,pickle
from PIL import Image,ImageDraw
from rigkit import Renderer

args=argparse.ArgumentParser()
args.add_argument('--poses-only',action='store_true')
opts=args.parse_args()
ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'build/cave_maw_polish/authoring'
DEST.mkdir(parents=True,exist_ok=True)
frames=pickle.load(open('out/frames.pkl','rb'))
renderer=Renderer()
view=dict(scale=.35,W=700,H=340,ox=350,oy=308)


def render(name,index):
    f=frames[name][index]
    result=Image.fromarray(renderer.render(f,**view,bg=(40,49,53)))
    ImageDraw.Draw(result).text((10,10),f'1.16.1 | {name} | {f["t"]:.2f}s | CPU authoring',fill='white')
    return result


def at(name,t):
    return render(name,min(len(frames[name])-1,round(t*60)))


poses={
    'idle_loop':[0,1.70,1.88,3.80,4.53,5.9],
    'attack':[0,.23,.48,.60,.85,1.35],
    'cast':[0,.24,.54,.74,.97,1.6],
    'devour':[0,.30,.85,1.20,1.40,2.1],
    'press':[0,.26,.44,.80,1.08,1.5],
    'empty':[0,.26,.52,.65,.90,1.15],
    'power_up':[0,.18,.48,.65,.93,1.4],
    'hurt':[0,.067,.13,.29,.43,.60],
    'die':[0,.38,.77,1.13,1.52,1.9],
    'revive':[0,.34,.68,1.02,1.38,1.70],
    'summon':[0,.30,.62,.94,1.28,1.6],
}
for name,times in poses.items():
    sheet=Image.new('RGB',(view['W']*3,view['H']*2))
    for i,t in enumerate(times):
        sheet.paste(at(name,t),((i%3)*view['W'],(i//3)*view['H']))
    sheet.save(DEST/f'{name}.jpg',quality=92)
    print('Authored poses:',name,flush=True)

reference=ROOT/'build/cave_maw_polish/before'
comparison=[('attack',.48),('cast',.74),('devour',1.40),('press',.80),('die',1.60)]
if all((reference/f'{name}.png').exists() for name,_ in comparison):
    sheet=Image.new('RGB',(view['W']*2,view['H']*len(comparison)))
    for i,(name,t) in enumerate(comparison):
        sheet.paste(Image.open(reference/f'{name}.png'),(0,i*view['H']))
        sheet.paste(at(name,t),(view['W'],i*view['H']))
    sheet.save(DEST/'comparison.jpg',quality=94)
    print('Saved authoring comparison.',flush=True)

if opts.poses_only:raise SystemExit(0)
for filename,names in [
    ('motion.gif',('idle_loop','cast','devour','attack','press','empty')),
    ('reactions.gif',('power_up','hurt','die','revive','summon')),
]:
    sequence=[]
    for name in names:
        for index in range(0,len(frames[name])-1,4):
            sequence.append(render(name,index).quantize(128))
        print('Authored motion:',name,flush=True)
    durations=[(70,60,70)[i%3] for i in range(len(sequence))]
    sequence[0].save(DEST/filename,save_all=True,append_images=sequence[1:],
                     duration=durations,loop=0,disposal=2)
    print(DEST/filename,flush=True)
