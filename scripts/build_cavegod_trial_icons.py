"""Rebuild trial icons from the reviewed Sunburst masters, never from card art."""
from PIL import Image
from build_cavegod_ui_assets import ROOT, SOURCE, fit_symbol, save, write_if_changed

ICONS = {
    'cave_god_broken_blade_power': 'broken_blade_power',
    'cave_god_shattered_shield_power': 'shattered_shield_power',
    'cave_god_martial_power': 'martial_power',
    'cave_god_arcane_power': 'arcane_power',
}


def main() -> None:
    for key, source in ICONS.items():
        icon = fit_symbol(Image.open(SOURCE / 'masters' / f'{source}.png').convert('RGBA'), (256, 256), 12)
        save(icon, ROOT / 'images/powers' / f'{key}.png')
        save(icon.resize((64, 64), Image.Resampling.LANCZOS), ROOT / 'images/powers' / f'{key}_packed.png')
        texture = f'''[gd_resource type="AtlasTexture" load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://images/powers/{key}_packed.png" id="1_icon"]

[resource]
atlas = ExtResource("1_icon")
region = Rect2(0, 0, 64, 64)
'''
        write_if_changed(ROOT / 'images/atlases/power_atlas.sprites' / f'{key}.tres', texture.encode())
    print('CaveGod reviewed trial icons: PASS (4 packed + 4 full-size)')


if __name__ == '__main__':
    main()
