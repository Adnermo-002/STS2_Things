"""Present native Spine render frames without changing their timing."""
from pathlib import Path
from PIL import Image, ImageDraw
import json,sys
ROOT=Path(__file__).resolve().parents[2]
TASK=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/"build/great-silk-moth-polish-20261008"
SRC=TASK/"native"
report=json.loads((SRC/"report.json").read_text())
fps=report["fps"]
CROP=(50,55,920,715)
def frame(path,w=500):
    image=Image.open(path).convert("RGB").crop(CROP)
    image.thumbnail((w,int(w*.8)),Image.Resampling.LANCZOS)
    return image
for name,times in {
    "attack":[0,.23,.48,.67,.92,1.35],
    "cast":[0,.32,.62,.78,1.03,1.55],
    "die":[0,.1,.50,.95,1.32,1.75],
    "flutter":[0,.20,.42,.55,.67,1.50],
}.items():
    files=sorted((SRC/name).glob("*.png"))
    canvas=Image.new("RGB",(1500,820),(36,43,49));draw=ImageDraw.Draw(canvas)
    for i,t in enumerate(times):
        image=frame(files[min(round(t*fps),len(files)-1)])
        x=(i%3)*500;y=(i//3)*410
        canvas.paste(image,(x,y+28))
        draw.text((x+10,y+8),f"{name} | {t:.2f}s | native Spine",fill="white")
    canvas.save(TASK/("native-"+name+".jpg"),quality=94)
sequences={name:sorted((SRC/("transition_"+name)).glob("*.png")) for name in ["attack","cast","flutter"]}
images=[]
for i in range(max(map(len,sequences.values()))+5):
    canvas=Image.new("RGB",(1200,352),(36,43,49));draw=ImageDraw.Draw(canvas)
    for col,(name,files) in enumerate(sequences.items()):
        image=frame(files[min(i,len(files)-1)],400)
        canvas.paste(image,(col*400,30))
        draw.text((col*400+12,8),name+" / native Spine + mix",fill="white")
    images.append(canvas.quantize(192))
images[0].save(TASK/"native-motion-review.gif",save_all=True,append_images=images[1:],
               duration=round(1000/fps),loop=0,disposal=2,optimize=False)
for name in ["idle_loop","die"]:
    files=sorted((SRC/name).glob("*.png"))
    images=[]
    for path in files:
        image=frame(path,540)
        draw=ImageDraw.Draw(image);draw.text((10,8),name+" / native Spine",fill="white")
        images.append(image.quantize(192))
    images[0].save(TASK/("native-"+name+".gif"),save_all=True,append_images=images[1:],
                   duration=round(1000/fps),loop=0,disposal=2)
print(TASK/"native-motion-review.gif")
