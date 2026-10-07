"""Composite continuous peripheral fades and offline bilingual event layouts."""
from pathlib import Path
import argparse
import json
import numpy as np
from PIL import Image, ImageOps
from native_event_preview import render_event

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--record-dir', default='build/practical_events')
parser.add_argument('--layout-only', action='store_true')
args = parser.parse_args()
BUILD = ROOT / args.record_dir
BUILD.mkdir(parents=True, exist_ok=True)
SIZE = (3440, 1616)


def smooth(value):
    value = np.clip(value, 0, 1)
    return value * value * value * (value * (value * 6 - 15) + 10)


# Coordinates are expressed in the actual overscanned native 1920x1080 view.
# This light field affects the whole painting rather than clipping an oval.
x = np.arange(SIZE[0], dtype=np.float32)[None, :] * (2662 / 3440) - 371
y = np.arange(SIZE[1], dtype=np.float32)[:, None] * (1251 / 1616) - 79
radius = ((x - 460) / 800) ** 2 + ((y - 540) / 680) ** 2
light = (.55 + .45 * np.exp(-radius)) * smooth((x + 170) / 370)
light *= smooth((y + 110) / 320) * (1 - smooth((y - 830) / 380))
light *= 1 - smooth((x - 780) / 740)

variables = {'Gold': 30, 'SaleGold': 200, 'SmallGold': 15, 'Candidates': 3, 'Heal': 4,
             'Offer': {'zhs': '锚', 'eng': 'Anchor'},
             'Relic': {'zhs': '金刚杵', 'eng': 'Vajra'},
             'Potion': {'zhs': '力量药水', 'eng': 'Strength Potion'},
             'Page': 1, 'Pages': 4}
card_examples = [{'Card': {'zhs': zh, 'eng': en}} for zh, en in
                 [('打击', 'Strike'), ('防御', 'Defend'), ('痛击+', 'Bash+')]]
report = {}
specs = [
    ('relic_workshop', ('TRADE', 'SELL', 'COINS'), 144),
    ('potion_tasting', ('SAMPLE', 'BUY', 'BARTER'), 144),
    ('narrow_gate', ('REMOVE_CARD', 'REMOVE_CARD', 'REMOVE_CARD', 'REROLL'), 144),
]
for event, options, minimum in specs:
    source = ROOT / f'source_assets/events/{event}'
    raw_path = ROOT / f'output/imagegen/{event}/portrait_v1.png'
    if args.layout_only:
        portrait = Image.open(ROOT / f'images/events/{event}.png').convert('RGBA')
    else:
        raw = Image.open(raw_path).convert('RGB')
        painting = ImageOps.fit(raw, SIZE, Image.Resampling.LANCZOS)
        painting.save(source / 'portrait_unframed.png')
        portrait = Image.fromarray(np.uint8(np.clip(np.rint(np.asarray(painting) * light[:, :, None]), 0, 255))).convert('RGBA')
        portrait.save(source / 'portrait_master.png')
        portrait.save(ROOT / f'images/events/{event}.png')
        Image.fromarray(np.uint8(np.rint(light * 255))).save(source / 'peripheral_fade_mask.png')
    values = dict(variables, Gold=25 if event == 'narrow_gate' else 30)
    report[event] = render_event(ROOT, event.upper(), portrait, values, options, BUILD / event,
                                 description_min_height=minimum,
                                 option_variables=card_examples if event == 'narrow_gate' else None)
    pages = []
    if event == 'relic_workshop':
        # Named examples exercise the worst five-button page; not live offers.
        pages = [('select', 'SELECT', 'SELECT_TRADE', ('TRADE', 'TRADE', 'TRADE', 'MORE', 'BACK')),
                 ('sell', 'SELECT', 'SELECT_SELL', ('SELL', 'SELL', 'SELL', 'MORE', 'BACK'))]
    if event == 'potion_tasting':
        pages = [('payment', 'PAYMENT', 'PAYMENT', ('GIVE', 'GIVE', 'GIVE', 'MORE', 'BACK')),
                 ('unavailable', 'INITIAL', 'INITIAL', ('WATER', 'CANNOT_RECEIVE', 'CANNOT_RECEIVE'))]
    if event == 'narrow_gate':
        pages = [('rerolled', 'INITIAL', 'REROLLED', ('REMOVE_CARD', 'REMOVE_CARD', 'REMOVE_CARD', 'REROLLED')),
                 ('empty', 'INITIAL', 'INITIAL', ('REST', 'REMOVE_LOCKED', 'REMOVE_LOCKED', 'NO_ALTERNATIVES'))]
    for name, page, description_page, keys in pages:
        overrides = None
        if page == 'SELECT':
            overrides = [{'Relic': {'zhs': zh, 'eng': en}} for zh, en in
                         [('金刚杵', 'Vajra'), ('奥利哈钢', 'Orichalcum'), ('铜质鳞片', 'Bronze Scales')]]
        if name == 'rerolled':
            overrides = card_examples
        if page == 'PAYMENT':
            overrides = [{'Potion': {'zhs': zh, 'eng': en}} for zh, en in
                         [('力量药水', 'Strength Potion'), ('格挡药水', 'Block Potion'), ('火焰药水', 'Fire Potion')]]
        report[event + '_' + name] = render_event(
            ROOT, event.upper(), portrait, values, keys, BUILD / event / name,
            page=page, description_min_height=144, description_page=description_page, option_variables=overrides)

overview = Image.new('RGB', (1920, 3240), 'black')
for index, (event, _, _) in enumerate(specs):
    overview.paste(Image.open(BUILD / event / 'event-layout-review.jpg'), (0, index * 1080))
overview.resize((1280, 2160), Image.Resampling.LANCZOS).save(BUILD / 'events-overview.jpg', quality=95)
report['method'] = 'Offline Pillow compositions with native fonts/buttons and native portrait overscan; no game or native probes.'
report['raw_images'] = {event: str(ROOT / f'output/imagegen/{event}/portrait_v1.png') for event, _, _ in specs}
(BUILD / 'art-layout-review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
