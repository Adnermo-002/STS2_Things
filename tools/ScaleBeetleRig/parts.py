"""Separate the canonical painting; reconstruct only occluded joint/plate pixels."""
from pathlib import Path
import json
import hashlib
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import binary_fill_holes, distance_transform_edt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = np.array(Image.open(ROOT / 'source_assets/monsters/scale_beetle.png').convert('RGBA'))
H, W = SRC.shape[:2]
RGB = SRC[:, :, :3]
A = SRC[:, :, 3] > 0
Y, X = np.indices((H, W))


def poly(points):
    mask = np.zeros((H, W), np.uint8)
    cv2.fillPoly(mask, [np.array(points, np.int32)], 1)
    return mask.astype(bool)


def dilate(mask, radius):
    return cv2.dilate(mask.astype(np.uint8), cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))) > 0


def largest(mask):
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    return labels == (1 + stats[1:, cv2.CC_STAT_AREA].argmax()) if count > 1 else mask


remaining = A.copy()
masks = {}


def take(name, mask):
    masks[name] = mask & remaining
    remaining[masks[name]] = False
    return masks[name]


blue = A & (RGB[:, :, 2] > RGB[:, :, 0] * 1.06) & (RGB[:, :, 1] > RGB[:, :, 0] * 1.08)
antennae = binary_fill_holes(dilate(blue & (Y < 584) & (X < 565) & ((Y < 495) | (X < 152)), 1)) & A
left = poly([(0, 0), (445, 0), (360, 75), (280, 125), (210, 190), (162, 270),
             (115, 350), (103, 450), (107, 505), (108, 590), (0, 590)])
take('antenna_far', antennae & left)
take('antenna_near', antennae & ~left)
eye = largest(blue & poly([(133, 560), (253, 553), (267, 630), (226, 669), (141, 665)]))
take('eye', dilate(binary_fill_holes(eye), 2))

take('jaw_far', poly([(53, 619), (72, 625), (76, 654), (66, 670), (54, 687),
                      (55, 716), (36, 714), (22, 683), (28, 649)]))
take('jaw_near', poly([(150, 655), (180, 654), (201, 671), (207, 689), (197, 720),
                       (173, 739), (139, 747), (96, 746), (78, 733), (129, 717),
                       (149, 700), (136, 681)]))

leg_polygons = {
    'leg_front': [(439, 638), (446, 672), (426, 690), (424, 721), (404, 742),
                  (391, 772), (365, 791), (343, 795), (315, 825), (292, 846),
                  (264, 839), (251, 872), (224, 854), (195, 862), (111, 857),
                  (58, 875), (10, 877), (9, 858), (62, 826), (109, 818),
                  (174, 820), (192, 782), (216, 794), (251, 760), (277, 763),
                  (298, 752), (315, 742), (310, 707), (338, 713), (353, 681),
                  (385, 657), (413, 638)],
    'leg_middle': [(607, 642), (631, 647), (646, 677), (639, 702), (653, 749),
                   (685, 821), (701, 847), (756, 873), (754, 883), (714, 885),
                   (671, 869), (654, 842), (621, 749), (605, 718), (583, 738),
                   (553, 729), (545, 707), (554, 682), (578, 655)],
    'leg_rear': [(878, 569), (895, 571), (901, 592), (894, 620), (912, 625),
                 (922, 665), (918, 710), (927, 772), (940, 815), (993, 835),
                 (1036, 850), (1030, 865), (969, 863), (933, 846), (914, 844),
                 (903, 828), (894, 770), (884, 695), (879, 653), (852, 704),
                 (828, 739), (815, 757), (788, 758), (772, 747), (760, 724),
                 (768, 699), (791, 662), (818, 621), (848, 582)],
    'leg_far_front': [(280, 648), (315, 672), (270, 705), (232, 729), (178, 748),
                      (88, 758), (52, 767), (0, 773), (0, 751), (45, 732),
                      (87, 733), (172, 708), (217, 699), (252, 669)],
    'leg_far_middle': [(606, 722), (624, 739), (605, 770), (573, 809),
                       (544, 820), (493, 819), (493, 806), (545, 791), (571, 747)],
}
grey = (RGB[:, :, 2] > RGB[:, :, 0] * 0.83) & (RGB[:, :, 2] > RGB[:, :, 1] * 0.80)
feet = {
    'leg_middle': poly([(665, 842), (698, 842), (759, 868), (759, 883), (669, 883)]),
    'leg_rear': poly([(914, 818), (945, 816), (1039, 846), (1039, 868), (914, 858)]),
    'leg_far_front': poly([(0, 735), (82, 728), (89, 761), (0, 780)]),
    'leg_far_middle': poly([(490, 799), (552, 790), (576, 803), (569, 823), (490, 825)]),
}
for name, points in leg_polygons.items():
    shape = poly(points)
    if name == 'leg_front':
        take(name, dilate(shape, 2) | (dilate(shape, 13) & grey))
    else:
        take(name, dilate(dilate(shape, 13) & grey & A, 2) | feet[name])

