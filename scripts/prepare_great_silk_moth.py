"""Partition the approved Sunburst sprite without replacing the painted silhouette."""
from pathlib import Path
import json
import shutil
import hashlib
import numpy as np
from PIL import Image, ImageDraw
import cv2

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source_assets/monsters/great_silk_moth'
PARTS = ROOT / 'tools/GreatSilkMothRig/parts'
PARTS.mkdir(parents=True, exist_ok=True)
image = Image.open(SOURCE / 'character-generated.png').convert('RGBA')
a = np.array(image)
# Remove detached extraction specks; preserve fine connected hair and silk.
count, labels, stats, _ = cv2.connectedComponentsWithStats((a[:,:,3] > 8).astype('uint8'), 8)
for i in range(1, count):
    if stats[i, cv2.CC_STAT_AREA] < 10:
        a[labels == i, 3] = 0
image = Image.fromarray(a)
image.save(SOURCE / 'character-final.png')
def polygon(points):
    mask = Image.new('L', image.size)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return np.array(mask) > 0
regions = [
 ('wing_far',[(145,22),(445,22),(675,430),(637,499),(483,527),(359,366),(178,208)]),
 ('wing_near',[(516,484),(790,198),(1165,15),(1379,15),(1385,475),(1320,666),(1040,658),(760,613),(623,579)]),
 ('wing_hind',[(600,550),(760,565),(897,628),(999,688),(1065,865),(790,898),(636,711)]),
 ('body',[(282,455),(422,431),(505,420),(599,470),(650,541),(675,644),(729,730),(808,844),(777,914),(659,900),(548,825),(494,766),(389,735),(305,653),(274,534)]),
 ('silk_a',[(335,672),(371,675),(392,801),(412,874),(419,937),(307,944),(304,807),(325,782)]),
 ('silk_b',[(469,718),(495,718),(513,856),(577,899),(579,1009),(439,1019),(430,947),(463,855)]),
 ('tail',[(743,847),(778,851),(847,887),(1036,910),(1074,1035),(1020,1110),(850,1029),(733,914)]),
 ('bridge_silk',[(347,690),(365,686),(381,746),(403,805),(450,852),(487,875),
                 (489,901),(466,906),(415,867),(381,822),(359,755)])
]
names=['body','wing_far','wing_near','wing_hind','silk_a','silk_b','tail','bridge_silk']
assignment=np.zeros(a.shape[:2],np.uint8)
masks={name:polygon(points) for name,points in regions}
for name, points in regions:
    assignment[masks[name]]=names.index(name)
# The near feather was originally split between the rear wing and body.
# Protect both complete feelers before inferring unassigned edge pixels.
near_feeler=polygon([(295,326),(330,327),(372,337),(414,361),(446,393),(467,434),
                     (479,500),(455,482),(446,443),(398,421),(353,398),(313,362)])
far_feeler=polygon([(49,388),(145,386),(235,349),(291,361),(344,401),(369,455),
                    (375,502),(355,495),(341,451),(316,431),(231,478),(130,488),(82,448)])
feelers=near_feeler|far_feeler
masks['body']|=feelers
assignment[feelers]=names.index('body')
unassigned=(assignment==names.index('body'))&~masks['body']
nearest=np.argmin(np.stack([cv2.distanceTransform((~masks[name]).astype('uint8'),
                        cv2.DIST_L2,3) for name in names]),axis=0)
assignment[unassigned]=nearest[unassigned]
meta={}
recomposed=np.zeros_like(a)
for i,name in enumerate(names):
    mask=(assignment==i).astype('uint8')
    # Painted overlap underneath neighbouring wing planes/neck prevents seams
    # opening during the fan stroke. Only existing silhouette pixels are used.
    if name.startswith('wing_'):
        mask=cv2.dilate(mask,np.ones((31,31),np.uint8))
        # A wing must not carry a second, detached copy of either feather.
        mask[feelers]=0
    elif name in ('silk_a','silk_b','tail'):
        mask=cv2.dilate(mask,np.ones((7,7),np.uint8))
    part=a.copy(); part[mask==0,3]=0
    y,x=np.where(part[:,:,3]>0)
    assert len(x),name
    x0,y0=max(0,int(x.min())-3),max(0,int(y.min())-3)
    x1,y1=min(image.width,int(x.max())+4),min(image.height,int(y.max())+4)
    Image.fromarray(part[y0:y1,x0:x1]).save(PARTS/(name+'.png'))
    meta[name]=dict(x=x0,y=y0,w=x1-x0,h=y1-y0)
    selected=assignment==i; recomposed[selected]=part[selected]
assert np.array_equal(recomposed[:,:,3],a[:,:,3]), 'Cutout alpha changed'
(PARTS/'meta.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
for name in ['rigkit.py','rigutil.py']:
    shutil.copyfile(ROOT/'tools/SilkMothRig'/name,PARTS.parent/name)
(SOURCE/'generation.json').write_text(json.dumps({'model':'gpt-image-2.5-sunburst',
 'endpoint':'https://cpa.yuseus.io/v1/','mode':'official imagegen CLI edit with small moth style reference',
 'prompt':'character-prompt.txt','reference':'source_assets/monsters/silk_moth/character_final.png',
 'raw_size':image.size,'parts':names,'alpha_partition':'exact',
 'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.glob('character-*.png')}},indent=2),encoding='utf-8')
print('Great moth RGBA parts prepared; silhouette alpha preserved.')
