"""Author the painted stone-disc Spine rig and offline motion previews.

The cylinder is ordinary weighted Spine meshes. Its 153 surface controls move
around the vertical axis; rear strips collapse at the silhouette and disappear.
The shipped game needs no image warping, mesh generator or custom shader.
"""
from pathlib import Path
import argparse
import json
import math
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source_assets/monsters/human_face_column'
PARTS = SOURCE / 'parts'
OUT = ROOT / 'STS2_Things/animations/monsters/human_face_column'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir', default='build/human_face_column')
BUILD = ROOT / parser.parse_args().output_dir
for directory in (SOURCE, PARTS, OUT, BUILD):
    directory.mkdir(parents=True, exist_ok=True)
KEY = 'human_face_column'
RES = f'res://STS2_Things/animations/monsters/{KEY}'
W, H = 1024, 298
RADIUS, DEPTH = 492.0, 49.0
TOP, MIDDLE, BOTTOM = 177.0, 98.0, 19.0
STRIPS = 16
DURATION = 12.0
FPS = 20


def smooth(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


def clean_part(image):
    pixels = np.array(image.convert('RGBA'))
    alpha = pixels[:, :, 3]
    count, labels, stats, _ = cv2.connectedComponentsWithStats((alpha > 100).astype('uint8'), 8)
    if count < 2:
        raise ValueError('Empty generated part')
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    mask = (labels == largest).astype('uint8')
    # Contract the generated fringe once; preserve the painted surface.
    mask = cv2.erode(mask, np.ones((3, 3), np.uint8))
    alpha = np.uint8(np.clip(cv2.distanceTransform(mask, cv2.DIST_L2, 3), 0, 1) * 255)
    pixels[:, :, 3] = np.minimum(alpha, pixels[:, :, 3])
    result = Image.fromarray(pixels)
    return result.crop(result.getbbox())


raw = Image.open(ROOT / 'output/imagegen/human_face_column/parts_v1.png').convert('RGBA')
rw, rh = raw.size
body = clean_part(raw.crop((0, 0, rw, int(rh * .53)))).resize((W, H), Image.Resampling.LANCZOS)
body.save(PARTS / 'stone_disc.png')
faces = []
bands = []
for i in range(3):
    face = clean_part(raw.crop((int(rw*i/3), int(rh*.55), int(rw*(i+1)/3), rh)))
    face.save(PARTS / f'face_{i}_master.png')
    face = face.resize((444, 147), Image.Resampling.LANCZOS)
    # Blend only the outer relief perimeter into the matching stone paint.
    rgba = np.array(face)
    distance = cv2.distanceTransform((rgba[:, :, 3] > 80).astype('uint8'), cv2.DIST_L2, 3)
    rgba[:, :, 3] = np.uint8(rgba[:, :, 3] * smooth(distance / 9))
    face = Image.fromarray(rgba)
    faces.append(face)
    band = body.crop((105, 118, 919, 277)).resize((1024, 158), Image.Resampling.LANCZOS)
    band.alpha_composite(face, (290, 5))
    pixels = np.array(band)
    yy = np.arange(band.height)[:, None]
    feather = smooth(yy / 10) * smooth((band.height - 1 - yy) / 10)
    pixels[:, :, 3] = np.uint8(pixels[:, :, 3] * feather)
    band = Image.fromarray(pixels)
    band.save(PARTS / f'face_band_{i}.png')
    bands.append(band)

# Fragments retain the same painted stone, with irregular fracture boundaries.
parts = {'stone_disc': body, **{f'face_band_{i}': b for i, b in enumerate(bands)}}
fragment_centres = []
for i in range(8):
    x = 36 + (i % 4) * 232
    y = 35 + (i // 4) * 120
    chip = body.crop((x, y, x + 220, min(H, y + 139)))
    mask = Image.new('L', chip.size)
    cw, ch = chip.size
    ImageDraw.Draw(mask).polygon([(4, ch*.17), (cw*.49, 1), (cw-3, ch*.24),
                                 (cw*.85, ch-2), (cw*.25, ch*.87)], fill=255)
    chip.putalpha(Image.fromarray(np.minimum(np.array(chip.getchannel('A')), np.array(mask))))
    parts[f'chip_{i}'] = chip
    fragment_centres.append((x + cw/2 - W/2, H-y-ch/2))


def turn(t, direction=1):
    segment = min(2, int(t // 4))
    local = t - segment*4
    amount = segment + float(smooth((local-1.1)/1.65))
    return direction * amount * 2*math.pi/3


def wrap(angle):
    return (angle + math.pi) % (2*math.pi) - math.pi


def surface(face, col, row, angle):
    theta = wrap(angle + face * 2*math.pi/3 + (col/STRIPS-.5)*2*math.pi/3)
    theta = float(np.clip(theta, -math.pi/2, math.pi/2))
    x = RADIUS * math.sin(theta)
    y = (TOP, MIDDLE, BOTTOM)[row] + DEPTH*(1-math.cos(theta))
    return x, y


# Atlas with a two-pixel extruded edge for each independent painted region.
atlas_image = Image.new('RGBA', (2048, 1024))
rects = {}
x = y = shelf = 2
for name, part in sorted(parts.items(), key=lambda item: -item[1].height):
    if x + part.width + 2 > atlas_image.width:
        x, y, shelf = 2, y+shelf+4, 0
    if y + part.height + 2 > atlas_image.height:
        raise ValueError('Atlas overflow')
    atlas_image.alpha_composite(part, (x, y))
    atlas_image.paste(part.crop((0,0,1,part.height)).resize((2,part.height)), (x-2,y))
    atlas_image.paste(part.crop((part.width-1,0,part.width,part.height)).resize((2,part.height)), (x+part.width,y))
    atlas_image.paste(part.crop((0,0,part.width,1)).resize((part.width,2)), (x,y-2))
    atlas_image.paste(part.crop((0,part.height-1,part.width,part.height)).resize((part.width,2)), (x,y+part.height))
    rects[name] = (x, y, part.width, part.height)
    x += part.width + 4
    shelf = max(shelf, part.height)
atlas_image.save(OUT / f'{KEY}.png')
atlas = [f'{KEY}.png', 'size: 2048,1024', 'format: RGBA8888', 'filter: Linear,Linear', 'repeat: none']
for name, (x, y, width, height) in rects.items():
    atlas += [name, '  rotate: false', f'  xy: {x}, {y}', f'  size: {width}, {height}',
              f'  orig: {width}, {height}', '  offset: 0, 0', '  index: -1']
atlas = '\n'.join(atlas) + '\n'
(OUT / f'{KEY}.atlas').write_text(atlas, 'utf-8')
(OUT / f'{KEY}.spatlas').write_text(json.dumps({'source_path': f'{RES}/{KEY}.atlas',
    'atlas_data': atlas, 'normal_texture_prefix': 'n', 'specular_texture_prefix': 's'}), 'utf-8')

bones = [{'name': 'root'}, {'name': 'motion', 'parent': 'root'}, {'name': 'stone', 'parent': 'motion'}]
for row in range(3):
    bones.append({'name': f'row_{row}', 'parent': 'motion'})
for face in range(3):
    for col in range(STRIPS+1):
        for row in range(3):
            px, py = surface(face, col, row, 0)
            bones.append({'name': f'f{face}_c{col}_r{row}', 'parent': f'row_{row}', 'x': round(px,4), 'y': round(py,4)})
for i, (cx, cy) in enumerate(fragment_centres):
    bones.append({'name': f'chip_{i}', 'parent': 'motion', 'x': cx, 'y': cy})
bone_ids = {bone['name']: i for i, bone in enumerate(bones)}
slots = [{'name': 'stone_disc', 'bone': 'stone', 'attachment': 'stone_disc'}]
attachments = {'stone_disc': {'stone_disc': {'type': 'region', 'path': 'stone_disc',
                                           'x': 0, 'y': H/2, 'width': W, 'height': H}}}
for face in range(3):
    for strip in range(STRIPS):
        name = f'wrap_{face}_{strip}'
        setup_theta = wrap(face*2*math.pi/3 + ((strip+.5)/STRIPS-.5)*2*math.pi/3)
        setup_alpha = round(float(smooth((math.cos(setup_theta)+.025)/.085))*255)
        setup_shade = round((.84+.16*max(0,math.cos(setup_theta)))*255)
        setup_colour = f'{setup_shade:02x}{setup_shade:02x}{setup_shade:02x}{setup_alpha:02x}'
        slots.append({'name': name, 'bone': 'motion', 'attachment': name, 'color': setup_colour})
        vertices, uvs = [], []
        for row in range(3):
            for col in (strip, strip+1):
                vertices += [1, bone_ids[f'f{face}_c{col}_r{row}'], 0, 0, 1]
                uvs += [col/STRIPS, row/2]
        attachments[name] = {name: {'type': 'mesh', 'path': f'face_band_{face}',
            'uvs': uvs, 'vertices': vertices, 'triangles': [0,1,2,1,3,2,2,3,4,3,5,4],
            'hull': 6, 'width': 1024, 'height': 158}}
for i in range(8):
    name = f'chip_{i}'
    slots.append({'name': name, 'bone': name, 'attachment': name, 'color': 'ffffff00'})
    attachments[name] = {name: {'type': 'region', 'width': parts[name].width, 'height': parts[name].height}}


def colour(alpha=1, light=1):
    n = max(0, min(255, round(light*255)))
    return f'{n:02x}{n:02x}{n:02x}{max(0,min(255,round(alpha*255))):02x}'


animations = {}
times = np.linspace(0, DURATION, int(DURATION*FPS)+1)
for name, direction in [('rotate_cw', -1), ('rotate_ccw', 1)]:
    bone_tracks, slot_tracks = {}, {}
    for face in range(3):
        for col in range(STRIPS+1):
            for row in range(3):
                key = f'f{face}_c{col}_r{row}'
                bx, by = surface(face,col,row,0)
                bone_tracks[key] = {'translate': [{'time': round(float(t),4),
                    'x': round(surface(face,col,row,turn(float(t),direction))[0]-bx,4),
                    'y': round(surface(face,col,row,turn(float(t),direction))[1]-by,4)} for t in times]}
        for strip in range(STRIPS):
            track = []
            previous = None
            previous_time = 0
            for t in times:
                theta = wrap(turn(float(t),direction) + face*2*math.pi/3 + ((strip+.5)/STRIPS-.5)*2*math.pi/3)
                # The back hemisphere collapses into its nearest silhouette.
                alpha = float(smooth((math.cos(theta)+.025)/.085))
                light = .84 + .16*max(0,math.cos(theta))
                value = colour(alpha,light)
                if value != previous or t == DURATION:
                    # Keep the end of a constant run; otherwise Spine linearly
                    # interpolates across a hold and ghosts the rear faces.
                    if previous is not None and previous_time > track[-1]['time']:
                        track.append({'time':previous_time,'color':previous})
                    track.append({'time':round(float(t),4),'color':value})
                    previous=value
                previous_time=round(float(t),4)
            slot_tracks[f'wrap_{face}_{strip}'] = {'rgba': track}
    animations[name] = {'bones': bone_tracks, 'slots': slot_tracks}

# Motion curves: time, rotation, x, y, scale-x, scale-y. Every intact disc
# stays rigid and level: only horizontal recoil is allowed. Vertical movement
# belongs to the creature's collapse tween, never attack/hurt/idle animations.
# A separate Spine track turns the three decorative faces around the cylinder.
POSES = {
 'idle_loop': [(0,0,0,0,1,1),(3.9,0,0,0,1,1)],
 'attack': [(0,0,0,0,1,1),(.18,0,14,0,1,1),(.38,0,-58,0,1,1),(.49,0,-38,0,1,1),(.93,0,0,0,1,1)],
 'cast': [(0,0,0,0,1,1),(.25,0,6,0,1,1),(.5,0,-10,0,1,1),(.7,0,2,0,1,1),(1.15,0,0,0,1,1)],
 'seal': [(0,0,0,0,1,1),(.2,0,5,0,1,1),(.42,0,-5,0,1,1),(.66,0,2,0,1,1),(1.1,0,0,0,1,1)],
 'rattle': [(0,0,0,0,1,1),(.15,0,10,0,1,1),(.34,0,-41,0,1,1),(.48,0,13,0,1,1),(.62,0,-35,0,1,1),(1.12,0,0,0,1,1)],
 'hurt': [(0,0,0,0,1,1),(.075,0,14,0,1,1),(.17,0,-5,0,1,1),(.37,0,0,0,1,1)],
 'stunned_loop': [(0,0,-3,0,1,1),(.55,0,3,0,1,1),(1.1,0,-3,0,1,1)],
 'recover': [(0,0,-3,0,1,1),(.16,0,2,0,1,1),(.38,0,0,0,1,1)],
 'fall': [(0,0,0,0,1,1),(.3,0,0,0,1,1),(.4,0,-7,0,1,1),(.48,0,4,0,1,1),(.66,0,0,0,1,1)],
 'summon': [(0,0,0,0,1,1),(.4,0,-4,0,1,1),(.7,0,0,0,1,1)],
 'revive': [(0,0,0,0,1,1),(.3,0,3,0,1,1),(.66,0,0,0,1,1)],
 'power_up': [(0,0,0,0,1,1),(.35,0,-5,0,1,1),(.8,0,0,0,1,1)],
 'die': [(0,0,0,0,1,1),(.12,0,5,0,1,1),(.24,0,-5,0,1,1),(1.08,0,0,0,1,1)],
}


def transform(keys):
    return {'rotate': [{'time':t,'value':r} for t,r,x,y,sx,sy in keys],
            'translate': [{'time':t,'x':x,'y':y} for t,r,x,y,sx,sy in keys],
            'scale': [{'time':t,'x':sx,'y':sy} for t,r,x,y,sx,sy in keys]}


for name, keys in POSES.items():
    duration = keys[-1][0]
    tracks = {'motion': transform(keys)}
    for row in range(3):
        tracks[f'row_{row}'] = {'translate': [{'time':0,'x':0,'y':0},
            {'time':duration,'x':0,'y':0}]}
    animations[name] = {'bones': tracks}
    if name == 'die':
        for parent in ('stone','row_0','row_1','row_2'):
            tracks.setdefault(parent,{})['scale'] = [{'time':0,'x':1,'y':1},
                {'time':.16,'x':1,'y':1},{'time':.27,'x':0,'y':0}]
        animations[name]['slots'] = {}
        for i in range(8):
            dx = (-1 if i%4<2 else 1)*(62+14*(i%3))
            dy = 64+21*(i%3)
            tracks[f'chip_{i}'] = {'translate':[{'time':.17,'x':0,'y':0},
                {'time':.47,'x':dx*.52,'y':dy},{'time':1.08,'x':dx,'y':-180-14*(i%2)}],
                'rotate':[{'time':.17,'value':0},{'time':1.08,'value':(-1 if i%2 else 1)*(34+i*7)}]}
            animations[name]['slots'][f'chip_{i}'] = {'rgba':[{'time':0,'color':'ffffff00'},
                {'time':.17,'color':'ffffff00'},{'time':.23,'color':'ffffffff'},
                {'time':.73,'color':'ffffffc0'},{'time':1.08,'color':'ffffff00'}]}

skeleton = {'skeleton': {'hash':'human-face-column-v1','spine':'4.2.43','x':-W/2,'y':0,'width':W,'height':H},
            'bones':bones,'slots':slots,'skins':[{'name':'default','attachments':attachments}],
            'animations':animations}
(OUT / f'{KEY}.spjson').write_text(json.dumps(skeleton,separators=(',',':')), 'utf-8')
(OUT / f'{KEY}_skel_data.tres').write_text(f'''[gd_resource type="SpineSkeletonDataResource" load_steps=3 format=3]
[ext_resource type="SpineAtlasResource" path="{RES}/{KEY}.spatlas" id="1"]
[ext_resource type="SpineSkeletonFileResource" path="{RES}/{KEY}.spjson" id="2"]
[resource]
atlas_res = ExtResource("1")
skeleton_file_res = ExtResource("2")
default_mix = 0.12
''', 'utf-8')


def composite(bottom, top):
    return Image.alpha_composite(bottom, top)


def disc(angle):
    """Continuous authoring projection of the same cylindrical bone controls."""
    yy, xx = np.mgrid[0:H,0:W].astype(np.float32)
    lx = (xx-W/2)/RADIUS
    theta = np.arcsin(np.clip(lx,-1,1))
    local = theta-angle
    sector = np.floor((local+math.pi/3)/(2*math.pi/3)).astype(np.int32)
    u = (local-sector*2*math.pi/3)/(2*math.pi/3)+.5
    world_y = H-yy
    shifted_top = TOP+DEPTH*(1-np.cos(theta))
    v = (shifted_top-world_y)/(TOP-BOTTOM)
    image = np.zeros((H,W,4),np.uint8)
    for index, band in enumerate(bands):
        sampled = cv2.remap(np.array(band),np.float32(u*(band.width-1)),np.float32(v*(band.height-1)),
                            cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        mask = (sector%3==index)&(np.abs(lx)<=1)&(v>=0)&(v<=1)
        image[mask] = sampled[mask]
    light = .84+.16*np.cos(theta)
    image[:,:,:3] = np.uint8(image[:,:,:3]*light[:,:,None])
    return composite(body,Image.fromarray(image))


def interpolate(keys, t):
    if t <= keys[0][0]: return keys[0][1:]
    for a,b in zip(keys,keys[1:]):
        if t <= b[0]:
            p=(t-a[0])/(b[0]-a[0])
            return tuple(x+(y-x)*p for x,y in zip(a[1:],b[1:]))
    return keys[-1][1:]


def pose(clip,t,angle=0):
    r,x,y,sx,sy=interpolate(POSES[clip],t)
    paint=disc(angle)
    if clip=='die' and t>.18:
        canvas=Image.new('RGBA',(1280,640))
        for i,(cx,cy) in enumerate(fragment_centres):
            elapsed=max(0,(t-.18)/.9)
            chip=parts[f'chip_{i}'].rotate((34+i*7)*elapsed*(-1 if i%2 else 1),resample=Image.Resampling.BICUBIC,expand=True)
            alpha=np.array(chip.getchannel('A')).astype(float)*(1-float(smooth((t-.7)/.38)))
            chip.putalpha(Image.fromarray(np.uint8(alpha)))
            dx=(-1 if i%4<2 else 1)*(62+14*(i%3))*elapsed
            dy=(64+21*(i%3))*4*elapsed*(1-elapsed)-180*elapsed*elapsed
            canvas.alpha_composite(chip,(round(640+cx+dx-chip.width/2),round(470-cy-dy-chip.height/2)))
        return canvas
    radians=math.radians(r);c,s=math.cos(radians),math.sin(radians)
    matrix=np.float32([[c*sx,s*sy,640+x-c*sx*W/2-s*sy*H],
                       [-s*sx,c*sy,470-y+s*sx*W/2-c*sy*H]])
    return Image.fromarray(cv2.warpAffine(np.array(paint),matrix,(1280,640),flags=cv2.INTER_LINEAR))


def backdrop(image, colour='#223038'):
    bg=Image.new('RGBA',image.size,colour);bg.alpha_composite(image);return bg.convert('RGB')


disc(0).save(SOURCE/'assembled_disc.png')
contact=Image.new('RGB',(1800,920),'#223038')
draw=ImageDraw.Draw(contact)
for i,degrees in enumerate((0,40,80,120,160,200,240,280,320)):
    thumb=disc(math.radians(degrees)).resize((570,166),Image.Resampling.LANCZOS)
    cell=Image.new('RGBA',(600,292),'#223038');cell.alpha_composite(thumb,(15,48))
    ImageDraw.Draw(cell).text((22,245),f'{degrees} degrees',fill='white')
    contact.paste(cell.convert('RGB'),((i%3)*600,(i//3)*300))
contact.save(BUILD/'rotation-contact-sheet.jpg',quality=95)

for name,direction in [('clockwise',-1),('counterclockwise',1)]:
    frames=[]
    for i in range(144):
        image=disc(turn(i/12,direction)).resize((768,224),Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',(840,300),'#223038');canvas.alpha_composite(image,(36,36))
        frames.append(canvas.convert('RGB'))
    frames[0].save(BUILD/f'{name}.gif',save_all=True,append_images=frames[1:],duration=83,loop=0,disposal=2)

sheet=Image.new('RGB',(1600,1200),'#223038')
for i,(clip,t) in enumerate([('attack',.18),('attack',.38),('cast',.5),('seal',.42),
                            ('rattle',.34),('rattle',.62),('hurt',.075),('stunned_loop',.55),
                            ('fall',.3),('recover',.16),('die',.3),('die',.7)]):
    cell=backdrop(pose(clip,t)).resize((400,200),Image.Resampling.LANCZOS)
    x,y=(i%4)*400,(i//4)*400
    sheet.paste(cell,(x,y+50));ImageDraw.Draw(sheet).text((x+20,y+275),f'{clip}  {t:.2f}s',fill='white')
sheet.save(BUILD/'motion-contact-sheet.jpg',quality=95)

# Native power icon: the three-disc silhouette stays readable at 64 px.
icon=Image.new('RGBA',(256,256))
thumb=disc(0).resize((145,107),Image.Resampling.LANCZOS)
for y in (141,75,9):icon.alpha_composite(thumb,(55,y))
icon.save(ROOT/'images/powers/human_face_column_power.png')
icon.resize((64,64),Image.Resampling.LANCZOS).save(ROOT/'images/powers/human_face_column_power_packed.png')
(ROOT/'images/atlases/power_atlas.sprites/human_face_column_power.tres').write_text('''[gd_resource type="AtlasTexture" load_steps=2 format=3]
[ext_resource type="Texture2D" path="res://images/powers/human_face_column_power_packed.png" id="1"]
[resource]
atlas = ExtResource("1")
region = Rect2(0, 0, 64, 64)
''','utf-8')

(SOURCE/'rig-authoring.json').write_text(json.dumps({'bones':len(bones),'weighted_meshes':STRIPS*3,
    'faces_per_disc':3,'rotation_seconds':DURATION,'spine_version':'4.2.43',
    'scene_scale':[.41,1.04],'layer_spacing':190,'intact_disc_motion':'horizontal only; rigid height; no roll or vertical squash',
    'animations':list(animations),'authoring_preview':'Pillow/OpenCV cylindrical projection; not a native game capture',
    'generator_model':'gpt-image-2.5-sunburst','parts_source':'output/imagegen/human_face_column/parts_v1.png'},
    ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps({'bones':len(bones),'meshes':STRIPS*3,'animations':len(animations),'out':str(OUT)},ensure_ascii=False))
