"""Assemble a freshly generated floor with the existing layered cave walls.

Run with Python + Pillow + numpy. Paths resolve from this file. Vanilla inputs
are read-only; all generated resources use the new hollow_grotto namespace.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
MOD = HERE.parents[2]
WORKSPACE = MOD.parent
VANILLA = WORKSPACE / "STS2-V111"
OUT = MOD / "images/rooms/hollow_grotto"
SIZE = (2048, 960)
RESAMPLE = Image.Resampling.LANCZOS
SOURCES = {}
GENERATED_FLOORS = {}


def source(path):
    full = VANILLA / path
    SOURCES[path] = hashlib.sha256(full.read_bytes()).hexdigest()
    return Image.open(full).convert("RGBA")


def load_generated_floor(slug):
    """There is intentionally no stock-floor fallback for the new region."""
    path = HERE.parent / "new_cave_floors/generated" / (slug + "_floor.png")
    if not path.is_file():
        raise FileNotFoundError(f"A newly generated floor is required: {path}")
    im = Image.open(path).convert("RGBA")
    if im.size != SIZE or im.getchannel("A").getextrema() != (255, 255):
        raise ValueError(f"The generated floor must be opaque and {SIZE}: {path}")
    GENERATED_FLOORS[slug] = {"path": path.relative_to(MOD).as_posix(),
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return im


def grade(im, dark, light, maximum=90, color_retention=0.10):
    """Map painted values to the cave palette; keep the artist's local variation."""
    a = np.asarray(im).astype(np.float32)
    rgb = a[..., :3]
    value = rgb @ np.array([0.2126, 0.7152, 0.0722])
    t = np.clip(value / maximum, 0, 1)[..., None]
    rgb = np.array(dark) + t * (np.array(light) - np.array(dark))
    rgb += (a[..., :3] - value[..., None]) * color_retention
    a[..., :3] = np.clip(rgb, 0, 255)
    return Image.fromarray(a.astype(np.uint8))


def blank():
    return Image.new("RGBA", SIZE)


def put(canvas, im, xy, size=None, flip_x=False, flip_y=False, opacity=1):
    if flip_x:
        im = ImageOps.mirror(im)
    if flip_y:
        im = ImageOps.flip(im)
    if size:
        im = im.resize(size, RESAMPLE)
    if opacity != 1:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda a: round(a * opacity)))
    canvas.alpha_composite(im, xy)


def viewport(im, width=1920, height=1080):
    """Vanilla TextureRect: 2048x960 -> 2764.8x1296; BgContainer x=23."""
    scale = 1.35
    x0 = (width / 2 + 23) - 1024 * scale
    y0 = height / 2 - 480 * scale
    return im.transform((width, height), Image.Transform.AFFINE,
                        (1 / scale, 0, -x0 / scale, 0, 1 / scale, -y0 / scale),
                        Image.Resampling.BICUBIC)


def build(revision="r05_new_floor"):
    OUT.mkdir(parents=True, exist_ok=True)
    (HERE / "review").mkdir(exist_ok=True)
    rocks = source("images/rooms/underdocks/underdocks_03_b.png")
    ridge = source("images/rooms/hive/hive_04_a.png")
    loose = source("images/rooms/waterfall_giant_bg/waterfallgiant_bg_4_rocksb.png")

    # This entire base plane is new generated artwork, including its distant
    # atmospheric fade. No old ground pixels, seams or textures are composited.
    base = load_generated_floor("hollow_grotto")
    # Lighting belongs to native additive CanvasItemMaterials, not alpha
    # compositing: the game's light.png contains an opaque black perimeter.

    far = blank()
    distant = grade(rocks, (13, 25, 35), (31, 47, 53), maximum=44, color_retention=.06)
    put(far, distant.crop((0, 0, 1165, 552)), (90, 80), (740, 438))
    put(far, distant.crop((1170, 0, 1550, 552)), (1260, 25), (325, 505))
    put(far, distant.crop((1605, 210, 1825, 515)), (1060, 379), (120, 155), flip_x=True)
    put(far, distant.crop((1605, 210, 1825, 515)), (760, 342), (172, 204))
    # A second, darker plane breaks the long row into an irregular chamber.
    back = grade(rocks, (15, 23, 34), (30, 39, 51), maximum=42, color_retention=.1)
    put(far, back.crop((294, 0, 701, 552)), (330, -20), (325, 605), flip_x=True)
    put(far, back.crop((1850, 0, 2048, 552)), (1480, 80), (270, 510))

    middle = blank()
    stone = grade(rocks, (8, 10, 20), (37, 40, 58), maximum=38, color_retention=.12)
    put(middle, stone.crop((1170, 0, 1550, 552)), (60, -125), (425, 750), flip_x=True)
    put(middle, stone.crop((0, 0, 274, 520)), (1470, -80), (620, 760), flip_x=True)
    put(middle, stone.crop((1600, 180, 1825, 550)), (420, 404), (205, 239), flip_x=True)
    put(middle, stone.crop((1600, 180, 1825, 550)), (1520, 400), (200, 256))

    canopy = blank()
    roof = grade(ridge, (6, 8, 16), (30, 32, 46), maximum=26, color_retention=.06)
    put(canopy, roof, (0, -20), flip_y=True)
    put(canopy, stone.crop((1600, 180, 1825, 550)), (562, -38), (238, 322), flip_y=True)
    put(canopy, stone.crop((970, 96, 1165, 500)), (1110, -20), (160, 210), flip_y=True, flip_x=True)
    put(canopy, stone.crop((294, 0, 701, 552)), (1300, -326), (280, 485), flip_y=True)
    scattered = grade(loose, (9, 11, 19), (40, 45, 55), maximum=65, color_retention=.10)
    # This isolated boulder has transparent padding on all four crop edges.
    pebble = scattered.crop((111, 34, 243, 84))
    put(canopy, pebble, (540, 641), (106, 40))
    put(canopy, pebble, (1450, 645), (89, 34), flip_x=True)

    front = blank()
    foreground = grade(ridge, (3, 4, 10), (18, 19, 30), maximum=27, color_retention=.03)
    put(front, foreground, (0, 93))

    layers = [base, far, middle, canopy, front]
    names = ["hollow_grotto_00", "hollow_grotto_01", "hollow_grotto_02", "hollow_grotto_03", "hollow_grotto_fg"]
    for name, im in zip(names, layers):
        im.save(OUT / (name + ".png"), optimize=True)
    composite = blank()
    for im in layers:
        composite.alpha_composite(im)
    composite.save(HERE / "review" / (revision + "_full_canvas.png"))
    viewport(composite).convert("RGB").save(HERE / "review" / (revision + "_composition.png"))
    manifest = {
        "name": "Hollow Grotto / 幽蓝溶洞",
        "method": "New floor generated via the user-provided Image API; existing vanilla-derived walls remain layered separately.",
        "source_version": "STS2-V111",
        "source_sha256": SOURCES,
        "generated_floors": GENERATED_FLOORS,
        "texture_size": list(SIZE),
        "texture_rect": [-1382.4, -648.0, 1382.4, 648.0],
        "nominal_viewport": [1920, 1080],
        "bg_container_x_offset": 23,
        "runtime_layers": [f"images/rooms/hollow_grotto/{n}.png" for n in names],
        "revision": revision,
    }
    (HERE / "asset_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Built", OUT)
    print("Review", HERE / "review" / (revision + "_composition.png"))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default="r05_new_floor")
    build(parser.parse_args().revision)
