"""CPU authoring sheets and continuous motion, not a native gameplay test."""
import os,sys,pickle,copy,argparse
from pathlib import Path
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('name');parser.add_argument('--motion',action='store_true')
parser.add_argument('--comparison',action='store_true')
parser.add_argument('--out',type=Path,default=ROOT/'build/depths_snails_polish/authoring')
args=parser.parse_args()
name=args.name;os.chdir(HERE/name);sys.path.insert(0,str(HERE/name))
from rigkit import Renderer
frames=pickle.load(open('out/frames.pkl','rb'));r=Renderer()
DEST=args.out;DEST.mkdir(parents=True,exist_ok=True)
VIEW=dict(scale=.35,W=620,H=370,ox=338,oy=337)

def at(clip,t,bare=False,renderer=None,source=None,label='1.18.1'):
    renderer=r if renderer is None else renderer;source=frames if source is None else source
    f=source[clip][min(len(source[clip])-1,round(t*60))]
    saved=renderer.rig['slots']
    if bare:renderer.rig['slots']=[s for s in saved if s['name']!='shell']
    result=Image.fromarray(renderer.render(f,**VIEW,bg=(41,53,63)))
    renderer.rig['slots']=saved
    ImageDraw.Draw(result).text((8,8),f'{label} | {name} | {clip} {t:.2f}s'+(' | BARE' if bare else ''),fill='white')
    return result

if args.comparison:
    baseline=ROOT/'build/depths_snails_polish/before'/name
    old_frames=pickle.load((baseline/'frames.pkl').open('rb'));old=Renderer(baseline/'rig_static.json')
    signature='cast' if name=='slime_snail' else 'retreat'
    samples=[('idle_loop',1.25),(signature,.58),('attack',.62 if name=='rock_snail' else .48),('die',1.1)]
    sheet=Image.new('RGB',(VIEW['W']*2,VIEW['H']*len(samples)))
    for i,(clip,t) in enumerate(samples):
        sheet.paste(at(clip,t,renderer=old,source=old_frames,label='1.18.0'),(0,i*VIEW['H']))
        sheet.paste(at(clip,t),(VIEW['W'],i*VIEW['H']))
    sheet.save(DEST/f'{name}-comparison.jpg',quality=92);print('Saved comparison',name,flush=True)
elif not args.motion:
    samples=[('idle_loop',0),('idle_loop',2.2),('attack',.28),('attack',.62 if name=='rock_snail' else .48),
             ('cast',.32),('cast',.58),('retreat',.55),('crawl',.62),('hurt',.10),
             ('die',1.1),('idle_loop',0),('shell_break',.15)]
    sheet=Image.new('RGB',(VIEW['W']*3,VIEW['H']*4))
    for i,(clip,t) in enumerate(samples):sheet.paste(at(clip,t,i>=10),((i%3)*VIEW['W'],(i//3)*VIEW['H']))
    sheet.save(DEST/f'{name}-poses.jpg',quality=92);print('Saved pose sheet',name,flush=True)
else:
    sequence=[]
    for clip,bare in [('idle_loop',False),('attack',False),('cast' if name=='slime_snail' else 'retreat',False),
                     ('crawl',False),('shell_break',True),('attack',True)]:
        for index in range(0,len(frames[clip])-1,3):sequence.append(at(clip,index/60,bare).quantize(160))
        print(name,clip,'sampled',flush=True)
    sequence[0].save(DEST/f'{name}-motion.gif',save_all=True,append_images=sequence[1:],duration=50,loop=0,disposal=2)
