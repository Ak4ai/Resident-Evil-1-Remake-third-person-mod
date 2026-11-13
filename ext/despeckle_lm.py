# lm_layers/<layer>.npy -> lm_layers/d_<layer>.npy : removes bake noise (Cycles undenoised, 192 spp) without re-baking.
# 3x3 median on lit texels, blended: texels close to their median stay, outliers (fireflies/speckle) are replaced; then a light 3x3 mean
# restricted to lit neighbours so it never pulls in the black margin between islands.
import numpy as np, sys
from numpy.lib.stride_tricks import sliding_window_view as sw
D = r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\%s.npy'
for name in sys.argv[1:] or ['base', 'lareira', 'velas', 'arandelas']:
    a = np.load(D % name).astype(np.float32); H = a.shape[0]
    lit = (a.sum(2) > 0)
    out = a.copy()
    for ch in range(3):
        x = a[:, :, ch]
        xp = np.pad(x, 1, mode='edge'); lp = np.pad(lit, 1, mode='edge')
        for r0 in range(0, H, 256):
            r1 = min(H, r0 + 256)
            w = sw(xp[r0:r1 + 2], (3, 3)).reshape(r1 - r0, H, 9)
            lw = sw(lp[r0:r1 + 2], (3, 3)).reshape(r1 - r0, H, 9)
            wm = np.where(lw, w, np.nan)                        # ignore unlit (black margin) neighbours
            med = np.nanmedian(wm, axis=2)
            mean = np.nanmean(wm, axis=2)
            cur = x[r0:r1]
            res = np.where(np.isnan(med), cur, 0.5 * med + 0.5 * mean)
            out[r0:r1, :, ch] = np.where(lit[r0:r1], res, cur)
    np.save(D % ('d_' + name), out.astype(np.float16))
    print(name, 'done', float(np.abs(out - a).mean()), flush=True)
