"""Review the revised native menus without regenerating any artwork."""
from pathlib import Path
import json
import re
from PIL import Image
from native_event_preview import render_event

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/'build/polite_maw_polish'
BUILD.mkdir(parents=True,exist_ok=True)
portrait = Image.open(ROOT/'images/events/polite_maw.png').convert('RGBA')
source = (ROOT/'STS2_Things/Events/PoliteMaw.cs').read_text('utf-8')
minimum = int(re.search(r'DescriptionMinimumHeight\s*=\s*(\d+)',source).group(1))
reports = {}
for shared in (False,True):
    mode = 'multiplayer' if shared else 'solo'
    for page,options in [('INITIAL',('ATTACK','SKILL','POWER','CURSE','TIP'))]:
        folder = BUILD if not shared and page=='INITIAL' else BUILD/mode/page.lower()
        reports[f'{mode}_{page.lower()}'] = render_event(ROOT,'POLITE_MAW',portrait,
            {'Gold':50,'SmallGold':15,'Relic':{'zhs':'石化蟾蜍','eng':'Petrified Toad'}},options,folder,
            page=page,shared=shared,description_min_height=minimum)
(BUILD/'layout-review.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n','utf-8')

references = {}
for lang in ('zhs','eng'):
    table = json.loads((ROOT.parent/f'STS2-V111/localization/{lang}/events.json').read_text('utf-8-sig'))
    keys = ('TEA_MASTER.pages.INITIAL.description', 'RANWID_THE_ELDER.pages.INITIAL.description',
            'RANWID_THE_ELDER.pages.GOLD.description', 'TRASH_HEAP.pages.INITIAL.options.GRAB.description')
    references[lang] = {key:table[key] for key in keys}
(BUILD/'native-writing-reference.json').write_text(json.dumps(references,ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps(reports,ensure_ascii=False))
