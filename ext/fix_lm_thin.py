# Segundo passo sobre captures/r105_lm_fix.rms4: triangulos FINOS (largura < THIN texels no atlas, ex.: quinas verticais das pilastras)
# ainda leem texels meio-pretos. Cada vertice do triangulo fino recebe o UV do ponto mais proximo num triangulo "bom" vizinho
# (largo, normal parecida); aceita so se os 3 UVs forem coerentes (mesma ilha: distancia no atlas ~ distancia 3D * densidade).
# Grava captures/r105_lm_fix2.rms4.
import numpy as np, struct, warnings
warnings.filterwarnings('ignore')
from collections import defaultdict
cap = r'C:\Users\HENRIQUE\Tools\captures'
W = 4096; THIN = 1.5; CELL = 20.0; RAD = 30.0
b = open(cap + r'\r105_lm_fix.rms4', 'rb').read(); n = struct.unpack_from('<I', b, 4)[0]; head = b[:72]; o = 72
dt = np.dtype([('p', '<f4', 3), ('u', '<f4', 2), ('m', '<f4', 2), ('c', '<u4')])
parts = []
for _ in range(n):
    tex = b[o:o + 64]; nv, nf = struct.unpack_from('<II', b, o + 64); o += 72
    v = np.frombuffer(b, dt, nv, o).copy(); o += nv * 32; o += nf * 12   # fix file is un-indexed
    parts.append([tex, v])
V = np.concatenate([p[1] for p in parts]); M = V['m'].astype(np.float64).reshape(-1, 3, 2) * W; P = V['p'].astype(np.float64).reshape(-1, 3, 3)
e = [np.linalg.norm(M[:, (i + 1) % 3] - M[:, i], axis=1) for i in range(3)]
area = np.abs((M[:, 1, 0] - M[:, 0, 0]) * (M[:, 2, 1] - M[:, 0, 1]) - (M[:, 2, 0] - M[:, 0, 0]) * (M[:, 1, 1] - M[:, 0, 1])) / 2
longest = np.maximum.reduce(e); alt = 2 * area / np.maximum(longest, 1e-9)
nrm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
good = (alt >= 2) & (area >= 4)
thin = (alt < THIN) & (longest >= 2)          # collapsed small tris have longest ~0 -> untouched
print('tris', len(M), 'good', good.sum(), 'thin', thin.sum(), flush=True)
cP = P.mean(1); gi = np.where(good)[0]
grid = defaultdict(list)
for i, k in zip(gi, map(tuple, np.floor(cP[gi] / CELL).astype(int))): grid[k].append(i)
grid = {k: np.array(v) for k, v in grid.items()}
def closest_uv(p, t):   # p (3,), triangles t -> (dist, uv) of closest point, barycentric clamped inside
    A, B, C = P[t, 0], P[t, 1], P[t, 2]
    nn = nrm[t]; q = p - ((p - A) * nn).sum(1)[:, None] * nn
    v0, v1, v2 = B - A, C - A, q - A
    d00 = (v0 * v0).sum(1); d01 = (v0 * v1).sum(1); d11 = (v1 * v1).sum(1); d20 = (v2 * v0).sum(1); d21 = (v2 * v1).sum(1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-12); bv = (d11 * d20 - d01 * d21) / den; bw = (d00 * d21 - d01 * d20) / den
    bv = np.clip(bv, 0, 1); bw = np.clip(bw, 0, 1); s = bv + bw; f = np.where(s > 1, 1 / s, 1); bv *= f; bw *= f; bu = 1 - bv - bw
    pt = A * bu[:, None] + B * bv[:, None] + C * bw[:, None]
    uv = M[t, 0] * bu[:, None] + M[t, 1] * bv[:, None] + M[t, 2] * bw[:, None]
    return np.linalg.norm(pt - p, axis=1), uv
R = int(np.ceil(RAD / CELL)); NM = M.copy(); ok = 0; flat = 0
for ti in np.where(thin)[0]:
    k = np.floor(cP[ti] / CELL).astype(int)
    cand = [grid[q] for q in ((k[0] + a, k[1] + bb, k[2] + c) for a in range(-R, R + 1) for bb in range(-R, R + 1) for c in range(-R, R + 1)) if q in grid]
    if not cand: continue
    cand = np.concatenate(cand); cand = cand[nrm[cand] @ nrm[ti] > 0.5]
    if not len(cand): continue
    uvs = []
    for j in range(3):
        d, uv = closest_uv(P[ti, j], cand); m = d.argmin()
        if d[m] > RAD: break
        uvs.append(uv[m])
    coh = False
    if len(uvs) == 3:
        uvs = np.array(uvs)
        du = np.linalg.norm(uvs[[1, 2, 0]] - uvs, axis=1); dp = np.linalg.norm(P[ti, [1, 2, 0]] - P[ti], axis=1) / 100 * 18
        coh = np.all(du <= dp * 2 + 2)
    if coh: NM[ti] = uvs; ok += 1
    else:
        d, uv = closest_uv(cP[ti], cand); m = d.argmin()
        if d[m] <= RAD: NM[ti] = uv[m]; flat += 1
print('thin fixed per-vertex', ok, 'flat', flat, flush=True)
out = bytearray(head); t0 = 0; nmw = (NM / W).astype('<f4')
for tex, v in parts:
    nf = len(v) // 3; v = v.copy(); v['m'] = nmw[t0:t0 + nf].reshape(-1, 2); t0 += nf
    out += tex + struct.pack('<II', len(v), nf) + v.tobytes() + np.arange(len(v), dtype='<u4').tobytes()
open(cap + r'\r105_lm_fix2.rms4', 'wb').write(out); print('MB', round(len(out) / 1e6, 1))
