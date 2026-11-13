# Lightmap quinas pretas sem rebake: o atlas tem ~18 texels/m, entao faces finas (quinas, molduras) caem em texels
# parcialmente cobertos que o Cycles mistura com preto.
# 1) triangulos grandes: encolhe o UV do lightmap ~1 texel para dentro (nao amostra a borda meio-coberta);
# 2) triangulos pequenos (< MINA texels): usa um UV unico, do centro do triangulo grande vizinho mais proximo com normal parecida.
# Le captures/r105_lm.rms4 e grava captures/r105_lm_fix.rms4 (mesmo formato). Nao mexe no lightmap PNG.
import numpy as np, struct, sys
from collections import defaultdict
cap = r'C:\Users\HENRIQUE\Tools\captures'
W = 4096; MINA = 4.0; SHR = 1.0; CELL = 20.0; RAD = 40.0   # texels, texels, cm, cm
b = open(cap + r'\r105_lm.rms4', 'rb').read(); o = 4; n = struct.unpack_from('<I', b, o)[0]; head = b[:8 + 64]; o = 8 + 64
dt = np.dtype([('p', '<f4', 3), ('u', '<f4', 2), ('m', '<f4', 2), ('c', '<u4')])
parts = []
for _ in range(n):
    tex = b[o:o + 64]; nv, nf = struct.unpack_from('<II', b, o + 64); o += 72
    v = np.frombuffer(b, dt, nv, o).copy(); o += nv * 32
    I = np.frombuffer(b, '<u4', nf * 3, o).reshape(-1, 3).copy(); o += nf * 12
    parts.append([tex, v, I])
# all triangles
M = []; P = []
for tex, v, I in parts: M.append(v['m'][I]); P.append(v['p'][I])
M = np.concatenate(M).astype(np.float64) * W; P = np.concatenate(P).astype(np.float64)
area = np.abs((M[:, 1, 0] - M[:, 0, 0]) * (M[:, 2, 1] - M[:, 0, 1]) - (M[:, 2, 0] - M[:, 0, 0]) * (M[:, 1, 1] - M[:, 0, 1])) / 2
nrm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
cM = M.mean(1); cP = P.mean(1)
big = area >= MINA; NM = M.copy()
# 1) shrink big
d = M[big] - cM[big][:, None]; L = np.linalg.norm(d, axis=2, keepdims=True)
NM[big] = cM[big][:, None] + d * np.clip(1 - SHR / np.maximum(L, 1e-9), 0.3, 1)
# 2) small -> donor
key = lambda p: tuple(np.floor(p / CELL).astype(int))
grid = defaultdict(list)
bi = np.where(big)[0]
for i, k in zip(bi, map(tuple, np.floor(cP[bi] / CELL).astype(int))): grid[k].append(i)
grid = {k: np.array(v) for k, v in grid.items()}
si = np.where(~big)[0]; sk = np.floor(cP[si] / CELL).astype(int)
groups = defaultdict(list)
for i, k in zip(si, map(tuple, sk)): groups[k].append(i)
R = int(np.ceil(RAD / CELL)); ok = 0
for k, idx in groups.items():
    cand = [grid[(k[0] + a, k[1] + bb, k[2] + c)] for a in range(-R, R + 1) for bb in range(-R, R + 1) for c in range(-R, R + 1) if (k[0] + a, k[1] + bb, k[2] + c) in grid]
    idx = np.array(idx)
    if not cand: NM[idx] = cM[idx][:, None]; continue
    cand = np.concatenate(cand)
    dist = np.linalg.norm(cP[idx][:, None] - cP[cand][None], axis=2)
    dot = nrm[idx] @ nrm[cand].T
    dist = np.where((dot > 0.7) & (dist < RAD), dist, np.inf)
    j = dist.argmin(1); has = np.isfinite(dist[np.arange(len(idx)), j])
    NM[idx[has]] = cM[cand[j[has]]][:, None]; ok += has.sum()
    NM[idx[~has]] = cM[idx[~has]][:, None]
print('tris', len(M), 'big', big.sum(), 'small', (~big).sum(), 'small with donor', ok, flush=True)
# write: un-index per triangle so every triangle owns its lm uv
out = bytearray(head); t0 = 0
for tex, v, I in parts:
    nf = len(I); nm = (NM[t0:t0 + nf] / W).astype('<f4'); t0 += nf
    nv = v[I.reshape(-1)].copy(); nv['m'] = nm.reshape(-1, 2)
    out += tex + struct.pack('<II', len(nv), nf) + nv.tobytes() + np.arange(len(nv), dtype='<u4').tobytes()
open(cap + r'\r105_lm_fix.rms4', 'wb').write(out); print('MB', round(len(out) / 1e6, 1))
