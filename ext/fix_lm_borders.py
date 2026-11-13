# Bake border texels are only partly covered by their triangle, so Cycles averages them with black -> dark lines on edges/corners.
# Takes the raw bake coverage, erodes it by E texels, throws away that ring (and the old dilation) and re-dilates from the core.
# In place on lm_layers/d_<layer>.npy. Run lm_layers_to_png.py afterwards.
import numpy as np, sys
L = r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\%s.npy'
E = 2; N = 12
def nb(m):
    r = m.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            r &= np.roll(np.roll(m, dy, 0), dx, 1)
    return r
for name in sys.argv[1:] or ['base', 'lareira', 'velas', 'arandelas']:
    cov = np.load(L % name).astype(np.float32).sum(2) > 0
    a = np.load(L % ('d_' + name)).astype(np.float32)
    core = cov.copy()
    for _ in range(E): core = nb(core)
    ring = cov & ~core
    lum = a.mean(2)
    print(name, 'ring/core lum %.3f / %.3f' % (lum[ring].mean(), lum[core].mean()), 'core frac of cov %.3f' % (core.sum() / cov.sum()), flush=True)
    lit = core.copy(); a[~lit] = 0
    for it in range(N):
        acc = np.zeros_like(a); cnt = np.zeros(a.shape[:2], np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0: continue
                s = np.roll(np.roll(a, dy, 0), dx, 1); m = np.roll(np.roll(lit, dy, 0), dx, 1)
                acc += s * m[..., None]; cnt += m
        fill = (~lit) & (cnt > 0)
        a[fill] = acc[fill] / cnt[fill][:, None]; lit = lit | fill
    np.save(L % ('d_' + name), a.astype(np.float16))
    print(name, 'refilled, frac', round(float(lit.mean()), 3), flush=True)