take('collar', poly([(402, 288), (428, 306), (469, 329), (488, 332), (510, 367),
                     (524, 409), (499, 458), (487, 488), (479, 549), (489, 627),
                     (487, 645), (461, 642), (444, 610), (430, 532), (417, 462),
                     (404, 397), (397, 344)]))
take('neck_shield', poly([(310, 315), (335, 334), (373, 377), (394, 423), (410, 477),
                          (420, 543), (417, 590), (404, 624), (374, 643), (343, 644),
                          (316, 620), (302, 561), (289, 501), (278, 465),
                          (296, 418), (299, 367)]))
take('shell_far', poly([(474, 336), (574, 303), (650, 296), (695, 278), (705, 309),
                        (789, 326), (850, 312), (850, 351), (951, 378), (950, 410),
                        (1054, 480), (1129, 551), (1129, 574), (1091, 585),
                        (1017, 531), (978, 511), (909, 469), (868, 450),
                        (784, 431), (695, 422), (662, 398), (596, 393),
                        (540, 411), (489, 462), (473, 416)]))
take('shell_near', poly([(490, 474), (506, 446), (544, 421), (597, 401), (657, 412),
                         (701, 451), (770, 451), (851, 445), (910, 484), (948, 511),
                         (1028, 535), (1130, 638), (1128, 666), (1075, 720),
                         (989, 764), (867, 785), (750, 795), (638, 778),
                         (555, 756), (515, 719), (490, 663), (477, 604), (467, 524)]))
take('head', poly([(0, 589), (166, 486), (224, 443), (229, 392), (239, 367),
                   (252, 390), (279, 432), (319, 423), (344, 491), (362, 556),
                   (397, 616), (402, 655), (328, 681), (218, 705), (0, 722)]))
body_hull = poly([(307, 603), (421, 508), (649, 421), (845, 473), (1023, 564),
                  (1074, 670), (986, 758), (840, 794), (653, 780), (466, 736), (346, 692)])
take('body', remaining & body_hull)
if remaining.any():
    names = list(masks)
    distances = np.stack([distance_transform_edt(~masks[name])[remaining] for name in names])
    nearest = distances.argmin(axis=0)
    ys, xs = np.nonzero(remaining)
    for index, name in enumerate(names):
        masks[name][ys[nearest == index], xs[nearest == index]] = True
    remaining[:] = False

# Restore hidden pieces beneath the plates and roots. The painterly colour field
# is extrapolated locally; no visible source pixel is recoloured.
extras = {
    'body': poly([(307, 603), (421, 508), (649, 421), (845, 473), (1023, 564),
                   (1074, 670), (986, 758), (840, 794), (653, 780), (466, 736), (346, 692)]),
    'head': poly([(102, 518), (251, 426), (318, 420), (387, 506), (420, 588),
                   (395, 646), (311, 674), (218, 699), (92, 695), (56, 649)]),
    'neck_shield': poly([(317, 372), (370, 390), (412, 484), (439, 589),
                          (409, 667), (350, 665), (307, 601), (287, 484)]),
    'collar': poly([(416, 361), (473, 347), (515, 405), (516, 594),
                     (484, 668), (437, 630), (413, 514)]),
    'shell_far': poly([(503, 346), (617, 325), (780, 346), (939, 405),
                        (1030, 492), (1101, 558), (1039, 610), (891, 571),
                        (713, 521), (578, 484), (504, 448)]),
    'shell_near': poly([(496, 481), (566, 443), (687, 445), (846, 476), (1028, 566),
                         (1090, 650), (990, 736), (843, 771), (689, 759), (553, 715), (501, 622)]),
}

ORDER = ['ground_shadow', 'leg_far_front', 'leg_far_middle', 'leg_far_rear', 'body', 'shell_far',
         'antenna_far', 'head', 'neck_shield', 'collar', 'shell_near', 'leg_rear',
         'leg_middle', 'eye', 'jaw_far', 'jaw_near', 'leg_front', 'antenna_near']


