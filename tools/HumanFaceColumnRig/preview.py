"""Offline CPU sampler of the delivered Spine JSON; never loads the game."""
from pathlib import Path
from bisect import bisect_right
from functools import lru_cache
import argparse,json,math,re
import numpy as np
import cv2
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'STS2_Things/animations/monsters/human_face_column'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir',default='build/human_face_column')
BUILD=ROOT/parser.parse_args().output_dir
BUILD.mkdir(parents=True,exist_ok=True)
SK=json.loads((OUT/'human_face_column.spjson').read_text())
ATLAS=Image.open(OUT/'human_face_column.png').convert('RGBA')
TEXTURES={}
lines=(OUT/'human_face_column.atlas').read_text().splitlines()
for i,line in enumerate(lines):
    if i<5 or not line or line.startswith(' '):continue
    fields={}
    for detail in lines[i+1:i+8]:
        if not detail.startswith(' '):break
        k,_,v=detail.strip().partition(':');fields[k]=v.strip()
    if 'xy' not in fields:continue
    x,y=map(int,fields['xy'].split(','));w,h=map(int,fields['size'].split(','))
    tex=np.array(ATLAS.crop((x,y,x+w,y+h))).astype(np.float32)/255
    tex[:,:,:3]*=tex[:,:,3:4]
    TEXTURES[line]=tex
BONES=SK['bones'];IDS={b['name']:i for i,b in enumerate(BONES)}
ATTACHMENTS=SK['skins'][0]['attachments']


def rgba(value):return np.array([int(value[i:i+2],16)/255 for i in range(0,8,2)],dtype=np.float32)


def sample(keys,t,kind):
    times=[k.get('time',0) for k in keys]
    i=max(0,bisect_right(times,t)-1)
    a=keys[i];b=keys[min(i+1,len(keys)-1)]
    p=0 if a is b else np.clip((t-times[i])/(times[i+1]-times[i]),0,1)
    if kind=='rgba':return rgba(a['color'])*(1-p)+rgba(b['color'])*p
    names=('value',) if kind=='rotate' else ('x','y')
    default=1 if kind=='scale' else 0
    return np.array([a.get(k,default)*(1-p)+b.get(k,default)*p for k in names])


def triangle(canvas,texture,source,destination,colour):
    a=destination[1]-destination[0];b=destination[2]-destination[0]
    if abs(a[0]*b[1]-a[1]*b[0])<.02:return
    low=np.floor(destination.min(axis=0)).astype(int);high=np.ceil(destination.max(axis=0)).astype(int)+1
    low=np.maximum(low,[0,0]);high=np.minimum(high,[canvas.shape[1],canvas.shape[0]])
    w,h=high-low
    if w<=0 or h<=0:return
    local=destination-low
    transform=cv2.getAffineTransform(np.float32(source),np.float32(local))
    warped=cv2.warpAffine(texture,transform,(w,h),flags=cv2.INTER_LINEAR)
    mask=np.zeros((h,w),np.uint8)
    cv2.fillConvexPoly(mask,np.int32(np.rint(local*256)),255,shift=8)
    coverage=mask[:,:,None].astype(np.float32)*np.float32(1/255)
    alpha=warped[:,:,3:4]*coverage*colour[3]
    rgb=warped[:,:,:3]*coverage*colour[:3]*colour[3]
    region=canvas[low[1]:high[1],low[0]:high[0]]
    region[:,:,:3]=rgb+region[:,:,:3]*(1-alpha)
    region[:,:,3:4]=alpha+region[:,:,3:4]*(1-alpha)


