"""Merge the two Depths events' source localization into native tables."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
for event in ('echoing_well', 'polite_maw'):
    source = json.loads((ROOT / f'source_assets/events/{event}/localization.json').read_text('utf-8'))
    for language, tables in source.items():
        for name, entries in tables.items():
            path = ROOT / f'STS2_Things/localization/{language}/{name}.json'
            table = json.loads(path.read_text('utf-8-sig'))
            table.update(entries)
            path.write_text(json.dumps(table, ensure_ascii=False, indent=2) + '\n', 'utf-8')
print('Integrated Echoing Well, Polite Maw, Bottled Echo and their settings in both languages.')
