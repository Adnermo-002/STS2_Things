"""Finish the optional bridge installation and record all four delivered hashes."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--version', default='1.24.0')
parser.add_argument('--record-dir', default='build/human_face_column')
args = parser.parse_args()
RECORD = ROOT / args.record_dir
STAGED = ROOT / f'dist/v{args.version}/STS2_Things'
install = json.loads((RECORD / 'install-result.json').read_text('utf-8'))
destination = Path(install['installed'])
expected = Path(r'D:\Steam\steamapps\common\Slay the Spire 2\mods\STS2_Things')
if destination.resolve() != expected.resolve():
    raise RuntimeError('Unexpected installation destination')

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

bridge = 'STS2_Things.BaseLibBridge.dll'
source, target = STAGED / bridge, destination / bridge
if not source.is_file():
    raise FileNotFoundError(source)
if target.exists() and sha(target) != sha(source):
    backup = Path(install['backup']) / bridge
    if backup.exists() and sha(backup) != sha(target):
        raise RuntimeError('Refusing to replace a different bridge backup')
    shutil.copy2(target, backup)
    install['bridge_backup'] = str(backup)
if not target.exists() or sha(target) != sha(source):
    shutil.copy2(source, target)

delivery_path = RECORD / 'delivery.json'
delivery = json.loads(delivery_path.read_text('utf-8'))
verified = []
for entry in delivery['files']:
    name, digest = entry['name'], entry['sha256']
    actual = sha(destination / name)
    if actual != digest or sha(STAGED / name) != digest:
        raise RuntimeError('Installed/staged file differs from delivery: ' + name)
    verified.append({'name': name, 'sha256': actual, 'matches_package': True})
install.update(version=args.version, verified_files=verified, gameplay_tests_run=False)
(RECORD / 'install-result.json').write_text(json.dumps(install, ensure_ascii=False, indent=2)+'\n', 'utf-8')
delivery['installation'] = install
delivery['art_review_record'] = str(RECORD / 'art-review.json')
delivery_path.write_text(json.dumps(delivery, ensure_ascii=False, indent=2)+'\n', 'utf-8')
print(json.dumps({'installed': str(destination), 'version': args.version, 'files_verified': len(verified)}, ensure_ascii=False))
