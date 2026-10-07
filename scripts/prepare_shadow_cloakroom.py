"""Prepare the native portrait, transparent relic textures and offline reviews."""
from pathlib import Path
import json
import numpy as np
import cv2
from PIL import Image, ImageOps, ImageFilter, ImageDraw
from native_event_preview import render_event

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source_assets/events/shadow_cloakroom'
BUILD = ROOT / 'build/shadow_cloakroom'
BUILD.mkdir(parents=True, exist_ok=True)
size = (3440, 1616)
raw = Image.open(ROOT / 'output/imagegen/shadow_cloakroom/event_portrait_v1.png').convert('RGB')
raw = raw.crop((2, 2, raw.width - 2, raw.height - 2))
painting = ImageOps.fit(raw, size, Image.Resampling.LANCZOS)
painting.save(SOURCE / 'portrait_unframed.png')
x = np.arange(size[0], dtype=np.float32)[None, :] * (2662 / 3440) - 371
y = np.arange(size[1], dtype=np.float32)[:, None] * (1251 / 1616) - 79

def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * t * (t * (t * 6 - 15) + 10)

# The generated painting already includes dark peripheral scenery. A broad
# light field gently joins that scenery to native black; there is no cutout.
radius = ((x - 460) / 800) ** 2 + ((y - 540) / 680) ** 2
light = .55 + .45 * np.exp(-radius)
light *= smooth((x + 170) / 370)
light *= smooth((y + 110) / 320)
light *= 1 - smooth((y - 830) / 380)
light *= 1 - smooth((x - 780) / 740)
portrait = Image.fromarray(np.uint8(np.clip(np.rint(np.asarray(painting) * light[:, :, None]), 0, 255))).convert('RGBA')
Image.fromarray(np.uint8(np.rint(light * 255))).save(SOURCE / 'peripheral_fade_mask.png')
portrait.save(SOURCE / 'portrait_master.png')
portrait.save(ROOT / 'images/events/shadow_cloakroom.png')
portrait.convert('RGB').resize((1720, 808), Image.Resampling.LANCZOS).save(BUILD / 'event-art.jpg', quality=95)

icon = Image.open(ROOT / 'output/imagegen/shadow_cloakroom/claim_ticket_v1.png').convert('RGBA')
rgba = np.array(icon)
alpha = rgba[:, :, 3].copy()
alpha[alpha < 12] = 0
magenta = (rgba[:, :, 0] > 150) & (rgba[:, :, 2] > 150) & (rgba[:, :, 1] < 80)
alpha[magenta] = 0
count, labels, stats, centers = cv2.connectedComponentsWithStats((alpha > 0).astype('uint8'), 8)
if count < 2:
    raise RuntimeError('Claim ticket has no visible subject')
largest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
alpha[labels != largest] = 0
rgba[:, :, 3] = alpha
icon = Image.fromarray(rgba)
icon.save(SOURCE / 'claim_ticket_cutout.png')
icon = icon.resize((256, 256), Image.Resampling.LANCZOS)
icon_path = ROOT / 'images/relics/shadow_claim_ticket.png'
icon.save(icon_path)
outline_alpha = icon.getchannel('A').filter(ImageFilter.MaxFilter(9))
outline = Image.new('RGBA', (256, 256), 'white')
outline.putalpha(outline_alpha)
outline_path = ROOT / 'images/atlases/relic_outline_atlas.sprites/shadow_claim_ticket_outline.png'
outline.save(outline_path)
for folder, path in (('relic_atlas.sprites', icon_path), ('relic_outline_atlas.sprites', outline_path)):
    texture_path = 'res://' + path.relative_to(ROOT).as_posix()
    (ROOT / 'images/atlases' / folder / 'shadow_claim_ticket.tres').write_text(
        '[gd_resource type="AtlasTexture" load_steps=2 format=3]\n\n'
        f'[ext_resource type="Texture2D" path="{texture_path}" id="1"]\n\n'
        '[resource]\natlas = ExtResource("1")\nregion = Rect2(0, 0, 256, 256)\n', 'utf-8')

sheet = Image.new('RGBA', (640, 320), '#16212b')
sheet.alpha_composite(icon, (24, 32))
sheet.alpha_composite(icon.resize((64, 64), Image.Resampling.LANCZOS), (350, 88))
sheet.alpha_composite(icon.resize((48, 48), Image.Resampling.LANCZOS), (490, 96))
ImageDraw.Draw(sheet).text((335, 182), '64 px', fill='white')
ImageDraw.Draw(sheet).text((480, 182), '48 px', fill='white')
sheet.convert('RGB').save(BUILD / 'relic-review.jpg', quality=95)
report = render_event(ROOT, 'SHADOW_CLOAKROOM', portrait, {'Gold': 25, 'Cards': 1, 'SmallGold': 15}, ('DEPOSIT', 'COINS'), BUILD)
report['review'] = 'Offline Pillow authoring preview; not a native capture or gameplay test.'
report['source_generation'] = 'User-authorized API via imagegen CLI, gpt-image-2.5-sunburst; native event used as style reference.'
(BUILD / 'art-review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
print(json.dumps(report, ensure_ascii=False))
