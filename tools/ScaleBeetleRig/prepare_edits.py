"""Prepare tightly masked image edits. API credentials never enter these files."""
from pathlib import Path
import json
import hashlib
import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = ROOT / 'tmp/imagegen/scale-beetle'
PROMPTS = HERE / 'art_edits'
WORK.mkdir(parents=True, exist_ok=True)
PROMPTS.mkdir(exist_ok=True)

REQUESTS = {
    'head': 'Reconstruct the olive-green chitin HEAD PLATE behind the separate eye, two gold jaws and antenna roots. Remove the smeared eye/socket remnants and blurred gold patches only inside the edit mask. Paint clean angular olive facets there so the separate eye and jaw sprites can move over an intact head surface. Do not add an eye, mouth, teeth or antennae to this isolated head layer. Keep the existing small horn and all unmasked head painting exactly as shown.',
    'shell_near': 'Repair this isolated large GOLDEN NEAR ELYTRON plate. Completely remove the dark grey leg/knee fragments and blurred inpaint streaks in the masked areas. Continue the surrounding flat ochre/gold angular chitin facets and the existing pale-gold curved markings across those occluded holes. Preserve the entire unmasked spiral pattern, upper spike ridge and the existing outer contour. No legs, sockets, extra ornaments or new spikes.',
    'shell_far': 'Repair this isolated GOLDEN FAR ELYTRON plate. Fill the masked lower/hidden edge continuously with matching gold and dark olive chitin facets, removing little leftover dark shards and smeared streaks. Preserve all unmasked golden spikes, painted edges, silhouette and original broad angular shading. It is a flat painted sprite, not realistic metal.',
    'body': 'Repair this isolated hidden UNDERBODY of the golden beetle. In the masked area replace the stretched rectangular stripes and blocky extrapolation with coherent dark olive and muted ochre chitin planes. This is a simple low-contrast beetle abdomen underneath the separate golden armor plates. Match the original polygonal painted facets and brush-edge softness from the reference. No limbs, eye, shells, gems, new line ornaments or added anatomy. Preserve the visible unmasked lower abdominal edge exactly.',
}
records = {}
for name, request in REQUESTS.items():
    part_path = HERE / 'parts' / f'{name}.png'
    rgba = np.array(Image.open(part_path).convert('RGBA'))
    visible = np.array(Image.open(HERE / 'parts/visible_masks' / f'{name}.png')) > 128
    alpha = rgba[:, :, 3] > 0
    editable = alpha & ~visible
    if name.startswith('shell'):
        rgb = rgba[:, :, :3].astype(float)
        contamination = (rgb[:, :, 2] > rgb[:, :, 0]*0.83) & (rgb[:, :, 2] > rgb[:, :, 1]*0.80)
        editable |= contamination & alpha
    editable = (cv2.dilate(editable.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0) & alpha
    h, w = alpha.shape
    scale = min(1.45, 880 / max(w, h))
    size = (round(w*scale), round(h*scale))
    offset = ((1024-size[0])//2, (1024-size[1])//2)
    target = Image.new('RGBA', (1024, 1024), (255, 0, 255, 255))
    target.alpha_composite(Image.fromarray(rgba).resize(size, Image.Resampling.LANCZOS), offset)
    target.save(WORK / f'{name}-target.png')
    mask = Image.new('RGBA', (1024, 1024), (255, 255, 255, 255))
    edit_alpha = Image.fromarray(np.where(editable, 0, 255).astype(np.uint8)).resize(size, Image.Resampling.NEAREST)
    mask_patch = Image.new('RGBA', size, (255, 255, 255, 255))
    mask_patch.putalpha(edit_alpha)
    mask.paste(mask_patch, offset)
    mask.save(WORK / f'{name}-mask.png')
    Image.fromarray((editable*255).astype(np.uint8)).save(WORK / f'{name}-editable.png')
    prompt = f'''Use case: precise-object-edit
Asset type: production 2D skeletal-animation texture restoration, not a redesign.
Input image 1: EDIT TARGET, an isolated sprite part on a flat pure-magenta background.
Input image 2: STYLE/IDENTITY REFERENCE ONLY, the complete original golden beetle painting. Do not reproduce the whole beetle.
Primary request: {request}
Style invariants: Keep EXACTLY the reference's restrained Slay-the-Spire-like 2D game illustration style: broad flat angular painted facets, subdued mustard-gold/ochre/olive colors, softly painted dark contour, minimal texture. Preserve the precise perspective and proportions. No 3D render, shiny metal, photoreal texture, gradients, extra detail, black comic outline, cartoon redesign or style transfer.
Composition invariants: Keep the part at its exact current position, orientation, scale and canvas coordinates in image 1. Never recenter, stretch, crop, enlarge or rotate it. Output exactly 1024x1024. Keep the pure magenta background (RGB 255,0,255) unchanged. No text or labels.
Mask rule: Change only the masked restoration regions. Preserve all unmasked painting. The result must fit back into the original game sprite with invisible seams.
'''
    (PROMPTS / f'{name}.txt').write_text(prompt, encoding='utf-8')
    records[name] = dict(size=[w, h], scaled_size=list(size), offset=list(offset),
                         source_sha256=hashlib.sha256(part_path.read_bytes()).hexdigest(),
                         editable_pixels=int(editable.sum()), prompt=f'{name}.txt')
(WORK / 'manifest.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
print(json.dumps({name:record['editable_pixels'] for name,record in records.items()}))
