"""Merge the Shadow Cloakroom's bilingual text without rewriting other entries."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
source = json.loads((ROOT / 'source_assets/events/shadow_cloakroom/localization.json').read_text('utf-8'))
for language, tables in source.items():
    for name, entries in tables.items():
        path = ROOT / f'STS2_Things/localization/{language}/{name}.json'
        table = json.loads(path.read_text('utf-8-sig'))
        table.update(entries)
        path.write_text(json.dumps(table, ensure_ascii=False, indent=2) + '\n', 'utf-8')
print('Integrated Shadow Cloakroom event, relic and settings text in both languages.')
