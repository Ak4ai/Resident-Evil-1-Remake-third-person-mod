# lm_layers/<layer>.npy (linear float16) -> captures/r105_lm_<layer>.png (gamma 2 encoded, /4) + lm_layers/scales.json
# The .npy rows are bottom-up (Blender image.pixels); PNG/D3D are top-down, so rows are flipped (export_3c writes lm v as 1-v).
# Prefers the despeckled d_<layer>.npy when it exists.
# Window layers go into ALPHA (no extra textures, the game is 32-bit): 'relampago' -> alpha of base, 'luar' -> alpha of lareira.
# The mod only uses an alpha when the PNG really has one (A8R8G8B8), so RGB PNGs stay safe.
import numpy as np, json, os
from PIL import Image
d = r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers'; cap = r'C:\Users\HENRIQUE\Tools\captures'
S = 4.0
def load(n):
    for f in ('d_' + n + '.npy', n + '.npy'):
        p = os.path.join(d, f)
        if os.path.exists(p): return np.flipud(np.load(p).astype(np.float32))
    return None
def enc(a): return (np.clip(a / S, 0, 1) ** 0.5 * 255 + .5).astype(np.uint8)
ALPHA = {'base': 'relampago', 'lareira': 'luar'}
sc = {}
for n in ('base', 'lareira', 'velas', 'arandelas'):
    a = load(n)
    if a is None: print(n, 'faltando'); continue
    rgb = enc(a); sc[n] = S
    w = ALPHA.get(n); al = load(w) if w else None
    if al is not None:
        A = enc(al.mean(2))
        Image.fromarray(np.dstack([rgb, A]), 'RGBA').save(os.path.join(cap, f'r105_lm_{n}.png'))
        print(n, 'RGBA (alfa =', w + ')', 'alfa p99', int(np.percentile(A[A > 0], 99)) if (A > 0).any() else 0)
    else:
        Image.fromarray(rgb, 'RGB').save(os.path.join(cap, f'r105_lm_{n}.png')); print(n, 'RGB')
json.dump(sc, open(os.path.join(d, 'scales.json'), 'w'), indent=1)