def reconstruct(visible, extra, darken=1, gold=False):
    region = visible | extra
    donors = visible
    if gold:
        donors = visible & (RGB[:, :, 0] > RGB[:, :, 2] * 1.2)
    _, indices = distance_transform_edt(~donors, return_indices=True)
    colour = RGB[indices[0], indices[1]].astype(np.float32)
    colour = cv2.GaussianBlur(colour, (0, 0), 3.0)
    colour[visible] = RGB[visible]
    alpha = np.where(region, 255, 0).astype(np.uint8)
    alpha[visible] = SRC[:, :, 3][visible]
    # Fade only the farthest occluded extensions; the original edge stays crisp.
    return np.dstack([np.clip(colour * darken, 0, 255).astype(np.uint8), alpha])


parts = {}
for name, mask in masks.items():
    extra = extras.get(name, np.zeros_like(A)) & ~mask
    if name.startswith('leg_'):
        # End caps at the roots are hidden under a coxa/shell, giving the joint
        # overlap through the full movement range without splitting a limb image.
        extra = dilate(mask, 8) & A & ~mask
    above = np.zeros_like(A)
    for other in ORDER[ORDER.index(name) + 1:]:
        if other in masks:
            above |= masks[other]
    extra &= above
    parts[name] = reconstruct(mask, extra, gold=name in ('shell_near', 'shell_far', 'collar', 'neck_shield'))
    if name.startswith('antenna') or name == 'head':
        count, labels, stats, _ = cv2.connectedComponentsWithStats((parts[name][:, :, 3] > 0).astype(np.uint8))
        for component in range(1, count):
            if stats[component, cv2.CC_STAT_AREA] < 130:
                parts[name][labels == component, 3] = 0

# A sixth, far rear support uses the painted far middle leg with a deeper shade.
parts['leg_far_rear'] = cv2.warpAffine(parts['leg_far_middle'], np.float32([[1, 0, 225], [0, 1, 8]]),
                                      (W, H), flags=cv2.INTER_NEAREST)
parts['leg_far_rear'][:, :, :3] = (parts['leg_far_rear'][:, :, :3] * 0.72).astype(np.uint8)

# One disconnected sliver at the far antenna tip was nearest to the wrong chain.
# Transfer its original pixels to the far chain, rather than animating it as debris.
count, labels, stats, _ = cv2.connectedComponentsWithStats((parts['antenna_near'][:, :, 3] > 0).astype(np.uint8))
main_component = 1 + stats[1:, cv2.CC_STAT_AREA].argmax()
for component in range(1, count):
    if component != main_component:
        selected = labels == component
        parts['antenna_far'][selected] = parts['antenna_near'][selected]
        parts['antenna_near'][selected] = 0
        masks['antenna_far'][selected] = True
        masks['antenna_near'][selected] = False

# Selected image-edit results are versioned source inputs. Keep exact alpha and
# untouched painting pixels; fail loudly if future segmentation invalidates them.
patch_root = ROOT / 'source_assets/monsters/scale_beetle_rig_patches'
if '--raw' not in sys.argv and (patch_root / 'manifest.json').exists():
    patch_records = json.loads((patch_root / 'manifest.json').read_text())['parts']
    for name, record in patch_records.items():
        crop = record['crop']
        x, y, w, h = [crop[key] for key in ('x', 'y', 'w', 'h')]
        original = parts[name][y:y+h, x:x+w]
        assert hashlib.sha256(original.tobytes()).hexdigest() == record['raw_rgba_sha256'], f'{name}: patch needs re-registration after segmentation changes'
        edited = np.array(Image.open(patch_root / f'{name}.png').convert('RGBA'))
        allowed = np.array(Image.open(patch_root / f'{name}_mask.png')) > 128
        assert np.array_equal(original[:, :, 3], edited[:, :, 3]), f'{name}: alpha drift'
        assert np.array_equal(original[~allowed], edited[~allowed]), f'{name}: unmasked painting changed'
        parts[name][y:y+h, x:x+w] = edited

# The warm reflected colours inside the knee collars are still leg pixels.
# Restore those source pixels above the clean shell backing; colour thresholding
# alone can mistake these small reflections for the golden elytron.
for name, points in {
    'leg_middle': [(618, 663), (635, 664), (645, 677), (642, 696), (630, 705), (611, 699), (610, 680)],
    'leg_rear': [(893, 589), (905, 590), (921, 603), (922, 619), (908, 639), (891, 649), (880, 635), (883, 616)],
}.items():
    selected = poly(points) & A
    parts[name][selected] = SRC[selected]
    masks[name] |= selected

