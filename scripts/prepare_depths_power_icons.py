"""Package the selected, vanilla-style Depths power glyphs for both game versions."""
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source_assets/ui/depths_icons_v2'
ICONS = {
    'absorbent': 'absorbent_sponge_power',
    'reservoir': 'sponge_reservoir_power',
    'rinse': 'sponge_rinse_power',
    'blindness': 'lantern_blindness_power',
    'leech_infestation': 'leech_infestation_power',
}


def prepare_icons():
    for source, name in ICONS.items():
        art = Image.open(SOURCE / f'{source}_final.png').convert('RGBA')
        art = ImageOps.contain(art.crop(art.getbbox()), (224, 224), Image.Resampling.LANCZOS)
        big = Image.new('RGBA', (256, 256))
        big.alpha_composite(art, ((256-art.width)//2, (256-art.height)//2))
        big.save(ROOT / f'images/powers/{name}.png')
        big.resize((64, 64), Image.Resampling.LANCZOS).save(ROOT / f'images/powers/{name}_packed.png')
        (ROOT / f'images/atlases/power_atlas.sprites/{name}.tres').write_text(f'''[gd_resource type="AtlasTexture" load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://images/powers/{name}_packed.png" id="1"]

[resource]
atlas = ExtResource("1")
region = Rect2(0, 0, 64, 64)
''', 'utf-8')


if __name__ == '__main__':
    prepare_icons()
    print('Packaged five Depths power icons at 256px and 64px.')
