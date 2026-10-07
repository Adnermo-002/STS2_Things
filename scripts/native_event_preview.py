"""Offline event-layout composition using native fonts and button art.

This is an authoring preview, not a Godot render or a game screenshot.
"""
from pathlib import Path
import json
import re
from PIL import Image, ImageDraw, ImageFont

PALETTE = {'default': '#fff6e2', 'gold': '#efcd73', 'red': '#ef8584',
           'blue': '#88cbe4', 'green': '#97d594', 'purple': '#c89adb'}


def render_event(root, event_id, portrait, variables, option_keys, output_dir, page='INITIAL', shared=False,
                 description_min_height=280, description_page=None, option_variables=None):
    output_dir.mkdir(parents=True, exist_ok=True)
    native = root.parent / 'STS2-V111'
    reports = {}
    for lang in ('zhs', 'eng'):
        values = json.loads((root / f'STS2_Things/localization/{lang}/events.json').read_text('utf-8'))
        face_path = native / ('fonts/zhs/SourceHanSerifSC-Medium.otf' if lang == 'zhs' else 'fonts/kreon_regular.ttf')
        font = ImageFont.truetype(str(face_path), 26)
        button_font = ImageFont.truetype(str(face_path), 24)
        title_font = ImageFont.truetype(str(native / ('fonts/zhs/SourceHanSerifSC-Bold.otf' if lang == 'zhs' else 'fonts/spectral_bold.ttf')), 36)

        def lines(text, face, width, overrides=None):
            text = re.sub(r'\{IsMultiplayer:([^{}|]*)\|([^{}]*)\}',
                          lambda match: match.group(1 if shared else 2), text)
            for key, value in (variables | (overrides or {})).items():
                if isinstance(value, dict):
                    value = value[lang]
                text = text.replace('{' + key + '}', str(value))
            color = 'default'
            stack, result, line = [], [], []
            length = 0
            for token in re.split(r'(\[[^\]]+\])', text):
                if token.startswith('['):
                    tag = token[1:-1]
                    if tag in PALETTE:
                        stack.append(color)
                        color = tag
                    elif tag.startswith('/') and tag[1:] in PALETTE:
                        color = stack.pop() if stack else 'default'
                    continue
                for char in token:
                    if char == '\n':
                        result.append(line)
                        line, length = [], 0
                        continue
                    advance = face.getlength(char)
                    if length + advance > width:
                        spaces = [i for i, item in enumerate(line) if item[0] == ' ']
                        if lang == 'eng' and spaces:
                            split = spaces[-1]
                            result.append(line[:split])
                            line = line[split + 1:]
                            length = sum(item[2] for item in line)
                        else:
                            result.append(line)
                            line, length = [], 0
                    if not line and char == ' ':
                        continue
                    line.append((char, color, advance))
                    length += advance
            result.append(line)
            return result

        def paint(draw, rows, x, y, width, face, line_height, centered=True):
            for row in rows:
                cursor = x + (width - sum(v[2] for v in row)) / 2 if centered else x
                for char, color, advance in row:
                    baseline = y + face.getmetrics()[0]
                    draw.text((cursor + 3, baseline + 2), char, font=face, fill='black', anchor='ls')
                    draw.text((cursor, baseline), char, font=face, fill=PALETTE[color], anchor='ls')
                    cursor += advance
                y += line_height

        canvas = Image.new('RGBA', (1920, 1080), 'black')
        canvas.alpha_composite(portrait.resize((2662, 1251), Image.Resampling.LANCZOS), (-371, -79))
        draw = ImageDraw.Draw(canvas)
        title = values[event_id + '.title']
        draw.text((1322 - title_font.getlength(title) / 2, 236), title, font=title_font, fill='#efd06d', anchor='lt')
        body = lines(values[event_id + f'.pages.{description_page or page}.description'], font, 800)
        height = max(description_min_height, len(body) * 34)
        paint(draw, body, 922, 300 + (height - len(body) * 34) / 2, 800, font, 34)

        texture = Image.open(native / 'images/packed/common_ui/event_button.png').convert('RGBA')
        texture = texture.resize((texture.width, 100), Image.Resampling.LANCZOS)
        edge = min(192, (texture.width - 2) // 2)
        button = Image.new('RGBA', (800, 100))
        button.paste(texture.crop((0, 0, edge, 100)).resize((192, 100)), (0, 0))
        button.paste(texture.crop((edge, 0, texture.width - edge, 100)).resize((416, 100)), (192, 0))
        button.paste(texture.crop((texture.width - edge, 0, texture.width, 100)).resize((192, 100)), (608, 0))
        y, options = 324 + height, []
        if shared:
            label = '这是一个合作事件。请投票决定接下来的行动。' if lang == 'zhs' else 'This is a collaborative event. Vote on a path everyone will take.'
            shared_font = ImageFont.truetype(str(face_path), 22)
            draw.text((1322 - shared_font.getlength(label) / 2, 300 + height + 10),
                      label, font=shared_font, fill='#88cbe4', anchor='lt')
            y += 48
        for index, key in enumerate(option_keys):
            canvas.alpha_composite(button, (922, y))
            option_page, option_key = key.split('/', 1) if '/' in key else (page, key)
            prefix = event_id + f'.pages.{option_page}.options.' + option_key
            overrides = option_variables[index] if option_variables and index < len(option_variables) else None
            rows = lines('[gold]' + values[prefix + '.title'] + '[/gold]\n' + values[prefix + '.description'], button_font, 716, overrides)
            paint(ImageDraw.Draw(canvas), rows, 964, y + 13, 716, button_font, 26, centered=False)
            options.append({'key': key, 'lines': len(rows), 'bottom': y + 13 + len(rows) * 26})
            y += 108
        caption = '离线排版预览 · 原版字体与按钮 · 非游戏截图' if lang == 'zhs' else 'Offline layout composition - not a game capture'
        ImageDraw.Draw(canvas).text((22, 1048), caption, font=ImageFont.truetype(str(face_path), 17), fill='#e9eff6')
        suffix = '' if lang == 'zhs' else '-eng'
        canvas.convert('RGB').save(output_dir / f'event-layout-review{suffix}.jpg', quality=95)
        reports[lang] = {'page': page, 'multiplayer_preview': shared,
                         'description_min_height': description_min_height,
                         'description_height': height,
                         'description_lines': len(body), 'options': options}
    return reports
