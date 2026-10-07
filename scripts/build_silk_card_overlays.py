"""Adapt Queen's packed-texture Affliction VFX into luminous silk card bindings."""
from pathlib import Path
import hashlib
import json
import math
import re
import shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT=Path(__file__).resolve().parents[1]
VANILLA=ROOT.parent/'STS2-V111'
VFX=ROOT/'scenes/vfx/ui/card/silk'
MATERIALS=ROOT/'materials/vfx/ui/card/silk'
IMAGES=ROOT/'images/vfx/ui/card/silk'
for folder in [VFX,MATERIALS,IMAGES]:folder.mkdir(parents=True,exist_ok=True)
def write(path,text):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,'utf-8')

# Preserve Queen's RG/A contract: intensity, moving light field, coverage.
reference=Image.open(VANILLA/'images/vfx/ui/card/afflictions/bound/ui_card_bound_main.png').convert('RGBA')
size=1024; scale=3
# Design in card-local pixels. The native main quad is 422 px, scaled by 1.2.
# Each pass crosses the portrait, rounds a card edge, then disappears behind it.
# Keep the title, cost and central rules area free of the opaque front strands.
card_pixel=422*1.2/size
silk=Image.new('RGBA',(size*scale,size*scale))
def curve(p,t):
    p=np.asarray(p,float);return (1-t)**3*p[0]+3*(1-t)**2*t*p[1]+3*(1-t)*t*t*p[2]+t**3*p[3]

def paint_pass(points,seed,count=5,spacing=1.35,weight=1.0,opacity=1.0):
    """A soft silk ribbon resolving into uneven filaments, with overlap depth."""
    ts=np.linspace(0,1,241)
    centers=np.array([curve(points,t) for t in ts])
    tangents=np.gradient(centers,axis=0)
    tangents/=np.maximum(np.linalg.norm(tangents,axis=1)[:,None],0.0001)
    normals=np.column_stack([-tangents[:,1],tangents[:,0]])
    taper=0.2+0.8*np.sin(np.pi*ts)**0.24

    def ribbon(offset,width,intensity,alpha,shift=(0,0)):
        local=centers+normals*np.asarray(offset)[:,None]+np.asarray(shift)
        widths=np.asarray(width)[:,None]
        left=(local+normals*widths)/card_pixel+size/2
        right=(local-normals*widths)/card_pixel+size/2
        polygon=[tuple(p*scale) for p in np.concatenate([left,right[::-1]])]
        layer=Image.new('RGBA',silk.size)
        ImageDraw.Draw(layer).polygon(polygon,fill=(intensity,intensity,intensity,round(alpha*opacity)))
        silk.alpha_composite(layer)

    wobble=np.sin(ts*math.tau*1.3+seed)*0.55
    # A low-opacity membrane joins the fibers. The displaced dark underlay
    # breaks older fibers at crossings, so they read as wound over/under.
    ribbon(wobble,np.full_like(ts,count*spacing*.52)*taper,48,95,(.6,1.25))
    ribbon(wobble,np.full_like(ts,count*spacing*.52)*taper,173,38)
    for strand in range(count):
        phase=seed+strand*1.7
        spread=(strand-(count-1)/2)*spacing
        offset=spread*(.72+.28*np.sin(math.pi*ts))+wobble
        offset+=np.sin(ts*math.tau*(1.2+strand*.09)+phase)*.52
        width=(.40+.10*(strand%3))*weight*taper
        ribbon(offset,width,180+(strand%3)*18,224)
        # Broken, tapered highlights avoid uniform vector-like lines.
        glint=np.maximum(0,np.sin(ts*math.tau*2.3+phase))**3
        ribbon(offset-.14,width*.42*glint,245,160)
    # A few loose hairs separate from the ribbon near the turn.
    for edge in [-1,1]:
        offset=edge*(count*spacing*.5+1.2)+np.sin(ts*math.tau+seed)*2.1
        ribbon(offset,.19*taper,212,125)

