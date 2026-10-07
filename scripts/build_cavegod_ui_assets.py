"""Build Cave God's reviewed raster UI art; never calls an image API."""
from pathlib import Path
from io import BytesIO
import argparse
import hashlib
import json

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source_assets/ui/cavegod_renew'
GENERATED = ROOT / 'output/imagegen/cavegod_renew'
REVIEW = ROOT / 'build/cavegod_ui_renew/art-review'
MANIFEST = json.loads((SOURCE / 'generation-manifest.json').read_text('utf-8'))


def write_if_changed(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def save(image: Image.Image, path: Path) -> None:
    stream = BytesIO()
    image.save(stream, format='PNG', optimize=True)
    write_if_changed(path, stream.getvalue())


def extract(image: Image.Image) -> Image.Image:
    # The approved symbols contain no magenta. Recover coverage at the black
    # ink boundary, then remove the key contribution before resizing the RGBA.
    rgb = np.asarray(image.convert('RGB'), dtype=np.float32)
    dominance = np.maximum(0, np.minimum(rgb[:, :, 0], rgb[:, :, 2]) - rgb[:, :, 1])
    alpha = np.clip(1 - dominance / 255, 0, 1)
    # The provider adds small compression variations even on the flat key.
    alpha[alpha < 0.25] = 0
    foreground = (rgb - (1 - alpha[:, :, None]) * np.array([255, 0, 255])) / np.maximum(alpha[:, :, None], 0.001)
    foreground[alpha == 0] = 0
    rgba = np.dstack((np.clip(foreground, 0, 255), alpha * 255)).round().astype(np.uint8)
    result = Image.fromarray(rgba)
    bounds = result.getbbox()
    assert bounds and bounds[0] > 0 and bounds[1] > 0 and bounds[2] < result.width and bounds[3] < result.height, 'Clipped symbol'
    return result


def fit_symbol(image: Image.Image, size: tuple[int, int], inset: int) -> Image.Image:
    symbol = ImageOps.contain(image.crop(image.getbbox()), (size[0] - 2 * inset, size[1] - 2 * inset), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', size)
    canvas.alpha_composite(symbol, ((size[0] - symbol.width) // 2, (size[1] - symbol.height) // 2))
    return canvas


def outline(image: Image.Image, radius: int) -> Image.Image:
    alpha = image.getchannel('A').filter(ImageFilter.MaxFilter(radius * 2 + 1))
    result = Image.new('RGBA', image.size, (255, 255, 255, 0))
    result.putalpha(alpha)
    return result


def make_map_icon(image: Image.Image) -> Image.Image:
    # Vanilla boss map art is a white stencil modulated by the map UI. Keep
    # the generated ink gaps transparent, with two soft white shade levels.
    light = ImageOps.grayscale(image).point(lambda value: 0 if value < 42 else min(255, int(135 + (value - 42) * 120 / 178)))
    result = Image.new('RGBA', image.size, (255, 255, 255, 0))
    result.putalpha(ImageChops.multiply(image.getchannel('A'), light))
    return result


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', size)


def contact_sheets(assets: dict[str, Image.Image]) -> None:
    REVIEW.mkdir(parents=True, exist_ok=True)
    label = font(18)
    canvas = Image.new('RGB', (1200, 800), '#243137')
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 18), 'Cave God · 全新能力图标（128 / 64 / 32 px）', font=font(26), fill='#f0e6c8')
    powers = [job for job in MANIFEST['jobs'] if job['kind'] == 'power']
    for i, job in enumerate(powers):
        x = 24 + i % 4 * 296
        y = 74 + i // 4 * 235
        icon = assets[job['target']]
        for dx, size in [(0, 128), (140, 64), (218, 32)]:
            small = icon.resize((size, size), Image.Resampling.LANCZOS)
            canvas.paste(small, (x + dx, y + 128 - size), small)
        draw.text((x, y + 142), job['slug'].replace('_power', ''), font=label, fill='white')
    native = Image.open(SOURCE / 'references/native-power-style.png').convert('RGB')
    native.thumbnail((500, 250))
    canvas.paste(native, (24, 530))
    draw.text((550, 565), '原版参考：粗轮廓 / 明确色块 / 缩小可辨', font=font(22), fill='#d8d1b7')
    save(canvas, REVIEW / 'power-icons.png')

    canvas = Image.new('RGB', (1500, 890), '#243137')
    draw = ImageDraw.Draw(canvas)
    for i, job in enumerate(job for job in MANIFEST['jobs'] if job['kind'] == 'card'):
        x = 10 + i % 3 * 500
        y = 30 + i // 3 * 440
        portrait = assets[job['target']].resize((480, 365), Image.Resampling.LANCZOS)
        canvas.paste(portrait, (x, y))
        draw.text((x, y + 374), job['slug'], font=label, fill='white')
    native = Image.open(SOURCE / 'references/native-card-style.png').convert('RGB')
    native.thumbnail((470, 370))
    canvas.paste(native, (1010, 470))
    draw.text((1010, 850), '原版卡面参考', font=label, fill='white')
    save(canvas, REVIEW / 'card-portraits.png')

    canvas = Image.new('RGB', (1050, 420), '#243137')
    draw = ImageDraw.Draw(canvas)
    for x, background in [(15, '#243137'), (382, '#b5aa90')]:
        draw.rectangle((x, 35, x + 351, 334), fill=background)
        icon = assets['images/map/cave_god_boss_icon.png']
        canvas.paste(icon, (x, 35), icon)
    avatar = assets['images/ui/run_history/cave_god_boss.png']
    canvas.paste(avatar, (830, 80), avatar)
    draw.text((20, 355), '地图：白色模板，由原版地图着色', font=label, fill='white')
    draw.text((780, 195), '战斗记录：88 px', font=label, fill='white')
    save(canvas, REVIEW / 'boss-avatars.png')


def build(install: bool) -> dict[str, Image.Image]:
    assets = {}
    for job in MANIFEST['jobs']:
        path = GENERATED / job.get('output', job['slug'] + '.png')
        image = Image.open(path)
        if job['kind'] in ['power', 'avatar']:
            image = extract(image)
            save(image, SOURCE / 'masters' / (job['slug'] + '.png'))
        if job['kind'] == 'power':
            icon = fit_symbol(image, (256, 256), 12)
            assets[job['target']] = icon
            assets[job['target'].replace('.png', '_packed.png')] = icon.resize((64, 64), Image.Resampling.LANCZOS)
        elif job['kind'] == 'card':
            image = ImageOps.fit(image.convert('RGB'), (1000, 760), Image.Resampling.LANCZOS)
            assets[job['target']] = image
            assets['images/cards/cave_god_' + job['slug'] + '.png'] = image
            # Match the native V107 private PortraitPngPath contract. Keep the
            # authoring names while making HasPortrait work without a patch.
            native_names = {'broken_blade': 'cave_god_broken_blade_trial',
                            'shattered_shield': 'cave_god_shattered_shield_trial',
                            'crystal_shard': 'things_cave_god_crystal_shard'}
            if job['slug'] in native_names:
                assets['images/packed/card_portraits/token/' + native_names[job['slug']] + '.png'] = image
        else:
            map_full = fit_symbol(image, (352, 300), 14)
            assets['images/map/cave_god_boss_icon.png'] = make_map_icon(map_full)
            assets['images/map/cave_god_boss_icon_outline.png'] = outline(map_full, 6)
            avatar = fit_symbol(image, (88, 88), 5)
            for stem in ['cave_god_boss', 'cave_god_boss_encounter']:
                assets['images/ui/run_history/' + stem + '.png'] = avatar
                assets['images/ui/run_history/' + stem + '_outline.png'] = outline(avatar, 2)
    contact_sheets(assets)
    if install:
        for name, image in assets.items():
            save(image, ROOT / name)
        for job in MANIFEST['jobs']:
            if job['kind'] != 'power':
                continue
            name = Path(job['target']).stem
            texture = f'''[gd_resource type="AtlasTexture" load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://images/powers/{name}_packed.png" id="1_icon"]

[resource]
atlas = ExtResource("1_icon")
region = Rect2(0, 0, 64, 64)
'''
            write_if_changed(ROOT / 'images/atlases/power_atlas.sprites' / (name + '.tres'), texture.encode())
        result = {name: {'size': list(image.size), 'mode': image.mode, 'sha256': hashlib.sha256((ROOT / name).read_bytes()).hexdigest()} for name, image in assets.items()}
        write_if_changed(SOURCE / 'integrated-assets.json', (json.dumps(result, indent=2) + '\n').encode())
        print(f'Cave God UI assets integrated: {len(assets)} PNGs; 8 power atlases')
    else:
        print('Review sheets ready; runtime assets were not changed.')
    return assets


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Replace the reviewed project UI images.')
    build(parser.parse_args().install)
