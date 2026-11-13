# Terceiro passo (sobre captures/r105_lm_fix2.rms4): triangulos cujo UV do lightmap cai em texel nunca assado (luz ~0,
# ilha toda feita de faces menores que um texel) recebem o UV (constante) do triangulo vizinho mais proximo que tem luz,
# com normal parecida. Usa o lightmap base para decidir. Grava captures/r105_lm_fix3.rms4.
import numpy as np, struct, warnings
from collections import defaultdict
from PIL import Image
warnings.filterwarnings('ignore')
cap = r'C:\Users\HENRIQUE\Tools\captures'; W = 4096; CELL = 25.0; ZERO = 0.002
b = open(cap + r'\r105_lm_fix2.rms4', 'rb').read(); n = struct.unpack_from('<I', b, 4)[0]; head = b[:72]; o = 72
dt = np.dtype([('p', '<f4', 3), ('u', '<f4', 2), ('m', '<f4', 2), ('c', '<u4')]); parts = []
for _ in range(n):
    tex = b[o:o + 64]; nv, nf = struct.unpack_from('<II', b, o + 64); o += 72
    v = np.frombuffer(b, dt, nv, o).copy(); o += nv * 32 + nf * 12; parts.append([tex, v])
V = np.concatenate([p[1] for p in parts]); M = V['m'].astype(np.float64).reshape(-1, 3, 2); P = V['p'].astype(np.float64).reshape(-1, 3, 3)
lum = ((np.asarray(Image.open(cap + r'\r105_lm_base.png').convert('RGB')).astype(np.float32) / 255) ** 2 * 4).mean(2)
def samp(uv):   # bilinear, like the GPU
    x = uv[:, 0] * W - 0.5; y = uv[:, 1] * W - 0.5; x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = x - x0; fy = y - y0
    g = lambda yy, xx: lum[np.clip(yy, 0, W - 1), np.clip(xx, 0, W - 1)]
    return g(y0, x0) * (1 - fx) * (1 - fy) + g(y0, x0 + 1) * fx * (1 - fy) + g(y0 + 1, x0) * (1 - fx) * fy + g(y0 + 1, x0 + 1) * fx * fy
# a triangle is "zero" if any vertex or its centre reads ~0
s = np.stack([samp(M[:, j]) for j in range(3)] + [samp(M.mean(1))], 1)
zero = s.min(1) < ZERO; good = s.min(1) >= ZERO * 3
nrm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
cP = P.mean(1); gi = np.where(good)[0]; cM = M.mean(1)
print('tris', len(M), 'zero', zero.sum(), 'good', good.sum(), flush=True)
grid = defaultdict(list)
for i, k in zip(gi, map(tuple, np.floor(cP[gi] / CELL).astype(int))): grid[k].append(i)
grid = {k: np.array(v) for k, v in grid.items()}
groups = defaultdict(list)
zi = np.where(zero)[0]
for i, k in zip(zi, map(tuple, np.floor(cP[zi] / CELL).astype(int))): groups[k].append(i)
NM = M.copy(); cnt = defaultdict(int)
for k, idx in groups.items():
    idx = np.array(idx); left = idx
    for R, mind in ((1, 0.7), (2, 0.7), (3, 0.3), (4, -1.1)):
        cand = [grid[q] for q in ((k[0] + a, k[1] + bb, k[2] + c) for a in range(-R, R + 1) for bb in range(-R, R + 1) for c in range(-R, R + 1)) if q in grid]
        if not cand or not len(left): continue
        cand = np.concatenate(cand)
        dist = np.linalg.norm(cP[left][:, None] - cP[cand][None], axis=2); dot = nrm[left] @ nrm[cand].T
        dist = np.where(dot > mind, dist, np.inf); j = dist.argmin(1); has = np.isfinite(dist[np.arange(len(left)), j])
        NM[left[has]] = cM[cand[j[has]]][:, None]; cnt[R] += has.sum(); left = left[~has]
    cnt['none'] += len(left)
print('fixed by radius step', dict(cnt), flush=True)
s2 = samp(NM.mean(1)); print('still zero', int((s2 < ZERO).sum()), flush=True)
out = bytearray(head); t0 = 0; nmw = NM.astype('<f4')
for tex, v in parts:
    nf = len(v) // 3; v = v.copy(); v['m'] = nmw[t0:t0 + nf].reshape(-1, 2); t0 += nf
    out += tex + struct.pack('<II', len(v), nf) + v.tobytes() + np.arange(len(v), dtype='<u4').tobytes()
open(cap + r'\r105_lm_fix3.rms4', 'wb').write(out); print('MB', round(len(out) / 1e6, 1))
