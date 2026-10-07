"""CPU authoring views; these are not native gameplay or multiplayer captures."""
from pathlib import Path
import argparse,pickle
from PIL import Image,ImageDraw
from rigkit import Renderer

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[2]/'build/radio_jellyfish/authoring')
parser.add_argument('--mode',choices=('all','sheets','motion'),default='all')
parser.add_argument('--baseline',type=Path)
args=parser.parse_args()
DEST=args.out
DEST.mkdir(parents=True,exist_ok=True)
frames=pickle.load(open('out/frames.pkl','rb'));renderer=Renderer()
VIEW=dict(scale=.33,W=600,H=575,ox=300,oy=537)


def at(name,t,source=None,label=None):
    source=frames if source is None else source
    f=source[name][min(len(source[name])-1,round(t*60))]
    image=Image.fromarray(renderer.render(f,**VIEW,bg=(40,48,58)))
    ImageDraw.Draw(image).text((9,9),f'{label or name} | {f["t"]:.2f}s | CPU authoring',fill='white')
    return image


for name,times in {
    'idle_loop':[0,.62,.98,2.26,3.98,5.9],
    'playback_1_1':[0,.28,.50,1.,1.55,2.3],
    'playback_1_2':[0,.28,.50,1.,1.55,2.3],
    'playback_2_2':[0,.28,.50,1.,1.55,2.3],
    'playback_3_3':[0,.28,.50,1.,1.55,2.3],
    'hurt':[0,.07,.15,.32,.48,.62],
    'die':[0,.4,.8,1.2,1.5,2.],
}.items():
    if args.mode=='motion':break
    sheet=Image.new('RGB',(VIEW['W']*3,VIEW['H']*2))
    for i,t in enumerate(times):sheet.paste(at(name,t),((i%3)*VIEW['W'],(i//3)*VIEW['H']))
    sheet.save(DEST/f'{name}.jpg',quality=91)
    print('Authored poses:',name,flush=True)

if args.baseline and args.mode!='motion':
    previous=pickle.load(args.baseline.open('rb'))
    pairs=[('idle_loop',.98),('playback_1_1',.50),('playback_2_2',.50),('die',1.5)]
    sheet=Image.new('RGB',(VIEW['W']*2,VIEW['H']*len(pairs)))
    for row,(name,t) in enumerate(pairs):
        for col,(source,label) in enumerate(((previous,'1.17.0'),(frames,'1.17.1'))):
            sheet.paste(at(name,t,source,f'{label} | {name}'),(col*VIEW['W'],row*VIEW['H']))
    sheet.save(DEST/'comparison.jpg',quality=92)
    print('Authored before/after comparison',flush=True)

for filename,names in [('motion.gif',('idle_loop','playback_1_1','playback_1_2','playback_2_2','playback_3_3')),
                       ('reactions.gif',('hurt','die','revive','summon'))]:
    if args.mode=='sheets':break
    sequence=[]
    for name in names:
        end=len(frames[name])-1
        for index in range(0,end,5):sequence.append(at(name,index/60).quantize(128))
        print('Authored motion:',name,flush=True)
    sequence[0].save(DEST/filename,save_all=True,append_images=sequence[1:],
        duration=[(80,80,90)[i%3] for i in range(len(sequence))],loop=0,disposal=2)
    print(DEST/filename,flush=True)
