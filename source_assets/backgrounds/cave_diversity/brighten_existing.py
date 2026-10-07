"""Apply a scoped, idempotent readability material to existing cave paintings."""
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
MOD = HERE.parents[2]
SLUGS = ["hollow_grotto", "hollow_grotto_moss", "hollow_grotto_ember", "hollow_grotto_violet"]
MATERIAL = "res://materials/backgrounds/cave_readable_existing.tres"


def apply():
    changed = []
    for slug in SLUGS:
        for path in sorted((MOD / "scenes/backgrounds" / slug / "layers").glob("*.tscn")):
            content = path.read_text(encoding="utf-8")
            if 'id="readability"' not in content:
                content = re.sub(r'load_steps=(\d+)',lambda m:"load_steps="+str(int(m[1])+1),content,count=1)
                first_break = content.index("\n")
                content = content[:first_break+1]+f'\n[ext_resource type="Material" path="{MATERIAL}" id="readability"]\n'+content[first_break+1:]
            target = '[node name="PaintedLayer" type="TextureRect" parent="."]'
            assert target in content, path
            if 'material = ExtResource("readability")' not in content:
                content = content.replace(target,target+'\nmaterial = ExtResource("readability")')
            path.write_text(content,encoding="utf-8")
            changed.append(path.relative_to(MOD).as_posix())
    print("READABILITY_MATERIAL_APPLIED",len(changed),"painted layers")
    return changed


if __name__ == "__main__":
    apply()