if '--raw' not in sys.argv:
    # The olive chip beneath the jaw is chin paint, not the blue far front leg.
    # Giving it to the head keeps it attached when the beetle raises its muzzle.
    leg = parts['leg_far_front']
    chin = (leg[:, :, 3] > 0) & (X > 90) & (X < 280) & (Y < 720)
    chin &= RGB[:, :, 2] < RGB[:, :, 1] * 0.78
    parts['head'][chin] = SRC[chin]
    masks['head'] |= chin
    leg[chin] = 0
    masks['leg_far_front'][chin] = False
    for name in ('leg_front', 'leg_middle', 'leg_rear', 'leg_far_front', 'leg_far_middle', 'leg_far_rear'):
        count, labels, stats, _ = cv2.connectedComponentsWithStats((parts[name][:, :, 3] > 0).astype(np.uint8))
        largest_component = 1 + stats[1:, cv2.CC_STAT_AREA].argmax()
        for component in range(1, count):
            if component != largest_component and stats[component, cv2.CC_STAT_AREA] < 130:
                parts[name][labels == component] = 0

shadow = np.zeros_like(SRC)
shadow[:, :, :3] = (9, 12, 15)
shadow[:, :, 3] = (60*np.exp(-2*((X-578)/470)**2-2*((Y-864)/11)**2)).astype(np.uint8)
parts['ground_shadow'] = shadow

GLOW_OF = {'eye_glow': 'eye', 'antenna_far_glow': 'antenna_far',
           'antenna_near_glow': 'antenna_near', 'shell_far_glow': 'shell_far',
           'shell_near_glow': 'shell_near', 'collar_glow': 'collar'}
for glow, base in GLOW_OF.items():
    tex = parts[base]
    if base.startswith('antenna') or base == 'eye':
        bright = (RGB[:, :, 1] > 155) & (RGB[:, :, 2] > 140) & (tex[:, :, 3] > 0) & masks[base]
        colour = (90, 210, 235)
    else:
        bright = (RGB[:, :, 0] > 220) & (RGB[:, :, 1] > 195) & (RGB[:, :, 2] < 190) & masks[base]
        colour = (255, 192, 60)
    alpha = cv2.GaussianBlur(bright.astype(np.float32), (0, 0), 2.5) * 165
    rgba = np.zeros_like(SRC)
    rgba[:, :, :3] = colour
    rgba[:, :, 3] = np.minimum(alpha, tex[:, :, 3]).astype(np.uint8)
    rgba[rgba[:, :, 3] == 0, :3] = 0
    parts[glow] = rgba

out = HERE / 'parts'
out.mkdir(exist_ok=True)
(out / 'visible_masks').mkdir(exist_ok=True)
meta = {}
for name, rgba in parts.items():
    # Shared bounds let the glow use exactly the host's mesh, including joints.
    bounds_image = parts[GLOW_OF[name]] if name in GLOW_OF else rgba
    ys, xs = np.nonzero(bounds_image[:, :, 3])
    x0, y0 = max(0, xs.min() - 2), max(0, ys.min() - 2)
    x1, y1 = min(W, xs.max() + 3), min(H, ys.max() + 3)
    Image.fromarray(rgba[y0:y1, x0:x1]).save(out / f'{name}.png')
    if name in masks:
        Image.fromarray((masks[name][y0:y1, x0:x1]*255).astype(np.uint8)).save(out / 'visible_masks' / f'{name}.png')
    meta[name] = dict(x=int(x0), y=int(y0), w=int(x1-x0), h=int(y1-y0))
(out / 'meta.json').write_text(json.dumps(meta, indent=2))
(out / 'order.json').write_text(json.dumps(dict(order=ORDER, glow_of=GLOW_OF), indent=2))

preview = HERE / 'out'
preview.mkdir(exist_ok=True)
canvas = Image.new('RGBA', (W, H))
for name in ORDER:
    canvas.alpha_composite(Image.fromarray(parts[name]))
canvas.save(preview / 'rest-composite.png')
source_float = SRC.astype(float) / 255
result_float = np.array(canvas).astype(float) / 255
error = np.abs(source_float[:, :, :3] * source_float[:, :, 3:] - result_float[:, :, :3] * result_float[:, :, 3:])
print(f'parts={len(parts)} source-composite mean RGB error={error.mean()*255:.3f}/255')

sheet = Image.new('RGB', (1200, ((len(ORDER)+3)//4)*270), '#20242a')
draw = ImageDraw.Draw(sheet)
font_path = Path('C:/Windows/Fonts/consola.ttf')
font = ImageFont.truetype(str(font_path), 15) if font_path.exists() else ImageFont.load_default()
for index, name in enumerate(ORDER):
    item = Image.open(out / f'{name}.png')
    item.thumbnail((280, 225), Image.Resampling.LANCZOS)
    x, y = (index % 4) * 300, (index // 4) * 270
    sheet.paste(item, (x+(300-item.width)//2, y+28+(230-item.height)//2), item)
    draw.text((x+8, y+5), name, fill='white', font=font)
sheet.save(preview / 'parts-sheet.jpg')
