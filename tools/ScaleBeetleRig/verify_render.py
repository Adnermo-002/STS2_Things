"""Check real Godot silhouettes for detached pieces and viewport clipping."""
from pathlib import Path
import argparse
import json
import cv2
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('frames', type=Path)
args = parser.parse_args()
report = json.loads((args.frames / 'report.json').read_text())
assert report.get('silhouette') is True, 'Use the silhouette render mode'
files = sorted(args.frames.glob('*.png'))
assert len(files) == report['frames'] and len(files) > 300, 'Incomplete capture'
failures = []
for file in files:
    image = cv2.imread(str(file), cv2.IMREAD_GRAYSCALE)
    mask = (image > 127).astype(np.uint8)
    assert mask.sum() > 15000, f'Missing subject: {file.name}'
    # Permit a subpixel filtering gap in narrow antenna collars, not whole beads
    # or disconnected limbs. The shader excludes shadow and glow attachments.
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    components = sorted(stats[1:], key=lambda row: -row[4])
    detached = [row.tolist() for row in components[1:] if row[4] > 36]
    clipped = bool(mask[:3].any() or mask[-3:].any() or mask[:, :3].any() or mask[:, -3:].any())
    if detached or clipped:
        failures.append(dict(frame=file.name, detached=detached, clipped=clipped))
for failure in failures[:15]:
    print(json.dumps(failure))
result = dict(frames=len(files), failed_frames=len(failures), failures=failures)
(args.frames.parent / 'silhouette-verification.json').write_text(json.dumps(result, indent=2))
print(f"SCALE_BEETLE_SILHOUETTE_{'FAIL' if failures else 'PASS'} frames={len(files)} failures={len(failures)}")
raise SystemExit(bool(failures))