# Narrow edge returns and lower coils establish volume around the entire card.
# They sit behind the stronger portrait crossings and avoid the rules text.
returns=[
    [(-143,-135),(-159,-119),(-155,-78),(-144,-70)],
    [(145,-143),(158,-128),(157,-91),(145,-76)],
    [(145,-45),(158,-23),(155,14),(144,30)],
    [(-143,2),(-159,18),(-155,45),(-143,57)],
    [(-145,53),(-150,95),(-152,157),(-137,178)],
    [(145,28),(153,91),(144,143),(132,184)],
    [(-139,168),(-98,205),(77,216),(137,183)],
    [(-144,146),(-121,205),(71,204),(139,162)],
]
for index,points in enumerate(returns):
    paint_pass(points,index+9,count=3,spacing=1.25,weight=.87,opacity=.85)

# Asymmetric front windings: two loosely parallel wraps, crossed by two
# steeper turns. These replace the previous four isolated corner ornaments.
front=[
    [(-146,-132),(-102,-110),(81,-99),(146,-42)],
    [(-146,-72),(-77,-55),(92,-22),(146,29)],
    [(146,-140),(93,-127),(-86,-70),(-145,3)],
    [(145,-76),(103,-49),(-75,4),(-145,57)],
]
for index,points in enumerate(front):
    paint_pass(points,index+1,count=5 if index%2==0 else 4,spacing=1.25)

# A small gathered tuft where the lower loops tighten, with two soft free ends.
for index,points in enumerate([
    [(130,177),(142,166),(140,157),(131,166)],
    [(131,167),(118,181),(126,193),(137,183)],
    [(132,180),(120,197),(130,210),(115,218)],
    [(134,181),(142,193),(134,209),(145,216)],
]):paint_pass(points,index+21,count=2,spacing=.95,weight=.7,opacity=.85)

silk=silk.resize((size,size),Image.Resampling.LANCZOS)
coverage=silk.getchannel('A')
mask=np.array(coverage,dtype=float)
halo=np.array(coverage.filter(ImageFilter.GaussianBlur(5)),dtype=float)*.24
pixels=np.array(reference)
pixels[:,:,0]=np.where(mask>0,np.array(silk)[:,:,0],127)
pixels[:,:,2]=0
pixels[:,:,3]=np.clip(np.maximum(mask,halo),0,255).astype('uint8')
Image.fromarray(pixels).save(IMAGES/'silk_main.png')

