"""Register edited artwork, then copy only approved masked pixels into source parts."""
from pathlib import Path
import hashlib
import json

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = ROOT / 'tmp/imagegen/scale-beetle'
DEST = ROOT / 'source_assets/monsters/scale_beetle_rig_patches'
DEST.mkdir(exist_ok=True)
requests = json.loads((WORK / 'manifest.json').read_text())
meta = json.loads((HERE / 'parts/meta.json').read_text())
records = {}

for name, request in requests.items():
    original = np.array(Image.open(HERE / 'parts' / f'{name}.png').convert('RGBA'))
    editable = np.array(Image.open(WORK / f'{name}-editable.png')) > 128
    generated_path = ROOT / f'output/imagegen/scale-beetle/{name}-edit-v1.png'
    generated = Image.open(generated_path).convert('RGBA').resize((1024, 1024), Image.Resampling.LANCZOS)
    x, y = request['offset']; w, h = request['scaled_size']
    edited = np.array(generated.crop((x, y, x+w, y+h)).resize(request['size'], Image.Resampling.LANCZOS))
    # The service returned RGBA cutouts. Extend their RGB below transparent edge
    # pixels before resampling; the final silhouette always uses the source alpha.
    valid = edited[:, :, 3] > 128
    _, indices = distance_transform_edt(~valid, return_indices=True)
    edited[:, :, :3][~valid] = edited[:, :, :3][indices[0][~valid], indices[1][~valid]]
    protected = ~editable & (original[:, :, 3] > 200)
    protected = cv2.erode(protected.astype(np.uint8), np.ones((5, 5), np.uint8))
    warp = np.eye(2, 3, dtype=np.float32)
    score = None
    try:
        a = cv2.cvtColor(original[:, :, :3], cv2.COLOR_RGB2GRAY).astype(np.float32)/255
        b = cv2.cvtColor(edited[:, :, :3], cv2.COLOR_RGB2GRAY).astype(np.float32)/255
        score, candidate = cv2.findTransformECC(a, b, warp.copy(), cv2.MOTION_AFFINE,
            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 150, 1e-6), protected, 5)
        scales = np.linalg.svd(candidate[:, :2])[1]
        if min(scales) > 0.94 and max(scales) < 1.06 and np.abs(candidate[:, 2]).max() < 16:
            warp = candidate
    except cv2.error:
        pass
    edited = cv2.warpAffine(edited, warp, request['size'],
        flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    colour = edited[:, :, :3].astype(float)
    fit_mask = protected > 0
    correction = []
    for channel in range(3):
        sample = colour[:, :, channel][fit_mask]
        target = original[:, :, channel][fit_mask].astype(float)
        gain, bias = np.linalg.lstsq(np.c_[sample, np.ones(len(sample))], target, rcond=None)[0]
        gain = np.clip(gain, 0.85, 1.15); bias = np.clip(bias, -18, 18)
        colour[:, :, channel] = colour[:, :, channel]*gain+bias
        correction.append([round(float(gain), 5), round(float(bias), 5)])
    feather = np.clip(cv2.distanceTransform(editable.astype(np.uint8), cv2.DIST_L2, 5)/3.0, 0, 1)
    result = original.copy()
    result[:, :, :3] = np.clip(original[:, :, :3]*(1-feather[:, :, None]) + colour*feather[:, :, None], 0, 255).round().astype(np.uint8)
    # Exact checks: source alpha and every unmasked pixel survive unchanged.
    assert np.array_equal(result[:, :, 3], original[:, :, 3])
    assert np.array_equal(result[~editable], original[~editable])
    Image.fromarray(result).save(DEST / f'{name}.png')
    Image.fromarray((editable*255).astype(np.uint8)).save(DEST / f'{name}_mask.png')
    records[name] = dict(crop=meta[name],
        raw_rgba_sha256=hashlib.sha256(original.tobytes()).hexdigest(),
        patched_rgba_sha256=hashlib.sha256(result.tobytes()).hexdigest(),
        generated_sha256=hashlib.sha256(generated_path.read_bytes()).hexdigest(),
        edited_pixels=int(editable.sum()), protected_pixel_error=0,
        registration_score=round(float(score), 5) if score else None,
        registration=warp.round(6).tolist(), colour_correction=correction,
        prompt=f'tools/ScaleBeetleRig/art_edits/{name}.txt')
    print(name, 'protected pixel error=0', 'registered=', round(float(score or 0), 3))

(DEST / 'manifest.json').write_text(json.dumps(dict(model='gpt-image-2', mode='CLI Image API edit', parts=records), indent=2), encoding='utf-8')