@lru_cache(maxsize=32)
def render(clip='idle_loop',time=0.,direction='rotate_cw',rotation_time=0.,scale=.41,vertical_scale=1.04):
    transforms={};colours={}
    for anim,t in [(clip,time),(direction,rotation_time%12)]:
        data=SK['animations'][anim]
        for bone,tracks in data.get('bones',{}).items():
            props=transforms.setdefault(bone,{})
            for kind,keys in tracks.items():props[kind]=sample(keys,t,kind)
        for slot,tracks in data.get('slots',{}).items():
            if 'rgba' in tracks:colours[slot]=sample(tracks['rgba'],t,'rgba')
    world=[]
    for bone in BONES:
        values=transforms.get(bone['name'],{})
        x,y=values.get('translate',(0,0));x+=bone.get('x',0);y+=bone.get('y',0)
        angle=math.radians(bone.get('rotation',0)+values.get('rotate',[0])[0])
        sx,sy=values.get('scale',(1,1));sx*=bone.get('scaleX',1);sy*=bone.get('scaleY',1)
        c,s=math.cos(angle),math.sin(angle)
        matrix=np.array([[c*sx,-s*sy,x],[s*sx,c*sy,y],[0,0,1]])
        world.append(world[IDS[bone['parent']]]@matrix if 'parent' in bone else matrix)
    width,height=600,480;origin=np.array([300,390.])
    canvas=np.zeros((height,width,4),np.float32)
    for slot in SK['slots']:
        colour=colours.get(slot['name'],rgba(slot.get('color','ffffffff')))
        if colour[3]<.002:continue
        attachment=ATTACHMENTS[slot['name']][slot['attachment']]
        texture=TEXTURES[attachment.get('path',slot['attachment'])]
        tw,th=texture.shape[1],texture.shape[0]
        if attachment.get('type')=='mesh':
            data=attachment['vertices'];cursor=0;points=[]
            for _ in range(len(attachment['uvs'])//2):
                count=int(data[cursor]);cursor+=1;point=np.zeros(2)
                for _ in range(count):
                    index,x,y,weight=data[cursor:cursor+4];cursor+=4
                    point+=(world[int(index)]@np.array([x,y,1]))[:2]*weight
                points.append(point)
            source=np.array(attachment['uvs']).reshape(-1,2)*[tw-1,th-1]
            indices=attachment['triangles']
        else:
            w,h=attachment.get('width',tw),attachment.get('height',th)
            x,y=attachment.get('x',0),attachment.get('y',0)
            local=np.array([[-w/2+x,h/2+y,1],[w/2+x,h/2+y,1],[-w/2+x,-h/2+y,1],[w/2+x,-h/2+y,1]])
            points=(world[IDS[slot['bone']]]@local.T).T[:,:2]
            source=np.array([[0,0],[tw-1,0],[0,th-1],[tw-1,th-1]])
            indices=[0,1,2,1,3,2]
        target=np.array(points)*[scale,-vertical_scale]+origin
        for i in range(0,len(indices),3):
            ids=indices[i:i+3]
            triangle(canvas,texture,source[ids],target[ids],colour)
    rgb=np.divide(canvas[:,:,:3],canvas[:,:,3:4],out=np.zeros_like(canvas[:,:,:3]),where=canvas[:,:,3:4]>.00001)
    result=np.concatenate([rgb,canvas[:,:,3:4]],axis=2)
    return Image.fromarray(np.uint8(np.clip(result*255,0,255)))


def multiply(image,tint):
    p=np.array(image).astype(np.float32);p*=np.array(tint,dtype=np.float32)[None,None,:]
    return Image.fromarray(np.uint8(np.clip(p,0,255)))


def reserve_tint(index):
    shade=max(.35,.76-.13*index)
    return np.array((shade*.94,shade,shade*.96,1),dtype=np.float32)


FONT='C:/Windows/Fonts/msyh.ttc'
font=ImageFont.truetype(FONT,23);small=ImageFont.truetype(FONT,18)
bg=Image.open(ROOT/'images/rooms/cave_quartz/cave_quartz_00.png').convert('RGBA').resize((2765,1296),Image.Resampling.LANCZOS)
bg=bg.crop((422,108,2342,1188))
snail=Image.open(ROOT/'source_assets/monsters/depths_snails/rock_snail/character.png').convert('RGBA')
snail=snail.crop(snail.getbbox());snail.thumbnail((320,192),Image.Resampling.LANCZOS)


def stack_frame(t=0,strong=False,fall=None,labels=True):
    scene_name='human_face_column_encounter' if strong else 'human_face_column_weak'
    scene=(ROOT/f'scenes/encounters/{scene_name}.tscn').read_text()
    def slot(name):
        return tuple(map(float,re.search(r'name="'+re.escape(name)+r'"[^\n]*\nposition = Vector2\(([^)]+)\)',scene)[1].split(',')))
    image=bg.copy();x,base=slot('column_bottom')
    for level in range(6):
        direction='rotate_ccw' if level==1 or level>=3 and level%2 else 'rotate_cw'
        phase=4 if level in (1,2) else 0
        clip='idle_loop';pt=t%3.9;rotation=round((t+phase)%12,3);y=base-level*190;offset_x=0
        tint=np.ones(4,dtype=np.float32) if level<3 else reserve_tint(level-3)
        if fall is not None:
            if level==0:
                if fall>1.08:continue
                clip='die';pt=min(fall,1.08)
            else:
                p=min(1,max(0,fall/.32));drop=p*p*190
                if fall>.32:
                    q=min(1,(fall-.32)/.23);offset_x=3*math.sin(math.pi*q)
                y+=drop
                clip='fall' if fall<.66 else 'stunned_loop'
                pt=fall if fall<.66 else (fall-.66)%1.1
                if level==3:tint=reserve_tint(0)*(1-p)+p
                elif level>3:tint=reserve_tint(level-4)
        tile=render(clip,round(pt,3),direction,rotation)
        tile=multiply(tile,tint)
        image.alpha_composite(tile,(round(x-300+offset_x),round(y-390)))
    if strong:
        snail_x,snail_y=slot('rock')
        image.alpha_composite(snail,(round(snail_x-snail.width//2),round(snail_y-snail.height)))
    draw=ImageDraw.Draw(image)
    draw.text((35,32),'人面柱 · '+('强池示例：搭配爬岩蜗牛' if strong else '弱池：单独出场'),font=font,fill='#e9d59d')
    draw.text((35,69),'骨骼与布局制作预览 · 采样导出的 Spine JSON · 非游戏截图',font=small,fill='#d5dee1')
    if labels and fall is None:
        for level,title in [(2,'顶层  免疫伤害'),(1,'中层  减伤 50%'),(0,'底层  正常受伤')]:
            y=base-level*190
            draw.text((x-440,y-141),title,font=font,fill='#f2e6c7')
            draw.text((x-440,y-108),'18–21 HP   剩余 6 层',font=small,fill='#cee1df')
    return image.convert('RGB')


for strong,name in [(False,'weak-layout'),(True,'strong-layout')]:stack_frame(strong=strong).save(BUILD/f'{name}.jpg',quality=96)
contact=Image.new('RGB',(1800,1040),'#223038')
for i,(clip,t) in enumerate([('idle_loop',0),('attack',.38),('cast',.5),('seal',.42),('rattle',.62),('die',.42)]):
    cell=Image.new('RGBA',(600,520),'#223038');cell.alpha_composite(render(clip,t), (0,0))
    ImageDraw.Draw(cell).text((20,479),clip+f' {t:.2f}s',font=small,fill='white')
    contact.paste(cell.convert('RGB'),((i%3)*600,(i//3)*520))
contact.save(BUILD/'spine-motion-review.jpg',quality=95)

turn_sheet=Image.new('RGB',(1800,540),'#223038')
for row,direction in enumerate(('rotate_cw','rotate_ccw')):
    for col,t in enumerate((0,1.65,2.3,4,5.8,8)):
        tile=Image.new('RGBA',(600,520),'#223038')
        tile.alpha_composite(render('idle_loop',0,direction,t))
        ImageDraw.Draw(tile).text((20,479),f'{direction}  {t:.2f}s',font=small,fill='white')
        turn_sheet.paste(tile.convert('RGB').resize((300,260),Image.Resampling.LANCZOS),(col*300,row*270))
turn_sheet.save(BUILD/'spine-rotation-review.jpg',quality=96)

frames=[stack_frame(t=i/8,strong=True,labels=False).resize((960,540),Image.Resampling.LANCZOS).quantize(128) for i in range(96)]
frames[0].save(BUILD/'column-idle.gif',save_all=True,append_images=frames[1:],duration=125,loop=0,disposal=2)
render.cache_clear()
fall_frames=[]
for i in range(34):
    t=i/20
    frame=stack_frame(strong=True,fall=t,labels=False)
    ImageDraw.Draw(frame).text((950,930),'击碎底层：6 → 5；其余柱层眩晕',font=font,fill='#efe4c8')
    fall_frames.append(frame.resize((960,540),Image.Resampling.LANCZOS).quantize(128))
fall_frames[0].save(BUILD/'column-collapse.gif',save_all=True,append_images=fall_frames[1:],duration=50,loop=0,disposal=2)
fall_contact=Image.new('RGB',(1920,1080))
for i,index in enumerate((0,5,10,19)):
    fall_contact.paste(fall_frames[index],((i%2)*960,(i//2)*540))
fall_contact.save(BUILD/'collapse-contact-sheet.jpg',quality=95)
(BUILD/'preview-method.json').write_text(json.dumps({'method':'CPU sampling of exported Spine transforms, weighted vertices and RGBA timelines; column layout and gravity authored from runtime constants',
    'native_capture':False,'gameplay_test':False,'loop_seconds':12,'visible_layers':3,'remaining_layers':6,
    'scale':[.41,1.04],'layer_spacing':190,'stack_draw_order':'bottom to top; upper disc covers lower top plane',
    'ordinary_animation_motion':'horizontal only; no vertical translation, roll or scale'},indent=2)+'\n')
print('Wrote exported-Spine motion, six-disc layouts, idle and collapse previews.')
