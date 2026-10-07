"""Build labelled GIFs from native Spine/Godot captures."""
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2]
folder=ROOT/'build/fleeting_echo/animation-polish/native/motion'
out=ROOT/'build/fleeting_echo/animation-polish'
sequences={name:sorted((folder/name).glob('*.png')) for name in ['idle_loop','grasp','scatter','die']}
assert all(sequences.values()),'Native motion frames are missing'
for name,files in sequences.items():
    ims=[]
    for file in files:
        im=Image.open(file).convert('RGB').crop((190,170,725,615)).resize((428,356),Image.Resampling.LANCZOS)
        ims.append(im.quantize(128))
    ims[0].save(out/('native-'+name+'.gif'),save_all=True,append_images=ims[1:],duration=50,loop=0)
clips=['grasp','scatter','die'];count=max(len(sequences[n]) for n in clips);frames=[]
for i in range(count+6):
    canvas=Image.new('RGB',(1200,365),(41,46,53));draw=ImageDraw.Draw(canvas)
    for column,name in enumerate(clips):
        file=sequences[name][min(i,len(sequences[name])-1)]
        image=Image.open(file).convert('RGB').crop((190,170,725,615))
        image.thumbnail((400,330),Image.Resampling.LANCZOS)
        canvas.paste(image,(column*400,28));draw.text((column*400+14,8),name+' / native Spine',fill='white')
    frames.append(canvas.quantize(128))
frames[0].save(out/'native-motion-review.gif',save_all=True,append_images=frames[1:],duration=50,loop=0)
print(out/'native-motion-review.gif')
