"""Segment the Bowlbug Progenitor full texture into rig parts.

Seeds (image px) are placed inside every part; a marker watershed over the
ink-darkness + hue-edge landscape splits the painting along its outlines.
"""
import numpy as np, cv2, json
from PIL import Image, ImageDraw
from skimage.segmentation import watershed

im = np.array(Image.open('src.png').convert('RGBA'))
rgb = im[..., :3]; a = im[..., 3]
H, W = a.shape
hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
h = hsv[..., 0].astype(int) * 2; s = hsv[..., 1].astype(int); v = hsv[..., 2].astype(int)
m = a > 0
pink = ((h >= 290) | (h < 12)) & (s > 60) & m
orange = (h >= 12) & (h < 50) & (s > 120) & m
teal = (h >= 160) & (h < 210) & (s > 60) & m
green = (h >= 50) & (h < 110) & m
yy, xx = np.mgrid[:H, :W]

def disc(x, y, r): return (xx - x) ** 2 + (yy - y) ** 2 <= r * r

# name -> list of (x, y, r[, class])
SEEDS = {
    'membrane_rear': [(900, 520, 14), (1200, 625, 6), (960, 300, 8), (820, 480, 12), (985, 210, 5), (950, 270, 7), (880, 400, 8), (900, 470, 8), (930, 520, 8), (980, 560, 5), (770, 590, 8)],
    'membrane_front': [(560, 420, 12), (480, 560, 12), (390, 625, 8), (600, 500, 10), (590, 576, 8), (620, 560, 6), (520, 330, 6), (440, 500, 8)],
    'egg_sac': [(1100, 300, 60), (1020, 450, 12), (1000, 380, 12), (1000, 420, 14), (1250, 420, 40), (1150, 500, 30), (1300, 250, 20), (1150, 170, 25)],
    'rear_shell': [(1050, 150, 14), (1100, 60, 10), (1350, 320, 14), (1385, 460, 12), (1300, 530, 10), (1150, 570, 8),
                   (1050, 585, 8), (1330, 150, 8), (1040, 600, 8), (1080, 630, 6), (1170, 590, 5), (1230, 590, 6), (1125, 597, 5), (1305, 572, 5), (1275, 555, 6), (1045, 35, 20), (1240, 90, 20), (1428, 380, 8), (1200, 580, 6)],
    'shell_mid': [(750, 250, 20), (700, 400, 16), (650, 300, 10), (900, 90, 12), (800, 110, 10), (705, 95, 25),
                  (635, 190, 22), (870, 225, 30), (800, 380, 12), (940, 150, 8), (760, 440, 12), (700, 470, 8), (850, 330, 8)],
    'dome2': [(660, 540, 8), (740, 540, 8), (655, 610, 7), (745, 620, 6), (755, 565, 5)],
    'dome3': [(880, 580, 10), (900, 630, 6), (975, 560, 8)],
    'leaf_plate': [(560, 250, 10), (580, 350, 12), (540, 200, 6), (600, 420, 10)],
    'crest_1': [(282, 100, 4), (290, 150, 7), (295, 200, 5)],
    'crest_2': [(322, 150, 4), (332, 200, 8), (335, 250, 6)],
    'crest_3': [(385, 160, 5), (375, 210, 9), (365, 250, 6)],
    'crest_4': [(455, 180, 5), (435, 225, 9), (420, 265, 7)],
    'crest_5': [(505, 260, 4), (490, 290, 7), (480, 315, 5)],
    'shell_front': [(330, 400, 12), (420, 370, 14), (460, 450, 10), (340, 305, 25), (270, 460, 8), (260, 540, 8), (330, 525, 8), (400, 490, 8), (230, 500, 6)],
    'head': [(230, 300, 10), (180, 400, 9), (230, 215, 22), (200, 350, 22), (200, 560, 8), (250, 610, 8), (320, 560, 9),
             (340, 630, 7), (215, 650, 6), (120, 470, 6), (262, 250, 6), (380, 560, 8), (160, 450, 8), (280, 600, 8), (360, 590, 7), (420, 540, 5)],
    'mandible_upper': [(40, 580, 8), (30, 640, 6), (70, 560, 6)],
    'mandible_lower': [(150, 665, 8), (200, 638, 6), (110, 682, 5), (222, 622, 4), (213, 650, 4)],
    'eye': [(160, 560, 18), (150, 600, 10), (175, 530, 8)],
    'leg1_upper': [(578, 605, 5), (530, 640, 9)],
    'leg1_shin': [(465, 680, 9), (450, 715, 7)],
    'leg1_claw': [(410, 765, 4), (430, 752, 4)],
    'leg2_upper': [(688, 600, 4)],
    'leg2_shin': [(722, 670, 10), (742, 715, 8)],
    'leg2_claw': [(760, 766, 3)],
    'leg3_upper': [(957, 612, 4)],
    'leg3_shin': [(990, 670, 9), (1008, 710, 7)],
    'leg3_claw': [(1050, 752, 4)],
    'leg4_upper': [(1143, 627, 5)],
    'leg4_shin': [(1185, 680, 9), (1208, 712, 7)],
    'leg4_claw': [(1255, 742, 4)],
    'leg5_upper': [(1326, 603, 5)],
    'leg5_shin': [(1350, 655, 9), (1372, 690, 6)],
    'leg5_claw': [(1410, 721, 4)],
}
PARTS = list(SEEDS)
markers = np.zeros((H, W), np.int32)
for i, p in enumerate(PARTS, 1):
    for sd in SEEDS[p]:
        x, y, r = sd[:3]
        markers[disc(x, y, r) & (a > 128)] = i
