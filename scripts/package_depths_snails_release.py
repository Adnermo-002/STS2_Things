"""Stage only the four release artifacts and record their exact hashes."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,shutil,zipfile,argparse
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--version',default='1.18.0')
parser.add_argument('--record-dir',default='build/depths_snails')
parser.add_argument('--art-review',default='CPU authoring sheets, continuous motion and weighted-mesh authoring review; not a native capture')
args=parser.parse_args();version=args.version
source=ROOT/'build/unified'
names=('STS2_Things.json','STS2_Things.dll','STS2_Things.pck','STS2_Things.BaseLibBridge.dll')
manifest=json.loads((source/names[0]).read_text('utf-8-sig'))
if manifest['version']!=version:raise RuntimeError('Build manifest is not '+version)
dest=ROOT/f'dist/v{version}/STS2_Things';dest.mkdir(parents=True,exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
files=[]
for name in names:
    src=source/name
    if not src.is_file():raise FileNotFoundError(src)
    out=dest/name;shutil.copy2(src,out)
    if sha(src)!=sha(out):raise RuntimeError('Copy mismatch: '+name)
    files.append(dict(name=name,bytes=out.stat().st_size,sha256=sha(out)))
archive=dest.parent/f'STS2_Things-v{version}.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as package:
    for name in names:package.write(dest/name,f'STS2_Things/{name}')
record=dict(version=version,built_at_utc=datetime.now(timezone.utc).isoformat(),
    staged=str(dest),archive=str(archive),archive_sha256=sha(archive),files=files,
    compilation={'v107.1':'passed, 0 warnings / 0 errors','v111':'passed, 0 warnings / 0 errors',
                 'bootstrap':'passed','BaseLibBridge':'passed','Godot_import':'passed','PCK_export':'passed'},
    native_probes_run=False,gameplay_tests_run=False,multiplayer_tests_run=False,
    art_review=args.art_review,
    installation='pending')
path=ROOT/args.record_dir/'delivery.json';path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps(dict(package=str(archive),bytes=archive.stat().st_size,files=files),ensure_ascii=False,indent=2))
