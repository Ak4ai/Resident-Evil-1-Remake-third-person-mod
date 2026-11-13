# Fills the empty (black) texels around every lightmap island with the average of their lit neighbours, repeated N times,
# so bilinear filtering / mip levels near island borders never pull in black (thin moldings showed black lines).
# In place on lm_layers/d_<layer>.npy. Lit texels are not changed.
import numpy as np, sys
D = r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\d_%s.npy'
N = 8
for name in sys.argv[1:] or ['base', 'lareira', 'velas', 'arandelas']:
    a = np.load(D % name).astype(np.float32)
    lit = a.sum(2) > 0
    for it in range(N):
        acc = np.zeros_like(a); cnt = np.zeros(a.shape[:2], np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0: continue
                s = np.roll(np.roll(a, dy, 0), dx, 1); m = np.roll(np.roll(lit, dy, 0), dx, 1)
                acc += s * m[..., None]; cnt += m
        fill = (~lit) & (cnt > 0)
        a[fill] = acc[fill] / cnt[fill][:, None]; lit = lit | fill
    np.save(D % name, a.astype(np.float16))
    print(name, 'dilated', N, 'filled frac', round(float(lit.mean()), 3), flush=True)