write(MATERIALS/'silk_main.tres','''[gd_resource type="ShaderMaterial" load_steps=2 format=3]
[ext_resource type="Shader" path="res://shaders/cards/silk_binding_main.gdshader" id="1"]
[resource]
resource_local_to_scene = true
shader = ExtResource("1")
shader_parameter/bright_st = Vector4(0, 0, 0.5, 0)
shader_parameter/bright_energy = 1.65
shader_parameter/effect_amount = 1.0
''')
write(MATERIALS/'silk_border.tres','''[gd_resource type="ShaderMaterial" load_steps=3 format=3]
[ext_resource type="Shader" path="res://shaders/cards/silk_binding_border.gdshader" id="1"]
[ext_resource type="Texture2D" path="res://images/vfx/ui/card/ui_card_border_vignette.png" id="2"]
[resource]
resource_local_to_scene = true
shader = ExtResource("1")
shader_parameter/main_st = Vector4(1, 3, 0.25, 0)
shader_parameter/mask_erosion = Vector2(0.4, 0.6)
shader_parameter/mask = ExtResource("2")
shader_parameter/effect_amount = 1.0
''')
source=VANILLA/'scenes/vfx/ui/card/afflictions/bound/vfx_ui_card_affliction_bound.tscn'
scene=re.sub(r' uid="[^"]+"','',source.read_text('utf-8-sig')).replace('load_steps=24','load_steps=28')
scene=scene.replace('res://materials/vfx/ui/card/afflictions/bound/vfx_ui_card_affliction_bound_border.tres','res://materials/vfx/ui/card/silk/silk_border.tres')
scene=scene.replace('res://materials/vfx/ui/card/afflictions/bound/vfx_ui_card_affliction_bound_main.tres','res://materials/vfx/ui/card/silk/silk_main.tres')
scene=scene.replace('res://images/vfx/ui/card/afflictions/bound/ui_card_bound_main.png','res://images/vfx/ui/card/silk/silk_main.png')
scene=scene.replace('Color(0.27396876, 0.5137255, 0.12941176, 0.76862746)','Color(0.44, 0.70, 0.49, 0.76)')
scene=scene.replace('Color(0.15, 0.6, 0.31499997, 0.1254902)','Color(0.20, 0.46, 0.34, 0.075)')
scene=scene.replace('Color(0.5505563, 1, 0.30270457, 1)','Color(0.72, 0.93, 0.66, 0.88)')
scene=scene.replace('Color(0.59557605, 1, 0.42108184, 1)','Color(0.84, 0.97, 0.74, 0.70)')
scene=scene.replace('Color(0.51294047, 0.819067, 0.24793532, 0.78431374)','Color(0.85, 0.95, 0.73, 0.94)')
scene=scene.replace('name="vfx_ui_card_afffliction_bound"','name="SilkCardEffect"')
def track(index,path,times,values,update=0):
    return f'''tracks/{index}/type = "value"
tracks/{index}/path = NodePath("{path}")
tracks/{index}/interp = 1
tracks/{index}/keys = {{"times": PackedFloat32Array({', '.join(map(str,times))}), "transitions": PackedFloat32Array({', '.join('1' for _ in times)}), "update": {update}, "values": [{', '.join(values)}]}}
'''
paths=['card_mask/border:material:shader_parameter/effect_amount','vfx_container/main:material:shader_parameter/effect_amount']
animations='''[sub_resource type="Animation" id="Reset"]
resource_name = "RESET"
length = 0.001
'''
for i,path in enumerate(paths):animations+=track(i,path,[0],['1.0'])
animations+='''
[sub_resource type="Animation" id="Apply"]
resource_name = "apply"
length = 0.55
'''
for i,path in enumerate(paths):animations+=track(i,path,[0],['1.0'])
# Queen's native effect is already readable on its first frame. Keep that
# property even when a hand-animation mod pauses an off-focus preview card.
animations+=track(2,'.:modulate',[0,.12,.55],['Color(1,1,1,0.82)','Color(1,1,1,1)','Color(1,1,1,1)'])
animations+=track(3,'vfx_container/main:scale',[0,.45],['Vector2(1.27,1.27)','Vector2(1.2,1.2)'])
animations+=track(4,'vfx_container/main:material:shader_parameter/bright_energy',[0,.12,.55],['1.65','2.15','1.65'])
animations+='''
[sub_resource type="Animation" id="Release"]
resource_name = "release"
length = 0.48
'''
for i,path in enumerate(paths):animations+=track(i,path,[0,.12,.42],['1.0','.82','0.0'])
animations+=track(2,'.:modulate',[0,.18,.48],['Color(1,1,1,1)','Color(1,1,1,.85)','Color(1,1,1,0)'])
animations+=track(3,'vfx_container/main:scale',[0,.48],['Vector2(1.2,1.2)','Vector2(1.32,1.32)'])
animations+=track(4,'card_mask/vfx_common_specks:emitting',[0],['false'],1)
animations+='''
[sub_resource type="AnimationLibrary" id="Animations"]
_data = {&"RESET": SubResource("Reset"), &"apply": SubResource("Apply"), &"release": SubResource("Release")}

'''
index=scene.index('[node name="SilkCardEffect"');scene=scene[:index]+animations+scene[index:]
scene+='''
[node name="AnimationPlayer" type="AnimationPlayer" parent="."]
process_mode = 3
libraries = {&"": SubResource("Animations")}
autoplay = "apply"
'''
scene=re.sub(r'(?<![A-Za-z0-9_])\.(?=\d)','0.',scene)
write(VFX/'silk_card_effect.tscn',scene)
for slug,name,order in [('silk_lead','SilkLead',1),('silk_bound','SilkBound',2)]:
    write(ROOT/f'scenes/cards/overlays/afflictions/{slug}.tscn',f'''[gd_scene load_steps=3 format=3]
[ext_resource type="Script" path="res://STS2_Things/Visuals/NSilkCardOverlay.cs" id="1"]
[ext_resource type="PackedScene" path="res://scenes/vfx/ui/card/silk/silk_card_effect.tscn" id="2"]
[node name="{name}" type="Control"]
mouse_filter = 2
script = ExtResource("1")
[node name="SilkEffect" parent="." instance=ExtResource("2")]
[node name="Sequence" type="Label" parent="."]
z_index = 8
offset_left = 34.0
offset_top = -256.0
offset_right = 86.0
offset_bottom = -212.0
mouse_filter = 2
theme_override_colors/font_color = Color({"0.97, 0.86, 0.57, 1" if order==1 else "0.76, 0.95, 0.84, 1"})
theme_override_colors/font_outline_color = Color(0.10, 0.15, 0.14, 1)
theme_override_constants/outline_size = 5
theme_override_font_sizes/font_size = 29
text = "{order}"
horizontal_alignment = 1
vertical_alignment = 1
''')
record={'reference':'Queen.PuppetStringsMove -> ChainsOfBindingPower -> Bound overlay',
 'native_scene':'scenes/vfx/ui/card/afflictions/bound/vfx_ui_card_affliction_bound.tscn',
 'source_scene_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'texture_contract':{'R':'strand intensity','G':'native Queen scrolling light field','A':'silk coverage and soft halo'},
 'new_texture':'images/vfx/ui/card/silk/silk_main.png',
 'notes':'Native card mask, border, vignette, glow, particle material and transitions retained. Asymmetric front windings, shaded edge returns, bottom coils and a gathered tuft replace the four corner bundles; opaque strands avoid the rules area.'}
