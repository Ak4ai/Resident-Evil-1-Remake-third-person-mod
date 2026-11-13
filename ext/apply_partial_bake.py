# Writes lm_layers/partial_bake.npz (from bake_objs_partial.py) into the 4096 atlas layers lm_layers/<layer>.npy:
# every atlas texel covered (with a 1-texel apron) by one of the re-baked triangles gets the value sampled from the
# temporary bake through the triangle's barycentric mapping lm -> lmtmp.
import numpy as np
D = r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\%s.npy'
Z = np.load(D % 'partial_bake'[:0] + r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\partial_bake.npz'[0:0] or r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\partial_bake.npz') if False else np.load(r'C:\Users\HENRIQUE\Tools\re1mod\lm_layers\partial_bake.npz')
LM = Z['LM'].astype(np.float64) * 4096.0; TM = Z['TM'].astype(np.float64)
def sample(img, uv):
    H = img.shape[0]; x = np.clip(uv[:, 0] * H - 0.5, 0, H - 1.001); y = np.clip(uv[:, 1] * H - 0.5, 0, H - 1.001)
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = (x - x0)[:, None]; fy = (y - y0)[:, None]
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)
rows = []; cols = []; tuv = []
for tri, tm in zip(LM, TM):
    lo = np.floor(tri.min(0) - 1).astype(int); hi = np.ceil(tri.max(0) + 1).astype(int)
    xs, ys = np.meshgrid(np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1))
    P = np.stack([xs.ravel() + 0.5, ys.ravel() + 0.5], 1)
    a, b, c = tri; v0 = b - a; v1 = c - a; den = v0[0] * v1[1] - v1[0] * v0[1]
    if abs(den) < 1e-9: continue
    d = P - a; l1 = (d[:, 0] * v1[1] - v1[0] * d[:, 1]) / den; l2 = (v0[0] * d[:, 1] - d[:, 0] * v0[1]) / den; l0 = 1 - l1 - l2
    # apron: accept texels up to ~1 texel outside, clamping the barycentrics back onto the triangle
    tol = 1.0 / max(np.linalg.norm(v0), np.linalg.norm(v1), 1e-6) * 1.5
    m = (l0 > -tol) & (l1 > -tol) & (l2 > -tol)
    if not m.any(): continue
    L = np.clip(np.stack([l0[m], l1[m], l2[m]], 1), 0, None); L /= L.sum(1, keepdims=True)
    tuv.append(L @ tm); cols.append(P[m, 0].astype(int)); rows.append(P[m, 1].astype(int))
rows = np.concatenate(rows); cols = np.concatenate(cols); tuv = np.concatenate(tuv)
ok = (rows >= 0) & (rows < 4096) & (cols >= 0) & (cols < 4096)
rows, cols, tuv = rows[ok], cols[ok], tuv[ok]
for layer in ('base', 'lareira', 'velas', 'arandelas'):
    A = np.load(D % layer).astype(np.float32)
    A[rows, cols] = sample(Z[layer].astype(np.float32), tuv)
    np.save(D % layer, A.astype(np.float16)); print(layer, 'texels', len(rows))
