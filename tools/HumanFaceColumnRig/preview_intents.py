"""Offline UI layout projection, using native atlas sprites; never loads Godot/game."""
from pathlib import Path
import json
import re
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT.parent / 'STS2-V111'
OUT = ROOT / 'build/human_face_column_intent'
OUT.mkdir(parents=True, exist_ok=True)
font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 22)
small = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18)
atlas = Image.open(NATIVE / 'images/atlases/intent_atlas.png').convert('RGBA')
sheet = json.loads((NATIVE / 'images/atlases/intent_atlas.tpsheet').read_text())
sprites = {entry['filename']: entry for entry in sheet['textures'][0]['sprites']}
scene = (ROOT / 'scenes/creature_visuals/human_face_column.tscn').read_text()
marker = tuple(map(float, re.search(r'name="IntentPos"[\s\S]+?Vector2\(([^)]+)\)', scene)[1].split(',')))
power = Image.open(ROOT / 'images/powers/human_face_column_power.png').convert('RGBA').resize((40, 40), Image.Resampling.LANCZOS)
background = Image.open(ROOT / 'images/rooms/cave_quartz/cave_quartz_00.png').convert('RGBA')
background = background.resize((2765, 1296), Image.Resampling.LANCZOS).crop((422, 108, 2342, 1188))


def icon(name):
    entry = sprites[name]
    r, m = entry['region'], entry['margin']
    image = Image.new('RGBA', (r['w'] + m['w'], r['h'] + m['h']))
    image.alpha_composite(atlas.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h'])), (m['x'], m['y']))
    return image


def ui_row(image, x, y, level, old=False, stunned=False):
    # These offsets come from creature.tscn / intent.tscn / NIntent._Process.
    # Old projection shows initial size 40 and a valid native scale of 1.1.
    scale = (1.1, 1.0, 1.0333333)[level] if old else 1.0
    ui_left = x - 426 * scale
    center_x = x - 330 if old else x + marker[0]
    top = y + (-140 - 20) * scale if old else y + marker[1] - 32
    bob = -8  # Midpoint of the native -18..+2 vertical motion.
    names = ['defend/intent_defend_00.png', 'debuff/intent_megadebuff_00.png', 'attack/intent_attack_1.png']
    sprite = icon('intent_stun.png' if stunned else names[level])
    sx, sy = round(center_x - 2), round(top + 31 + bob)
    image.alpha_composite(sprite, (sx - sprite.width // 2, sy - sprite.height // 2))
    draw = ImageDraw.Draw(image)
    if level == 2 and not stunned:
        draw.text((center_x, top + 40 + bob), '5', font=font, anchor='mt', fill='#fff6e2', stroke_width=3, stroke_fill='#262c31')
    hp_y = y + 7 - (190 / 2 + 9)
    draw.rounded_rectangle((ui_left, hp_y, ui_left + 184, hp_y + 16), radius=5, fill='#632932', outline='#271e23', width=2)
    draw.rounded_rectangle((ui_left + 5, hp_y + 3, ui_left + 179, hp_y + 13), radius=2, fill='#bf5458')
    draw.text((ui_left + 92, hp_y + 8), '21/21', font=small, anchor='mm', fill='#fff6e2', stroke_width=2, stroke_fill='#27252a')
    image.alpha_composite(power, (round(ui_left), round(hp_y + 18)))
    draw.text((ui_left + 40, hp_y + 42), '5' if stunned else '6', font=small, anchor='mm', fill='#fff6e2', stroke_width=2, stroke_fill='#27252a')


def layout(strong=True, old=False, stunned=False):
    image = background.copy()
    # Reuse the unchanged exported-Spine authoring render; its old UI labels
    # lie outside this crop. This is not a screenshot or a new native render.
    name = 'strong-layout' if strong else 'weak-layout'
    previous = Image.open(ROOT / f'build/human_face_column_tall/{name}.jpg').convert('RGBA')
    x = 1360 if strong else 1460
    image.alpha_composite(previous.crop((x - 216, 0, 1920, 870)), (x - 216, 0))
    for level in (0, 1, 2):
        ui_row(image, x, 830 - level * 190, level, old, stunned)
    draw = ImageDraw.Draw(image)
    draw.text((35, 32), '人面柱 · 意图与血条排版', font=font, fill='#efe2b9')
    draw.text((35, 68), '离线排版推算 · 原版意图图集与控件偏移 · 非游戏截图', font=small, fill='#d4dce1')
    return image


for strong, name in [(True, 'strong-intent-layout'), (False, 'weak-intent-layout')]:
    layout(strong).convert('RGB').save(OUT / f'{name}.jpg', quality=95)
comparison = Image.new('RGB', (1520, 750), '#222c35')
for index, old in enumerate((True, False)):
    panel = layout(old=old).crop((855, 230, 1585, 890)).convert('RGB')
    comparison.paste(panel, (15 + index * 760, 65))
    ImageDraw.Draw(comparison).text((28 + index * 760, 22), '旧版：缩放和初始尺寸造成偏移' if old else '调整后：各层使用统一侧栏坐标', font=font, fill='#efdfb3')
comparison.save(OUT / 'intent-layout-comparison.jpg', quality=95)
record = {
    'version': '1.24.2',
    'method': 'Static source/scene review and Pillow layout projection; reused unchanged CPU Spine art. HP appearance/font are approximate; native intent atlas and control offsets used.',
    'native_capture': False, 'gameplay_tests_run': False, 'regression_tests_run': False,
    'source_findings': [
        'NCreature.UpdateBounds centers the initially 1000x40 HBox before 64px NIntent children are added; UpdateIntent does not recenter.',
        'NCombatRoom randomizes same-type Visuals scale; old side Bounds inherited that scale while native IntentPos X was not scaled.',
        'A later native UpdateBounds could restore the health/power bounds, but the previous one-shot side layout did not reapply.'
    ],
    'fixed_intent_center_local': list(marker),
    'side_bounds_parent': 'NCreature (same coordinate space as native Intents)',
    'native_ui_preserved': ['intent sprite/number/bob/fade', 'health show/hide and damage/block animations', 'power tooltip/layout'],
    'limitations': 'No in-game reproduction or runtime verification, per user request; preview is not evidence of native rendering.',
    'visual_review': 'pending'
}
(OUT / 'art-review.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', 'utf-8')
print('Wrote static layout projections and source findings; no game or tests started.')