# pupil: dark core inside the eye
eye_disc = disc(150, 565, 52)
pupil = eye_disc & (v < 70) & m
pupil = cv2.morphologyEx(pupil.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
n, lab, st, _ = cv2.connectedComponentsWithStats(pupil.astype(np.uint8), 8)
k = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA]) if n > 1 else 0
pupil = lab == k
PARTS.append('pupil'); markers[cv2.erode(pupil.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = len(PARTS)

lum = cv2.GaussianBlur(v.astype(np.float32), (0, 0), 1.0)
elev = 255 - lum
cls = np.zeros((H, W), np.uint8); cls[pink] = 1; cls[orange] = 2; cls[teal] = 3; cls[green] = 4
edge = np.zeros((H, W), np.float32)
for kk in (1, 2, 3, 4):
    mk = cv2.GaussianBlur((cls == kk).astype(np.float32), (0, 0), 1.2)
    edge += np.hypot(cv2.Sobel(mk, cv2.CV_32F, 1, 0), cv2.Sobel(mk, cv2.CV_32F, 0, 1))
elev = elev + edge * 60
# hand-drawn barriers along weak (bevel-highlight) edges
BARRIERS = [
    [(220, 502), (235, 552), (280, 557), (340, 555), (385, 530), (432, 497)],   # front plate / cheek
    [(321, 128), (303, 170), (296, 205), (292, 250)],   # crest 1|2
    [(383, 132), (360, 165), (343, 205), (336, 255)],   # crest 2|3
]
bar = np.zeros((H, W), np.uint8)
for pl in BARRIERS:
    cv2.polylines(bar, [np.array(pl, np.int32)], False, 1, 2)
# egg sac outline: filled orange blob + its light rim, used as a barrier ring
from scipy import ndimage as ndi
og = orange.copy(); og[:, :800] = False
og = cv2.morphologyEx(og.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
og = ndi.binary_fill_holes(og)
n_, lab_, st_, _ = cv2.connectedComponentsWithStats(og.astype(np.uint8), 8)
og = lab_ == 1 + np.argmax(st_[1:, cv2.CC_STAT_AREA])
sac = cv2.dilate(og.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
ring = sac - cv2.erode(sac, np.ones((3, 3), np.uint8))
bar |= ring.astype(np.uint8)
np.save('sac_mask.npy', sac > 0)
elev = elev + bar * 600.0
labels = watershed(elev, markers, mask=m)
# orange pixels in the face always belong to a mandible
iu, il = PARTS.index('mandible_upper') + 1, PARTS.index('mandible_lower') + 1
face_or = cv2.dilate((orange & (xx < 270) & (yy > 520)).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
face_or &= m & np.isin(labels, [iu, il, PARTS.index('head') + 1])
from scipy import ndimage as ndi2
du = ndi2.distance_transform_edt(labels != iu); dl = ndi2.distance_transform_edt(labels != il)
labels[face_or & (du < dl)] = iu; labels[face_or & (du >= dl)] = il
# crest spikes are pink/purple: green texels labelled crest belong to the horn/front plate
crest_ids = [PARTS.index(f'crest_{i}') + 1 for i in range(1, 6)]
gcrest = np.isin(labels, crest_ids) & green & (s > 50)
gcrest = cv2.morphologyEx(gcrest.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
ih, isf = PARTS.index('head') + 1, PARTS.index('shell_front') + 1
dh = ndi2.distance_transform_edt(labels != ih); dsf = ndi2.distance_transform_edt(labels != isf)
labels[gcrest & (dh <= dsf)] = ih; labels[gcrest & (dh > dsf)] = isf
print('green crest texels moved', int(gcrest.sum()))
np.save('labels.npy', labels)
json.dump(PARTS, open('parts_list.json', 'w'))

pal = np.random.default_rng(7).integers(30, 255, (len(PARTS) + 1, 3))
vis = rgb.astype(float) * 0.3
for i in range(1, len(PARTS) + 1):
    vis[labels == i] += pal[i] * 0.7
bnd = cv2.morphologyEx(labels.astype(np.uint16), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
vis[bnd & m] = [255, 255, 255]
out = Image.fromarray(np.clip(vis, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(out)
for i, p in enumerate(PARTS, 1):
    ys, xs = np.nonzero(labels == i)
    if len(xs): d.text((int(np.median(xs)) - 15, int(np.median(ys))), p, fill='white')
out.save('vis_seg.jpg', quality=90)
# overlay of boundaries on original, for judging accuracy
ov = rgb.copy(); ov[bnd & m] = [255, 0, 255]
Image.fromarray(ov).save('vis_bnd.png')
print({p: int((labels == i).sum()) for i, p in enumerate(PARTS, 1)})
