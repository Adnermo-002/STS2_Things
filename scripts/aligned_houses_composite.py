"""Keep the full landscape and dim it continuously away from the focal area.

The light field uses native viewport coordinates. No silhouette or cutout is
applied: sky, houses, grass and road continue into the peripheral darkness.
"""
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
SIZE=(3440,1616)

def smooth(t):
    t=np.clip(t,0,1);return t*t*t*(t*(t*6-15)+10)

def compose(source,width_factor=1.):
    # Cover the whole native portrait, including its offscreen overscan.
    # Shift the painting slightly to keep the blue cottage inside the viewport.
    # The uncovered overscan is outside the visible area and has zero light.
    scene=ImageOps.fit(source.convert('RGB'),SIZE,Image.Resampling.LANCZOS)
    shifted=Image.new('RGB',SIZE)
    shifted.paste(scene,(round(180*3440/2662),0))
    scene=shifted
    x=np.arange(SIZE[0],dtype=np.float32)[None,:]*(2662/3440)-371
    y=np.arange(SIZE[1],dtype=np.float32)[:,None]*(1251/1616)-79
    radius=((x-510)/(570*width_factor))**2+((y-575)/(490*width_factor))**2
    light=np.exp(-radius)
    # Long tails preserve several hundred pixels of dim peripheral scenery.
    # The start of the text column retains faint context without a vertical edge.
    light*=smooth((x+100)/430)
    light*=smooth((y+160)/500)
    light*=1-smooth((y-760)/460)
    light*=1-smooth((x-650)/800)
    pixels=np.asarray(scene,dtype=np.float32)*light[:,:,None]
    output=Image.fromarray(np.uint8(np.clip(np.rint(pixels),0,255))).convert('RGBA')
    matte=Image.fromarray(np.uint8(np.clip(np.rint(light*255),0,255)))
    return output,matte

def viewport(image):
    canvas=Image.new('RGB',(1920,1080),'black')
    im=image.convert('RGBA').resize((2662,1251),Image.Resampling.LANCZOS)
    canvas.paste(im,(-371,-79),im)
    return canvas

if __name__=='__main__':
    source=Image.open(ROOT/'output/imagegen/reality_aligned_houses/event_portrait_v3_grassland.png')
    dest=ROOT/'build/reality_aligned_houses_radial_fade';dest.mkdir(exist_ok=True)
    samples=[('1.19.3',Image.open(dest/'before/reality_aligned_houses.png'))]
    for name,strength in [('focused',.90),('balanced',1.),('open',1.14)]:
        image,matte=compose(source,strength)
        image.save(dest/f'candidate-{name}.png')
        samples.append((name,image))
    sheet=Image.new('RGB',(1920,1160),'#070707')
    for i,(name,image) in enumerate(samples):
        sample=viewport(image).resize((960,540),Image.Resampling.LANCZOS)
        x=(i%2)*960;y=(i//2)*580+32
        sheet.paste(sample,(x,y));ImageDraw.Draw(sheet).text((x,y-28),name,fill='white')
    sheet.save(dest/'fade-variants.jpg',quality=95)
    print(dest/'fade-variants.jpg')