native_map={}
def localize_native(path):
    original=VANILLA/path
    if not original.is_file():return path
    if path in native_map:return native_map[path]
    kind={'png':'images/vfx/ui/card/silk/native','tres':'materials/vfx/ui/card/silk/native',
          'tscn':'scenes/vfx/ui/card/silk/native','gdshader':'shaders/cards/silk_native',
          'gdshaderinc':'shaders/cards/silk_native'}[original.suffix[1:]]
    relative=kind+'/'+original.name;native_map[path]=relative
    destination=ROOT/relative;destination.parent.mkdir(parents=True,exist_ok=True)
    if original.suffix=='.png':shutil.copy2(original,destination)
    else:
        content=re.sub(r' uid="[^"]+"','',original.read_text('utf-8-sig'))
        content=re.sub(r'res://([^"\s]+)',lambda m:'res://'+localize_native(m[1]),content)
        write(destination,content)
    return relative
for path in [VFX/'silk_card_effect.tscn',MATERIALS/'silk_main.tres',MATERIALS/'silk_border.tres',
             ROOT/'shaders/cards/silk_binding_main.gdshader',ROOT/'shaders/cards/silk_binding_border.gdshader']:
    content=re.sub(r'res://([^"\s]+)',lambda m:'res://'+localize_native(m[1]),path.read_text('utf-8'))
    write(path,content)
record['native_dependency_remap']=native_map
write(ROOT/'source_assets/ui/silk_queen/reference.json',json.dumps(record,indent=2)+'\n')
print('Built Queen-derived card VFX, packed silk texture, local materials and native wrappers.')
