"""Build the three native HUD icons from the existing, unmodified power art."""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
for name in ("things_scale_beetle_power", "things_scale_up_power", "things_scale_down_power"):
    source = ROOT / "images/powers" / f"{name}.png"
    output = source.with_name(f"{name}_packed.png")
    with Image.open(source) as image:
        image.convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS).save(output, optimize=True)
    resource = ROOT / "images/atlases/power_atlas.sprites" / f"{name}.tres"
    resource.write_text(f'''[gd_resource type="AtlasTexture" load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://images/powers/{name}_packed.png" id="1_icon"]

[resource]
atlas = ExtResource("1_icon")
region = Rect2(0, 0, 64, 64)
''', encoding="utf-8")
    print(resource.relative_to(ROOT))
