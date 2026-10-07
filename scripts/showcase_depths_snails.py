"""Present authored idle poses and existing continuous GIFs; not gameplay captures."""
from pathlib import Path
import argparse
from PIL import Image,ImageDraw,ImageFont,ImageSequence
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=ROOT/'build/depths_snails_polish/authoring')
parser.add_argument('--motion',action='store_true');args=parser.parse_args();DEST=args.source
names=('crystal_snail','slime_snail','rock_snail')
titles=('晶壳蜗牛','涎丝蜗牛','爬岩蜗牛')
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',27)
small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',17)
tile_width=Image.open(DEST/f'{names[0]}-poses.jpg').width//3
poster=Image.new('RGB',(tile_width*3,430),'#29353f')
for i,(name,title) in enumerate(zip(names,titles)):
    pose=Image.open(DEST/f'{name}-poses.jpg').crop((0,25,tile_width,370))
    poster.paste(pose,(i*tile_width,58));d=ImageDraw.Draw(poster)
    d.text((i*tile_width+26,18),title,font=font,fill='#ede7d5')
ImageDraw.Draw(poster).text((22,403),'骨骼制作预览 · 非游戏截图',font=small,fill='#b1bcc2')
poster.save(DEST/'snail-trio.jpg',quality=94)
if args.motion:
    clips=[];duration=50
    for name in names:
        im=Image.open(DEST/f'{name}-motion.gif')
        duration=im.info.get('duration',50)
        clips.append([f.convert('RGB').copy() for f in ImageSequence.Iterator(im)])
    sequence=[]
    for t in range(max(map(len,clips))):
        frame=poster.copy()
        for i,clip in enumerate(clips):frame.paste(clip[t%len(clip)].crop((0,25,tile_width,370)),(i*tile_width,58))
        sequence.append(frame.resize((round(tile_width*2.25),323),Image.Resampling.LANCZOS).quantize(192))
    sequence[0].save(DEST/'snail-trio-motion.gif',save_all=True,append_images=sequence[1:],duration=duration,loop=0,disposal=2)
print(DEST/'snail-trio.jpg')
